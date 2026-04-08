package com.example.pricing.service;

import com.example.pricing.entity.AgentRunLog;
import com.example.pricing.entity.PricingResult;
import com.example.pricing.entity.PricingTask;
import com.example.pricing.entity.Product;
import com.example.pricing.mapper.AgentRunLogMapper;
import com.example.pricing.mapper.PricingResultMapper;
import com.example.pricing.mapper.PricingTaskMapper;
import com.example.pricing.mapper.ProductMapper;
import com.example.pricing.service.impl.DecisionTaskServiceImpl;
import com.example.pricing.vo.PricingTaskSnapshotVO;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.mockito.ArgumentMatchers.any;
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

    @Test
    void taskSnapshotAggregatesDetailLogsAndComparison() {
        PricingTask task = new PricingTask();
        task.setId(20L);
        task.setShopId(9L);
        task.setProductId(101L);
        task.setTaskStatus("RUNNING");
        task.setCurrentPrice(new BigDecimal("99.00"));

        Product product = new Product();
        product.setId(101L);
        product.setTitle("测试商品");
        product.setCurrentPrice(new BigDecimal("99.00"));

        PricingResult result = new PricingResult();
        result.setId(200L);
        result.setTaskId(20L);
        result.setFinalPrice(new BigDecimal("105.00"));
        result.setExpectedSales(321);
        result.setExpectedProfit(new BigDecimal("1234.56"));
        result.setProfitGrowth(new BigDecimal("120.00"));
        result.setIsPass(1);
        result.setExecuteStrategy("DIRECT");
        result.setResultSummary("ok");
        result.setReviewRequired(0);

        AgentRunLog runLog = new AgentRunLog();
        runLog.setId(1L);
        runLog.setTaskId(20L);
        runLog.setRoleName("数据分析Agent");
        runLog.setDisplayOrder(1);
        runLog.setThinkingSummary("thinking");
        runLog.setEvidenceJson("[{\"label\":\"x\",\"value\":1}]");
        runLog.setSuggestionJson("{\"summary\":\"fine\"}");

        when(shopService.getShopIdsByUser(77L)).thenReturn(List.of(9L));
        when(taskMapper.selectById(20L)).thenReturn(task);
        when(productMapper.selectById(101L)).thenReturn(product);
        when(resultMapper.selectOne(any())).thenReturn(result);
        when(logMapper.selectList(any())).thenReturn(List.of(runLog));

        PricingTaskSnapshotVO snapshot = service.getTaskSnapshot(20L, 77L);

        assertNotNull(snapshot.getDetail());
        assertEquals(20L, snapshot.getDetail().getTaskId());
        assertEquals("测试商品", snapshot.getDetail().getProductTitle());

        assertEquals(1, snapshot.getLogs().size());
        assertEquals("DATA_ANALYSIS", snapshot.getLogs().get(0).getAgentCode());

        assertEquals(1, snapshot.getComparison().size());
        assertEquals(new BigDecimal("105.00"), snapshot.getComparison().get(0).getSuggestedPrice());
    }
}
