package com.example.pricing.service;

import com.example.pricing.entity.AgentRunLog;
import com.example.pricing.entity.PricingResult;
import com.example.pricing.entity.PricingTask;
import com.example.pricing.entity.Product;
import com.example.pricing.entity.UserLlmConfig;
import com.example.pricing.dto.TaskDispatchEvent;
import com.example.pricing.mapper.AgentRunLogMapper;
import com.example.pricing.mapper.PricingBatchItemMapper;
import com.example.pricing.mapper.PricingResultMapper;
import com.example.pricing.mapper.PricingTaskMapper;
import com.example.pricing.mapper.ProductMapper;
import com.example.pricing.mapper.UserLlmConfigMapper;
import com.example.pricing.service.impl.DecisionTaskServiceImpl;
import com.example.pricing.vo.DecisionLogVO;
import com.example.pricing.vo.PricingTaskSnapshotVO;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.AbstractPlatformTransactionManager;
import org.springframework.transaction.support.DefaultTransactionStatus;
import org.springframework.transaction.support.TransactionTemplate;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.contains;
import static org.mockito.ArgumentMatchers.isNull;
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
    private PricingBatchItemMapper pricingBatchItemMapper;

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
                pricingBatchItemMapper,
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
    void startTaskReturnsExistingTaskWhenConcurrentInsertHitsActiveIdempotencyKey() {
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
        existing.setId(116L);
        existing.setShopId(2L);
        existing.setProductId(221L);
        existing.setTaskStatus("PENDING");
        existing.setTraceId("trace-pending");

        when(shopService.getShopIdsByUser(1L)).thenReturn(List.of(2L));
        when(productMapper.selectById(221L)).thenReturn(product);
        when(userLlmConfigMapper.selectOne(any())).thenReturn(llmConfig);
        when(pricingTaskReuseSupport.buildIdempotencyKey(List.of(221L), "MARKET_SHARE", "", 1L)).thenReturn("idem-221");
        when(pricingTaskReuseSupport.findReusableTask("idem-221", 2L)).thenReturn(null, existing);
        doThrow(new DuplicateKeyException("Duplicate entry for uk_pricing_task_active_idem"))
                .when(taskMapper).insert(any(PricingTask.class));

        Long taskId = service.startTask(List.of(221L), "MARKET_SHARE", "", 1L);

        assertEquals(116L, taskId);
        verify(taskDispatchPublisher, never()).publishAndConfirm(any());
        verify(taskMapper, never()).updateStatusIfPending(any(), any());
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

    @Test
    void retryTaskRequeuesFailedTaskWithFreshDispatchSnapshot() {
        PricingTask task = new PricingTask();
        task.setId(31L);
        task.setShopId(5L);
        task.setProductId(301L);
        task.setTaskStatus("FAILED");
        task.setTraceId("trace-old");

        UserLlmConfig llmConfig = new UserLlmConfig();
        llmConfig.setLlmApiKeyEnc("enc-new");
        llmConfig.setLlmBaseUrl("https://llm.example");
        llmConfig.setLlmModel("qwen-max");

        when(taskMapper.selectById(31L)).thenReturn(task);
        when(shopService.getShopIdsByUser(88L)).thenReturn(List.of(5L));
        when(userLlmConfigMapper.selectOne(any())).thenReturn(llmConfig);
        when(taskMapper.retryFailedTask(eq(31L), any(), eq("enc-new"), eq("https://llm.example"), eq("qwen-max"))).thenReturn(1);

        service.retryTask(31L, 88L);

        ArgumentCaptor<String> traceCaptor = ArgumentCaptor.forClass(String.class);
        verify(taskMapper).retryFailedTask(eq(31L), traceCaptor.capture(), eq("enc-new"), eq("https://llm.example"), eq("qwen-max"));
        assertNotEquals("trace-old", traceCaptor.getValue());

        ArgumentCaptor<TaskDispatchEvent> eventCaptor = ArgumentCaptor.forClass(TaskDispatchEvent.class);
        verify(taskDispatchPublisher).publishAndConfirm(eventCaptor.capture());
        assertEquals(31L, eventCaptor.getValue().taskId());
        assertEquals(traceCaptor.getValue(), eventCaptor.getValue().traceId());
    }

    @Test
    void retryTaskRejectsNonFailedTaskWithoutPublishing() {
        PricingTask task = new PricingTask();
        task.setId(32L);
        task.setShopId(5L);
        task.setTaskStatus("MANUAL_REVIEW");

        when(taskMapper.selectById(32L)).thenReturn(task);
        when(shopService.getShopIdsByUser(88L)).thenReturn(List.of(5L));

        assertThrows(IllegalStateException.class, () -> service.retryTask(32L, 88L));

        verify(taskMapper, never()).retryFailedTask(any(), any(), any(), any(), any());
        verify(taskDispatchPublisher, never()).publishAndConfirm(any());
    }

    @Test
    void applyDecisionRejectsGuardrailBlockedResultWithoutUpdatingProduct() {
        PricingResult result = new PricingResult();
        result.setId(501L);
        result.setTaskId(601L);
        result.setFinalPrice(new BigDecimal("88.00"));
        result.setIsPass(0);
        result.setResultSummary("系统风控兜底已触发");

        PricingTask task = new PricingTask();
        task.setId(601L);
        task.setShopId(5L);
        task.setProductId(701L);
        task.setTaskStatus("MANUAL_REVIEW");

        Product product = new Product();
        product.setId(701L);
        product.setShopId(5L);
        product.setCurrentPrice(new BigDecimal("99.00"));

        when(resultMapper.selectById(501L)).thenReturn(result);
        when(taskMapper.selectById(601L)).thenReturn(task);
        when(shopService.getShopIdsByUser(88L)).thenReturn(List.of(5L));
        when(productMapper.selectById(701L)).thenReturn(product);

        IllegalStateException ex = assertThrows(IllegalStateException.class, () -> service.applyDecision(501L, 88L));

        assertEquals("Pricing result requires manual review: 系统风控兜底已触发", ex.getMessage());
        verify(resultMapper, never()).updateById(any(PricingResult.class));
        verify(productMapper, never()).updateById(any(Product.class));
        verify(taskMapper, never()).updateById(any(PricingTask.class));
    }

    @Test
    void applyDecisionRejectsMissingPassFlagWithoutUpdatingProduct() {
        PricingResult result = new PricingResult();
        result.setId(502L);
        result.setTaskId(602L);
        result.setFinalPrice(new BigDecimal("88.00"));
        result.setIsPass(null);

        PricingTask task = new PricingTask();
        task.setId(602L);
        task.setShopId(5L);
        task.setProductId(702L);
        task.setTaskStatus("MANUAL_REVIEW");

        Product product = new Product();
        product.setId(702L);
        product.setShopId(5L);
        product.setCurrentPrice(new BigDecimal("99.00"));

        when(resultMapper.selectById(502L)).thenReturn(result);
        when(taskMapper.selectById(602L)).thenReturn(task);
        when(shopService.getShopIdsByUser(88L)).thenReturn(List.of(5L));
        when(productMapper.selectById(702L)).thenReturn(product);

        IllegalStateException ex = assertThrows(IllegalStateException.class, () -> service.applyDecision(502L, 88L));

        assertEquals("Pricing result requires manual review: Pricing result is blocked by guardrails", ex.getMessage());
        verify(resultMapper, never()).updateById(any(PricingResult.class));
        verify(productMapper, never()).updateById(any(Product.class));
        verify(taskMapper, never()).updateById(any(PricingTask.class));
    }

    @Test
    void batchDeleteTasksRemovesOwnedTerminalTasksAndArtifacts() {
        PricingTask completed = new PricingTask();
        completed.setId(12L);
        completed.setShopId(3L);
        completed.setTaskStatus("COMPLETED");

        PricingTask failed = new PricingTask();
        failed.setId(13L);
        failed.setShopId(3L);
        failed.setTaskStatus("FAILED");

        when(shopService.getShopIdsByUser(99L)).thenReturn(List.of(3L));
        when(taskMapper.selectBatchIds(List.of(12L, 13L))).thenReturn(List.of(completed, failed));
        when(taskMapper.deleteBatchIds(List.of(12L, 13L))).thenReturn(2);

        int deleted = service.batchDeleteTasks(List.of(12L, 13L), 99L);

        assertEquals(2, deleted);
        verify(pricingBatchItemMapper).update(isNull(), any());
        verify(logMapper).delete(any());
        verify(resultMapper).delete(any());
        verify(taskMapper).deleteBatchIds(List.of(12L, 13L));
    }

    @Test
    void batchDeleteTasksRejectsActiveTasksWithoutDeletingArtifacts() {
        PricingTask running = new PricingTask();
        running.setId(14L);
        running.setShopId(3L);
        running.setTaskStatus("RUNNING");

        when(shopService.getShopIdsByUser(99L)).thenReturn(List.of(3L));
        when(taskMapper.selectBatchIds(List.of(14L))).thenReturn(List.of(running));

        assertThrows(IllegalStateException.class, () -> service.batchDeleteTasks(List.of(14L), 99L));

        verify(pricingBatchItemMapper, never()).update(any(), any());
        verify(logMapper, never()).delete(any());
        verify(resultMapper, never()).delete(any());
        verify(taskMapper, never()).deleteBatchIds(any());
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
        task.setCurrentExecutionId("exec-current");

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
        result.setExecutionId("exec-current");
        result.setExecuteStrategy("DIRECT");
        result.setResultSummary("ok");
        result.setReviewRequired(0);

        AgentRunLog runLog = new AgentRunLog();
        runLog.setId(1L);
        runLog.setTaskId(20L);
        runLog.setExecutionId("exec-current");
        runLog.setRoleName("数据分析Agent");
        runLog.setDisplayOrder(1);
        runLog.setStage("completed");
        runLog.setThinkingSummary("thinking");
        runLog.setEvidenceJson("[{\"label\":\"x\",\"value\":1}]");
        runLog.setSuggestionJson("{\"summary\":\"fine\",\"strategy\":\"DIRECT\",\"action\":\"人工审核\"}");
        runLog.setRawOutputJson("{\"agentOpinion\":{\"summary\":\"thinking\"}}");

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
        assertEquals(true, snapshot.getLogs().get(0).getNeedManualReview());

        assertEquals(1, snapshot.getComparison().size());
        assertEquals(new BigDecimal("105.00"), snapshot.getComparison().get(0).getSuggestedPrice());
        assertEquals("人工审核", snapshot.getComparison().get(0).getExecuteStrategy());
    }

    @Test
    void getTaskSnapshotUsesEffectiveTimelineWhileGetTaskLogsKeepsAuditTrail() {
        PricingTask task = new PricingTask();
        task.setId(21L);
        task.setShopId(9L);
        task.setProductId(101L);
        task.setTaskStatus("RUNNING");
        task.setCurrentPrice(new BigDecimal("99.00"));
        task.setCurrentExecutionId("exec-current");

        Product product = new Product();
        product.setId(101L);
        product.setTitle("娴嬭瘯鍟嗗搧");
        product.setCurrentPrice(new BigDecimal("99.00"));

        PricingResult result = new PricingResult();
        result.setId(201L);
        result.setTaskId(21L);
        result.setExecutionId("exec-old-1");
        result.setFinalPrice(new BigDecimal("105.00"));
        result.setExpectedSales(321);
        result.setExpectedProfit(new BigDecimal("1234.56"));
        result.setProfitGrowth(new BigDecimal("120.00"));
        result.setIsPass(1);
        result.setExecuteStrategy("DIRECT");
        result.setResultSummary("ok");
        result.setReviewRequired(0);

        AgentRunLog historyData = completedReplayableLog(2101L, 21L, "exec-old-1", 1, 1, "thinking");
        AgentRunLog historyMarket = completedReplayableLog(2102L, 21L, "exec-old-1", 1, 2, "market");
        AgentRunLog historyRisk = completedReplayableLog(2103L, 21L, "exec-old-1", 1, 3, "risk");
        AgentRunLog currentManager = completedReplayableLog(2104L, 21L, "exec-current", 2, 4, "manager");

        when(shopService.getShopIdsByUser(77L)).thenReturn(List.of(9L));
        when(taskMapper.selectById(21L)).thenReturn(task);
        when(productMapper.selectById(101L)).thenReturn(product);
        when(resultMapper.selectOne(any())).thenReturn(result);
        when(logMapper.selectList(any())).thenReturn(List.of(historyData, historyMarket, historyRisk, currentManager));

        PricingTaskSnapshotVO snapshot = service.getTaskSnapshot(21L, 77L);
        List<DecisionLogVO> allLogs = service.getTaskLogs(21L, 77L);

        assertEquals(4, snapshot.getLogs().size());
        assertEquals(List.of(1, 2, 3, 4), snapshot.getLogs().stream().map(DecisionLogVO::getDisplayOrder).toList());
        assertEquals(List.of(2, 2, 2, 2), snapshot.getLogs().stream().map(DecisionLogVO::getRunAttempt).toList());
        assertEquals(List.of(true, true, true, false), snapshot.getLogs().stream().map(DecisionLogVO::getReplayed).toList());
        assertEquals(java.util.Arrays.asList(2101L, 2102L, 2103L, null), snapshot.getLogs().stream().map(DecisionLogVO::getSourceLogId).toList());
        assertEquals(java.util.Arrays.asList("exec-old-1", "exec-old-1", "exec-old-1", null), snapshot.getLogs().stream().map(DecisionLogVO::getSourceExecutionId).toList());
        assertEquals(java.util.Arrays.asList(1, 1, 1, null), snapshot.getLogs().stream().map(DecisionLogVO::getSourceRunAttempt).toList());

        assertEquals(4, allLogs.size());
        assertEquals(List.of(false, false, false, false), allLogs.stream().map(log -> Boolean.TRUE.equals(log.getReplayed())).toList());
    }

    @Test
    void activeRetrySnapshotDoesNotExposeStaleResultFromPreviousExecution() {
        PricingTask task = new PricingTask();
        task.setId(22L);
        task.setShopId(9L);
        task.setProductId(101L);
        task.setTaskStatus("RETRYING");
        task.setCurrentExecutionId("exec-current");
        task.setCurrentPrice(new BigDecimal("99.00"));

        Product product = new Product();
        product.setId(101L);
        product.setTitle("测试商品");
        product.setCurrentPrice(new BigDecimal("99.00"));

        PricingResult staleResult = new PricingResult();
        staleResult.setId(202L);
        staleResult.setTaskId(22L);
        staleResult.setExecutionId("exec-old");
        staleResult.setFinalPrice(new BigDecimal("105.00"));
        staleResult.setExpectedSales(321);
        staleResult.setExpectedProfit(new BigDecimal("1234.56"));
        staleResult.setProfitGrowth(new BigDecimal("120.00"));

        when(shopService.getShopIdsByUser(77L)).thenReturn(List.of(9L));
        when(taskMapper.selectById(22L)).thenReturn(task);
        when(productMapper.selectById(101L)).thenReturn(product);
        when(resultMapper.selectOne(any())).thenReturn(staleResult);
        when(logMapper.selectList(any())).thenReturn(List.of());

        PricingTaskSnapshotVO snapshot = service.getTaskSnapshot(22L, 77L);

        assertEquals(null, snapshot.getDetail().getFinalPrice());
        assertEquals(null, snapshot.getDetail().getStrategy());
        assertEquals(List.of(), snapshot.getComparison());
    }

    @Test
    void getTaskSnapshotDoesNotReplayHistoricalCompletedCardWhenRawOutputIsEmpty() {
        PricingTask task = new PricingTask();
        task.setId(35L);
        task.setShopId(9L);
        task.setProductId(101L);
        task.setTaskStatus("RUNNING");
        task.setCurrentExecutionId("exec-current");

        Product product = new Product();
        product.setId(101L);
        product.setTitle("娴嬭瘯鍟嗗搧");

        AgentRunLog invalidHistory = completedReplayableLog(11L, 35L, "exec-old-1", 1, 1, "bad-history");
        invalidHistory.setRawOutputJson("{}");
        AgentRunLog historyMarket = completedReplayableLog(12L, 35L, "exec-old-1", 1, 2, "market");
        AgentRunLog historyRisk = completedReplayableLog(13L, 35L, "exec-old-1", 1, 3, "risk");
        AgentRunLog currentManager = completedReplayableLog(14L, 35L, "exec-current", 2, 4, "manager");

        when(shopService.getShopIdsByUser(77L)).thenReturn(List.of(9L));
        when(taskMapper.selectById(35L)).thenReturn(task);
        when(productMapper.selectById(101L)).thenReturn(product);
        when(resultMapper.selectOne(any())).thenReturn(null);
        when(logMapper.selectList(any())).thenReturn(List.of(invalidHistory, historyMarket, historyRisk, currentManager));

        PricingTaskSnapshotVO snapshot = service.getTaskSnapshot(35L, 77L);

        assertEquals(List.of(2, 3, 4), snapshot.getLogs().stream().map(DecisionLogVO::getDisplayOrder).toList());
        assertEquals(List.of(true, true, false), snapshot.getLogs().stream().map(DecisionLogVO::getReplayed).toList());
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

    @Test
    void getTaskLogsUsesRawAgentOpinionAndKeepsSuggestionAsLegacyDisplayData() {
        PricingTask task = new PricingTask();
        task.setId(32L);
        task.setShopId(9L);

        AgentRunLog runLog = new AgentRunLog();
        runLog.setId(4L);
        runLog.setTaskId(32L);
        runLog.setRoleName("Manager Agent");
        runLog.setDisplayOrder(4);
        runLog.setStage("completed");
        runLog.setThinkingSummary("manager thinking");
        runLog.setRawOutputJson("""
                {
                  "agentOpinion": {
                    "opinionId": "raw-op-32",
                    "summary": "Follow market with guardrail"
                  }
                }
                """);
        runLog.setSuggestionJson("""
                {
                  "summary":"legacy summary",
                  "strategy":"DIRECT",
                  "agentOpinion":{"opinionId":"wrong-source"},
                  "acceptedOpinions":["market"],
                  "arbitrationDecision":"follow market"
                }
                """);

        when(shopService.getShopIdsByUser(77L)).thenReturn(List.of(9L));
        when(taskMapper.selectById(32L)).thenReturn(task);
        when(logMapper.selectList(any())).thenReturn(List.of(runLog));

        var logs = service.getTaskLogs(32L, 77L);

        assertEquals(1, logs.size());
        assertEquals(Map.of(
                "opinionId", "raw-op-32",
                "summary", "Follow market with guardrail"
        ), logs.get(0).getAgentOpinion());
        assertEquals("legacy summary", logs.get(0).getSuggestion().get("summary"));
        assertEquals("\u4eba\u5de5\u5ba1\u6838", logs.get(0).getSuggestion().get("strategy"));
        assertEquals(List.of("market"), logs.get(0).getSuggestion().get("acceptedOpinions"));
        assertEquals("follow market", logs.get(0).getSuggestion().get("arbitrationDecision"));
        assertEquals(false, logs.get(0).getSuggestion().containsKey("agentOpinion"));
    }

    @Test
    void getTaskLogsBuildsLegacyAgentOpinionWhenRawOutputHasNoOpinion() {
        PricingTask task = new PricingTask();
        task.setId(33L);
        task.setShopId(9L);

        AgentRunLog runLog = new AgentRunLog();
        runLog.setId(5L);
        runLog.setTaskId(33L);
        runLog.setRoleName("Manager Agent");
        runLog.setDisplayOrder(4);
        runLog.setStage("completed");
        runLog.setRunAttempt(2);
        runLog.setThinkingSummary("legacy manager thinking");
        runLog.setSuggestionJson("""
                {
                  "summary":"legacy arbitration",
                  "strategy":"DIRECT",
                  "acceptedOpinions":["market"],
                  "rejectedOpinions":["risk"],
                  "disagreementPoints":[{"field":"price","reason":"risk too high"}],
                  "arbitrationDecision":"merge",
                  "arbitrationReason":"trade off growth and safety"
                }
                """);

        when(shopService.getShopIdsByUser(77L)).thenReturn(List.of(9L));
        when(taskMapper.selectById(33L)).thenReturn(task);
        when(logMapper.selectList(any())).thenReturn(List.of(runLog));

        var logs = service.getTaskLogs(33L, 77L);

        assertEquals(1, logs.size());
        Map<String, Object> agentOpinion = logs.get(0).getAgentOpinion();
        assertNotNull(agentOpinion);
        assertEquals("legacy arbitration", agentOpinion.get("summary"));
        assertEquals(List.of("market"), agentOpinion.get("acceptedOpinions"));
        assertEquals(List.of("risk"), agentOpinion.get("rejectedOpinions"));
        assertEquals(List.of(Map.of("field", "price", "reason", "risk too high")), agentOpinion.get("disagreementPoints"));
        assertEquals("merge", agentOpinion.get("arbitrationDecision"));
        assertEquals("trade off growth and safety", agentOpinion.get("arbitrationReason"));
    }

    @Test
    void getTaskLogsTreatsNullLiteralJsonFieldsAsEmptyStructures() {
        PricingTask task = new PricingTask();
        task.setId(34L);
        task.setShopId(9L);

        AgentRunLog runLog = new AgentRunLog();
        runLog.setId(6L);
        runLog.setTaskId(34L);
        runLog.setRoleName("Manager Agent");
        runLog.setDisplayOrder(4);
        runLog.setStage("failed");
        runLog.setThinkingSummary("Agent execution failed: LLM API timeout");
        runLog.setRawOutputJson("null");
        runLog.setSuggestionJson("null");

        when(shopService.getShopIdsByUser(77L)).thenReturn(List.of(9L));
        when(taskMapper.selectById(34L)).thenReturn(task);
        when(logMapper.selectList(any())).thenReturn(List.of(runLog));

        var logs = service.getTaskLogs(34L, 77L);

        assertEquals(1, logs.size());
        assertEquals("failed", logs.get(0).getStage());
        assertEquals("failed", logs.get(0).getRunStatus());
        assertEquals(Map.of(), logs.get(0).getSuggestion());
        assertEquals(null, logs.get(0).getAgentOpinion());
    }

    private static AgentRunLog completedReplayableLog(Long id, Long taskId, String executionId, int runAttempt, int displayOrder, String thinking) {
        AgentRunLog log = new AgentRunLog();
        log.setId(id);
        log.setTaskId(taskId);
        log.setExecutionId(executionId);
        log.setRunAttempt(runAttempt);
        log.setDisplayOrder(displayOrder);
        log.setRoleName("Agent-" + displayOrder);
        log.setStage("completed");
        log.setThinkingSummary(thinking);
        log.setSuggestionJson("{\"summary\":\"ok\",\"strategy\":\"DIRECT\"}");
        log.setRawOutputJson("{\"agentOpinion\":{\"summary\":\"" + thinking + "\"}}");
        return log;
    }
}
