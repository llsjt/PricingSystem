package com.example.pricing.service.impl;

import com.example.pricing.common.Result;
import com.example.pricing.mapper.BizProductMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
public class ProductServiceImplTest {

    @Mock
    private BizProductMapper productMapper;

    @InjectMocks
    private ProductServiceImpl productService;

    @Test
    public void testBatchDelete_Success() {
        List<Long> ids = Arrays.asList(1L, 2L, 3L);
        when(productMapper.deleteBatchIds(ids)).thenReturn(3);

        Result<Void> result = productService.batchDelete(ids);

        assertEquals(200, result.getCode());
        verify(productMapper, times(1)).deleteBatchIds(ids);
    }

    @Test
    public void testBatchDelete_EmptyList() {
        List<Long> ids = Collections.emptyList();

        Result<Void> result = productService.batchDelete(ids);

        assertEquals(500, result.getCode());
        assertEquals("请选择要删除的商品", result.getMessage());
        verify(productMapper, never()).deleteBatchIds(anyList());
    }

    @Test
    public void testBatchDelete_NullList() {
        Result<Void> result = productService.batchDelete(null);

        assertEquals(500, result.getCode());
        assertEquals("请选择要删除的商品", result.getMessage());
        verify(productMapper, never()).deleteBatchIds(anyList());
    }

    @Test
    public void testBatchDelete_Exception() {
        List<Long> ids = Arrays.asList(1L, 2L);
        when(productMapper.deleteBatchIds(ids)).thenThrow(new RuntimeException("DB Error"));

        Result<Void> result = productService.batchDelete(ids);

        assertEquals(500, result.getCode());
        assertEquals("批量删除失败：DB Error", result.getMessage());
        verify(productMapper, times(1)).deleteBatchIds(ids);
    }
}
