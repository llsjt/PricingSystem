package com.example.pricing.service;

import com.example.pricing.entity.PricingResult;
import com.example.pricing.entity.PricingTask;
import org.junit.jupiter.api.Test;

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
