package com.example.pricing;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * Java 后端应用启动入口，负责初始化 Spring Boot 容器和 MyBatis Mapper 扫描。
 */
@SpringBootApplication
@MapperScan("com.example.pricing.mapper")
@EnableScheduling
public class PricingBackendApplication {

    /**
     * 启动定价决策后端服务。
     */
    public static void main(String[] args) {
        SpringApplication.run(PricingBackendApplication.class, args);
    }
}
