package com.example.pricing.service.impl;

import com.example.pricing.common.Result;
import com.example.pricing.mapper.AgentRunLogMapper;
import com.example.pricing.mapper.PricingResultMapper;
import com.example.pricing.mapper.PricingTaskMapper;
import com.example.pricing.mapper.ProductDailyMetricMapper;
import com.example.pricing.mapper.ProductMapper;
import com.example.pricing.mapper.ShopMapper;
import com.example.pricing.mapper.TrafficPromoDailyMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ProductServiceImplTest {

    @Mock
    private ProductMapper productMapper;

    @Mock
    private ProductDailyMetricMapper statMapper;

    @Mock
    private TrafficPromoDailyMapper trafficPromoDailyMapper;

    @Mock
    private PricingTaskMapper pricingTaskMapper;

    @Mock
    private PricingResultMapper pricingResultMapper;

    @Mock
    private AgentRunLogMapper agentRunLogMapper;

    @Mock
    private ShopMapper shopMapper;

    @Mock
    private TaobaoExcelImportService taobaoExcelImportService;

    @InjectMocks
    private ProductServiceImpl productService;

    @Test
    void testBatchDeleteSuccess() {
        List<Long> ids = Arrays.asList(1L, 2L, 3L);
        when(pricingTaskMapper.selectList(any())).thenReturn(Collections.emptyList());
        when(productMapper.deleteBatchIds(ids)).thenReturn(3);

        Result<Void> result = productService.batchDelete(ids);

        assertEquals(200, result.getCode());
        verify(productMapper, times(1)).deleteBatchIds(ids);
    }

    @Test
    void testBatchDeleteEmptyList() {
        List<Long> ids = Collections.emptyList();

        Result<Void> result = productService.batchDelete(ids);

        assertEquals(500, result.getCode());
        assertTrue(result.getMessage().contains("删除"));
        verify(productMapper, never()).deleteBatchIds(anyList());
    }

    @Test
    void testBatchDeleteNullList() {
        Result<Void> result = productService.batchDelete(null);

        assertEquals(500, result.getCode());
        assertTrue(result.getMessage().contains("删除"));
        verify(productMapper, never()).deleteBatchIds(anyList());
    }

    @Test
    void testBatchDeleteException() {
        List<Long> ids = Arrays.asList(1L, 2L);
        when(pricingTaskMapper.selectList(any())).thenReturn(Collections.emptyList());
        when(productMapper.deleteBatchIds(ids)).thenThrow(new RuntimeException("DB Error"));

        Result<Void> result = productService.batchDelete(ids);

        assertEquals(500, result.getCode());
        assertTrue(result.getMessage().contains("DB Error"));
        verify(productMapper, times(1)).deleteBatchIds(ids);
    }
}
