package com.example.pricing.dto;

import java.time.Instant;
import java.util.Map;

/**
 * 任务进度事件对象，用于在 Java 侧接收并转发执行进度。
 */
public record TaskProgressEvent(
        String eventId,
        String eventType,
        Long taskId,
        String executionId,
        String traceId,
        Map<String, Object> payload,
        Instant occurredAt
) {
}
