package com.example.pricing.security;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.time.Duration;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.LongSupplier;

@Component
public class LoginAttemptService {

    private final int maxAttempts;
    private final long lockDurationMillis;
    private final LongSupplier nowMillisSupplier;
    private final ConcurrentHashMap<String, AttemptState> attempts = new ConcurrentHashMap<>();

    @Autowired
    public LoginAttemptService(
            @Value("${app.security.login.max-attempts:5}") int maxAttempts,
            @Value("${app.security.login.lock-minutes:15}") long lockMinutes
    ) {
        this(maxAttempts, Duration.ofMinutes(Math.max(lockMinutes, 1)), System::currentTimeMillis);
    }

    public LoginAttemptService(int maxAttempts, Duration lockDuration, LongSupplier nowMillisSupplier) {
        this.maxAttempts = Math.max(maxAttempts, 1);
        this.lockDurationMillis = Math.max(lockDuration.toMillis(), 1L);
        this.nowMillisSupplier = nowMillisSupplier;
    }

    public boolean isAllowed(String key) {
        if (key == null || key.isBlank()) {
            return true;
        }
        AttemptState state = attempts.get(key);
        if (state == null) {
            return true;
        }
        long now = nowMillisSupplier.getAsLong();
        if (state.lockedUntilMillis > 0 && now >= state.lockedUntilMillis) {
            attempts.remove(key);
            return true;
        }
        return state.lockedUntilMillis <= 0 || now >= state.lockedUntilMillis;
    }

    public void recordFailure(String key) {
        if (key == null || key.isBlank()) {
            return;
        }
        attempts.compute(key, (ignored, current) -> {
            AttemptState next = current == null ? new AttemptState() : current;
            next.failureCount += 1;
            if (next.failureCount >= maxAttempts) {
                next.lockedUntilMillis = nowMillisSupplier.getAsLong() + lockDurationMillis;
            }
            return next;
        });
    }

    public void recordSuccess(String key) {
        if (key == null || key.isBlank()) {
            return;
        }
        attempts.remove(key);
    }

    public String blockedMessage() {
        return "登录失败次数过多，请稍后再试";
    }

    private static final class AttemptState {
        private int failureCount;
        private long lockedUntilMillis;
    }
}
