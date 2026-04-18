package com.example.pricing.service;

import com.example.pricing.entity.AgentRunLog;
import com.example.pricing.entity.PricingResult;
import com.example.pricing.entity.PricingTask;
import com.example.pricing.entity.Product;
import com.example.pricing.entity.UserLlmConfig;
import com.example.pricing.common.AesGcmUtil;
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

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class DecisionTaskServiceImplTest {

    private static final String TEST_LLM_SECRET = "MGo++WTIw8a+iOkZAak7BVYIcE5DXix2uOjWsh1I4aY=";

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

    @Mock
    private UserLlmConfigMapper userLlmConfigMapper;

    private DecisionTaskServiceImpl service;

    @BeforeEach
    void setUp() {
        service = new DecisionTaskServiceImpl(
                taskMapper,
                resultMapper,
                logMapper,
                productMapper,
                shopService,
                pythonDispatchClient,
                userLlmConfigMapper
        );
        ReflectionTestUtils.setField(service, "llmKeyEncryptionSecret", TEST_LLM_SECRET);
    }

    @Test
    void startTaskDoesNotOverwritePythonQueuedStatusAfterSuccessfulDispatch() {
        Product product = new Product();
        product.setId(221L);
        product.setShopId(2L);
        product.setCurrentPrice(new BigDecimal("250.06"));

        UserLlmConfig llmConfig = new UserLlmConfig();
        llmConfig.setUserId(1L);
        llmConfig.setLlmApiKeyEnc(AesGcmUtil.encrypt("sk-test", TEST_LLM_SECRET));
        llmConfig.setLlmBaseUrl("https://dashscope.aliyuncs.com/compatible-mode/v1");
        llmConfig.setLlmModel("qwen3.5-122b-a10b");

        when(shopService.getShopIdsByUser(1L)).thenReturn(List.of(2L));
        when(productMapper.selectById(221L)).thenReturn(product);
        when(userLlmConfigMapper.selectOne(any())).thenReturn(llmConfig);
        when(taskMapper.selectOne(any())).thenReturn(null);
        doAnswer(invocation -> {
            PricingTask task = invocation.getArgument(0);
            task.setId(113L);
            return 1;
        }).when(taskMapper).insert(any(PricingTask.class));

        Long taskId = service.startTask(List.of(221L), "MARKET_SHARE", "", 1L);

        assertEquals(113L, taskId);
        verify(taskMapper).insert(any(PricingTask.class));
        verify(pythonDispatchClient).dispatchTask(any(), any());
        verify(taskMapper, never()).updateById(any(PricingTask.class));
    }

    @Test
    void startTaskRefreshesLlmConfigWhenReusingActiveTask() {
        Product product = new Product();
        product.setId(221L);
        product.setShopId(2L);
        product.setCurrentPrice(new BigDecimal("250.06"));

        UserLlmConfig llmConfig = new UserLlmConfig();
        llmConfig.setUserId(1L);
        llmConfig.setLlmApiKeyEnc(AesGcmUtil.encrypt("sk-current", TEST_LLM_SECRET));
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
        when(taskMapper.selectOne(any())).thenReturn(existing);

        Long taskId = service.startTask(List.of(221L), "MARKET_SHARE", "", 1L);

        assertEquals(114L, taskId);
        verify(taskMapper, never()).insert(any(PricingTask.class));
        ArgumentCaptor<Map<String, Object>> payloadCaptor = ArgumentCaptor.forClass(Map.class);
        verify(pythonDispatchClient).dispatchTask(payloadCaptor.capture(), any());
        assertEquals("sk-current", payloadCaptor.getValue().get("llmApiKey"));
        assertEquals("https://dashscope.aliyuncs.com/compatible-mode/v1", payloadCaptor.getValue().get("llmBaseUrl"));
        assertEquals("qwen3.5-122b-a10b", payloadCaptor.getValue().get("llmModel"));
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
