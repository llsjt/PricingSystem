package com.example.pricing.security;

import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

@Component
public class ProductionReadinessChecker {

    private static final String DEFAULT_DB_PASSWORD = "123456";
    private static final String DEFAULT_JWT_SECRET = "PricingSystem2024SecretKeyForHS256AlgorithmMustBeLongEnough";

    public void assertSafe(Settings settings) {
        if (settings == null || !"prod".equalsIgnoreCase(String.valueOf(settings.appEnv()).trim())) {
            return;
        }

        List<String> problems = new ArrayList<>();
        if (DEFAULT_DB_PASSWORD.equals(settings.datasourcePassword())) {
            problems.add("default database password");
        }
        if (DEFAULT_JWT_SECRET.equals(settings.jwtSecret()) || settings.jwtSecret() == null || settings.jwtSecret().isBlank()) {
            problems.add("default jwt secret");
        }
        if (settings.internalToken() == null || settings.internalToken().isBlank()) {
            problems.add("blank internal api token");
        }
        if (settings.allowDevBootstrap()) {
            problems.add("dev bootstrap enabled");
        }
        if (settings.marketSimulationEnabled()) {
            problems.add("market simulation enabled");
        }

        if (!problems.isEmpty()) {
            throw new IllegalStateException("Unsafe production configuration detected in production mode: " + String.join(", ", problems));
        }
    }

    public record Settings(
            String appEnv,
            String datasourcePassword,
            String jwtSecret,
            String internalToken,
            boolean allowDevBootstrap,
            boolean marketSimulationEnabled
    ) {
    }
}
