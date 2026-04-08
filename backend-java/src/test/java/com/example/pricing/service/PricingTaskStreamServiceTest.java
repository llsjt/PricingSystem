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
    }

    @Test
    void cardPayloadAllowsNullReason() {
        Map<String, Object> payload = PricingTaskStreamService.buildCardPayload(
                "thinking",
                List.of(Map.of("label", "x", "value", 1)),
                Map.of("summary", "ok"),
                null
        );

        assertEquals("thinking", payload.get("thinking"));
        assertNull(payload.get("reasonWhy"));
    }

    @Test
    void resultPayloadAllowsNullOptionalFields() {
        PricingResult result = new PricingResult();
        result.setExpectedSales(1);

        Map<String, Object> payload = PricingTaskStreamService.buildResultPayload(result);

        assertNull(payload.get("strategy"));
        assertNull(payload.get("summary"));
        assertEquals(1, payload.get("expectedSales"));
    }
}
