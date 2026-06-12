package com.example.pricing.controller;

import com.example.pricing.exception.GlobalExceptionHandler;
import com.example.pricing.service.DecisionTaskService;
import com.example.pricing.service.PricingTaskStreamService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.validation.beanvalidation.LocalValidatorFactoryBean;

import static org.mockito.Mockito.verifyNoInteractions;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class PricingTaskControllerValidationTest {

    @Mock
    private DecisionTaskService decisionTaskService;

    @Mock
    private PricingTaskStreamService pricingTaskStreamService;

    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        LocalValidatorFactoryBean validator = new LocalValidatorFactoryBean();
        validator.afterPropertiesSet();
        mockMvc = MockMvcBuilders.standaloneSetup(new PricingTaskController(decisionTaskService, pricingTaskStreamService))
                .setControllerAdvice(new GlobalExceptionHandler())
                .setValidator(validator)
                .build();
    }

    @Test
    void createTaskRejectsOverlongStrategyGoalAtControllerBoundary() throws Exception {
        mockMvc.perform(post("/api/pricing/tasks")
                        .contentType(MediaType.APPLICATION_JSON)
                        .requestAttr("currentUserId", 7L)
                        .content("""
                                {
                                  "productId": 101,
                                  "strategyGoal": "%s",
                                  "constraints": ""
                                }
                                """.formatted("A".repeat(51))))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value(400))
                .andExpect(jsonPath("$.message").value("strategyGoal length cannot exceed 50"));

        verifyNoInteractions(decisionTaskService, pricingTaskStreamService);
    }
}
