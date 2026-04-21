package com.example.pricing.dto;

import java.time.Instant;
import java.util.Map;

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
