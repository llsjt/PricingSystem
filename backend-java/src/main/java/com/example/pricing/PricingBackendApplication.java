package com.example.pricing;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
@MapperScan("com.example.pricing.mapper")
public class PricingBackendApplication {

    public static void main(String[] args) {
        SpringApplication.run(PricingBackendApplication.class, args);
    }

}
