package com.example.pricing.dto;

import com.fasterxml.jackson.annotation.JsonFormat;

import java.time.Instant;

public record TaskDispatchEvent(
        String eventId,
        Long taskId,
        String traceId,
        @JsonFormat(shape = JsonFormat.Shape.STRING)
        Instant occurredAt
) {
}
