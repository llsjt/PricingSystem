package com.example.pricing.controller;

import com.example.pricing.service.OperationsMetricsService;
import com.example.pricing.service.PythonBackendHealthClient;
import org.springframework.amqp.rabbit.connection.Connection;
import org.springframework.amqp.rabbit.connection.ConnectionFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/health")
public class HealthController {

    private final JdbcTemplate jdbcTemplate;
    private final PythonBackendHealthClient pythonBackendHealthClient;
    private final OperationsMetricsService operationsMetricsService;
    private final ConnectionFactory connectionFactory;

    public HealthController(
            JdbcTemplate jdbcTemplate,
            PythonBackendHealthClient pythonBackendHealthClient,
            OperationsMetricsService operationsMetricsService,
            ConnectionFactory connectionFactory
    ) {
        this.jdbcTemplate = jdbcTemplate;
        this.pythonBackendHealthClient = pythonBackendHealthClient;
        this.operationsMetricsService = operationsMetricsService;
        this.connectionFactory = connectionFactory;
    }

    @GetMapping
    public Map<String, Object> health() {
        return ready();
    }

    @GetMapping("/live")
    public Map<String, Object> live() {
        return Map.of("status", "ok");
    }

    @GetMapping("/ready")
    public Map<String, Object> ready() {
        Map<String, Object> payload = new LinkedHashMap<>();
        boolean databaseOk = false;
        boolean pythonOk = pythonBackendHealthClient.isReady();
        boolean rabbitmqOk = false;
        try {
            jdbcTemplate.queryForObject("SELECT 1", Integer.class);
            databaseOk = true;
        } catch (Exception e) {
        }
        try (Connection ignored = connectionFactory.createConnection()) {
            rabbitmqOk = true;
        } catch (Exception ignore) {
        }
        payload.put("status", databaseOk && pythonOk && rabbitmqOk ? "ok" : "degraded");
        payload.put("database", databaseOk ? "ok" : "down");
        payload.put("pythonWorker", pythonOk ? "ok" : "down");
        payload.put("rabbitmq", rabbitmqOk ? "ok" : "down");
        return payload;
    }

    @GetMapping("/metrics")
    public Map<String, Object> metrics() {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("status", ready().get("status"));
        payload.put("tasks", operationsMetricsService.snapshot());
        return payload;
    }
}
