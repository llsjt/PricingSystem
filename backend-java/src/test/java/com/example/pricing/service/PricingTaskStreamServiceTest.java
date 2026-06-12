package com.example.pricing.service;

import com.example.pricing.dto.TaskProgressEvent;
import com.example.pricing.entity.AgentRunLog;
import com.example.pricing.entity.PricingResult;
import com.example.pricing.entity.PricingTask;
import com.example.pricing.mapper.AgentRunLogMapper;
import com.example.pricing.mapper.PricingResultMapper;
import com.example.pricing.mapper.PricingTaskMapper;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentMatchers;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.lang.reflect.Method;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class PricingTaskStreamServiceTest {

    @Test
    void emitSnapshotPrefersCurrentExecutionLogsOverHigherRunAttemptHistory() {
        PricingTaskMapper taskMapper = mock(PricingTaskMapper.class);
        PricingResultMapper resultMapper = mock(PricingResultMapper.class);
        AgentRunLogMapper logMapper = mock(AgentRunLogMapper.class);
        PricingTaskStreamService service = new PricingTaskStreamService(taskMapper, resultMapper, logMapper, null);
        RecordingSseEmitter emitter = new RecordingSseEmitter();
        PricingTask task = task(101L, "RUNNING", "exec-current");

        AgentRunLog oldAttempt = completedLog(101L, "exec-old", 9, 1, "Data old");
        AgentRunLog currentData = completedLog(101L, "exec-current", 1, 1, "Data current");
        AgentRunLog currentManager = completedLog(101L, "exec-current", 1, 4, "Manager current");

        when(taskMapper.selectById(101L)).thenReturn(task);
        when(logMapper.selectList(ArgumentMatchers.any())).thenReturn(List.of(oldAttempt, currentData, currentManager));

        ReflectionTestUtils.invokeMethod(service, "emitSnapshot", 101L, emitter);

        assertEquals(List.of("task_started", "agent_card", "agent_card"), emitter.types());
        assertEquals(List.of(1, 1), emitter.agentCardRunAttempts());
        assertEquals(List.of("Data current", "Manager current"), emitter.agentCardThinkings());
    }

    @Test
    void emitSnapshotFallsBackToLatestRunAttemptWhenTerminalTaskHasNoCurrentExecution() {
        PricingTaskMapper taskMapper = mock(PricingTaskMapper.class);
        PricingResultMapper resultMapper = mock(PricingResultMapper.class);
        AgentRunLogMapper logMapper = mock(AgentRunLogMapper.class);
        PricingTaskStreamService service = new PricingTaskStreamService(taskMapper, resultMapper, logMapper, null);
        RecordingSseEmitter emitter = new RecordingSseEmitter();
        PricingTask task = task(102L, "FAILED", null);

        AgentRunLog oldData = completedLog(102L, "exec-old", 0, 1, "Old data");
        AgentRunLog oldMarket = completedLog(102L, "exec-old", 0, 2, "Old market");
        AgentRunLog latestData = completedLog(102L, "exec-new", 2, 1, "Latest data");
        AgentRunLog latestManager = completedLog(102L, "exec-new", 2, 4, "Latest manager");

        when(taskMapper.selectById(102L)).thenReturn(task);
        when(logMapper.selectList(ArgumentMatchers.any())).thenReturn(List.of(oldData, oldMarket, latestData, latestManager));

        ReflectionTestUtils.invokeMethod(service, "emitSnapshot", 102L, emitter);

        assertEquals(List.of("task_started", "agent_card", "agent_card", "task_failed"), emitter.types());
        assertEquals(List.of(2, 2), emitter.agentCardRunAttempts());
        assertEquals(List.of("Latest data", "Latest manager"), emitter.agentCardThinkings());
    }

    @Test
    void realtimeAgentCardUsesCurrentExecutionLogOnly() {
        PricingTaskMapper taskMapper = mock(PricingTaskMapper.class);
        PricingResultMapper resultMapper = mock(PricingResultMapper.class);
        AgentRunLogMapper logMapper = mock(AgentRunLogMapper.class);
        PricingTaskStreamService service = new PricingTaskStreamService(taskMapper, resultMapper, logMapper, null);
        RecordingSseEmitter emitter = new RecordingSseEmitter();
        PricingTask task = task(103L, "RUNNING", "exec-current");

        AgentRunLog staleLog = completedLog(103L, "exec-old", 0, 3, "Risk old");
        AgentRunLog currentLog = completedLog(103L, "exec-current", 1, 3, "Risk current");

        when(taskMapper.selectById(103L)).thenReturn(task);
        when(logMapper.selectOne(ArgumentMatchers.any())).thenReturn(staleLog);
        when(logMapper.selectList(ArgumentMatchers.any())).thenReturn(List.of(staleLog, currentLog));

        service.register(103L, emitter);
        service.handleProgressEvent(new TaskProgressEvent(
                "evt-103",
                "AGENT_CARD_COMPLETED",
                103L,
                "exec-current",
                "trace-103",
                Map.of("agentName", "Agent-3"),
                Instant.parse("2026-04-30T10:00:00Z")
        ));

        assertEquals(List.of("agent_card"), emitter.types());
        assertEquals(List.of(1), emitter.agentCardRunAttempts());
        assertEquals(List.of("Risk current"), emitter.agentCardThinkings());
    }

    @Test
    void taskCompletedRealtimeEventDoesNotWaitForFourCompletedCards() {
        PricingTaskMapper taskMapper = mock(PricingTaskMapper.class);
        PricingResultMapper resultMapper = mock(PricingResultMapper.class);
        AgentRunLogMapper logMapper = mock(AgentRunLogMapper.class);
        PricingTaskStreamService service = new PricingTaskStreamService(taskMapper, resultMapper, logMapper, null);
        RecordingSseEmitter emitter = new RecordingSseEmitter();
        PricingTask task = task(104L, "COMPLETED", "exec-current");
        PricingResult result = new PricingResult();

        when(taskMapper.selectById(104L)).thenReturn(task);
        when(resultMapper.selectOne(ArgumentMatchers.any())).thenReturn(result);
        when(logMapper.selectList(ArgumentMatchers.any())).thenReturn(List.of(
                completedLog(104L, "exec-current", 1, 1, "Data"),
                completedLog(104L, "exec-current", 1, 2, "Market"),
                completedLog(104L, "exec-current", 1, 3, "Risk"),
                completedLog(104L, "exec-old", 0, 4, "Old manager")
        ));

        service.register(104L, emitter);
        service.handleProgressEvent(new TaskProgressEvent(
                "evt-104",
                "TASK_COMPLETED",
                104L,
                "exec-current",
                "trace-104",
                Map.of(),
                Instant.parse("2026-04-30T10:01:00Z")
        ));

        assertEquals(List.of("task_completed"), emitter.types());
    }

    @Test
    void emitSnapshotReplaysHistoricalAnalysisCardsWhenCurrentExecutionOnlyHasManager() {
        PricingTaskMapper taskMapper = mock(PricingTaskMapper.class);
        PricingResultMapper resultMapper = mock(PricingResultMapper.class);
        AgentRunLogMapper logMapper = mock(AgentRunLogMapper.class);
        PricingTaskStreamService service = new PricingTaskStreamService(taskMapper, resultMapper, logMapper, null);
        RecordingSseEmitter emitter = new RecordingSseEmitter();
        PricingTask task = task(107L, "RUNNING", "exec-current");

        AgentRunLog historyData = completedReplayableLog(1001L, 107L, "exec-old-1", 1, 1, "Historical data");
        AgentRunLog historyMarket = completedReplayableLog(1002L, 107L, "exec-old-1", 1, 2, "Historical market");
        AgentRunLog historyRisk = completedReplayableLog(1003L, 107L, "exec-old-1", 1, 3, "Historical risk");
        AgentRunLog currentManager = completedReplayableLog(1004L, 107L, "exec-current", 2, 4, "Current manager");

        when(taskMapper.selectById(107L)).thenReturn(task);
        when(logMapper.selectList(ArgumentMatchers.any())).thenReturn(List.of(
                historyData,
                historyMarket,
                historyRisk,
                currentManager
        ));

        ReflectionTestUtils.invokeMethod(service, "emitSnapshot", 107L, emitter);

        assertEquals(List.of("task_started", "agent_card", "agent_card", "agent_card", "agent_card"), emitter.types());
        assertEquals(List.of(2, 2, 2, 2), emitter.agentCardRunAttempts());
        assertEquals(List.of(true, true, true, false), emitter.agentCardReplayedFlags());
        assertEquals(java.util.Arrays.asList(1001L, 1002L, 1003L, null), emitter.agentCardSourceLogIds());
        assertEquals(java.util.Arrays.asList("exec-old-1", "exec-old-1", "exec-old-1", null), emitter.agentCardSourceExecutionIds());
        assertEquals(java.util.Arrays.asList(1, 1, 1, null), emitter.agentCardSourceRunAttempts());
        assertEquals(List.of("Historical data", "Historical market", "Historical risk", "Current manager"), emitter.agentCardThinkings());
    }

    @Test
    void taskManualReviewRealtimeEventUsesEffectiveTimelineForCompletion() {
        PricingTaskMapper taskMapper = mock(PricingTaskMapper.class);
        PricingResultMapper resultMapper = mock(PricingResultMapper.class);
        AgentRunLogMapper logMapper = mock(AgentRunLogMapper.class);
        PricingTaskStreamService service = new PricingTaskStreamService(taskMapper, resultMapper, logMapper, null);
        RecordingSseEmitter emitter = new RecordingSseEmitter();
        PricingTask task = task(108L, "MANUAL_REVIEW", "exec-current");
        PricingResult result = new PricingResult();
        result.setTaskId(108L);
        result.setExecutionId("exec-old-1");
        result.setFinalPrice(new java.math.BigDecimal("88.00"));

        when(taskMapper.selectById(108L)).thenReturn(task);
        when(resultMapper.selectOne(ArgumentMatchers.any())).thenReturn(result);
        when(logMapper.selectList(ArgumentMatchers.any())).thenReturn(List.of(
                completedReplayableLog(1081L, 108L, "exec-old-1", 1, 1, "Historical data"),
                completedReplayableLog(1082L, 108L, "exec-old-1", 1, 2, "Historical market"),
                completedReplayableLog(1083L, 108L, "exec-old-1", 1, 3, "Historical risk"),
                completedReplayableLog(1084L, 108L, "exec-current", 2, 4, "Current manager")
        ));

        service.register(108L, emitter);
        service.handleProgressEvent(new TaskProgressEvent(
                "evt-108",
                "TASK_MANUAL_REVIEW",
                108L,
                "exec-current",
                "trace-108",
                Map.of(),
                Instant.parse("2026-04-30T10:03:00Z")
        ));

        assertEquals(List.of("task_completed"), emitter.types());
        assertEquals("MANUAL_REVIEW", emitter.payloads().get(0).get("status"));
    }

    @Test
    void terminalRealtimeEventIgnoresClearedOwnerWhenResultExists() {
        PricingTaskMapper taskMapper = mock(PricingTaskMapper.class);
        PricingResultMapper resultMapper = mock(PricingResultMapper.class);
        AgentRunLogMapper logMapper = mock(AgentRunLogMapper.class);
        PricingTaskStreamService service = new PricingTaskStreamService(taskMapper, resultMapper, logMapper, null);
        RecordingSseEmitter emitter = new RecordingSseEmitter();
        PricingTask task = task(111L, "MANUAL_REVIEW", null);
        PricingResult result = new PricingResult();
        result.setTaskId(111L);
        result.setExecutionId("exec-finished");
        result.setFinalPrice(new java.math.BigDecimal("88.00"));

        when(taskMapper.selectById(111L)).thenReturn(task);
        when(resultMapper.selectOne(ArgumentMatchers.any())).thenReturn(result);
        when(logMapper.selectList(ArgumentMatchers.any())).thenReturn(List.of());

        service.register(111L, emitter);
        service.handleProgressEvent(new TaskProgressEvent(
                "evt-111",
                "TASK_MANUAL_REVIEW",
                111L,
                "exec-finished",
                "trace-111",
                Map.of(),
                Instant.parse("2026-04-30T10:04:00Z")
        ));

        assertEquals(List.of("task_completed"), emitter.types());
        assertEquals("MANUAL_REVIEW", emitter.payloads().get(0).get("status"));
    }

    @Test
    void emitSnapshotDoesNotReplayHistoricalCompletedCardWhenRawOutputIsEmpty() {
        PricingTaskMapper taskMapper = mock(PricingTaskMapper.class);
        PricingResultMapper resultMapper = mock(PricingResultMapper.class);
        AgentRunLogMapper logMapper = mock(AgentRunLogMapper.class);
        PricingTaskStreamService service = new PricingTaskStreamService(taskMapper, resultMapper, logMapper, null);
        RecordingSseEmitter emitter = new RecordingSseEmitter();
        PricingTask task = task(109L, "RUNNING", "exec-current");

        AgentRunLog invalidHistory = completedReplayableLog(1091L, 109L, "exec-old-1", 1, 1, "Historical data");
        invalidHistory.setRawOutputJson("{}");
        AgentRunLog historyMarket = completedReplayableLog(1092L, 109L, "exec-old-1", 1, 2, "Historical market");
        AgentRunLog historyRisk = completedReplayableLog(1093L, 109L, "exec-old-1", 1, 3, "Historical risk");
        AgentRunLog currentManager = completedReplayableLog(1094L, 109L, "exec-current", 2, 4, "Current manager");

        when(taskMapper.selectById(109L)).thenReturn(task);
        when(logMapper.selectList(ArgumentMatchers.any())).thenReturn(List.of(
                invalidHistory,
                historyMarket,
                historyRisk,
                currentManager
        ));

        ReflectionTestUtils.invokeMethod(service, "emitSnapshot", 109L, emitter);

        assertEquals(List.of("task_started", "agent_card", "agent_card", "agent_card"), emitter.types());
        assertEquals(List.of(2, 3, 4), emitter.agentCardDisplayOrders());
        assertEquals(List.of(true, true, false), emitter.agentCardReplayedFlags());
    }

    @Test
    void emitSnapshotKeepsCurrentRunningOrFailedCardsInsteadOfReplacingWithHistory() {
        PricingTaskMapper taskMapper = mock(PricingTaskMapper.class);
        PricingResultMapper resultMapper = mock(PricingResultMapper.class);
        AgentRunLogMapper logMapper = mock(AgentRunLogMapper.class);
        PricingTaskStreamService service = new PricingTaskStreamService(taskMapper, resultMapper, logMapper, null);
        RecordingSseEmitter emitter = new RecordingSseEmitter();
        PricingTask task = task(110L, "RUNNING", "exec-current");

        AgentRunLog oldCompletedData = completedReplayableLog(1101L, 110L, "exec-old-1", 1, 1, "Historical data");
        AgentRunLog currentRunningData = completedReplayableLog(1102L, 110L, "exec-current", 2, 1, "Current data");
        currentRunningData.setStage("running");
        currentRunningData.setRawOutputJson(null);
        AgentRunLog oldCompletedMarket = completedReplayableLog(1103L, 110L, "exec-old-1", 1, 2, "Historical market");
        AgentRunLog currentFailedMarket = completedReplayableLog(1104L, 110L, "exec-current", 2, 2, "Current market failed");
        currentFailedMarket.setStage("failed");
        currentFailedMarket.setSuggestionJson("{\"error\":true,\"message\":\"timeout\"}");
        currentFailedMarket.setRawOutputJson(null);
        AgentRunLog historyRisk = completedReplayableLog(1105L, 110L, "exec-old-1", 1, 3, "Historical risk");
        AgentRunLog currentManager = completedReplayableLog(1106L, 110L, "exec-current", 2, 4, "Current manager");

        when(taskMapper.selectById(110L)).thenReturn(task);
        when(logMapper.selectList(ArgumentMatchers.any())).thenReturn(List.of(
                oldCompletedData,
                currentRunningData,
                oldCompletedMarket,
                currentFailedMarket,
                historyRisk,
                currentManager
        ));

        ReflectionTestUtils.invokeMethod(service, "emitSnapshot", 110L, emitter);

        assertEquals(List.of("task_started", "agent_card", "agent_card", "agent_card", "agent_card"), emitter.types());
        assertEquals(List.of(1, 2, 3, 4), emitter.agentCardDisplayOrders());
        assertEquals(List.of("running", "failed", "completed", "completed"), emitter.agentCardStages());
        assertEquals(List.of(false, false, true, false), emitter.agentCardReplayedFlags());
    }

    @Test
    void completedEventWaitsUntilTaskStatusBecomesTerminal() {
        PricingTask task = new PricingTask();
        PricingResult result = new PricingResult();

        task.setTaskStatus("RUNNING");
        assertFalse(PricingTaskStreamService.shouldEmitCompletedEvent(task, result, 4));

        task.setTaskStatus("MANUAL_REVIEW");
        assertTrue(PricingTaskStreamService.shouldEmitCompletedEvent(task, result, 3));
        assertTrue(PricingTaskStreamService.shouldEmitCompletedEvent(task, result, 4));

        task.setTaskStatus("COMPLETED");
        assertTrue(PricingTaskStreamService.shouldEmitCompletedEvent(task, result, 2));
        assertTrue(PricingTaskStreamService.shouldEmitCompletedEvent(task, result, 4));
    }

    @Test
    void manualReviewWithoutResultIsStillATerminalStatus() {
        PricingTask task = new PricingTask();
        task.setTaskStatus("MANUAL_REVIEW");

        assertTrue(PricingTaskStreamService.shouldEmitTerminalFailure(task, null));
        assertFalse(PricingTaskStreamService.resolveTerminalMessage(task).isBlank());
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
                Map.of("opinionId", "op-1", "summary", "raw opinion"),
                null
        );

        assertEquals("thinking", payload.get("thinking"));
        assertEquals("\u4eba\u5de5\u5ba1\u6838", ((Map<?, ?>) payload.get("suggestion")).get("strategy"));
        assertEquals(Map.of("opinionId", "op-1", "summary", "raw opinion"), payload.get("agentOpinion"));
        assertNull(payload.get("reasonWhy"));
    }

    @Test
    void runningAgentLogProducesRunningPayloadWithEmptyCard() {
        PricingTaskStreamService service = new PricingTaskStreamService(null, null, null, null);
        AgentRunLog log = new AgentRunLog();
        log.setTaskId(10L);
        log.setRoleName("Data Agent");
        log.setDisplayOrder(1);
        log.setStage("running");
        log.setRunAttempt(2);

        Map<String, Object> payload = ReflectionTestUtils.invokeMethod(service, "toAgentCard", 10L, log);

        assertEquals("agent_card", payload.get("type"));
        assertEquals("DATA_ANALYSIS", payload.get("agentCode"));
        assertEquals(2, payload.get("runAttempt"));
        assertEquals("running", payload.get("stage"));
        Map<?, ?> card = (Map<?, ?>) payload.get("card");
        assertEquals(Set.of("thinking", "evidence", "suggestion"), card.keySet());
        assertEquals("", card.get("thinking"));
        assertEquals(List.of(), card.get("evidence"));
        assertEquals(Map.of(), card.get("suggestion"));
        assertNull(card.get("reasonWhy"));
        assertNull(card.get("disagreementPoints"));
        assertNull(card.get("acceptedOpinions"));
        assertNull(card.get("rejectedOpinions"));
        assertNull(card.get("arbitrationDecision"));
        assertNull(card.get("arbitrationReason"));
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
    void failedAgentLogAllowsNullLiteralRawOutputWithoutThrowing() {
        PricingTaskStreamService service = new PricingTaskStreamService(null, null, null, null);
        AgentRunLog log = new AgentRunLog();
        log.setTaskId(10L);
        log.setRoleName("Manager Agent");
        log.setDisplayOrder(4);
        log.setStage("failed");
        log.setThinkingSummary("Agent execution failed: LLM API timeout");
        log.setSuggestionJson("{\"error\":true,\"message\":\"LLM API timeout\"}");
        log.setRawOutputJson("null");

        Map<String, Object> payload = ReflectionTestUtils.invokeMethod(service, "toAgentCard", 10L, log);

        assertEquals("agent_card", payload.get("type"));
        assertEquals("failed", payload.get("stage"));
        Map<?, ?> card = (Map<?, ?>) payload.get("card");
        assertFalse(card.containsKey("agentOpinion"));
        assertEquals(Boolean.TRUE, ((Map<?, ?>) card.get("suggestion")).get("error"));
    }

    @Test
    void legacyErrorSuggestionAlsoProducesFailedPayload() {
        PricingTaskStreamService service = new PricingTaskStreamService(null, null, null, null);
        AgentRunLog log = new AgentRunLog();
        log.setTaskId(11L);
        log.setRoleName("Market Agent");
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

        assertEquals("\u4eba\u5de5\u5ba1\u6838", payload.get("strategy"));
        assertNull(payload.get("summary"));
        assertEquals(1, payload.get("expectedSales"));
    }

    @Test
    void resultPayloadAlwaysReportsManualReviewStrategy() {
        PricingResult result = new PricingResult();
        result.setExecuteStrategy("DIRECT");
        result.setReviewRequired(0);

        Map<String, Object> payload = PricingTaskStreamService.buildResultPayload(result);

        assertEquals("\u4eba\u5de5\u5ba1\u6838", payload.get("strategy"));
    }

    @Test
    void managerSuggestionFieldsPassThroughToFrontend() {
        PricingTaskStreamService service = new PricingTaskStreamService(null, null, null, null);
        AgentRunLog log = completedLog(105L, "exec-manager", 1, 4, "Manager summary");
        log.setRoleName("Manager Agent");
        log.setRawOutputJson("""
                {
                  "agentOpinion": {
                    "opinionId": "raw-manager-1",
                    "summary": "Prefer market opinion",
                    "status": "MERGED"
                  }
                }
                """);
        log.setSuggestionJson("""
                {
                  "strategy":"DIRECT",
                  "summary":"Use coupon defense",
                  "agentOpinion":{"opinionId":"wrong-source"},
                  "disagreementPoints":[{"field":"price","reason":"market down"}],
                  "arbitrationDecision":"follow market",
                  "arbitrationReason":"sample is reliable",
                  "acceptedOpinions":["market"],
                  "rejectedOpinions":["risk"],
                  "consensusScore":0.72
                }
                """);

        Map<String, Object> payload = ReflectionTestUtils.invokeMethod(service, "toAgentCard", 105L, log);

        Map<?, ?> card = (Map<?, ?>) payload.get("card");
        assertEquals(Set.of("thinking", "evidence", "suggestion", "agentOpinion", "reasonWhy"), card.keySet());
        assertNull(card.get("disagreementPoints"));
        assertNull(card.get("acceptedOpinions"));
        assertNull(card.get("rejectedOpinions"));
        assertNull(card.get("arbitrationDecision"));
        assertNull(card.get("arbitrationReason"));
        assertEquals(Map.of(
                "opinionId", "raw-manager-1",
                "summary", "Prefer market opinion",
                "status", "MERGED"
        ), card.get("agentOpinion"));

        Map<?, ?> suggestion = (Map<?, ?>) card.get("suggestion");
        assertEquals("\u4eba\u5de5\u5ba1\u6838", suggestion.get("strategy"));
        assertEquals("Use coupon defense", suggestion.get("summary"));
        assertFalse(suggestion.containsKey("agentOpinion"));
        assertEquals(List.of(Map.of("field", "price", "reason", "market down")), suggestion.get("disagreementPoints"));
        assertEquals("follow market", suggestion.get("arbitrationDecision"));
        assertEquals("sample is reliable", suggestion.get("arbitrationReason"));
        assertEquals(List.of("market"), suggestion.get("acceptedOpinions"));
        assertEquals(List.of("risk"), suggestion.get("rejectedOpinions"));
        assertEquals(0.72d, suggestion.get("consensusScore"));
    }

    @Test
    void snapshotAndRealtimeAgentCardsUseSameAgentOpinionPayload() {
        PricingTaskMapper taskMapper = mock(PricingTaskMapper.class);
        PricingResultMapper resultMapper = mock(PricingResultMapper.class);
        AgentRunLogMapper logMapper = mock(AgentRunLogMapper.class);
        PricingTaskStreamService service = new PricingTaskStreamService(taskMapper, resultMapper, logMapper, null);
        PricingTask task = task(106L, "RUNNING", "exec-106");
        AgentRunLog currentLog = completedLog(106L, "exec-106", 1, 2, "Market current");
        currentLog.setRoleName("Market Agent");
        currentLog.setRawOutputJson("""
                {
                  "agentOpinion": {
                    "opinionId": "snapshot-rt-1",
                    "summary": "Use the same opinion everywhere"
                  }
                }
                """);

        when(taskMapper.selectById(106L)).thenReturn(task);
        when(logMapper.selectList(ArgumentMatchers.any())).thenReturn(List.of(currentLog));

        RecordingSseEmitter snapshotEmitter = new RecordingSseEmitter();
        ReflectionTestUtils.invokeMethod(service, "emitSnapshot", 106L, snapshotEmitter);

        RecordingSseEmitter realtimeEmitter = new RecordingSseEmitter();
        service.register(106L, realtimeEmitter);
        service.handleProgressEvent(new TaskProgressEvent(
                "evt-106",
                "AGENT_CARD_COMPLETED",
                106L,
                "exec-106",
                "trace-106",
                Map.of("agentName", "Market Agent"),
                Instant.parse("2026-04-30T10:02:00Z")
        ));

        Map<String, Object> snapshotCard = snapshotEmitter.payloads().stream()
                .filter(item -> "agent_card".equals(item.get("type")))
                .findFirst()
                .map(item -> (Map<String, Object>) item.get("card"))
                .orElseThrow();
        Map<String, Object> realtimeCard = realtimeEmitter.payloads().stream()
                .filter(item -> "agent_card".equals(item.get("type")))
                .findFirst()
                .map(item -> (Map<String, Object>) item.get("card"))
                .orElseThrow();

        assertEquals(snapshotCard, realtimeCard);
        assertEquals(Map.of(
                "opinionId", "snapshot-rt-1",
                "summary", "Use the same opinion everywhere"
        ), snapshotCard.get("agentOpinion"));
    }

    private static PricingTask task(Long taskId, String status, String currentExecutionId) {
        PricingTask task = new PricingTask();
        task.setId(taskId);
        task.setTaskStatus(status);
        task.setCurrentExecutionId(currentExecutionId);
        return task;
    }

    private static AgentRunLog completedLog(Long taskId, String executionId, int runAttempt, int displayOrder, String thinking) {
        AgentRunLog log = new AgentRunLog();
        log.setTaskId(taskId);
        log.setExecutionId(executionId);
        log.setRunAttempt(runAttempt);
        log.setDisplayOrder(displayOrder);
        log.setRoleName("Agent-" + displayOrder);
        log.setStage("completed");
        log.setThinkingSummary(thinking);
        log.setSuggestionJson("{\"summary\":\"ok\"}");
        return log;
    }

    private static AgentRunLog completedReplayableLog(Long id, Long taskId, String executionId, int runAttempt, int displayOrder, String thinking) {
        AgentRunLog log = completedLog(taskId, executionId, runAttempt, displayOrder, thinking);
        log.setId(id);
        log.setRawOutputJson("{\"agentOpinion\":{\"summary\":\"" + thinking + "\"}}");
        return log;
    }

    private static final class RecordingSseEmitter extends SseEmitter {

        private final List<Map<String, Object>> payloads = new ArrayList<>();

        @Override
        @SuppressWarnings("unchecked")
        public void send(SseEventBuilder builder) throws IOException {
            try {
                Method buildMethod = builder.getClass().getMethod("build");
                buildMethod.setAccessible(true);
                Set<?> entries = (Set<?>) buildMethod.invoke(builder);
                for (Object entry : entries) {
                    Method getDataMethod = entry.getClass().getMethod("getData");
                    getDataMethod.setAccessible(true);
                    Object data = getDataMethod.invoke(entry);
                    if (data instanceof Map<?, ?> map) {
                        payloads.add((Map<String, Object>) map);
                    }
                }
            } catch (ReflectiveOperationException ex) {
                throw new IOException(ex);
            }
        }

        List<Map<String, Object>> payloads() {
            return payloads;
        }

        List<String> types() {
            return payloads.stream().map(item -> String.valueOf(item.get("type"))).toList();
        }

        List<Integer> agentCardRunAttempts() {
            return payloads.stream()
                    .filter(item -> "agent_card".equals(item.get("type")))
                    .map(item -> (Integer) item.get("runAttempt"))
                    .toList();
        }

        List<Integer> agentCardDisplayOrders() {
            return payloads.stream()
                    .filter(item -> "agent_card".equals(item.get("type")))
                    .map(item -> (Integer) item.get("displayOrder"))
                    .toList();
        }

        List<String> agentCardStages() {
            return payloads.stream()
                    .filter(item -> "agent_card".equals(item.get("type")))
                    .map(item -> String.valueOf(item.get("stage")))
                    .toList();
        }

        List<Boolean> agentCardReplayedFlags() {
            return payloads.stream()
                    .filter(item -> "agent_card".equals(item.get("type")))
                    .map(item -> (Boolean) item.get("replayed"))
                    .toList();
        }

        List<Long> agentCardSourceLogIds() {
            return payloads.stream()
                    .filter(item -> "agent_card".equals(item.get("type")))
                    .map(item -> (Long) item.get("sourceLogId"))
                    .toList();
        }

        List<String> agentCardSourceExecutionIds() {
            return payloads.stream()
                    .filter(item -> "agent_card".equals(item.get("type")))
                    .map(item -> (String) item.get("sourceExecutionId"))
                    .toList();
        }

        List<Integer> agentCardSourceRunAttempts() {
            return payloads.stream()
                    .filter(item -> "agent_card".equals(item.get("type")))
                    .map(item -> (Integer) item.get("sourceRunAttempt"))
                    .toList();
        }

        List<String> agentCardThinkings() {
            return payloads.stream()
                    .filter(item -> "agent_card".equals(item.get("type")))
                    .map(item -> {
                        Map<?, ?> card = (Map<?, ?>) item.get("card");
                        return String.valueOf(card.get("thinking"));
                    })
                    .toList();
        }
    }
}
