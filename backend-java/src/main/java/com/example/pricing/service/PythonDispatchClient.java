package com.example.pricing.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.UriComponentsBuilder;

import java.time.Duration;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.LongSupplier;

/**
 * 遗留的 Python 同步派发客户端，主要保留给兼容/测试场景。
 * 当前主任务创建链路已经改为 RabbitMQ 异步派发，不再依赖此客户端。
 */
@Component
public class PythonDispatchClient {

    private final String pythonBaseUrl;
    private final String pythonDispatchPath;
    private final String pythonInternalToken;
    private final int maxAttempts;
    private final long retryBackoffMillis;
    private final int circuitFailureThreshold;
    private final long circuitOpenMillis;
    private final LongSupplier clock;
    private final Sleeper sleeper;
    private final DispatchTransport transport;
    private final AtomicInteger consecutiveTransientFailures = new AtomicInteger();

    private volatile long circuitOpenUntilMillis;

    @Autowired
    public PythonDispatchClient(
            @Value("${agent.python.base-url:http://localhost:8000}") String pythonBaseUrl,
            @Value("${agent.python.dispatch-path:/internal/tasks/dispatch}") String pythonDispatchPath,
            @Value("${agent.python.internal-token:}") String pythonInternalToken,
            @Value("${agent.python.connect-timeout-ms:3000}") int connectTimeoutMillis,
            @Value("${agent.python.read-timeout-ms:15000}") int readTimeoutMillis,
            @Value("${agent.python.max-attempts:3}") int maxAttempts,
            @Value("${agent.python.retry-backoff-ms:300}") long retryBackoffMillis,
            @Value("${agent.python.circuit-breaker.failure-threshold:3}") int circuitFailureThreshold,
            @Value("${agent.python.circuit-breaker.open-ms:30000}") long circuitOpenMillis) {
        this(
                pythonBaseUrl,
                pythonDispatchPath,
                pythonInternalToken,
                Math.max(maxAttempts, 1),
                Duration.ofMillis(Math.max(retryBackoffMillis, 100)),
                Math.max(circuitFailureThreshold, 1),
                Duration.ofMillis(Math.max(circuitOpenMillis, 1_000)),
                System::currentTimeMillis,
                PythonDispatchClient::sleepUnchecked,
                createTransport(connectTimeoutMillis, readTimeoutMillis)
        );
    }

    PythonDispatchClient(
            int maxAttempts,
            Duration retryBackoff,
            int circuitFailureThreshold,
            Duration circuitOpenDuration,
            LongSupplier clock,
            Sleeper sleeper,
            DispatchTransport transport) {
        this(
                "http://python",
                "/internal/tasks/dispatch",
                "",
                maxAttempts,
                retryBackoff,
                circuitFailureThreshold,
                circuitOpenDuration,
                clock,
                sleeper,
                transport
        );
    }

    private PythonDispatchClient(
            String pythonBaseUrl,
            String pythonDispatchPath,
            String pythonInternalToken,
            int maxAttempts,
            Duration retryBackoff,
            int circuitFailureThreshold,
            Duration circuitOpenDuration,
            LongSupplier clock,
            Sleeper sleeper,
            DispatchTransport transport) {
        this.pythonBaseUrl = Objects.requireNonNull(pythonBaseUrl);
        this.pythonDispatchPath = Objects.requireNonNull(pythonDispatchPath);
        this.pythonInternalToken = pythonInternalToken == null ? "" : pythonInternalToken;
        this.maxAttempts = Math.max(maxAttempts, 1);
        this.retryBackoffMillis = Math.max(retryBackoff.toMillis(), 100L);
        this.circuitFailureThreshold = Math.max(circuitFailureThreshold, 1);
        this.circuitOpenMillis = Math.max(circuitOpenDuration.toMillis(), 1_000L);
        this.clock = Objects.requireNonNull(clock);
        this.sleeper = Objects.requireNonNull(sleeper);
        this.transport = Objects.requireNonNull(transport);
    }

    public void dispatchTask(Map<String, Object> payload, String traceId) {
        String url = UriComponentsBuilder.fromHttpUrl(pythonBaseUrl)
                .path(pythonDispatchPath)
                .toUriString();

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        if (!pythonInternalToken.isBlank()) {
            headers.set("X-Internal-Token", pythonInternalToken);
        }
        if (traceId != null && !traceId.isBlank()) {
            headers.set("X-Trace-Id", traceId);
        }

        post(url, new HttpEntity<>(payload, headers));
    }

    public ResponseEntity<Map<String, Object>> post(String url, HttpEntity<Map<String, Object>> request) {
        long now = clock.getAsLong();
        if (isCircuitOpen(now)) {
            throw new CircuitOpenException("Python dispatch circuit is open");
        }

        PythonDispatchException lastFailure = null;
        for (int attempt = 1; attempt <= maxAttempts; attempt++) {
            try {
                ResponseEntity<Map<String, Object>> response = transport.post(url, request);
                validateResponse(response);
                recordSuccess();
                return response;
            } catch (PythonDispatchException e) {
                lastFailure = e;
                if (!e.isRetryable() || attempt >= maxAttempts) {
                    recordFailure(e.isTransientFailure());
                    throw e;
                }
            } catch (Exception e) {
                lastFailure = new PythonDispatchException(e.getMessage(), e, true, true);
                if (attempt >= maxAttempts) {
                    recordFailure(true);
                    throw lastFailure;
                }
            }

            try {
                sleeper.sleep(backoffForAttempt(attempt));
            } catch (InterruptedException interruptedException) {
                Thread.currentThread().interrupt();
                PythonDispatchException interrupted = new PythonDispatchException(
                        "Dispatch retry interrupted",
                        interruptedException,
                        false,
                        true
                );
                recordFailure(true);
                throw interrupted;
            }
        }

        recordFailure(lastFailure == null || lastFailure.isTransientFailure());
        throw lastFailure == null
                ? new PythonDispatchException("Dispatch failed without an upstream response", null, true, true)
                : lastFailure;
    }

    private void validateResponse(ResponseEntity<Map<String, Object>> response) {
        if (response == null) {
            throw new PythonDispatchException("Python dispatch returned no response", null, true, true);
        }

        if (!response.getStatusCode().is2xxSuccessful()) {
            boolean retryable = response.getStatusCode().is5xxServerError();
            throw new PythonDispatchException("HTTP " + response.getStatusCode().value(), null, retryable, retryable);
        }

        Map<String, Object> body = response.getBody();
        if (body != null && body.containsKey("accepted")) {
            Object accepted = body.get("accepted");
            if (accepted instanceof Boolean acceptedFlag && !acceptedFlag) {
                Object message = body.get("message");
                throw new PythonDispatchException(
                        message == null ? "python declined task" : String.valueOf(message),
                        null,
                        false,
                        false
                );
            }
        }
    }

    private long backoffForAttempt(int attempt) {
        long multiplier = 1L << Math.max(attempt - 1, 0);
        return retryBackoffMillis * multiplier;
    }

    private boolean isCircuitOpen(long nowMillis) {
        return circuitOpenUntilMillis > nowMillis;
    }

    private void recordSuccess() {
        consecutiveTransientFailures.set(0);
        circuitOpenUntilMillis = 0L;
    }

    private void recordFailure(boolean transientFailure) {
        if (!transientFailure) {
            return;
        }

        int failures = consecutiveTransientFailures.incrementAndGet();
        if (failures >= circuitFailureThreshold) {
            circuitOpenUntilMillis = clock.getAsLong() + circuitOpenMillis;
        }
    }

    private static DispatchTransport createTransport(int connectTimeoutMillis, int readTimeoutMillis) {
        SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(Math.max(connectTimeoutMillis, 1_000));
        requestFactory.setReadTimeout(Math.max(readTimeoutMillis, 1_000));
        RestTemplate restTemplate = new RestTemplate(requestFactory);
        return (url, request) -> restTemplate.postForEntity(url, request, (Class<Map<String, Object>>) (Class<?>) Map.class);
    }

    private static void sleepUnchecked(long millis) throws InterruptedException {
        Thread.sleep(millis);
    }

    @FunctionalInterface
    interface DispatchTransport {
        ResponseEntity<Map<String, Object>> post(String url, HttpEntity<Map<String, Object>> request) throws Exception;
    }

    @FunctionalInterface
    interface Sleeper {
        void sleep(long millis) throws InterruptedException;
    }

    public static class PythonDispatchException extends RuntimeException {
        private final boolean retryable;
        private final boolean transientFailure;

        public PythonDispatchException(String message, Throwable cause, boolean retryable, boolean transientFailure) {
            super(message, cause);
            this.retryable = retryable;
            this.transientFailure = transientFailure;
        }

        public boolean isRetryable() {
            return retryable;
        }

        public boolean isTransientFailure() {
            return transientFailure;
        }
    }

    public static class CircuitOpenException extends PythonDispatchException {
        public CircuitOpenException(String message) {
            super(message, null, false, true);
        }
    }
}
