package com.example.pricing.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.UriComponentsBuilder;

import java.util.Map;
import java.util.Objects;

@Component
public class PythonBackendHealthClient {

    private final String pythonBaseUrl;
    private final String readyPath;
    private final HealthTransport transport;

    @Autowired
    public PythonBackendHealthClient(
            @Value("${agent.python.base-url:http://127.0.0.1:8000}") String pythonBaseUrl,
            @Value("${agent.python.ready-path:/health/ready}") String readyPath,
            @Value("${agent.python.health-timeout-ms:2000}") int timeoutMillis) {
        this(pythonBaseUrl, readyPath, createTransport(timeoutMillis));
    }

    PythonBackendHealthClient(String pythonBaseUrl, String readyPath, HealthTransport transport) {
        this.pythonBaseUrl = Objects.requireNonNull(pythonBaseUrl);
        this.readyPath = Objects.requireNonNull(readyPath);
        this.transport = Objects.requireNonNull(transport);
    }

    public boolean isReady() {
        try {
            String url = UriComponentsBuilder.fromHttpUrl(pythonBaseUrl).path(readyPath).toUriString();
            ResponseEntity<Map<String, Object>> response = transport.get(url);
            if (response == null || !response.getStatusCode().is2xxSuccessful()) {
                return false;
            }

            Map<String, Object> body = response.getBody();
            if (body == null || body.isEmpty()) {
                return false;
            }

            return "ok".equalsIgnoreCase(String.valueOf(body.getOrDefault("status", "")));
        } catch (Exception ignored) {
            return false;
        }
    }

    @FunctionalInterface
    interface HealthTransport {
        ResponseEntity<Map<String, Object>> get(String url) throws Exception;
    }

    @SuppressWarnings("unchecked")
    private static HealthTransport createTransport(int timeoutMillis) {
        SimpleClientHttpRequestFactory requestFactory = new SimpleClientHttpRequestFactory();
        requestFactory.setConnectTimeout(Math.max(timeoutMillis, 500));
        requestFactory.setReadTimeout(Math.max(timeoutMillis, 500));
        RestTemplate restTemplate = new RestTemplate(requestFactory);
        return url -> restTemplate.getForEntity(url, (Class<Map<String, Object>>) (Class<?>) Map.class);
    }
}
