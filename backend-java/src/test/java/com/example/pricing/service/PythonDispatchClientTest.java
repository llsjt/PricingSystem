package com.example.pricing.service;

import org.junit.jupiter.api.Test;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class PythonDispatchClientTest {

    @Test
    void retriesTemporaryTransportFailuresBeforeSucceeding() {
        AtomicInteger attempts = new AtomicInteger();
        List<Long> sleepDurations = new ArrayList<>();

        PythonDispatchClient client = new PythonDispatchClient(
                3,
                Duration.ofMillis(200),
                3,
                Duration.ofSeconds(30),
                () -> 1_000L,
                millis -> sleepDurations.add(millis),
                (url, request) -> {
                    if (attempts.incrementAndGet() < 3) {
                        throw new IllegalStateException("temporary upstream failure");
                    }
                    return ResponseEntity.ok(Map.of("accepted", true));
                }
        );

        assertDoesNotThrow(() -> client.post(
                "http://python/internal/tasks/dispatch",
                new HttpEntity<>(Map.of("taskId", 1L))
        ));

        assertEquals(3, attempts.get());
        assertEquals(List.of(200L, 400L), sleepDurations);
    }

    @Test
    void opensCircuitAfterConfiguredFailuresAndRejectsImmediatelyDuringCooldown() {
        AtomicLong nowMillis = new AtomicLong(10_000L);
        AtomicInteger attempts = new AtomicInteger();

        PythonDispatchClient client = new PythonDispatchClient(
                2,
                Duration.ofMillis(50),
                1,
                Duration.ofSeconds(30),
                nowMillis::get,
                ignored -> {
                },
                (url, request) -> {
                    attempts.incrementAndGet();
                    throw new IllegalStateException("python unavailable");
                }
        );

        assertThrows(PythonDispatchClient.PythonDispatchException.class, () -> client.post(
                "http://python/internal/tasks/dispatch",
                new HttpEntity<>(Map.of("taskId", 2L))
        ));

        assertEquals(2, attempts.get());

        assertThrows(PythonDispatchClient.CircuitOpenException.class, () -> client.post(
                "http://python/internal/tasks/dispatch",
                new HttpEntity<>(Map.of("taskId", 3L))
        ));

        assertEquals(2, attempts.get());
    }

    @Test
    void allowsTrafficAgainAfterCircuitCooldownExpires() {
        AtomicLong nowMillis = new AtomicLong(20_000L);
        AtomicInteger attempts = new AtomicInteger();

        PythonDispatchClient client = new PythonDispatchClient(
                1,
                Duration.ofMillis(100),
                1,
                Duration.ofSeconds(10),
                nowMillis::get,
                ignored -> {
                },
                (url, request) -> {
                    if (attempts.incrementAndGet() == 1) {
                        throw new IllegalStateException("first failure opens circuit");
                    }
                    return ResponseEntity.ok(Map.of("accepted", true));
                }
        );

        assertThrows(PythonDispatchClient.PythonDispatchException.class, () -> client.post(
                "http://python/internal/tasks/dispatch",
                new HttpEntity<>(Map.of("taskId", 4L))
        ));

        nowMillis.addAndGet(Duration.ofSeconds(11).toMillis());

        assertDoesNotThrow(() -> client.post(
                "http://python/internal/tasks/dispatch",
                new HttpEntity<>(Map.of("taskId", 5L))
        ));

        assertEquals(2, attempts.get());
    }

    @Test
    void doesNotRetryBusinessRejectionReturnedByPython() {
        AtomicInteger attempts = new AtomicInteger();

        PythonDispatchClient client = new PythonDispatchClient(
                3,
                Duration.ofMillis(200),
                3,
                Duration.ofSeconds(30),
                () -> 1_000L,
                ignored -> {
                },
                (url, request) -> {
                    attempts.incrementAndGet();
                    return ResponseEntity.status(HttpStatus.OK).body(Map.of(
                            "accepted", false,
                            "message", "worker queue is full"
                    ));
                }
        );

        PythonDispatchClient.PythonDispatchException exception = assertThrows(
                PythonDispatchClient.PythonDispatchException.class,
                () -> client.post("http://python/internal/tasks/dispatch", new HttpEntity<>(Map.of("taskId", 6L)))
        );

        assertEquals("worker queue is full", exception.getMessage());
        assertEquals(1, attempts.get());
    }
}
