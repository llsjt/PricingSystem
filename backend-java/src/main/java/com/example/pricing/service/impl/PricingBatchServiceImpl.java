/*
 * 批量定价服务实现，负责批次创建、批次进度统计和批次取消。
 */

package com.example.pricing.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
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
import com.example.pricing.service.DecisionTaskService;
import com.example.pricing.service.PricingBatchService;
import com.example.pricing.service.PricingTaskReuseSupport;
import com.example.pricing.service.ShopService;
import com.example.pricing.vo.PricingBatchCancelVO;
import com.example.pricing.vo.PricingBatchCreateVO;
import com.example.pricing.vo.PricingBatchDetailVO;
import com.example.pricing.vo.PricingBatchItemVO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.math.RoundingMode;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Slf4j
public class PricingBatchServiceImpl implements PricingBatchService {

    private static final String MANUAL_REVIEW_STRATEGY = "人工审核";
    private static final List<String> RUNNING_TASK_STATUSES = List.of("PENDING", "QUEUED", "RUNNING", "RETRYING");
    private static final List<String> CANCELLABLE_TASK_STATUSES = List.of("PENDING", "QUEUED", "RUNNING", "RETRYING");

    private final PricingBatchMapper pricingBatchMapper;
    private final PricingBatchItemMapper pricingBatchItemMapper;
    private final ProductMapper productMapper;
    private final PricingTaskMapper pricingTaskMapper;
    private final PricingResultMapper pricingResultMapper;
    private final DecisionTaskService decisionTaskService;
    private final PricingTaskReuseSupport pricingTaskReuseSupport;
    private final ShopService shopService;

    @Override
    public PricingBatchCreateVO createBatch(PricingBatchCreateDTO request, Long userId) {
        // 这里故意不包整批事务：单个商品创建失败时，也要保留其他商品的建链结果和失败原因。
        List<Long> productIds = normalizeProductIds(request == null ? null : request.getProductIds());
        String strategyGoal = normalizeRequiredStrategyGoal(request == null ? null : request.getStrategyGoal());
        String constraints = normalizeConstraints(request == null ? null : request.getConstraints());
        validateBatchProducts(productIds, userId);

        PricingBatch batch = new PricingBatch();
        batch.setBatchCode(generateBatchCode());
        batch.setRequestedByUserId(userId);
        batch.setStrategyGoal(strategyGoal);
        batch.setConstraintText(constraints);
        batch.setTotalCount(productIds.size());
        batch.setCompletedCount(0);
        batch.setManualReviewCount(0);
        batch.setFailedCount(0);
        batch.setCancelledCount(0);
        batch.setBatchStatus("RUNNING");
        pricingBatchMapper.insert(batch);

        List<Long> linkedTaskIds = new ArrayList<>();
        int createFailedCount = 0;
        int itemOrder = 1;
        // 逐商品建立批次子项，保证每个商品都能记录到“成功建链”或“建链失败”的最终状态。
        for (Long productId : productIds) {
            PricingBatchItem item = new PricingBatchItem();
            item.setBatchId(batch.getId());
            item.setProductId(productId);
            item.setItemOrder(itemOrder++);
            item.setItemStatus("TASK_LINKED");
            try {
                Long taskId = decisionTaskService.createPricingTask(productId, strategyGoal, constraints, userId);
                item.setTaskId(taskId);
                linkedTaskIds.add(taskId);
            } catch (Exception e) {
                PricingTask recoveredTask = recoverTaskAfterCreateFailure(productId, strategyGoal, constraints, userId);
                if (recoveredTask != null) {
                    item.setTaskId(recoveredTask.getId());
                    linkedTaskIds.add(recoveredTask.getId());
                } else {
                    item.setTaskId(null);
                    item.setItemStatus("CREATE_FAILED");
                    item.setErrorMessage(truncate(e.getMessage(), 255));
                    createFailedCount++;
                }
                log.warn("create pricing batch item failed, batchId={}, productId={}, message={}",
                        batch.getId(), productId, e.getMessage());
            }
            pricingBatchItemMapper.insert(item);
        }

        BatchContext context = loadBatchContext(batch.getId(), userId);
        BatchAggregate aggregate = aggregate(context);
        syncBatchSummary(context.batch(), aggregate);

        PricingBatchCreateVO vo = new PricingBatchCreateVO();
        vo.setBatchId(batch.getId());
        vo.setBatchCode(batch.getBatchCode());
        vo.setTotalCount(productIds.size());
        vo.setLinkedTaskIds(linkedTaskIds);
        vo.setCreateFailedCount(createFailedCount);
        return vo;
    }

    @Override
    public Page<PricingBatchDetailVO> getRecentBatches(int page, int size, String status, Long userId) {
        int normalizedPage = Math.max(page, 1);
        int normalizedSize = size <= 0 ? 5 : Math.min(size, 20);
        String normalizedStatus = normalizeStatus(status);

        LambdaQueryWrapper<PricingBatch> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(PricingBatch::getRequestedByUserId, userId);
        if (!normalizedStatus.isBlank()) {
            wrapper.eq(PricingBatch::getBatchStatus, normalizedStatus);
        }
        wrapper.orderByDesc(PricingBatch::getCreatedAt, PricingBatch::getId);

        Page<PricingBatch> batchPage = pricingBatchMapper.selectPage(new Page<>(normalizedPage, normalizedSize), wrapper);
        Page<PricingBatchDetailVO> result = new Page<>(batchPage.getCurrent(), batchPage.getSize(), batchPage.getTotal());
        result.setRecords(batchPage.getRecords().stream()
                .map(batch -> toLiveBatchSummaryVO(batch, userId))
                .toList());
        return result;
    }

    @Override
    public PricingBatchDetailVO getBatchDetail(Long batchId, Long userId) {
        BatchContext context = loadBatchContext(batchId, userId);
        BatchAggregate aggregate = aggregate(context);
        syncBatchSummary(context.batch(), aggregate);

        PricingBatchDetailVO vo = new PricingBatchDetailVO();
        vo.setBatchId(context.batch().getId());
        vo.setBatchCode(context.batch().getBatchCode());
        vo.setBatchStatus(context.batch().getBatchStatus());
        vo.setStrategyGoal(context.batch().getStrategyGoal());
        vo.setConstraintText(context.batch().getConstraintText());
        vo.setTotalCount(aggregate.totalCount());
        vo.setRunningCount(aggregate.runningCount());
        vo.setCompletedCount(aggregate.completedCount());
        vo.setManualReviewCount(aggregate.manualReviewCount());
        vo.setFailedCount(aggregate.failedCount());
        vo.setCancelledCount(aggregate.cancelledCount());
        vo.setFinalizedAt(context.batch().getFinalizedAt());
        vo.setCreatedAt(context.batch().getCreatedAt());
        vo.setUpdatedAt(context.batch().getUpdatedAt());
        return vo;
    }

    private PricingBatchDetailVO toLiveBatchSummaryVO(PricingBatch batch, Long userId) {
        BatchContext context = loadBatchContext(batch, userId);
        BatchAggregate aggregate = aggregate(context);
        syncBatchSummary(context.batch(), aggregate);
        return toBatchSummaryVO(context.batch());
    }

    private PricingBatchDetailVO toBatchSummaryVO(PricingBatch batch) {
        int totalCount = valueOrZero(batch.getTotalCount());
        int completedCount = valueOrZero(batch.getCompletedCount());
        int manualReviewCount = valueOrZero(batch.getManualReviewCount());
        int failedCount = valueOrZero(batch.getFailedCount());
        int cancelledCount = valueOrZero(batch.getCancelledCount());
        int runningCount = Math.max(totalCount - completedCount - manualReviewCount - failedCount - cancelledCount, 0);

        PricingBatchDetailVO vo = new PricingBatchDetailVO();
        vo.setBatchId(batch.getId());
        vo.setBatchCode(batch.getBatchCode());
        vo.setBatchStatus(batch.getBatchStatus());
        vo.setStrategyGoal(batch.getStrategyGoal());
        vo.setConstraintText(batch.getConstraintText());
        vo.setTotalCount(totalCount);
        vo.setRunningCount(runningCount);
        vo.setCompletedCount(completedCount);
        vo.setManualReviewCount(manualReviewCount);
        vo.setFailedCount(failedCount);
        vo.setCancelledCount(cancelledCount);
        vo.setFinalizedAt(batch.getFinalizedAt());
        vo.setCreatedAt(batch.getCreatedAt());
        vo.setUpdatedAt(batch.getUpdatedAt());
        return vo;
    }

    @Override
    public Page<PricingBatchItemVO> getBatchItems(Long batchId, int page, int size, String status, Long userId) {
        BatchContext context = loadBatchContext(batchId, userId);
        BatchAggregate aggregate = aggregate(context);
        syncBatchSummary(context.batch(), aggregate);

        List<PricingBatchItemVO> rows = buildItemRows(context);
        String normalizedStatus = normalizeStatus(status);
        if (!normalizedStatus.isBlank()) {
            rows = rows.stream()
                    .filter(row -> normalizedStatus.equals(normalizeStatus(row.getDisplayStatus())))
                    .toList();
        }

        int normalizedPage = Math.max(page, 1);
        int normalizedSize = size <= 0 ? 10 : size;
        int fromIndex = Math.min((normalizedPage - 1) * normalizedSize, rows.size());
        int toIndex = Math.min(fromIndex + normalizedSize, rows.size());

        Page<PricingBatchItemVO> result = new Page<>(normalizedPage, normalizedSize);
        result.setTotal(rows.size());
        result.setRecords(rows.subList(fromIndex, toIndex));
        return result;
    }

    @Override
    public PricingBatchCancelVO cancelBatch(Long batchId, Long userId) {
        BatchContext context = loadBatchContext(batchId, userId);
        int cancelledCount = 0;
        int skippedCount = 0;

        for (PricingBatchItem item : context.items()) {
            if (!"TASK_LINKED".equals(normalizeStatus(item.getItemStatus())) || item.getTaskId() == null) {
                skippedCount++;
                continue;
            }
            PricingTask task = context.tasks().get(item.getTaskId());
            if (task == null || !CANCELLABLE_TASK_STATUSES.contains(normalizeStatus(task.getTaskStatus()))) {
                skippedCount++;
                continue;
            }
            try {
                decisionTaskService.cancelTask(task.getId(), userId);
                cancelledCount++;
            } catch (IllegalStateException e) {
                skippedCount++;
                log.info("cancel batch task skipped, batchId={}, taskId={}, message={}",
                        batchId, task.getId(), e.getMessage());
            } catch (Exception e) {
                skippedCount++;
                log.warn("cancel batch task failed, batchId={}, taskId={}, message={}",
                        batchId, task.getId(), e.getMessage());
            }
        }

        BatchContext refreshedContext = loadBatchContext(batchId, userId);
        BatchAggregate aggregate = aggregate(refreshedContext);
        syncBatchSummary(refreshedContext.batch(), aggregate);

        PricingBatchCancelVO vo = new PricingBatchCancelVO();
        vo.setCancelledCount(cancelledCount);
        vo.setSkippedCount(skippedCount);
        return vo;
    }

    private PricingTask recoverTaskAfterCreateFailure(Long productId, String strategyGoal, String constraints, Long userId) {
        Product product = productMapper.selectById(productId);
        if (product == null || product.getShopId() == null) {
            return null;
        }
        String idempotencyKey = pricingTaskReuseSupport.buildIdempotencyKey(List.of(productId), strategyGoal, constraints, userId);
        return pricingTaskReuseSupport.findRecoverableTaskAfterCreateFailure(idempotencyKey, product.getShopId());
    }

    private void validateBatchProducts(List<Long> productIds, Long userId) {
        List<Long> shopIds = shopService.getShopIdsByUser(userId);
        if (shopIds == null || shopIds.isEmpty()) {
            throw new IllegalStateException("您还没有店铺，请先创建店铺");
        }
        List<Product> products = productMapper.selectBatchIds(productIds);
        if (products.size() != productIds.size()) {
            throw new IllegalArgumentException("商品不存在");
        }
        boolean hasForbiddenProduct = products.stream()
                .anyMatch(product -> product == null || product.getShopId() == null || !shopIds.contains(product.getShopId()));
        if (hasForbiddenProduct) {
            throw new IllegalArgumentException("无权操作此商品");
        }
    }

    private BatchContext loadBatchContext(Long batchId, Long userId) {
        PricingBatch batch = pricingBatchMapper.selectById(batchId);
        if (batch == null) {
            throw new IllegalArgumentException("批次不存在");
        }
        return loadBatchContext(batch, userId);
    }

    private BatchContext loadBatchContext(PricingBatch batch, Long userId) {
        verifyBatchOwnership(batch, userId);

        LambdaQueryWrapper<PricingBatchItem> itemWrapper = new LambdaQueryWrapper<>();
        itemWrapper.eq(PricingBatchItem::getBatchId, batch.getId())
                .orderByAsc(PricingBatchItem::getItemOrder, PricingBatchItem::getId);
        List<PricingBatchItem> items = pricingBatchItemMapper.selectList(itemWrapper);

        Map<Long, Product> productMap = toProductMap(items.stream()
                .map(PricingBatchItem::getProductId)
                .filter(Objects::nonNull)
                .toList());
        Map<Long, PricingTask> taskMap = toTaskMap(items.stream()
                .map(PricingBatchItem::getTaskId)
                .filter(Objects::nonNull)
                .toList());
        Map<Long, PricingResult> resultMap = toResultMap(taskMap.keySet());

        return new BatchContext(batch, items, productMap, taskMap, resultMap);
    }

    private Map<Long, Product> toProductMap(Collection<Long> productIds) {
        if (productIds == null || productIds.isEmpty()) {
            return Map.of();
        }
        List<Product> products = productMapper.selectBatchIds(new ArrayList<>(new LinkedHashSet<>(productIds)));
        Map<Long, Product> productMap = new LinkedHashMap<>();
        for (Product product : products) {
            productMap.put(product.getId(), product);
        }
        return productMap;
    }

    private Map<Long, PricingTask> toTaskMap(Collection<Long> taskIds) {
        if (taskIds == null || taskIds.isEmpty()) {
            return Map.of();
        }
        LambdaQueryWrapper<PricingTask> wrapper = new LambdaQueryWrapper<>();
        wrapper.in(PricingTask::getId, new ArrayList<>(new LinkedHashSet<>(taskIds)));
        List<PricingTask> tasks = pricingTaskMapper.selectList(wrapper);
        Map<Long, PricingTask> taskMap = new LinkedHashMap<>();
        for (PricingTask task : tasks) {
            taskMap.put(task.getId(), task);
        }
        return taskMap;
    }

    private Map<Long, PricingResult> toResultMap(Collection<Long> taskIds) {
        if (taskIds == null || taskIds.isEmpty()) {
            return Map.of();
        }
        LambdaQueryWrapper<PricingResult> wrapper = new LambdaQueryWrapper<>();
        wrapper.in(PricingResult::getTaskId, new ArrayList<>(new LinkedHashSet<>(taskIds)))
                .orderByDesc(PricingResult::getId);
        List<PricingResult> results = pricingResultMapper.selectList(wrapper);
        Map<Long, PricingResult> resultMap = new LinkedHashMap<>();
        for (PricingResult result : results) {
            resultMap.putIfAbsent(result.getTaskId(), result);
        }
        return resultMap;
    }

    private List<PricingBatchItemVO> buildItemRows(BatchContext context) {
        List<PricingBatchItemVO> rows = new ArrayList<>();
        for (PricingBatchItem item : context.items()) {
            Product product = context.products().get(item.getProductId());
            PricingTask task = item.getTaskId() == null ? null : context.tasks().get(item.getTaskId());
            PricingResult result = task == null ? null : context.results().get(task.getId());

            PricingBatchItemVO vo = new PricingBatchItemVO();
            vo.setId(item.getId());
            vo.setBatchId(item.getBatchId());
            vo.setItemOrder(item.getItemOrder());
            vo.setProductId(item.getProductId());
            vo.setTaskId(item.getTaskId());
            vo.setResultId(result == null ? null : result.getId());
            vo.setProductTitle(product == null ? "-" : product.getTitle());
            vo.setCurrentPrice(task != null ? task.getCurrentPrice() : (product == null ? null : product.getCurrentPrice()));
            vo.setFinalPrice(result == null ? null : result.getFinalPrice());
            vo.setExpectedSales(result == null ? null : result.getExpectedSales());
            vo.setExpectedProfit(result == null ? null : result.getExpectedProfit());
            vo.setProfitGrowth(result == null ? null : result.getProfitGrowth());
            vo.setCreationStatus(resolveCreationStatus(item));
            vo.setTaskStatus(task == null ? null : normalizeStatus(task.getTaskStatus()));
            vo.setDisplayStatus(resolveDisplayStatus(item, task));
            vo.setExecuteStrategy(result == null ? null : resolveExecuteStrategy(result));
            vo.setReviewRequired(result != null && Integer.valueOf(1).equals(result.getReviewRequired()));
            vo.setAppliedStatus(result == null ? null : (isApplied(product, result) ? "已应用" : "未应用"));
            vo.setErrorMessage(resolveErrorMessage(item, task));
            vo.setCreatedAt(item.getCreatedAt());
            vo.setBatchItemUpdatedAt(item.getUpdatedAt());
            vo.setTaskUpdatedAt(task == null ? null : task.getUpdatedAt());
            vo.setUpdatedAt(item.getUpdatedAt());
            rows.add(vo);
        }
        return rows;
    }

    private BatchAggregate aggregate(BatchContext context) {
        int totalCount = context.items().size();
        int runningCount = 0;
        int completedCount = 0;
        int manualReviewCount = 0;
        int failedCount = 0;
        int cancelledCount = 0;

        for (PricingBatchItem item : context.items()) {
            String creationStatus = resolveCreationStatus(item);
            if ("CREATE_FAILED".equals(creationStatus)) {
                failedCount++;
                continue;
            }
            PricingTask task = item.getTaskId() == null ? null : context.tasks().get(item.getTaskId());
            String taskStatus = task == null ? "FAILED" : normalizeStatus(task.getTaskStatus());
            if (RUNNING_TASK_STATUSES.contains(taskStatus)) {
                runningCount++;
                continue;
            }
            switch (taskStatus) {
                case "COMPLETED" -> completedCount++;
                case "MANUAL_REVIEW" -> manualReviewCount++;
                case "CANCELLED" -> cancelledCount++;
                case "FAILED" -> failedCount++;
                default -> failedCount++;
            }
        }

        return new BatchAggregate(
                totalCount,
                runningCount,
                completedCount,
                manualReviewCount,
                failedCount,
                cancelledCount,
                deriveBatchStatus(totalCount, runningCount, manualReviewCount, failedCount, cancelledCount),
                runningCount == 0
        );
    }

    private void syncBatchSummary(PricingBatch batch, BatchAggregate aggregate) {
        boolean changed = !Objects.equals(batch.getTotalCount(), aggregate.totalCount())
                || !Objects.equals(batch.getCompletedCount(), aggregate.completedCount())
                || !Objects.equals(batch.getManualReviewCount(), aggregate.manualReviewCount())
                || !Objects.equals(batch.getFailedCount(), aggregate.failedCount())
                || !Objects.equals(batch.getCancelledCount(), aggregate.cancelledCount())
                || !Objects.equals(normalizeStatus(batch.getBatchStatus()), aggregate.batchStatus())
                || (aggregate.finalized() && batch.getFinalizedAt() == null);

        batch.setTotalCount(aggregate.totalCount());
        batch.setCompletedCount(aggregate.completedCount());
        batch.setManualReviewCount(aggregate.manualReviewCount());
        batch.setFailedCount(aggregate.failedCount());
        batch.setCancelledCount(aggregate.cancelledCount());
        batch.setBatchStatus(aggregate.batchStatus());

        if (changed) {
            LocalDateTime now = LocalDateTime.now();
            if (aggregate.finalized() && batch.getFinalizedAt() == null) {
                batch.setFinalizedAt(now);
            }
            batch.setUpdatedAt(now);
            pricingBatchMapper.updateById(batch);
        }
    }

    private void verifyBatchOwnership(PricingBatch batch, Long userId) {
        if (batch.getRequestedByUserId() == null || !batch.getRequestedByUserId().equals(userId)) {
            throw new IllegalArgumentException("无权访问该批次");
        }
    }

    private List<Long> normalizeProductIds(List<Long> productIds) {
        if (productIds == null || productIds.isEmpty()) {
            throw new IllegalArgumentException("至少选择一个商品");
        }
        List<Long> normalized = productIds.stream()
                .filter(Objects::nonNull)
                .distinct()
                .toList();
        if (normalized.isEmpty()) {
            throw new IllegalArgumentException("至少选择一个商品");
        }
        if (normalized.size() > 50) {
            throw new IllegalArgumentException("单批最多支持 50 个商品");
        }
        return normalized;
    }

    private String normalizeRequiredStrategyGoal(String strategyGoal) {
        if (strategyGoal == null || strategyGoal.isBlank()) {
            throw new IllegalArgumentException("策略目标不能为空");
        }
        return strategyGoal.trim();
    }

    private String normalizeConstraints(String constraints) {
        return constraints == null ? "" : constraints.trim();
    }

    private String resolveCreationStatus(PricingBatchItem item) {
        String status = normalizeStatus(item.getItemStatus());
        return status.isBlank() ? "TASK_LINKED" : status;
    }

    private String resolveDisplayStatus(PricingBatchItem item, PricingTask task) {
        if ("CREATE_FAILED".equals(resolveCreationStatus(item))) {
            return "CREATE_FAILED";
        }
        return task == null ? "FAILED" : normalizeStatus(task.getTaskStatus());
    }

    private String resolveErrorMessage(PricingBatchItem item, PricingTask task) {
        if ("CREATE_FAILED".equals(resolveCreationStatus(item))) {
            return item.getErrorMessage();
        }
        return task == null ? null : task.getFailureReason();
    }

    private boolean isApplied(Product product, PricingResult result) {
        if (product == null || result == null || product.getCurrentPrice() == null || result.getFinalPrice() == null) {
            return false;
        }
        return product.getCurrentPrice().setScale(2, RoundingMode.HALF_UP)
                .compareTo(result.getFinalPrice().setScale(2, RoundingMode.HALF_UP)) == 0;
    }

    private String resolveExecuteStrategy(PricingResult result) {
        if (result == null || result.getExecuteStrategy() == null || result.getExecuteStrategy().isBlank()) {
            return MANUAL_REVIEW_STRATEGY;
        }
        return result.getExecuteStrategy();
    }

    private String deriveBatchStatus(int totalCount, int runningCount, int manualReviewCount, int failedCount, int cancelledCount) {
        if (runningCount > 0) {
            return "RUNNING";
        }
        if (totalCount > 0 && totalCount == cancelledCount) {
            return "CANCELLED";
        }
        if (totalCount > 0 && totalCount == failedCount) {
            return "FAILED";
        }
        if (failedCount + cancelledCount > 0) {
            return "PARTIAL_FAILED";
        }
        if (manualReviewCount > 0) {
            return "MANUAL_REVIEW";
        }
        return "COMPLETED";
    }

    private String normalizeStatus(String status) {
        return status == null ? "" : status.trim().toUpperCase();
    }

    private int valueOrZero(Integer value) {
        return value == null ? 0 : value;
    }

    private String truncate(String value, int maxLength) {
        if (value == null) {
            return null;
        }
        return value.length() <= maxLength ? value : value.substring(0, maxLength);
    }

    private String generateBatchCode() {
        return "BATCH-"
                + LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMddHHmmss"))
                + "-"
                + UUID.randomUUID().toString().replace("-", "").substring(0, 12).toUpperCase();
    }

    private record BatchContext(
            PricingBatch batch,
            List<PricingBatchItem> items,
            Map<Long, Product> products,
            Map<Long, PricingTask> tasks,
            Map<Long, PricingResult> results
    ) {
    }

    private record BatchAggregate(
            int totalCount,
            int runningCount,
            int completedCount,
            int manualReviewCount,
            int failedCount,
            int cancelledCount,
            String batchStatus,
            boolean finalized
    ) {
    }
}
