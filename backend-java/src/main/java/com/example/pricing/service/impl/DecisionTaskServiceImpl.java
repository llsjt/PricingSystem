package com.example.pricing.service.impl;

import com.alibaba.excel.EasyExcel;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.dto.TaskDispatchEvent;
import com.example.pricing.entity.AgentRunLog;
import com.example.pricing.entity.PricingResult;
import com.example.pricing.entity.PricingTask;
import com.example.pricing.entity.Product;
import com.example.pricing.entity.UserLlmConfig;
import com.example.pricing.mapper.AgentRunLogMapper;
import com.example.pricing.mapper.PricingResultMapper;
import com.example.pricing.mapper.PricingTaskMapper;
import com.example.pricing.mapper.ProductMapper;
import com.example.pricing.mapper.UserLlmConfigMapper;
import com.example.pricing.service.DecisionTaskService;
import com.example.pricing.service.PricingTaskReuseSupport;
import com.example.pricing.service.ShopService;
import com.example.pricing.service.TaskDispatchPublisher;
import com.example.pricing.vo.DecisionComparisonVO;
import com.example.pricing.vo.DecisionLogVO;
import com.example.pricing.vo.DecisionTaskItemVO;
import com.example.pricing.vo.PricingTaskDetailVO;
import com.example.pricing.vo.PricingTaskSnapshotVO;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionTemplate;

import java.io.IOException;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.net.URLEncoder;
import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * 定价决策任务服务实现，负责任务创建、下发 Python 协作端、结果聚合和报告导出。
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class DecisionTaskServiceImpl implements DecisionTaskService {

    private static final String MANUAL_REVIEW_STRATEGY = "人工审核";

    private final PricingTaskMapper taskMapper;
    private final PricingResultMapper resultMapper;
    private final AgentRunLogMapper logMapper;
    private final ProductMapper productMapper;
    private final ShopService shopService;
    private final TaskDispatchPublisher taskDispatchPublisher;
    private final UserLlmConfigMapper userLlmConfigMapper;
    private final PricingTaskReuseSupport pricingTaskReuseSupport;
    private final TransactionTemplate transactionTemplate;

    @Value("${app.pricing.max-adjustment-ratio:0.30}")
    private BigDecimal maxAdjustmentRatio;

    @Value("${app.pricing.min-margin-rate:0.05}")
    private BigDecimal minMarginRate;

    private final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * 基于单个商品创建任务，本质上是对多商品启动逻辑的单商品封装。
     */
    @Override
    public Long createPricingTask(Long productId, String strategyGoal, String constraints, Long userId) {
        if (productId == null) {
            throw new IllegalArgumentException("productId不能为空");
        }
        String goal = (strategyGoal == null || strategyGoal.isBlank()) ? "MAX_PROFIT" : strategyGoal.trim();
        String constraintText = constraints == null ? "" : constraints.trim();
        return startTask(List.of(productId), goal, constraintText, userId);
    }

    /**
     * 创建任务主记录并通知 Python 协作端开始执行决策分析。
     */
    @Override
    public Long startTask(List<Long> productIds, String strategyGoal, String constraints, Long userId) {
        if (productIds == null || productIds.isEmpty()) {
            throw new IllegalArgumentException("至少选择一个商品");
        }

        List<Long> userShopIds = getUserShopIds(userId);
        Long productId = productIds.get(0);
        Product product = productMapper.selectById(productId);
        if (product == null) {
            throw new IllegalArgumentException("商品不存在");
        }
        if (!userShopIds.contains(product.getShopId())) {
            throw new IllegalArgumentException("无权操作此商品");
        }

        // 查询用户 LLM 配置
        LambdaQueryWrapper<UserLlmConfig> llmWrapper = new LambdaQueryWrapper<>();
        llmWrapper.eq(UserLlmConfig::getUserId, userId);
        UserLlmConfig llmConfig = userLlmConfigMapper.selectOne(llmWrapper);
        if (llmConfig == null) {
            throw new IllegalStateException("请先在个人中心配置大模型 API 密钥");
        }
        String normalizedGoal = (strategyGoal == null || strategyGoal.isBlank()) ? "MAX_PROFIT" : strategyGoal.trim();
        String normalizedConstraints = constraints == null ? "" : constraints.trim();
        String idempotencyKey = pricingTaskReuseSupport.buildIdempotencyKey(productIds, normalizedGoal, normalizedConstraints, userId);

        PricingTask existingTask = pricingTaskReuseSupport.findReusableTask(idempotencyKey, product.getShopId());
        if (existingTask != null) {
            return existingTask.getId();
        }

        PricingTask task = new PricingTask();
        task.setTaskCode("TASK-" + UUID.randomUUID().toString().replace("-", "").substring(0, 12).toUpperCase());
        task.setShopId(product.getShopId());
        task.setProductId(product.getId());
        task.setCurrentPrice(scaleMoney(product.getCurrentPrice()));
        task.setBaselineProfit(BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP));
        task.setStrategyGoal(normalizedGoal);
        task.setConstraintText(normalizedConstraints);
        task.setTaskStatus("PENDING");
        task.setRequestedByUserId(userId);
        task.setTraceId(UUID.randomUUID().toString().replace("-", ""));
        task.setIdempotencyKey(idempotencyKey);
        task.setRetryCount(0);
        task.setConsumerRetryCount(0);
        task.setCurrentExecutionId(null);
        task.setFailureReason(null);
        task.setLlmApiKeyEnc(llmConfig.getLlmApiKeyEnc());
        task.setLlmBaseUrl(llmConfig.getLlmBaseUrl());
        task.setLlmModel(llmConfig.getLlmModel());

        Long taskId = transactionTemplate.execute(status -> {
            taskMapper.insert(task);
            return task.getId();
        });
        if (taskId == null) {
            throw new IllegalStateException("任务创建失败");
        }

        TaskDispatchEvent event = new TaskDispatchEvent(
                UUID.randomUUID().toString(),
                taskId,
                task.getTraceId(),
                Instant.now()
        );
        try {
            taskDispatchPublisher.publishAndConfirm(event);
        } catch (RuntimeException e) {
            log.error("Publish decision task dispatch failed, taskId={}", taskId, e);
            transactionTemplate.executeWithoutResult(status ->
                    taskMapper.updateStatusAndReason(taskId, "FAILED", truncate("派发失败: " + e.getMessage(), 255))
            );
            throw new IllegalStateException("任务派发失败: " + e.getMessage(), e);
        }

        transactionTemplate.executeWithoutResult(status -> taskMapper.updateStatusIfPending(taskId, "QUEUED"));
        return taskId;
    }

    /**
     * 获取任务结果列表，供结果页展示。
     */
    @Override
    public List<DecisionComparisonVO> getTaskResult(Long taskId, Long userId) {
        verifyTaskOwnership(taskId, userId);
        return buildComparisonRows(taskId);
    }

    /**
     * 组装任务日志，补齐前端展示所需的兼容字段。
     */
    @Override
    public List<DecisionLogVO> getTaskLogs(Long taskId, Long userId) {
        verifyTaskOwnership(taskId, userId);
        LambdaQueryWrapper<AgentRunLog> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentRunLog::getTaskId, taskId)
                .orderByAsc(AgentRunLog::getDisplayOrder, AgentRunLog::getSpeakOrder, AgentRunLog::getId);
        return logMapper.selectList(wrapper).stream().map(logItem -> {
            DecisionLogVO vo = new DecisionLogVO();
            Integer displayOrder = logItem.getDisplayOrder() == null ? logItem.getSpeakOrder() : logItem.getDisplayOrder();
            String thinking = logItem.getThinkingSummary();
            if (thinking == null || thinking.isBlank()) {
                thinking = logItem.getThoughtContent();
            }

            List<Map<String, Object>> evidence = parseJsonArray(logItem.getEvidenceJson());
            Map<String, Object> suggestion = parseJsonObject(logItem.getSuggestionJson());
            normalizeSuggestionStrategy(suggestion);
            String action = String.valueOf(suggestion.getOrDefault("action", ""));
            boolean needManualReview = "MANUAL_REVIEW".equalsIgnoreCase(action) || "人工审核".equals(action);

            vo.setId(logItem.getId());
            vo.setTaskId(logItem.getTaskId());
            vo.setRoleName(logItem.getRoleName());
            vo.setSpeakOrder(logItem.getSpeakOrder());
            vo.setThoughtContent(logItem.getThoughtContent());
            vo.setAgentCode(resolveAgentCode(displayOrder));
            vo.setAgentName(logItem.getRoleName());
            vo.setRunAttempt(logItem.getRunAttempt() == null ? 0 : logItem.getRunAttempt());
            vo.setRunOrder(displayOrder);
            vo.setDisplayOrder(displayOrder);
            String stage = normalizeLogStage(logItem.getStage(), suggestion);
            vo.setStage(stage);
            vo.setRunStatus(resolveRunStatus(stage));
            vo.setOutputSummary(thinking);
            vo.setNeedManualReview(needManualReview);
            vo.setThinking(thinking);
            vo.setEvidence(evidence);
            vo.setSuggestion(suggestion);
            vo.setReasonWhy(logItem.getFinalReason());
            vo.setCreatedAt(logItem.getCreatedAt());
            return vo;
        }).toList();
    }

    /**
     * 分页查询历史任务，并拼出商品标题和最终执行策略。
     */
    @Override
    public Page<DecisionTaskItemVO> getTasks(int page, int size, String status, String startTime, String endTime, String sortOrder, Long userId) {
        List<Long> userShopIds = getUserShopIds(userId);
        Page<PricingTask> pageParam = new Page<>(Math.max(page, 1), size <= 0 ? 10 : size);
        LambdaQueryWrapper<PricingTask> wrapper = new LambdaQueryWrapper<>();
        wrapper.in(PricingTask::getShopId, userShopIds);
        if (status != null && !status.isBlank()) {
            wrapper.eq(PricingTask::getTaskStatus, status);
        }

        LocalDateTime start = parseDateTime(startTime, false);
        LocalDateTime end = parseDateTime(endTime, true);
        if (start != null) {
            wrapper.ge(PricingTask::getCreatedAt, start);
        }
        if (end != null) {
            wrapper.le(PricingTask::getCreatedAt, end);
        }

        if ("asc".equalsIgnoreCase(sortOrder)) {
            wrapper.orderByAsc(PricingTask::getCreatedAt, PricingTask::getId);
        } else {
            wrapper.orderByDesc(PricingTask::getCreatedAt, PricingTask::getId);
        }

        Page<PricingTask> taskPage = taskMapper.selectPage(pageParam, wrapper);
        Page<DecisionTaskItemVO> resultPage = new Page<>();
        resultPage.setCurrent(taskPage.getCurrent());
        resultPage.setSize(taskPage.getSize());
        resultPage.setTotal(taskPage.getTotal());
        resultPage.setRecords(taskPage.getRecords().stream().map(this::toTaskItem).toList());
        return resultPage;
    }

    /**
     * 按时间范围统计任务总数及不同执行状态的数量。
     */
    @Override
    public Map<String, Long> getTaskStats(String startTime, String endTime, Long userId) {
        List<Long> userShopIds = getUserShopIds(userId);
        LambdaQueryWrapper<PricingTask> wrapper = new LambdaQueryWrapper<>();
        wrapper.in(PricingTask::getShopId, userShopIds);
        LocalDateTime start = parseDateTime(startTime, false);
        LocalDateTime end = parseDateTime(endTime, true);
        if (start != null) {
            wrapper.ge(PricingTask::getCreatedAt, start);
        }
        if (end != null) {
            wrapper.le(PricingTask::getCreatedAt, end);
        }

        List<PricingTask> tasks = taskMapper.selectList(wrapper);
        long total = tasks.size();
        long completed = tasks.stream()
                .filter(task -> List.of("COMPLETED", "MANUAL_REVIEW").contains(String.valueOf(task.getTaskStatus()).toUpperCase()))
                .count();
        long running = tasks.stream()
                .filter(task -> List.of("QUEUED", "RUNNING", "RETRYING").contains(String.valueOf(task.getTaskStatus()).toUpperCase()))
                .count();
        long failed = tasks.stream()
                .filter(task -> List.of("FAILED", "CANCELLED").contains(String.valueOf(task.getTaskStatus()).toUpperCase()))
                .count();
        return Map.of("total", total, "completed", completed, "running", running, "failed", failed);
    }

    /**
     * 获取任务价格对比结果，当前直接复用结果构造逻辑。
     */
    @Override
    public List<DecisionComparisonVO> getTaskComparison(Long taskId, Long userId) {
        verifyTaskOwnership(taskId, userId);
        return buildComparisonRows(taskId);
    }

    /**
     * 查询任务详情，汇总任务、商品和结果三部分信息。
     */
    @Override
    public PricingTaskDetailVO getTaskDetail(Long taskId, Long userId) {
        PricingTask task = taskMapper.selectById(taskId);
        if (task == null) {
            throw new IllegalArgumentException("任务不存在");
        }
        verifyTaskOwnership(task, userId);
        Product product = productMapper.selectById(task.getProductId());
        PricingResult result = getResultByTaskId(taskId);

        PricingTaskDetailVO vo = new PricingTaskDetailVO();
        vo.setTaskId(task.getId());
        vo.setProductId(task.getProductId());
        vo.setProductTitle(product == null ? "-" : product.getTitle());
        vo.setTaskStatus(task.getTaskStatus());
        vo.setCurrentPrice(task.getCurrentPrice());
        vo.setSuggestedMinPrice(task.getSuggestedMinPrice());
        vo.setSuggestedMaxPrice(task.getSuggestedMaxPrice());
        vo.setFinalPrice(result == null ? null : result.getFinalPrice());
        vo.setExpectedSales(result == null ? null : result.getExpectedSales());
        vo.setExpectedProfit(result == null ? null : result.getExpectedProfit());
        vo.setStrategy(result == null ? null : resolveExecuteStrategy(result));
        vo.setFinalSummary(result == null ? null : result.getResultSummary());
        vo.setCreatedAt(task.getCreatedAt());
        vo.setUpdatedAt(task.getUpdatedAt());
        return vo;
    }

    @Override
    public PricingTaskSnapshotVO getTaskSnapshot(Long taskId, Long userId) {
        PricingTaskSnapshotVO snapshot = new PricingTaskSnapshotVO();
        snapshot.setDetail(getTaskDetail(taskId, userId));
        snapshot.setLogs(getTaskLogs(taskId, userId));
        snapshot.setComparison(getTaskComparison(taskId, userId));
        return snapshot;
    }

    /**
     * 将某条决策结果中的价格真正写回商品当前售价。
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public void applyDecision(Long resultId, Long userId) {
        PricingResult result = resultMapper.selectById(resultId);
        if (result == null) {
            throw new IllegalArgumentException("结果不存在");
        }
        PricingTask task = taskMapper.selectById(result.getTaskId());
        if (task == null) {
            throw new IllegalArgumentException("任务不存在");
        }
        verifyTaskOwnership(task, userId);
        Product product = productMapper.selectById(task.getProductId());
        if (product == null) {
            throw new IllegalArgumentException("商品不存在");
        }
        BigDecimal finalPrice = scaleMoney(result.getFinalPrice());
        assertPriceWithinGuardrails(product, task, finalPrice);

        result.setAppliedPreviousPrice(scaleMoney(product.getCurrentPrice()));
        result.setAppliedAt(LocalDateTime.now());
        result.setAppliedByUserId(userId);
        result.setReviewRequired(0);
        resultMapper.updateById(result);

        product.setCurrentPrice(finalPrice);
        productMapper.updateById(product);
        task.setTaskStatus("COMPLETED");
        if (task.getCompletedAt() == null) {
            task.setCompletedAt(LocalDateTime.now());
        }
        taskMapper.updateById(task);
    }

    @Override
    public void cancelTask(Long taskId, Long userId) {
        PricingTask task = taskMapper.selectById(taskId);
        if (task == null) {
            throw new IllegalArgumentException("任务不存在");
        }
        verifyTaskOwnership(task, userId);

        String status = String.valueOf(task.getTaskStatus()).toUpperCase();
        if (List.of("COMPLETED", "FAILED", "CANCELLED", "MANUAL_REVIEW").contains(status)) {
            throw new IllegalStateException("当前任务状态不允许取消");
        }

        int updated = taskMapper.cancelIfRunning(taskId);
        if (updated == 0) {
            throw new IllegalStateException("当前任务状态不允许取消");
        }
    }

    /**
     * 导出任务报告为 Excel，便于离线查看和汇报。
     */
    @Override
    public void exportDecisionReport(Long taskId, HttpServletResponse response, Long userId) throws IOException {
        verifyTaskOwnership(taskId, userId);
        List<DecisionComparisonVO> rows = buildComparisonRows(taskId);
        response.setContentType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
        response.setCharacterEncoding("utf-8");
        String fileName = URLEncoder.encode("DecisionReport_" + taskId, "UTF-8").replaceAll("\\+", "%20");
        response.setHeader("Content-disposition", "attachment;filename*=utf-8''" + fileName + ".xlsx");
        EasyExcel.write(response.getOutputStream(), DecisionComparisonVO.class).sheet("决策报告").doWrite(rows);
    }

    private List<Long> getUserShopIds(Long userId) {
        List<Long> shopIds = shopService.getShopIdsByUser(userId);
        if (shopIds.isEmpty()) {
            throw new IllegalStateException("您还没有店铺，请先创建店铺");
        }
        return shopIds;
    }

    private void verifyTaskOwnership(Long taskId, Long userId) {
        PricingTask task = taskMapper.selectById(taskId);
        if (task == null) {
            throw new IllegalArgumentException("任务不存在");
        }
        verifyTaskOwnership(task, userId);
    }

    private void verifyTaskOwnership(PricingTask task, Long userId) {
        List<Long> shopIds = getUserShopIds(userId);
        if (!shopIds.contains(task.getShopId())) {
            throw new IllegalArgumentException("无权操作此任务");
        }
    }

    /**
     * 将任务实体转换为列表页摘要对象。
     */
    private DecisionTaskItemVO toTaskItem(PricingTask task) {
        Product product = productMapper.selectById(task.getProductId());
        PricingResult result = getResultByTaskId(task.getId());
        DecisionTaskItemVO vo = new DecisionTaskItemVO();
        vo.setId(task.getId());
        vo.setTaskCode(task.getTaskCode());
        vo.setProductId(task.getProductId());
        vo.setProductTitle(product == null ? "-" : product.getTitle());
        vo.setCurrentPrice(task.getCurrentPrice());
        vo.setSuggestedMinPrice(task.getSuggestedMinPrice());
        vo.setSuggestedMaxPrice(task.getSuggestedMaxPrice());
        vo.setFinalPrice(result == null ? null : result.getFinalPrice());
        vo.setTaskStatus(task.getTaskStatus());
        vo.setExecuteStrategy(result == null ? null : resolveExecuteStrategy(result));
        vo.setCreatedAt(task.getCreatedAt());
        return vo;
    }

    /**
     * 构造任务结果对比行，统一结果页和导出逻辑的数据来源。
     */
    private List<DecisionComparisonVO> buildComparisonRows(Long taskId) {
        PricingTask task = taskMapper.selectById(taskId);
        if (task == null) {
            return new ArrayList<>();
        }
        Product product = productMapper.selectById(task.getProductId());
        PricingResult result = getResultByTaskId(taskId);
        if (product == null || result == null) {
            return new ArrayList<>();
        }

        DecisionComparisonVO vo = new DecisionComparisonVO();
        vo.setResultId(result.getId());
        vo.setProductId(product.getId());
        vo.setProductTitle(product.getTitle());
        vo.setOriginalPrice(task.getCurrentPrice());
        vo.setSuggestedPrice(result.getFinalPrice());
        vo.setProfitChange(result.getProfitGrowth());
        vo.setExpectedSales(result.getExpectedSales());
        vo.setExpectedProfit(result.getExpectedProfit());
        boolean reviewRequired = result.getReviewRequired() != null && result.getReviewRequired() == 1;
        vo.setPassStatus(reviewRequired ? "待人工审核" : (result.getIsPass() != null && result.getIsPass() == 1 ? "通过" : "未通过"));
        vo.setExecuteStrategy(resolveExecuteStrategy(result));
        vo.setResultSummary(result.getResultSummary());
        vo.setAppliedStatus(isApplied(product, result) ? "已应用" : "未应用");
        return List.of(vo);
    }

    /**
     * 判断建议价格是否已经应用到商品当前售价。
     */
    private boolean isApplied(Product product, PricingResult result) {
        if (product == null || result == null || product.getCurrentPrice() == null || result.getFinalPrice() == null) {
            return false;
        }
        return product.getCurrentPrice().setScale(2, RoundingMode.HALF_UP)
                .compareTo(result.getFinalPrice().setScale(2, RoundingMode.HALF_UP)) == 0;
    }

    /**
     * 查询任务对应的定价结果记录。
     */
    private PricingResult getResultByTaskId(Long taskId) {
        LambdaQueryWrapper<PricingResult> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(PricingResult::getTaskId, taskId).last("LIMIT 1");
        return resultMapper.selectOne(wrapper);
    }

    /**
     * 解析查询条件中的时间文本，兼容完整时间和日期格式。
     */
    private LocalDateTime parseDateTime(String text, boolean endOfDay) {
        if (text == null || text.isBlank()) {
            return null;
        }
        String trimmed = text.trim();
        try {
            return LocalDateTime.parse(trimmed, DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));
        } catch (Exception ignore) {
        }
        try {
            LocalDate date = LocalDate.parse(trimmed, DateTimeFormatter.ofPattern("yyyy-MM-dd"));
            return endOfDay ? date.atTime(23, 59, 59) : date.atStartOfDay();
        } catch (Exception ignore) {
            return null;
        }
    }

    /**
     * 根据展示顺序映射前端约定的 Agent 编码。
     */
    private String resolveAgentCode(Integer displayOrder) {
        if (displayOrder == null) {
            return "UNKNOWN";
        }
        return switch (displayOrder) {
            case 1 -> "DATA_ANALYSIS";
            case 2 -> "MARKET_INTEL";
            case 3 -> "RISK_CONTROL";
            case 4 -> "MANAGER_COORDINATOR";
            default -> "UNKNOWN";
        };
    }

    /**
     * 解析日志中的 JSON 数组字段，失败时返回空集合。
     */
    private List<Map<String, Object>> parseJsonArray(String json) {
        if (json == null || json.isBlank()) {
            return List.of();
        }
        try {
            return objectMapper.readValue(json, new TypeReference<List<Map<String, Object>>>() {
            });
        } catch (Exception ignore) {
            return List.of();
        }
    }

    /**
     * 解析日志中的 JSON 对象字段，失败时返回空对象。
     */
    private Map<String, Object> parseJsonObject(String json) {
        if (json == null || json.isBlank()) {
            return new LinkedHashMap<>();
        }
        try {
            return objectMapper.readValue(json, new TypeReference<Map<String, Object>>() {
            });
        } catch (Exception ignore) {
            return new LinkedHashMap<>();
        }
    }

    private void normalizeSuggestionStrategy(Map<String, Object> suggestion) {
        if (suggestion != null && suggestion.containsKey("strategy")) {
            suggestion.put("strategy", MANUAL_REVIEW_STRATEGY);
        }
    }

    private String normalizeLogStage(String rawStage, Map<String, Object> suggestion) {
        String normalized = rawStage == null ? "" : rawStage.trim().toLowerCase();
        if ("running".equals(normalized)) {
            return "running";
        }
        if ("failed".equals(normalized) || Boolean.TRUE.equals(suggestion.get("error"))) {
            return "failed";
        }
        return "completed";
    }

    private String resolveRunStatus(String stage) {
        return switch (stage) {
            case "running" -> "running";
            case "failed" -> "failed";
            default -> "success";
        };
    }

    private void assertPriceWithinGuardrails(Product product, PricingTask task, BigDecimal finalPrice) {
        BigDecimal currentPrice = scaleMoney(task.getCurrentPrice());
        if (currentPrice.compareTo(BigDecimal.ZERO) > 0) {
            BigDecimal changeRatio = finalPrice.subtract(currentPrice)
                    .abs()
                    .divide(currentPrice, 4, RoundingMode.HALF_UP);
            if (changeRatio.compareTo(maxAdjustmentRatio) > 0) {
                throw new IllegalStateException("Price adjustment exceeds configured guardrail");
            }
        }

        BigDecimal costPrice = product.getCostPrice();
        if (costPrice != null && finalPrice.compareTo(BigDecimal.ZERO) > 0) {
            BigDecimal marginRate = finalPrice.subtract(costPrice)
                    .divide(finalPrice, 4, RoundingMode.HALF_UP);
            if (marginRate.compareTo(minMarginRate) < 0) {
                throw new IllegalStateException("Price violates minimum margin guardrail");
            }
        }
    }

    private String resolveExecuteStrategy(PricingResult result) {
        return MANUAL_REVIEW_STRATEGY;
    }

    private String truncate(String value, int maxLength) {
        if (value == null) {
            return null;
        }
        return value.length() <= maxLength ? value : value.substring(0, maxLength);
    }

    private BigDecimal scaleMoney(BigDecimal value) {
        if (value == null) {
            return BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
        }
        return value.setScale(2, RoundingMode.HALF_UP);
    }
}
