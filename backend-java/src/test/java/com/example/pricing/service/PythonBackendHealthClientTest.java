package com.example.pricing.service;

import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class PythonBackendHealthClientTest {

    @Test
    void reportsReadyWhenPythonHealthEndpointReturnsOk() {
        AtomicReference<String> requestedUrl = new AtomicReference<>();
        PythonBackendHealthClient client = new PythonBackendHealthClient(
                "http://127.0.0.1:8000",
                "/health/ready",
                url -> {
                    requestedUrl.set(url);
                    return ResponseEntity.ok(Map.of("status", "ok"));
                }
        );

        assertTrue(client.isReady());
        assertEquals("http://127.0.0.1:8000/health/ready", requestedUrl.get());
    }

    @Test
    void reportsNotReadyWhenUpstreamReturnsNonSuccessfulStatus() {
        PythonBackendHealthClient client = new PythonBackendHealthClient(
                "http://127.0.0.1:8000",
                "/health/ready",
                url -> ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(Map.of("status", "degraded"))
        );

        assertFalse(client.isReady());
    }

    @Test
    void reportsNotReadyWhenUpstreamThrowsException() {
        PythonBackendHealthClient client = new PythonBackendHealthClient(
                "http://127.0.0.1:8000",
                "/health/ready",
                url -> {
                    throw new IllegalStateException("connection refused");
                }
        );

        assertFalse(client.isReady());
    }
}
