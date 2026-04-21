package com.example.pricing.common;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;
import org.springframework.web.filter.CorsFilter;

import java.util.Arrays;

/**
 * 跨域配置类，统一放行前端访问 Java API 所需的来源、方法与请求头。
 */
@Configuration
public class CorsConfig {

    @Value("${app.security.allowed-origins:http://localhost:*,http://127.0.0.1:*,http://[::1]:*}")
    private String allowedOrigins;

    @Bean
    public CorsFilter corsFilter() {
        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        CorsConfiguration corsConfiguration = buildCorsConfiguration(allowedOrigins);
        source.registerCorsConfiguration("/**", corsConfiguration);
        return new CorsFilter(source);
    }

    static CorsConfiguration buildCorsConfiguration(String allowedOrigins) {
        CorsConfiguration corsConfiguration = new CorsConfiguration();
        Arrays.stream(String.valueOf(allowedOrigins).split(","))
                .map(String::trim)
                .filter(origin -> !origin.isBlank())
                .forEach(origin -> {
                    if (origin.contains("*")) {
                        corsConfiguration.addAllowedOriginPattern(origin);
                        return;
                    }
                    corsConfiguration.addAllowedOrigin(origin);
                });
        corsConfiguration.addAllowedHeader("*");
        corsConfiguration.addAllowedMethod("*");
        corsConfiguration.addExposedHeader("Authorization");
        corsConfiguration.setAllowCredentials(true);
        return corsConfiguration;
    }
}
