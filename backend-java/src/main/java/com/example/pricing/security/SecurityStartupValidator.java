package com.example.pricing.security;

import com.example.pricing.config.LaunchSecurityValidator;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * 安全启动校验服务，在生产环境启动前检查关键安全配置。
 */
@Component
@RequiredArgsConstructor
public class SecurityStartupValidator {

    private final LaunchSecurityValidator launchSecurityValidator;

    @Value("${app.env:dev}")
    private String appEnv;

    @Value("${spring.datasource.password:}")
    private String datasourcePassword;

    @Value("${jwt.secret:}")
    private String jwtSecret;

    @Value("${agent.python.internal-token:}")
    private String internalToken;

    @Value("${app.security.allow-dev-bootstrap:true}")
    private boolean allowDevBootstrap;

    @Value("${app.security.allowed-origins:http://localhost:*,http://127.0.0.1:*,http://[::1]:*}")
    private String allowedOrigins;

    @PostConstruct
    public void validate() {
        launchSecurityValidator.validateOrThrow(
                appEnv,
                allowDevBootstrap,
                datasourcePassword,
                jwtSecret,
                internalToken,
                allowedOrigins
        );
    }
}
