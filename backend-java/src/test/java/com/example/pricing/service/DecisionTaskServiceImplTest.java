package com.example.pricing.service;

import com.example.pricing.entity.PricingTask;
import com.example.pricing.mapper.AgentRunLogMapper;
import com.example.pricing.mapper.PricingResultMapper;
import com.example.pricing.mapper.PricingTaskMapper;
import com.example.pricing.mapper.ProductMapper;
import com.example.pricing.service.impl.DecisionTaskServiceImpl;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class DecisionTaskServiceImplTest {

    @Mock
    private PricingTaskMapper taskMapper;

    @Mock
    private PricingResultMapper resultMapper;

    @Mock
    private AgentRunLogMapper logMapper;

    @Mock
    private ProductMapper productMapper;

    @Mock
    private ShopService shopService;

    @Mock
    private PythonDispatchClient pythonDispatchClient;

    private DecisionTaskServiceImpl service;

    @BeforeEach
    void setUp() {
        service = new DecisionTaskServiceImpl(
                taskMapper,
                resultMapper,
                logMapper,
                productMapper,
                shopService,
                pythonDispatchClient
        );
    }

    @Test
    void cancelTaskMarksQueuedTaskAsCancelled() {
        PricingTask task = new PricingTask();
        task.setId(12L);
        task.setShopId(3L);
        task.setTaskStatus("QUEUED");
        when(taskMapper.selectById(12L)).thenReturn(task);
        when(shopService.getShopIdsByUser(99L)).thenReturn(List.of(3L));

        service.cancelTask(12L, 99L);

        assertEquals("CANCELLED", task.getTaskStatus());
        assertEquals("任务已取消", task.getFailureReason());
        verify(taskMapper).updateById(task);
    }

    @Test
    void cancelTaskMarksRunningTaskAsCancelled() {
        PricingTask task = new PricingTask();
        task.setId(13L);
        task.setShopId(5L);
        task.setTaskStatus("RUNNING");
        when(taskMapper.selectById(13L)).thenReturn(task);
        when(shopService.getShopIdsByUser(88L)).thenReturn(List.of(5L));

        service.cancelTask(13L, 88L);

        assertEquals("CANCELLED", task.getTaskStatus());
        assertEquals("任务已取消", task.getFailureReason());
        verify(taskMapper).updateById(task);
    }
}
