package com.example.pricing.dto;

import com.fasterxml.jackson.annotation.JsonFormat;

import java.time.Instant;

/**
 * 任务派发事件对象，用于 Java 向异步通道发布待执行任务。
 */
public record TaskDispatchEvent(
        String eventId,
        Long taskId,
        String traceId,
        @JsonFormat(shape = JsonFormat.Shape.STRING)
        Instant occurredAt
) {
}
