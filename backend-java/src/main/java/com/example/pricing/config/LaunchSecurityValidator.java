package com.example.pricing.config;

import com.example.pricing.security.ProductionReadinessChecker;
import org.springframework.stereotype.Component;

@Component
public class LaunchSecurityValidator {

    private final ProductionReadinessChecker productionReadinessChecker = new ProductionReadinessChecker();

    public void validateOrThrow(
            String appEnv,
            boolean allowDevBootstrap,
            String datasourcePassword,
            String jwtSecret,
            String internalToken,
            String allowedOrigins
    ) {
        productionReadinessChecker.assertSafe(new ProductionReadinessChecker.Settings(
                appEnv,
                datasourcePassword,
                jwtSecret,
                internalToken,
                allowDevBootstrap
        ));

        if (!"prod".equalsIgnoreCase(String.valueOf(appEnv).trim())) {
            return;
        }

        String normalizedOrigins = String.valueOf(allowedOrigins).trim().toLowerCase();
        if (normalizedOrigins.isBlank()) {
            throw new IllegalStateException("Unsafe production configuration detected in production mode: blank allowed origins");
        }
        if (normalizedOrigins.contains("localhost")
                || normalizedOrigins.contains("127.0.0.1")
                || normalizedOrigins.contains("[::1]")) {
            throw new IllegalStateException("Unsafe production configuration detected in production mode: localhost origins");
        }
    }
}
