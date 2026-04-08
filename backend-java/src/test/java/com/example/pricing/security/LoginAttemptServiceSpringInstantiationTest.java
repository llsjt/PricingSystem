package com.example.pricing.security;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Import;
import org.springframework.context.support.PropertySourcesPlaceholderConfigurer;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.junit.jupiter.SpringJUnitConfig;

import static org.junit.jupiter.api.Assertions.assertNotNull;

@SpringJUnitConfig(classes = LoginAttemptServiceSpringInstantiationTest.Config.class)
@TestPropertySource(properties = {
        "app.security.login.max-attempts=5",
        "app.security.login.lock-minutes=15"
})
class LoginAttemptServiceSpringInstantiationTest {

    @Autowired
    private LoginAttemptService loginAttemptService;

    @Test
    void springCanInstantiateLoginAttemptServiceBean() {
        assertNotNull(loginAttemptService);
    }

    @Configuration
    @Import(LoginAttemptService.class)
    static class Config {
        @Bean
        static PropertySourcesPlaceholderConfigurer propertySourcesPlaceholderConfigurer() {
            return new PropertySourcesPlaceholderConfigurer();
        }
    }
}
