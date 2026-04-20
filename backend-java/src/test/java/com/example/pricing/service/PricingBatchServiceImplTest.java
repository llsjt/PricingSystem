package com.example.pricing.service;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.dto.PricingBatchCreateDTO;
import com.example.pricing.entity.PricingBatch;
import com.example.pricing.entity.PricingBatchItem;
import com.example.pricing.entity.PricingResult;
import com.example.pricing.entity.PricingTask;
import com.example.pricing.entity.Product;
import com.example.pricing.mapper.PricingBatchItemMapper;
import com.example.pricing.mapper.PricingBatchMapper;
import com.example.pricing.mapper.PricingResultMapper;
import com.example.pricing.mapper.PricingTaskMapper;
import com.example.pricing.mapper.ProductMapper;
import com.example.pricing.service.impl.PricingBatchServiceImpl;
import com.example.pricing.vo.PricingBatchCancelVO;
import com.example.pricing.vo.PricingBatchCreateVO;
import com.example.pricing.vo.PricingBatchDetailVO;
import com.example.pricing.vo.PricingBatchItemVO;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicLong;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class PricingBatchServiceImplTest {

    @Mock
    private PricingBatchMapper pricingBatchMapper;

    @Mock
    private PricingBatchItemMapper pricingBatchItemMapper;

    @Mock
    private ProductMapper productMapper;

    @Mock
    private PricingTaskMapper pricingTaskMapper;

    @Mock
    private PricingResultMapper pricingResultMapper;

    @Mock
    private DecisionTaskService decisionTaskService;

    @Mock
    private PricingTaskReuseSupport pricingTaskReuseSupport;

    @Mock
    private ShopService shopService;

    private PricingBatchServiceImpl service;

    @BeforeEach
    void setUp() {
        service = new PricingBatchServiceImpl(
                pricingBatchMapper,
                pricingBatchItemMapper,
                productMapper,
                pricingTaskMapper,
                pricingResultMapper,
                decisionTaskService,
                pricingTaskReuseSupport,
                shopService
        );
    }

    @Test
    void createBatchCreatesLinkedItemsWhenAllTasksStartNormally() {
        PricingBatchCreateDTO request = new PricingBatchCreateDTO();
        request.setProductIds(List.of(101L, 102L));
        request.setStrategyGoal("MAX_PROFIT");
        request.setConstraints("{\"min_profit_rate\":0.15}");

        Product product101 = product(101L, 9L, "A", new BigDecimal("80.00"));
        Product product102 = product(102L, 9L, "B", new BigDecimal("90.00"));
        PricingTask task501 = task(501L, 9L, 101L, "QUEUED", new BigDecimal("80.00"));
        PricingTask task502 = task(502L, 9L, 102L, "RUNNING", new BigDecimal("90.00"));

        List<PricingBatchItem> storedItems = new ArrayList<>();
        doAnswer(invocation -> {
            PricingBatch batch = invocation.getArgument(0);
            batch.setId(44L);
            return 1;
        }).when(pricingBatchMapper).insert(any(PricingBatch.class));
        AtomicLong itemId = new AtomicLong(1L);
        doAnswer(invocation -> {
            PricingBatchItem item = invocation.getArgument(0);
            item.setId(itemId.getAndIncrement());
            storedItems.add(item);
            return 1;
        }).when(pricingBatchItemMapper).insert(any(PricingBatchItem.class));

        when(shopService.getShopIdsByUser(7L)).thenReturn(List.of(9L));
        when(decisionTaskService.createPricingTask(101L, "MAX_PROFIT", "{\"min_profit_rate\":0.15}", 7L)).thenReturn(501L);
        when(decisionTaskService.createPricingTask(102L, "MAX_PROFIT", "{\"min_profit_rate\":0.15}", 7L)).thenReturn(502L);
        when(pricingBatchMapper.selectById(44L)).thenReturn(batch(44L, 7L, "RUNNING"));
        when(pricingBatchItemMapper.selectList(any())).thenReturn(storedItems);
        when(productMapper.selectBatchIds(any())).thenReturn(List.of(product101, product102));
        when(pricingTaskMapper.selectList(any())).thenReturn(List.of(task501, task502));
        when(pricingResultMapper.selectList(any())).thenReturn(List.of());

        PricingBatchCreateVO response = service.createBatch(request, 7L);

        assertEquals(44L, response.getBatchId());
        ArgumentCaptor<PricingBatch> createdBatchCaptor = ArgumentCaptor.forClass(PricingBatch.class);
        verify(pricingBatchMapper).insert(createdBatchCaptor.capture());
        assertEquals(true, createdBatchCaptor.getValue().getBatchCode().matches("BATCH-\\d{14}-[0-9A-F]{12}"));
        assertEquals(List.of(501L, 502L), response.getLinkedTaskIds());
        assertEquals(0, response.getCreateFailedCount());
        assertEquals(2, storedItems.size());
        assertEquals("TASK_LINKED", storedItems.get(0).getItemStatus());
        assertEquals(501L, storedItems.get(0).getTaskId());
        assertEquals("TASK_LINKED", storedItems.get(1).getItemStatus());
        assertEquals(502L, storedItems.get(1).getTaskId());

        ArgumentCaptor<PricingBatch> batchCaptor = ArgumentCaptor.forClass(PricingBatch.class);
        verify(pricingBatchMapper).updateById(batchCaptor.capture());
        assertEquals("RUNNING", batchCaptor.getValue().getBatchStatus());
        assertEquals(0, batchCaptor.getValue().getFailedCount());
        assertEquals(2, batchCaptor.getValue().getTotalCount());
    }

    @Test
    void createBatchRejectsBlankStrategyGoal() {
        PricingBatchCreateDTO request = new PricingBatchCreateDTO();
        request.setProductIds(List.of(101L));
        request.setStrategyGoal("   ");
        request.setConstraints("");

        IllegalArgumentException error = assertThrows(
                IllegalArgumentException.class,
                () -> service.createBatch(request, 7L)
        );

        assertEquals("策略目标不能为空", error.getMessage());
        verify(pricingBatchMapper, never()).insert(any(PricingBatch.class));
    }

    @Test
    void createBatchRejectsProductOutsideCurrentUserScope() {
        PricingBatchCreateDTO request = new PricingBatchCreateDTO();
        request.setProductIds(List.of(101L));
        request.setStrategyGoal("MAX_PROFIT");
        request.setConstraints("");

        Product product = product(101L, 9L, "A", new BigDecimal("55.00"));
        when(shopService.getShopIdsByUser(7L)).thenReturn(List.of(8L));
        when(productMapper.selectBatchIds(any())).thenReturn(List.of(product));

        IllegalArgumentException error = assertThrows(IllegalArgumentException.class, () -> service.createBatch(request, 7L));

        assertEquals("无权操作此商品", error.getMessage());
        verify(pricingBatchMapper, never()).insert(any(PricingBatch.class));
        verify(decisionTaskService, never()).createPricingTask(any(), any(), any(), any());
    }

    @Test
    void createBatchMarksItemCreateFailedWhenTaskCreationThrowsAndNoRecoverableTaskExists() {
        PricingBatchCreateDTO request = new PricingBatchCreateDTO();
        request.setProductIds(List.of(101L));
        request.setStrategyGoal("MAX_PROFIT");
        request.setConstraints("");

        Product product = product(101L, 9L, "A", new BigDecimal("80.00"));

        List<PricingBatchItem> storedItems = new ArrayList<>();
        doAnswer(invocation -> {
            PricingBatch batch = invocation.getArgument(0);
            batch.setId(66L);
            return 1;
        }).when(pricingBatchMapper).insert(any(PricingBatch.class));
        doAnswer(invocation -> {
            PricingBatchItem item = invocation.getArgument(0);
            item.setId(1L);
            storedItems.add(item);
            return 1;
        }).when(pricingBatchItemMapper).insert(any(PricingBatchItem.class));

        when(shopService.getShopIdsByUser(7L)).thenReturn(List.of(9L));
        when(decisionTaskService.createPricingTask(101L, "MAX_PROFIT", "", 7L))
                .thenThrow(new IllegalStateException("dispatch failed"));
        when(productMapper.selectById(101L)).thenReturn(product);
        when(productMapper.selectBatchIds(any())).thenReturn(List.of(product));
        when(pricingTaskReuseSupport.buildIdempotencyKey(List.of(101L), "MAX_PROFIT", "", 7L)).thenReturn("idem-101");
        when(pricingTaskReuseSupport.findRecoverableTaskAfterCreateFailure("idem-101", 9L)).thenReturn(null);
        when(pricingBatchMapper.selectById(66L)).thenReturn(batch(66L, 7L, "RUNNING"));
        when(pricingBatchItemMapper.selectList(any())).thenReturn(storedItems);

        PricingBatchCreateVO response = service.createBatch(request, 7L);

        assertEquals(1, response.getCreateFailedCount());
        assertEquals(List.of(), response.getLinkedTaskIds());
        assertEquals(1, storedItems.size());
        assertEquals("CREATE_FAILED", storedItems.get(0).getItemStatus());
        assertEquals("dispatch failed", storedItems.get(0).getErrorMessage());
        assertNull(storedItems.get(0).getTaskId());

        ArgumentCaptor<PricingBatch> batchCaptor = ArgumentCaptor.forClass(PricingBatch.class);
        verify(pricingBatchMapper).updateById(batchCaptor.capture());
        assertEquals("FAILED", batchCaptor.getValue().getBatchStatus());
        assertEquals(1, batchCaptor.getValue().getFailedCount());
    }

    @Test
    void createBatchLinksRecoverableFailedTaskWhenDispatchAlreadyPersistedTask() {
        PricingBatchCreateDTO request = new PricingBatchCreateDTO();
        request.setProductIds(List.of(101L));
        request.setStrategyGoal("MAX_PROFIT");
        request.setConstraints("");

        Product product = product(101L, 9L, "运动水杯", new BigDecimal("55.00"));
        PricingTask failedTask = task(301L, 9L, 101L, "FAILED", new BigDecimal("55.00"));
        failedTask.setFailureReason("worker queue is full");

        List<PricingBatchItem> storedItems = new ArrayList<>();
        doAnswer(invocation -> {
            PricingBatch batch = invocation.getArgument(0);
            batch.setId(11L);
            return 1;
        }).when(pricingBatchMapper).insert(any(PricingBatch.class));
        AtomicLong itemId = new AtomicLong(1L);
        doAnswer(invocation -> {
            PricingBatchItem item = invocation.getArgument(0);
            item.setId(itemId.getAndIncrement());
            storedItems.add(item);
            return 1;
        }).when(pricingBatchItemMapper).insert(any(PricingBatchItem.class));

        when(shopService.getShopIdsByUser(7L)).thenReturn(List.of(9L));
        when(productMapper.selectById(101L)).thenReturn(product);
        when(productMapper.selectBatchIds(any())).thenReturn(List.of(product));
        when(decisionTaskService.createPricingTask(101L, "MAX_PROFIT", "", 7L))
                .thenThrow(new IllegalStateException("worker queue is full"));
        when(pricingTaskReuseSupport.buildIdempotencyKey(List.of(101L), "MAX_PROFIT", "", 7L)).thenReturn("idem-101");
        when(pricingTaskReuseSupport.findRecoverableTaskAfterCreateFailure("idem-101", 9L)).thenReturn(failedTask);
        when(pricingBatchMapper.selectById(11L)).thenReturn(batch(11L, 7L, "RUNNING"));
        when(pricingBatchItemMapper.selectList(any())).thenReturn(storedItems);
        when(pricingTaskMapper.selectList(any())).thenReturn(List.of(failedTask));
        when(pricingResultMapper.selectList(any())).thenReturn(List.of());

        PricingBatchCreateVO response = service.createBatch(request, 7L);

        assertEquals(11L, response.getBatchId());
        assertEquals(List.of(301L), response.getLinkedTaskIds());
        assertEquals(0, response.getCreateFailedCount());
        assertEquals(1, storedItems.size());
        assertEquals("TASK_LINKED", storedItems.get(0).getItemStatus());
        assertEquals(301L, storedItems.get(0).getTaskId());
        assertNull(storedItems.get(0).getErrorMessage());

        ArgumentCaptor<PricingBatch> batchCaptor = ArgumentCaptor.forClass(PricingBatch.class);
        verify(pricingBatchMapper).updateById(batchCaptor.capture());
        assertEquals("FAILED", batchCaptor.getValue().getBatchStatus());
        assertEquals(1, batchCaptor.getValue().getFailedCount());
    }

    @Test
    void getBatchItemsFiltersByDisplayStatusAndKeepsResultMetadata() {
        PricingBatch batch = batch(22L, 7L, "RUNNING");
        batch.setStrategyGoal("MAX_PROFIT");
        batch.setConstraintText("{\"min_profit_rate\":0.15}");
        batch.setFinalizedAt(LocalDateTime.now().minusMinutes(2));

        PricingBatchItem failedItem = batchItem(1L, 22L, 301L, 1, null, "CREATE_FAILED");
        failedItem.setErrorMessage("商品不存在");
        PricingBatchItem manualReviewItem = batchItem(2L, 22L, 101L, 2, 201L, "TASK_LINKED");
        PricingBatchItem completedItem = batchItem(3L, 22L, 102L, 3, 202L, "TASK_LINKED");
        LocalDateTime itemUpdatedAt = LocalDateTime.now().minusMinutes(4);
        LocalDateTime taskUpdatedAt = LocalDateTime.now().minusMinutes(1);
        manualReviewItem.setUpdatedAt(itemUpdatedAt);

        Product product101 = product(101L, 9L, "夏季T恤", new BigDecimal("80.00"));
        Product product102 = product(102L, 9L, "运动短裤", new BigDecimal("91.00"));
        Product product301 = product(301L, 9L, "缺失商品", new BigDecimal("70.00"));

        PricingTask task201 = task(201L, 9L, 101L, "MANUAL_REVIEW", new BigDecimal("80.00"));
        task201.setUpdatedAt(taskUpdatedAt);
        PricingTask task202 = task(202L, 9L, 102L, "COMPLETED", new BigDecimal("90.00"));

        PricingResult result201 = result(401L, 201L, new BigDecimal("82.00"), 1);
        PricingResult result202 = result(402L, 202L, new BigDecimal("91.00"), 0);

        when(pricingBatchMapper.selectById(22L)).thenReturn(batch);
        when(pricingBatchItemMapper.selectList(any())).thenReturn(List.of(failedItem, manualReviewItem, completedItem));
        when(productMapper.selectBatchIds(any())).thenReturn(List.of(product101, product102, product301));
        when(pricingTaskMapper.selectList(any())).thenReturn(List.of(task201, task202));
        when(pricingResultMapper.selectList(any())).thenReturn(List.of(result202, result201));

        Page<PricingBatchItemVO> manualReviewPage = service.getBatchItems(22L, 1, 10, "MANUAL_REVIEW", 7L);
        PricingBatchItemVO manualReviewRow = manualReviewPage.getRecords().getFirst();
        assertEquals(1, manualReviewPage.getTotal());
        assertEquals(401L, manualReviewRow.getResultId());
        assertEquals("MANUAL_REVIEW", manualReviewRow.getDisplayStatus());
        assertEquals("人工审核", manualReviewRow.getExecuteStrategy());
        assertEquals(Boolean.TRUE, manualReviewRow.getReviewRequired());
        assertEquals("未应用", manualReviewRow.getAppliedStatus());
        assertEquals(itemUpdatedAt, manualReviewRow.getUpdatedAt());
        assertEquals(itemUpdatedAt, manualReviewRow.getBatchItemUpdatedAt());
        assertEquals(taskUpdatedAt, manualReviewRow.getTaskUpdatedAt());
        assertNull(manualReviewRow.getErrorMessage());

        Page<PricingBatchItemVO> failedPage = service.getBatchItems(22L, 1, 10, "CREATE_FAILED", 7L);
        assertEquals(1, failedPage.getTotal());
        assertEquals("CREATE_FAILED", failedPage.getRecords().getFirst().getDisplayStatus());
        assertEquals("商品不存在", failedPage.getRecords().getFirst().getErrorMessage());

        PricingBatchDetailVO detail = service.getBatchDetail(22L, 7L);
        assertEquals("PARTIAL_FAILED", detail.getBatchStatus());
        assertEquals(1, detail.getManualReviewCount());
        assertEquals(1, detail.getCompletedCount());
        assertEquals(1, detail.getFailedCount());
        assertEquals(batch.getFinalizedAt(), detail.getFinalizedAt());
    }

    @Test
    void getRecentBatchesReturnsPagedSummariesForCurrentUser() {
        PricingBatch running = batch(44L, 7L, "RUNNING");
        running.setBatchCode("BATCH-RUNNING");
        running.setStrategyGoal("MAX_PROFIT");
        running.setTotalCount(3);
        running.setCompletedCount(1);

        PricingBatch completed = batch(45L, 7L, "COMPLETED");
        completed.setBatchCode("BATCH-COMPLETED");
        completed.setStrategyGoal("CLEAR_STOCK");
        completed.setTotalCount(2);
        completed.setCompletedCount(2);
        completed.setFinalizedAt(LocalDateTime.now().minusMinutes(1));

        PricingBatchItem runningItem1 = batchItem(1L, 44L, 101L, 1, 501L, "TASK_LINKED");
        PricingBatchItem runningItem2 = batchItem(2L, 44L, 102L, 2, 502L, "TASK_LINKED");
        PricingBatchItem completedItem1 = batchItem(3L, 44L, 103L, 3, 503L, "TASK_LINKED");
        PricingBatchItem completedItem2 = batchItem(4L, 45L, 201L, 1, 601L, "TASK_LINKED");
        PricingBatchItem completedItem3 = batchItem(5L, 45L, 202L, 2, 602L, "TASK_LINKED");

        Product product101 = product(101L, 9L, "A", new BigDecimal("10.00"));
        Product product102 = product(102L, 9L, "B", new BigDecimal("11.00"));
        Product product103 = product(103L, 9L, "C", new BigDecimal("12.00"));
        Product product201 = product(201L, 9L, "D", new BigDecimal("13.00"));
        Product product202 = product(202L, 9L, "E", new BigDecimal("14.00"));

        PricingTask task501 = task(501L, 9L, 101L, "RUNNING", new BigDecimal("10.00"));
        PricingTask task502 = task(502L, 9L, 102L, "QUEUED", new BigDecimal("11.00"));
        PricingTask task503 = task(503L, 9L, 103L, "COMPLETED", new BigDecimal("12.00"));
        PricingTask task601 = task(601L, 9L, 201L, "COMPLETED", new BigDecimal("13.00"));
        PricingTask task602 = task(602L, 9L, 202L, "COMPLETED", new BigDecimal("14.00"));

        when(pricingBatchMapper.selectPage(any(Page.class), any())).thenAnswer(invocation -> {
            Page<PricingBatch> page = invocation.getArgument(0);
            page.setTotal(2);
            page.setRecords(List.of(running, completed));
            return page;
        });
        when(pricingBatchItemMapper.selectList(any()))
                .thenReturn(List.of(runningItem1, runningItem2, completedItem1))
                .thenReturn(List.of(completedItem2, completedItem3));
        when(productMapper.selectBatchIds(any()))
                .thenReturn(List.of(product101, product102, product103))
                .thenReturn(List.of(product201, product202));
        when(pricingTaskMapper.selectList(any()))
                .thenReturn(List.of(task501, task502, task503))
                .thenReturn(List.of(task601, task602));
        when(pricingResultMapper.selectList(any()))
                .thenReturn(List.of())
                .thenReturn(List.of());

        Page<PricingBatchDetailVO> response = service.getRecentBatches(1, 5, null, 7L);

        assertEquals(2, response.getTotal());
        assertEquals(5, response.getSize());
        assertEquals(44L, response.getRecords().getFirst().getBatchId());
        assertEquals("BATCH-RUNNING", response.getRecords().getFirst().getBatchCode());
        assertEquals("RUNNING", response.getRecords().getFirst().getBatchStatus());
        assertEquals(3, response.getRecords().getFirst().getTotalCount());
        assertEquals(2, response.getRecords().getFirst().getRunningCount());
        assertEquals(45L, response.getRecords().get(1).getBatchId());
        assertEquals(completed.getFinalizedAt(), response.getRecords().get(1).getFinalizedAt());
    }

    @Test
    void getRecentBatchesRefreshesSummaryFromLinkedTasks() {
        PricingBatch staleBatch = batch(77L, 7L, "RUNNING");
        staleBatch.setBatchCode("BATCH-STALE");
        staleBatch.setStrategyGoal("MARKET_SHARE");
        staleBatch.setTotalCount(2);
        staleBatch.setCompletedCount(0);
        staleBatch.setManualReviewCount(0);
        staleBatch.setFailedCount(0);
        staleBatch.setCancelledCount(0);

        PricingBatchItem firstItem = batchItem(1L, 77L, 101L, 1, 701L, "TASK_LINKED");
        PricingBatchItem secondItem = batchItem(2L, 77L, 102L, 2, 702L, "TASK_LINKED");
        Product firstProduct = product(101L, 9L, "A", new BigDecimal("10.00"));
        Product secondProduct = product(102L, 9L, "B", new BigDecimal("11.00"));
        PricingTask firstTask = task(701L, 9L, 101L, "MANUAL_REVIEW", new BigDecimal("10.00"));
        PricingTask secondTask = task(702L, 9L, 102L, "MANUAL_REVIEW", new BigDecimal("11.00"));

        when(pricingBatchMapper.selectPage(any(Page.class), any())).thenAnswer(invocation -> {
            Page<PricingBatch> page = invocation.getArgument(0);
            page.setTotal(1);
            page.setRecords(List.of(staleBatch));
            return page;
        });
        when(pricingBatchItemMapper.selectList(any())).thenReturn(List.of(firstItem, secondItem));
        when(productMapper.selectBatchIds(any())).thenReturn(List.of(firstProduct, secondProduct));
        when(pricingTaskMapper.selectList(any())).thenReturn(List.of(firstTask, secondTask));
        when(pricingResultMapper.selectList(any())).thenReturn(List.of());

        Page<PricingBatchDetailVO> response = service.getRecentBatches(1, 5, null, 7L);
        PricingBatchDetailVO row = response.getRecords().getFirst();

        assertEquals("MANUAL_REVIEW", row.getBatchStatus());
        assertEquals(2, row.getTotalCount());
        assertEquals(0, row.getRunningCount());
        assertEquals(2, row.getManualReviewCount());

        ArgumentCaptor<PricingBatch> batchCaptor = ArgumentCaptor.forClass(PricingBatch.class);
        verify(pricingBatchMapper).updateById(batchCaptor.capture());
        assertEquals("MANUAL_REVIEW", batchCaptor.getValue().getBatchStatus());
        assertEquals(2, batchCaptor.getValue().getManualReviewCount());
    }

    @Test
    void cancelBatchCancelsOnlyRunningLikeItems() {
        PricingBatch batch = batch(33L, 7L, "RUNNING");
        PricingBatchItem runningItem = batchItem(1L, 33L, 101L, 1, 501L, "TASK_LINKED");
        PricingBatchItem queuedItem = batchItem(2L, 33L, 102L, 2, 502L, "TASK_LINKED");
        PricingBatchItem manualReviewItem = batchItem(3L, 33L, 103L, 3, 503L, "TASK_LINKED");
        PricingBatchItem failedCreateItem = batchItem(4L, 33L, 104L, 4, null, "CREATE_FAILED");

        Product product101 = product(101L, 9L, "A", new BigDecimal("10.00"));
        Product product102 = product(102L, 9L, "B", new BigDecimal("11.00"));
        Product product103 = product(103L, 9L, "C", new BigDecimal("12.00"));
        Product product104 = product(104L, 9L, "D", new BigDecimal("13.00"));

        PricingTask runningTask = task(501L, 9L, 101L, "RUNNING", new BigDecimal("10.00"));
        PricingTask queuedTask = task(502L, 9L, 102L, "QUEUED", new BigDecimal("11.00"));
        PricingTask manualReviewTask = task(503L, 9L, 103L, "MANUAL_REVIEW", new BigDecimal("12.00"));
        PricingTask refreshedRunningTask = task(501L, 9L, 101L, "CANCELLED", new BigDecimal("10.00"));
        PricingTask refreshedQueuedTask = task(502L, 9L, 102L, "CANCELLED", new BigDecimal("11.00"));
        PricingTask refreshedManualReviewTask = task(503L, 9L, 103L, "MANUAL_REVIEW", new BigDecimal("12.00"));

        when(pricingBatchMapper.selectById(33L)).thenReturn(batch);
        when(pricingBatchItemMapper.selectList(any())).thenReturn(List.of(runningItem, queuedItem, manualReviewItem, failedCreateItem));
        when(productMapper.selectBatchIds(any())).thenReturn(List.of(product101, product102, product103, product104));
        when(pricingTaskMapper.selectList(any()))
                .thenReturn(List.of(runningTask, queuedTask, manualReviewTask))
                .thenReturn(List.of(refreshedRunningTask, refreshedQueuedTask, refreshedManualReviewTask));
        when(pricingResultMapper.selectList(any())).thenReturn(List.of());

        PricingBatchCancelVO response = service.cancelBatch(33L, 7L);

        assertEquals(2, response.getCancelledCount());
        assertEquals(2, response.getSkippedCount());
        assertEquals("RUNNING", runningTask.getTaskStatus());
        assertEquals("QUEUED", queuedTask.getTaskStatus());
        verify(decisionTaskService).cancelTask(501L, 7L);
        verify(decisionTaskService).cancelTask(502L, 7L);
        verify(decisionTaskService, never()).cancelTask(503L, 7L);

        ArgumentCaptor<PricingBatch> batchCaptor = ArgumentCaptor.forClass(PricingBatch.class);
        verify(pricingBatchMapper).updateById(batchCaptor.capture());
        assertEquals("PARTIAL_FAILED", batchCaptor.getValue().getBatchStatus());
        assertEquals(2, batchCaptor.getValue().getCancelledCount());
    }

    private PricingBatch batch(Long batchId, Long userId, String status) {
        PricingBatch batch = new PricingBatch();
        batch.setId(batchId);
        batch.setRequestedByUserId(userId);
        batch.setBatchCode("BATCH-TEST");
        batch.setBatchStatus(status);
        batch.setCreatedAt(LocalDateTime.now().minusMinutes(5));
        batch.setUpdatedAt(LocalDateTime.now().minusMinutes(1));
        return batch;
    }

    private PricingBatchItem batchItem(Long id, Long batchId, Long productId, int order, Long taskId, String status) {
        PricingBatchItem item = new PricingBatchItem();
        item.setId(id);
        item.setBatchId(batchId);
        item.setProductId(productId);
        item.setItemOrder(order);
        item.setTaskId(taskId);
        item.setItemStatus(status);
        item.setCreatedAt(LocalDateTime.now().minusMinutes(5));
        item.setUpdatedAt(LocalDateTime.now().minusMinutes(1));
        return item;
    }

    private Product product(Long id, Long shopId, String title, BigDecimal currentPrice) {
        Product product = new Product();
        product.setId(id);
        product.setShopId(shopId);
        product.setTitle(title);
        product.setCurrentPrice(currentPrice);
        return product;
    }

    private PricingTask task(Long id, Long shopId, Long productId, String status, BigDecimal currentPrice) {
        PricingTask task = new PricingTask();
        task.setId(id);
        task.setShopId(shopId);
        task.setProductId(productId);
        task.setTaskStatus(status);
        task.setCurrentPrice(currentPrice);
        task.setUpdatedAt(LocalDateTime.now());
        return task;
    }

    private PricingResult result(Long id, Long taskId, BigDecimal finalPrice, int reviewRequired) {
        PricingResult result = new PricingResult();
        result.setId(id);
        result.setTaskId(taskId);
        result.setFinalPrice(finalPrice);
        result.setExpectedSales(120);
        result.setExpectedProfit(new BigDecimal("456.78"));
        result.setProfitGrowth(new BigDecimal("87.65"));
        result.setReviewRequired(reviewRequired);
        result.setExecuteStrategy("人工审核");
        return result;
    }
}
