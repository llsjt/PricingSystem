package com.example.pricing.common;

import org.junit.jupiter.api.Test;
import org.slf4j.MDC;

import static org.junit.jupiter.api.Assertions.assertEquals;

class ResultTest {

    @Test
    void successCopiesTraceIdFromMdc() {
        MDC.put("traceId", "req-123");
        try {
            Result<String> result = Result.success("ok");
            assertEquals("req-123", result.getTraceId());
        } finally {
            MDC.remove("traceId");
        }
    }

    @Test
    void errorCopiesTraceIdFromMdc() {
        MDC.put("traceId", "req-456");
        try {
            Result<Void> result = Result.error(500, "boom");
            assertEquals("req-456", result.getTraceId());
        } finally {
            MDC.remove("traceId");
        }
    }
}
