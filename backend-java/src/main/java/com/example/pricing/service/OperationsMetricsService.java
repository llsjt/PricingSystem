package com.example.pricing.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.pricing.entity.PricingTask;
import com.example.pricing.mapper.PricingTaskMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class OperationsMetricsService {

    private final PricingTaskMapper pricingTaskMapper;

    @Value("${app.metrics.stale-running-minutes:15}")
    private long staleRunningMinutes;

    public Map<String, Object> snapshot() {
        List<PricingTask> tasks = pricingTaskMapper.selectList(new LambdaQueryWrapper<>());
        return summarize(tasks, LocalDateTime.now(), Duration.ofMinutes(Math.max(staleRunningMinutes, 1L)));
    }

    static Map<String, Object> summarize(List<PricingTask> tasks, LocalDateTime now, Duration staleAfter) {
        int total = tasks == null ? 0 : tasks.size();
        int queued = 0;
        int retrying = 0;
        int running = 0;
        int completed = 0;
        int manualReview = 0;
        int failed = 0;
        int cancelled = 0;
        int staleRunningTasks = 0;
        long durationSamples = 0L;
        double durationSumSeconds = 0d;
        double maxDurationSeconds = 0d;
        LocalDateTime latestTaskCreatedAt = null;
        LocalDateTime staleThreshold = now.minus(staleAfter);

        for (PricingTask task : tasks) {
            String status = normalizeStatus(task);
            if (task.getCreatedAt() != null && (latestTaskCreatedAt == null || task.getCreatedAt().isAfter(latestTaskCreatedAt))) {
                latestTaskCreatedAt = task.getCreatedAt();
            }

            switch (status) {
                case "QUEUED" -> queued++;
                case "RETRYING" -> retrying++;
                case "RUNNING" -> running++;
                case "COMPLETED" -> completed++;
                case "MANUAL_REVIEW" -> manualReview++;
                case "FAILED" -> failed++;
                case "CANCELLED" -> cancelled++;
                default -> {
                }
            }

            if (("RUNNING".equals(status) || "RETRYING".equals(status))
                    && task.getStartedAt() != null
                    && !task.getStartedAt().isAfter(staleThreshold)) {
                staleRunningTasks++;
            }

            if (isTerminal(status) && task.getStartedAt() != null && task.getCompletedAt() != null && !task.getCompletedAt().isBefore(task.getStartedAt())) {
                double durationSeconds = Duration.between(task.getStartedAt(), task.getCompletedAt()).toMillis() / 1000d;
                durationSamples++;
                durationSumSeconds += durationSeconds;
                maxDurationSeconds = Math.max(maxDurationSeconds, durationSeconds);
            }
        }

        Map<String, Object> snapshot = new LinkedHashMap<>();
        snapshot.put("total", total);
        snapshot.put("queued", queued);
        snapshot.put("retrying", retrying);
        snapshot.put("running", running);
        snapshot.put("queueDepth", queued + retrying);
        snapshot.put("activeExecutions", running);
        snapshot.put("completed", completed);
        snapshot.put("manualReview", manualReview);
        snapshot.put("failed", failed);
        snapshot.put("cancelled", cancelled);
        snapshot.put("staleRunningTasks", staleRunningTasks);
        snapshot.put("avgDurationSeconds", durationSamples == 0 ? 0d : round(durationSumSeconds / durationSamples));
        snapshot.put("maxDurationSeconds", round(maxDurationSeconds));
        snapshot.put("latestTaskCreatedAt", latestTaskCreatedAt == null ? null : latestTaskCreatedAt.toString());
        return snapshot;
    }

    private static boolean isTerminal(String status) {
        return "COMPLETED".equals(status)
                || "MANUAL_REVIEW".equals(status)
                || "FAILED".equals(status)
                || "CANCELLED".equals(status);
    }

    private static String normalizeStatus(PricingTask task) {
        return String.valueOf(task == null ? null : task.getTaskStatus()).toUpperCase();
    }

    private static double round(double value) {
        return Math.round(value * 100d) / 100d;
    }
}
