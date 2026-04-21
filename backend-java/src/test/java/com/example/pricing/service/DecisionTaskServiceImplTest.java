package com.example.pricing.service;

import com.example.pricing.entity.AgentRunLog;
import com.example.pricing.entity.PricingResult;
import com.example.pricing.entity.PricingTask;
import com.example.pricing.entity.Product;
import com.example.pricing.entity.UserLlmConfig;
import com.example.pricing.dto.TaskDispatchEvent;
import com.example.pricing.mapper.AgentRunLogMapper;
import com.example.pricing.mapper.PricingResultMapper;
import com.example.pricing.mapper.PricingTaskMapper;
import com.example.pricing.mapper.ProductMapper;
import com.example.pricing.mapper.UserLlmConfigMapper;
import com.example.pricing.service.impl.DecisionTaskServiceImpl;
import com.example.pricing.vo.PricingTaskSnapshotVO;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.AbstractPlatformTransactionManager;
import org.springframework.transaction.support.DefaultTransactionStatus;
import org.springframework.transaction.support.TransactionTemplate;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.contains;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.never;
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
    private TaskDispatchPublisher taskDispatchPublisher;

    @Mock
    private UserLlmConfigMapper userLlmConfigMapper;

    @Mock
    private PricingTaskReuseSupport pricingTaskReuseSupport;

    private DecisionTaskServiceImpl service;

    @BeforeEach
    void setUp() {
        service = new DecisionTaskServiceImpl(
                taskMapper,
                resultMapper,
                logMapper,
                productMapper,
                shopService,
                taskDispatchPublisher,
                userLlmConfigMapper,
                pricingTaskReuseSupport,
                noOpTransactionTemplate()
        );
    }

    @Test
    void startTaskPublishesDispatchAndMarksPendingTaskQueuedAfterConfirm() {
        Product product = new Product();
        product.setId(221L);
        product.setShopId(2L);
        product.setCurrentPrice(new BigDecimal("250.06"));

        UserLlmConfig llmConfig = new UserLlmConfig();
        llmConfig.setUserId(1L);
        llmConfig.setLlmApiKeyEnc("cipher-from-user-config");
        llmConfig.setLlmBaseUrl("https://dashscope.aliyuncs.com/compatible-mode/v1");
        llmConfig.setLlmModel("qwen3.5-122b-a10b");

        when(shopService.getShopIdsByUser(1L)).thenReturn(List.of(2L));
        when(productMapper.selectById(221L)).thenReturn(product);
        when(userLlmConfigMapper.selectOne(any())).thenReturn(llmConfig);
        when(pricingTaskReuseSupport.buildIdempotencyKey(List.of(221L), "MARKET_SHARE", "", 1L)).thenReturn("idem-221");
        when(pricingTaskReuseSupport.findReusableTask("idem-221", 2L)).thenReturn(null);
        doAnswer(invocation -> {
            PricingTask task = invocation.getArgument(0);
            task.setId(113L);
            return 1;
        }).when(taskMapper).insert(any(PricingTask.class));

        Long taskId = service.startTask(List.of(221L), "MARKET_SHARE", "", 1L);

        assertEquals(113L, taskId);
        ArgumentCaptor<PricingTask> taskCaptor = ArgumentCaptor.forClass(PricingTask.class);
        verify(taskMapper).insert(taskCaptor.capture());
        PricingTask inserted = taskCaptor.getValue();
        assertEquals("PENDING", inserted.getTaskStatus());
        assertEquals("cipher-from-user-config", inserted.getLlmApiKeyEnc());
        assertEquals("https://dashscope.aliyuncs.com/compatible-mode/v1", inserted.getLlmBaseUrl());
        assertEquals("qwen3.5-122b-a10b", inserted.getLlmModel());

        ArgumentCaptor<TaskDispatchEvent> eventCaptor = ArgumentCaptor.forClass(TaskDispatchEvent.class);
        verify(taskDispatchPublisher).publishAndConfirm(eventCaptor.capture());
        assertEquals(113L, eventCaptor.getValue().taskId());
        assertEquals(inserted.getTraceId(), eventCaptor.getValue().traceId());
        verify(taskMapper).updateStatusIfPending(113L, "QUEUED");
        verify(taskMapper, never()).updateById(any(PricingTask.class));
    }

    @Test
    void startTaskDoesNotPublishWhenReusingActiveTask() {
        Product product = new Product();
        product.setId(221L);
        product.setShopId(2L);
        product.setCurrentPrice(new BigDecimal("250.06"));

        UserLlmConfig llmConfig = new UserLlmConfig();
        llmConfig.setUserId(1L);
        llmConfig.setLlmApiKeyEnc("cipher-current");
        llmConfig.setLlmBaseUrl("https://dashscope.aliyuncs.com/compatible-mode/v1");
        llmConfig.setLlmModel("qwen3.5-122b-a10b");

        PricingTask existing = new PricingTask();
        existing.setId(114L);
        existing.setShopId(2L);
        existing.setProductId(221L);
        existing.setTaskStatus("QUEUED");
        existing.setTraceId("trace-existing");

        when(shopService.getShopIdsByUser(1L)).thenReturn(List.of(2L));
        when(productMapper.selectById(221L)).thenReturn(product);
        when(userLlmConfigMapper.selectOne(any())).thenReturn(llmConfig);
        when(pricingTaskReuseSupport.buildIdempotencyKey(List.of(221L), "MARKET_SHARE", "", 1L)).thenReturn("idem-221");
        when(pricingTaskReuseSupport.findReusableTask("idem-221", 2L)).thenReturn(existing);

        Long taskId = service.startTask(List.of(221L), "MARKET_SHARE", "", 1L);

        assertEquals(114L, taskId);
        verify(taskMapper, never()).insert(any(PricingTask.class));
        verify(taskDispatchPublisher, never()).publishAndConfirm(any());
    }

    @Test
    void startTaskMarksTaskFailedWhenDispatchPublishFails() {
        Product product = new Product();
        product.setId(221L);
        product.setShopId(2L);
        product.setCurrentPrice(new BigDecimal("250.06"));

        UserLlmConfig llmConfig = new UserLlmConfig();
        llmConfig.setUserId(1L);
        llmConfig.setLlmApiKeyEnc("cipher-from-user-config");
        llmConfig.setLlmBaseUrl("https://dashscope.aliyuncs.com/compatible-mode/v1");
        llmConfig.setLlmModel("qwen3.5-122b-a10b");

        when(shopService.getShopIdsByUser(1L)).thenReturn(List.of(2L));
        when(productMapper.selectById(221L)).thenReturn(product);
        when(userLlmConfigMapper.selectOne(any())).thenReturn(llmConfig);
        when(pricingTaskReuseSupport.buildIdempotencyKey(List.of(221L), "MARKET_SHARE", "", 1L)).thenReturn("idem-221");
        when(pricingTaskReuseSupport.findReusableTask("idem-221", 2L)).thenReturn(null);
        doAnswer(invocation -> {
            PricingTask task = invocation.getArgument(0);
            task.setId(115L);
            return 1;
        }).when(taskMapper).insert(any(PricingTask.class));
        doThrow(new IllegalStateException("rabbit down")).when(taskDispatchPublisher).publishAndConfirm(any());

        assertThrows(IllegalStateException.class, () -> service.startTask(List.of(221L), "MARKET_SHARE", "", 1L));

        verify(taskMapper).updateStatusAndReason(eq(115L), eq("FAILED"), contains("派发失败"));
    }

    @Test
    void cancelTaskMarksQueuedTaskAsCancelled() {
        PricingTask task = new PricingTask();
        task.setId(12L);
        task.setShopId(3L);
        task.setTaskStatus("QUEUED");
        when(taskMapper.selectById(12L)).thenReturn(task);
        when(shopService.getShopIdsByUser(99L)).thenReturn(List.of(3L));
        when(taskMapper.cancelIfRunning(12L)).thenReturn(1);

        service.cancelTask(12L, 99L);

        verify(taskMapper).cancelIfRunning(12L);
        verify(taskMapper, never()).updateById(task);
    }

    @Test
    void cancelTaskMarksRunningTaskAsCancelled() {
        PricingTask task = new PricingTask();
        task.setId(13L);
        task.setShopId(5L);
        task.setTaskStatus("RUNNING");
        when(taskMapper.selectById(13L)).thenReturn(task);
        when(shopService.getShopIdsByUser(88L)).thenReturn(List.of(5L));
        when(taskMapper.cancelIfRunning(13L)).thenReturn(1);

        service.cancelTask(13L, 88L);

        verify(taskMapper).cancelIfRunning(13L);
        verify(taskMapper, never()).updateById(task);
    }

    private static TransactionTemplate noOpTransactionTemplate() {
        return new TransactionTemplate(new AbstractPlatformTransactionManager() {
            @Override
            protected Object doGetTransaction() {
                return new Object();
            }

            @Override
            protected void doBegin(Object transaction, TransactionDefinition definition) {
            }

            @Override
            protected void doCommit(DefaultTransactionStatus status) {
            }

            @Override
            protected void doRollback(DefaultTransactionStatus status) {
            }
        });
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
        runLog.setStage("completed");
        runLog.setThinkingSummary("thinking");
        runLog.setEvidenceJson("[{\"label\":\"x\",\"value\":1}]");
        runLog.setSuggestionJson("{\"summary\":\"fine\",\"strategy\":\"DIRECT\"}");

        when(shopService.getShopIdsByUser(77L)).thenReturn(List.of(9L));
        when(taskMapper.selectById(20L)).thenReturn(task);
        when(productMapper.selectById(101L)).thenReturn(product);
        when(resultMapper.selectOne(any())).thenReturn(result);
        when(logMapper.selectList(any())).thenReturn(List.of(runLog));

        PricingTaskSnapshotVO snapshot = service.getTaskSnapshot(20L, 77L);

        assertNotNull(snapshot.getDetail());
        assertEquals(20L, snapshot.getDetail().getTaskId());
        assertEquals("测试商品", snapshot.getDetail().getProductTitle());
        assertEquals("人工审核", snapshot.getDetail().getStrategy());

        assertEquals(1, snapshot.getLogs().size());
        assertEquals("DATA_ANALYSIS", snapshot.getLogs().get(0).getAgentCode());
        assertEquals("completed", snapshot.getLogs().get(0).getStage());
        assertEquals("人工审核", snapshot.getLogs().get(0).getSuggestion().get("strategy"));

        assertEquals(1, snapshot.getComparison().size());
        assertEquals(new BigDecimal("105.00"), snapshot.getComparison().get(0).getSuggestedPrice());
        assertEquals("人工审核", snapshot.getComparison().get(0).getExecuteStrategy());
    }

    @Test
    void getTaskLogsReturnsRunningStageForRunningAgentPlaceholder() {
        PricingTask task = new PricingTask();
        task.setId(30L);
        task.setShopId(9L);

        AgentRunLog runLog = new AgentRunLog();
        runLog.setId(2L);
        runLog.setTaskId(30L);
        runLog.setRoleName("市场情报Agent");
        runLog.setDisplayOrder(2);
        runLog.setStage("running");
        runLog.setRunAttempt(3);

        when(shopService.getShopIdsByUser(77L)).thenReturn(List.of(9L));
        when(taskMapper.selectById(30L)).thenReturn(task);
        when(logMapper.selectList(any())).thenReturn(List.of(runLog));

        var logs = service.getTaskLogs(30L, 77L);

        assertEquals(1, logs.size());
        assertEquals("MARKET_INTEL", logs.get(0).getAgentCode());
        assertEquals(3, logs.get(0).getRunAttempt());
        assertEquals("running", logs.get(0).getStage());
        assertEquals("running", logs.get(0).getRunStatus());
    }

    @Test
    void getTaskLogsReturnsFailedStageForFailedAgentCard() {
        PricingTask task = new PricingTask();
        task.setId(31L);
        task.setShopId(9L);

        AgentRunLog runLog = new AgentRunLog();
        runLog.setId(3L);
        runLog.setTaskId(31L);
        runLog.setRoleName("Manager Agent");
        runLog.setDisplayOrder(4);
        runLog.setStage("failed");
        runLog.setThinkingSummary("Agent execution failed: LLM API timeout");
        runLog.setSuggestionJson("{\"error\":true,\"message\":\"LLM API timeout\"}");

        when(shopService.getShopIdsByUser(77L)).thenReturn(List.of(9L));
        when(taskMapper.selectById(31L)).thenReturn(task);
        when(logMapper.selectList(any())).thenReturn(List.of(runLog));

        var logs = service.getTaskLogs(31L, 77L);

        assertEquals(1, logs.size());
        assertEquals("MANAGER_COORDINATOR", logs.get(0).getAgentCode());
        assertEquals("failed", logs.get(0).getStage());
        assertEquals("failed", logs.get(0).getRunStatus());
        assertEquals(Boolean.TRUE, logs.get(0).getSuggestion().get("error"));
    }
}
