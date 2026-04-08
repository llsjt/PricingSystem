package com.example.pricing.service;

import com.example.pricing.entity.PricingTask;
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;

class OperationsMetricsServiceTest {

    @Test
    void summarizesTaskCountsDurationsAndStaleRunningTasks() {
        LocalDateTime now = LocalDateTime.of(2026, 4, 8, 13, 0, 0);

        PricingTask queued = task("QUEUED", now.minusMinutes(3), null, null);
        PricingTask retrying = task("RETRYING", now.minusMinutes(5), now.minusMinutes(5), null);
        PricingTask running = task("RUNNING", now.minusMinutes(20), now.minusMinutes(20), null);
        PricingTask completed = task("COMPLETED", now.minusMinutes(15), now.minusMinutes(14), now.minusMinutes(10));
        PricingTask manualReview = task("MANUAL_REVIEW", now.minusMinutes(12), now.minusMinutes(11), now.minusMinutes(8));
        PricingTask failed = task("FAILED", now.minusMinutes(7), now.minusMinutes(6), now.minusMinutes(5));
        PricingTask cancelled = task("CANCELLED", now.minusMinutes(4), now.minusMinutes(4), now.minusMinutes(3));

        Map<String, Object> snapshot = OperationsMetricsService.summarize(
                List.of(queued, retrying, running, completed, manualReview, failed, cancelled),
                now,
                Duration.ofMinutes(15)
        );

        assertEquals(7, snapshot.get("total"));
        assertEquals(1, snapshot.get("queued"));
        assertEquals(1, snapshot.get("retrying"));
        assertEquals(1, snapshot.get("running"));
        assertEquals(2, snapshot.get("queueDepth"));
        assertEquals(1, snapshot.get("activeExecutions"));
        assertEquals(1, snapshot.get("completed"));
        assertEquals(1, snapshot.get("manualReview"));
        assertEquals(1, snapshot.get("failed"));
        assertEquals(1, snapshot.get("cancelled"));
        assertEquals(1, snapshot.get("staleRunningTasks"));
        assertEquals(135.0d, snapshot.get("avgDurationSeconds"));
        assertEquals(240.0d, snapshot.get("maxDurationSeconds"));
    }

    private static PricingTask task(String status, LocalDateTime createdAt, LocalDateTime startedAt, LocalDateTime completedAt) {
        PricingTask task = new PricingTask();
        task.setTaskStatus(status);
        task.setCreatedAt(createdAt);
        task.setStartedAt(startedAt);
        task.setCompletedAt(completedAt);
        return task;
    }
}
