package com.example.pricing.controller;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 健康检查控制器，用于确认 Java 后端服务是否正常启动。
 */
@RestController
@RequestMapping("/api")
public class HealthController {

    /**
     * 返回简单文本，供前端或网关探测服务可用性。
     */
    @GetMapping("/health")
    public String health() {
        return "Java Backend Ready";
    }
}
