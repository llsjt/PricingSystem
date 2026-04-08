package com.example.pricing.security;

import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.util.concurrent.atomic.AtomicLong;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class LoginAttemptServiceTest {

    @Test
    void blocksFurtherAttemptsAfterConfiguredFailuresUntilWindowExpires() {
        AtomicLong nowMillis = new AtomicLong(1_000L);
        LoginAttemptService service = new LoginAttemptService(3, Duration.ofMinutes(15), nowMillis::get);

        assertTrue(service.isAllowed("alice"));

        service.recordFailure("alice");
        service.recordFailure("alice");
        service.recordFailure("alice");

        assertFalse(service.isAllowed("alice"));

        nowMillis.addAndGet(Duration.ofMinutes(16).toMillis());

        assertTrue(service.isAllowed("alice"));
    }

    @Test
    void successResetsFailureCounter() {
        AtomicLong nowMillis = new AtomicLong(1_000L);
        LoginAttemptService service = new LoginAttemptService(3, Duration.ofMinutes(15), nowMillis::get);

        service.recordFailure("bob");
        service.recordFailure("bob");
        service.recordSuccess("bob");
        service.recordFailure("bob");

        assertTrue(service.isAllowed("bob"));
    }
}
