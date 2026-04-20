package com.example.pricing.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.exception.GlobalExceptionHandler;
import com.example.pricing.service.PricingBatchService;
import com.example.pricing.vo.PricingBatchDetailVO;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.validation.beanvalidation.LocalValidatorFactoryBean;

import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@ExtendWith(MockitoExtension.class)
class PricingBatchControllerValidationTest {

    @Mock
    private PricingBatchService pricingBatchService;

    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        LocalValidatorFactoryBean validator = new LocalValidatorFactoryBean();
        validator.afterPropertiesSet();
        mockMvc = MockMvcBuilders.standaloneSetup(new PricingBatchController(pricingBatchService))
                .setControllerAdvice(new GlobalExceptionHandler())
                .setValidator(validator)
                .build();
    }

    @Test
    void createBatchRejectsBlankStrategyGoalAtControllerBoundary() throws Exception {
        mockMvc.perform(post("/api/pricing/batches")
                        .contentType(MediaType.APPLICATION_JSON)
                        .requestAttr("currentUserId", 7L)
                        .content("""
                                {
                                  "productIds": [101],
                                  "strategyGoal": "   ",
                                  "constraints": ""
                                }
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value(400));

        verifyNoInteractions(pricingBatchService);
    }

    @Test
    void createBatchRejectsEmptyProductIdsAtControllerBoundary() throws Exception {
        mockMvc.perform(post("/api/pricing/batches")
                        .contentType(MediaType.APPLICATION_JSON)
                        .requestAttr("currentUserId", 7L)
                        .content("""
                                {
                                  "productIds": [],
                                  "strategyGoal": "MAX_PROFIT",
                                  "constraints": ""
                                }
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value(400));

        verifyNoInteractions(pricingBatchService);
    }

    @Test
    void listBatchesUsesCurrentUserAndReturnsPagedSummaries() throws Exception {
        PricingBatchDetailVO row = new PricingBatchDetailVO();
        row.setBatchId(44L);
        row.setBatchCode("BATCH-RUNNING");
        row.setBatchStatus("RUNNING");
        row.setTotalCount(3);

        Page<PricingBatchDetailVO> page = new Page<>(1, 5);
        page.setTotal(1);
        page.setRecords(java.util.List.of(row));
        when(pricingBatchService.getRecentBatches(1, 5, "RUNNING", 7L)).thenReturn(page);

        mockMvc.perform(get("/api/pricing/batches")
                        .requestAttr("currentUserId", 7L)
                        .param("page", "1")
                        .param("size", "5")
                        .param("status", "RUNNING"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(200))
                .andExpect(jsonPath("$.data.records[0].batchId").value(44))
                .andExpect(jsonPath("$.data.records[0].batchStatus").value("RUNNING"));

        verify(pricingBatchService).getRecentBatches(1, 5, "RUNNING", 7L);
    }
}
