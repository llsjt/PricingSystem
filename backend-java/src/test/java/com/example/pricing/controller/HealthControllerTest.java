package com.example.pricing.controller;

import com.example.pricing.service.OperationsMetricsService;
import com.example.pricing.service.PythonBackendHealthClient;
import org.junit.jupiter.api.Test;
import org.springframework.amqp.rabbit.connection.Connection;
import org.springframework.amqp.rabbit.connection.ConnectionFactory;
import org.springframework.jdbc.core.JdbcTemplate;

import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class HealthControllerTest {

    @Test
    void readyReportsOkOnlyWhenDatabasePythonAndRabbitmqAreAllReady() {
        JdbcTemplate jdbcTemplate = mock(JdbcTemplate.class);
        PythonBackendHealthClient pythonBackendHealthClient = mock(PythonBackendHealthClient.class);
        OperationsMetricsService operationsMetricsService = mock(OperationsMetricsService.class);
        ConnectionFactory connectionFactory = mock(ConnectionFactory.class);
        Connection connection = mock(Connection.class);

        when(jdbcTemplate.queryForObject("SELECT 1", Integer.class)).thenReturn(1);
        when(pythonBackendHealthClient.isReady()).thenReturn(true);
        when(connectionFactory.createConnection()).thenReturn(connection);

        HealthController controller = new HealthController(
                jdbcTemplate,
                pythonBackendHealthClient,
                operationsMetricsService,
                connectionFactory
        );

        Map<String, Object> payload = controller.ready();

        assertEquals("ok", payload.get("status"));
        assertEquals("ok", payload.get("database"));
        assertEquals("ok", payload.get("pythonWorker"));
        assertEquals("ok", payload.get("rabbitmq"));
    }
}
