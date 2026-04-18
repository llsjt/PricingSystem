package com.example.pricing.service;

import com.example.pricing.entity.AgentRunLog;
import com.example.pricing.entity.PricingResult;
import com.example.pricing.entity.PricingTask;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

class PricingTaskStreamServiceTest {

    @Test
    void completedEventWaitsUntilTaskStatusBecomesTerminal() {
        PricingTask task = new PricingTask();
        PricingResult result = new PricingResult();

        task.setTaskStatus("RUNNING");
        assertFalse(PricingTaskStreamService.shouldEmitCompletedEvent(task, result, 4));

        task.setTaskStatus("MANUAL_REVIEW");
        assertFalse(PricingTaskStreamService.shouldEmitCompletedEvent(task, result, 3));
        assertTrue(PricingTaskStreamService.shouldEmitCompletedEvent(task, result, 4));

        task.setTaskStatus("COMPLETED");
        assertFalse(PricingTaskStreamService.shouldEmitCompletedEvent(task, result, 2));
        assertTrue(PricingTaskStreamService.shouldEmitCompletedEvent(task, result, 4));
    }

    @Test
    void manualReviewWithoutResultIsStillATerminalStatus() {
        PricingTask task = new PricingTask();
        task.setTaskStatus("MANUAL_REVIEW");

        assertTrue(PricingTaskStreamService.shouldEmitTerminalFailure(task, null));
        assertEquals("需要人工审核", PricingTaskStreamService.resolveTerminalMessage(task));
    }

    @Test
    void exceptionMessageFallsBackWhenBlank() {
        Exception emptyMessageException = new RuntimeException((String) null);
        Exception blankMessageException = new RuntimeException("   ");

        assertEquals("stream failed", PricingTaskStreamService.resolveExceptionMessage(emptyMessageException));
        assertEquals("stream failed", PricingTaskStreamService.resolveExceptionMessage(blankMessageException));
        assertEquals("stream failed", PricingTaskStreamService.resolveExceptionMessage(new RuntimeException("null")));
    }

    @Test
    void cardPayloadAllowsNullReason() {
        Map<String, Object> payload = PricingTaskStreamService.buildCardPayload(
                "thinking",
                List.of(Map.of("label", "x", "value", 1)),
                Map.of("summary", "ok", "strategy", "DIRECT"),
                null
        );

        assertEquals("thinking", payload.get("thinking"));
        assertEquals("人工审核", ((Map<?, ?>) payload.get("suggestion")).get("strategy"));
        assertNull(payload.get("reasonWhy"));
    }

    @Test
    void runningAgentLogProducesRunningPayloadWithEmptyCard() {
        PricingTaskStreamService service = new PricingTaskStreamService(null, null, null, null);
        AgentRunLog log = new AgentRunLog();
        log.setTaskId(10L);
        log.setRoleName("数据分析Agent");
        log.setDisplayOrder(1);
        log.setStage("running");
        log.setRunAttempt(2);

        Map<String, Object> payload = ReflectionTestUtils.invokeMethod(service, "toAgentCard", 10L, log);

        assertEquals("agent_card", payload.get("type"));
        assertEquals("DATA_ANALYSIS", payload.get("agentCode"));
        assertEquals(2, payload.get("runAttempt"));
        assertEquals("running", payload.get("stage"));
        Map<?, ?> card = (Map<?, ?>) payload.get("card");
        assertEquals("", card.get("thinking"));
        assertEquals(List.of(), card.get("evidence"));
        assertEquals(Map.of(), card.get("suggestion"));
    }

    @Test
    void onlyCompletedAgentLogsCountTowardCompletion() {
        AgentRunLog running = new AgentRunLog();
        running.setDisplayOrder(1);
        running.setStage("running");

        AgentRunLog failed = new AgentRunLog();
        failed.setDisplayOrder(1);
        failed.setStage("failed");

        AgentRunLog completed = new AgentRunLog();
        completed.setDisplayOrder(1);
        completed.setStage("completed");

        AgentRunLog legacy = new AgentRunLog();
        legacy.setDisplayOrder(2);

        assertFalse(PricingTaskStreamService.isCompletedAgentCard(running));
        assertFalse(PricingTaskStreamService.isCompletedAgentCard(failed));
        assertTrue(PricingTaskStreamService.isCompletedAgentCard(completed));
        assertTrue(PricingTaskStreamService.isCompletedAgentCard(legacy));
    }

    @Test
    void failedAgentLogProducesFailedPayloadWithErrorCard() {
        PricingTaskStreamService service = new PricingTaskStreamService(null, null, null, null);
        AgentRunLog log = new AgentRunLog();
        log.setTaskId(10L);
        log.setRoleName("Manager Agent");
        log.setDisplayOrder(4);
        log.setStage("failed");
        log.setThinkingSummary("Agent execution failed: LLM API timeout");
        log.setEvidenceJson("[{\"label\":\"error\",\"value\":\"LLM API timeout\"}]");
        log.setSuggestionJson("{\"error\":true,\"message\":\"LLM API timeout\"}");

        Map<String, Object> payload = ReflectionTestUtils.invokeMethod(service, "toAgentCard", 10L, log);

        assertEquals("agent_card", payload.get("type"));
        assertEquals("MANAGER_COORDINATOR", payload.get("agentCode"));
        assertEquals("failed", payload.get("stage"));
        Map<?, ?> card = (Map<?, ?>) payload.get("card");
        assertEquals("Agent execution failed: LLM API timeout", card.get("thinking"));
        assertEquals(Boolean.TRUE, ((Map<?, ?>) card.get("suggestion")).get("error"));
    }

    @Test
    void legacyErrorSuggestionAlsoProducesFailedPayload() {
        PricingTaskStreamService service = new PricingTaskStreamService(null, null, null, null);
        AgentRunLog log = new AgentRunLog();
        log.setTaskId(11L);
        log.setRoleName("市场情报Agent");
        log.setDisplayOrder(2);
        log.setThinkingSummary("Agent execution failed");
        log.setSuggestionJson("{\"error\":true,\"message\":\"LLM API timeout\"}");

        Map<String, Object> payload = ReflectionTestUtils.invokeMethod(service, "toAgentCard", 11L, log);

        assertEquals("failed", payload.get("stage"));
        assertFalse(PricingTaskStreamService.isCompletedAgentCard(log));
    }

    @Test
    void resultPayloadUsesManualReviewStrategyWhenOptionalFieldsAreBlank() {
        PricingResult result = new PricingResult();
        result.setExpectedSales(1);

        Map<String, Object> payload = PricingTaskStreamService.buildResultPayload(result);

        assertEquals("人工审核", payload.get("strategy"));
        assertNull(payload.get("summary"));
        assertEquals(1, payload.get("expectedSales"));
    }

    @Test
    void resultPayloadAlwaysReportsManualReviewStrategy() {
        PricingResult result = new PricingResult();
        result.setExecuteStrategy("DIRECT");
        result.setReviewRequired(0);

        Map<String, Object> payload = PricingTaskStreamService.buildResultPayload(result);

        assertEquals("人工审核", payload.get("strategy"));
    }
}
