package com.example.pricing.service;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.context.support.PropertySourcesPlaceholderConfigurer;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.junit.jupiter.SpringJUnitConfig;

import static org.junit.jupiter.api.Assertions.assertNotNull;

@SpringJUnitConfig(classes = PythonDispatchClientSpringInstantiationTest.Config.class)
@TestPropertySource(properties = {
        "agent.python.base-url=http://localhost:8000",
        "agent.python.dispatch-path=/internal/tasks/dispatch",
        "agent.python.internal-token=test-token"
})
class PythonDispatchClientSpringInstantiationTest {

    @Autowired
    private PythonDispatchClient pythonDispatchClient;

    @Test
    void springCanInstantiatePythonDispatchClientBean() {
        assertNotNull(pythonDispatchClient);
    }

    @Configuration
    @Import(PythonDispatchClient.class)
    static class Config {
        @Bean
        static PropertySourcesPlaceholderConfigurer propertySourcesPlaceholderConfigurer() {
            return new PropertySourcesPlaceholderConfigurer();
        }
    }
}
