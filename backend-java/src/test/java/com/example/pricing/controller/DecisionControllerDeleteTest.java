package com.example.pricing.controller;

import com.example.pricing.exception.GlobalExceptionHandler;
import com.example.pricing.service.DecisionTaskService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.List;

import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class DecisionControllerDeleteTest {

    @Mock
    private DecisionTaskService decisionTaskService;

    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        mockMvc = MockMvcBuilders.standaloneSetup(new DecisionController(decisionTaskService))
                .setControllerAdvice(new GlobalExceptionHandler())
                .build();
    }

    @Test
    void batchDeleteUsesLiteralRouteAndCommaSeparatedIds() throws Exception {
        when(decisionTaskService.batchDeleteTasks(List.of(12L, 13L), 7L)).thenReturn(2);

        mockMvc.perform(delete("/api/decision/tasks/batch-delete")
                        .requestAttr("currentUserId", 7L)
                        .param("ids", "12,13"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data").value(2));

        verify(decisionTaskService).batchDeleteTasks(List.of(12L, 13L), 7L);
    }

    @Test
    void deleteTaskUsesNumericTaskRoute() throws Exception {
        mockMvc.perform(delete("/api/decision/tasks/12")
                        .requestAttr("currentUserId", 7L))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200));

        verify(decisionTaskService).deleteTask(12L, 7L);
    }
}
