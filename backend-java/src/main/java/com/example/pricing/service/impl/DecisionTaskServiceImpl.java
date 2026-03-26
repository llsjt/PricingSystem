package com.example.pricing.service.impl;

import com.alibaba.excel.EasyExcel;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.entity.BizProduct;
import com.example.pricing.entity.BizProductDailyStat;
import com.example.pricing.entity.DecAgentLog;
import com.example.pricing.entity.DecResult;
import com.example.pricing.entity.DecTask;
import com.example.pricing.mapper.BizProductDailyStatMapper;
import com.example.pricing.mapper.BizProductMapper;
import com.example.pricing.mapper.DecAgentLogMapper;
import com.example.pricing.mapper.DecResultMapper;
import com.example.pricing.mapper.DecTaskMapper;
import com.example.pricing.service.DecisionTaskService;
import com.example.pricing.vo.DecisionComparisonVO;
import com.example.pricing.vo.DecisionLogVO;
import com.example.pricing.vo.DecisionTaskItemVO;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.io.IOException;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.net.URLEncoder;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
@RequiredArgsConstructor
@Slf4j
public class DecisionTaskServiceImpl implements DecisionTaskService {

    private static final BigDecimal ONE_HUNDRED = new BigDecimal("100");

    private final DecTaskMapper taskMapper;
    private final DecResultMapper resultMapper;
    private final DecAgentLogMapper logMapper;
    private final BizProductMapper productMapper;
    private final BizProductDailyStatMapper statMapper;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Long startTask(List<Long> productIds, String strategyGoal, String constraints) {
        if (productIds == null || productIds.isEmpty()) {
            throw new IllegalArgumentException("至少选择一个商品");
        }

        Long productId = productIds.get(0);
        BizProduct product = productMapper.selectById(productId);
        if (product == null) {
            throw new IllegalArgumentException("商品不存在");
        }

        MetricsSnapshot metrics = loadMetrics(product);
        ConstraintBundle constraintBundle = parseConstraints(constraints);
        BigDecimal baselineProfit = estimateProfit(product.getCurrentPrice(), product.getCostPrice(), metrics.monthlySales);

        DecTask task = new DecTask();
        task.setTaskCode("TASK-" + UUID.randomUUID().toString().replace("-", "").substring(0, 12).toUpperCase());
        task.setShopId(product.getShopId());
        task.setProductId(product.getId());
        task.setCurrentPrice(scaleMoney(product.getCurrentPrice()));
        task.setBaselineProfit(scaleMoney(baselineProfit));
        task.setTaskStatus("RUNNING");
        taskMapper.insert(task);

        AgentProposal dataProposal = buildDataProposal(product, metrics, strategyGoal);
        AgentProposal marketProposal = buildMarketProposal(product, metrics, strategyGoal);
        AgentProposal riskProposal = buildRiskProposal(product, constraintBundle);
        FinalDecision finalDecision = buildFinalDecision(
                product,
                metrics,
                strategyGoal,
                constraintBundle,
                dataProposal,
                marketProposal,
                riskProposal,
                baselineProfit
        );

        saveLog(task.getId(), dataProposal);
        saveLog(task.getId(), marketProposal);
        saveLog(task.getId(), riskProposal);
        saveLog(task.getId(), finalDecision.managerProposal);

        task.setSuggestedMinPrice(finalDecision.suggestedMinPrice);
        task.setSuggestedMaxPrice(finalDecision.suggestedMaxPrice);
        task.setTaskStatus("COMPLETED");
        taskMapper.updateById(task);

        DecResult result = new DecResult();
        result.setTaskId(task.getId());
        result.setFinalPrice(finalDecision.finalPrice);
        result.setExpectedSales(finalDecision.expectedSales);
        result.setExpectedProfit(finalDecision.expectedProfit);
        result.setProfitGrowth(finalDecision.profitGrowth);
        result.setIsPass(finalDecision.isPass ? 1 : 0);
        result.setExecuteStrategy(finalDecision.executeStrategy);
        result.setResultSummary(finalDecision.resultSummary);
        resultMapper.insert(result);

        return task.getId();
    }

    @Override
    public List<DecisionComparisonVO> getTaskResult(Long taskId) {
        return buildComparisonRows(taskId);
    }

    @Override
    public List<DecisionLogVO> getTaskLogs(Long taskId) {
        LambdaQueryWrapper<DecAgentLog> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(DecAgentLog::getTaskId, taskId).orderByAsc(DecAgentLog::getRunOrder, DecAgentLog::getId);
        return logMapper.selectList(wrapper).stream().map(logItem -> {
            DecisionLogVO vo = new DecisionLogVO();
            vo.setId(logItem.getId());
            vo.setAgentCode(logItem.getAgentCode());
            vo.setAgentName(logItem.getAgentName());
            vo.setRunOrder(logItem.getRunOrder());
            vo.setRunStatus(logItem.getRunStatus());
            vo.setOutputSummary(logItem.getOutputSummary());
            vo.setSuggestedPrice(logItem.getSuggestedPrice());
            vo.setPredictedProfit(logItem.getPredictedProfit());
            vo.setConfidenceScore(logItem.getConfidenceScore());
            vo.setRiskLevel(logItem.getRiskLevel());
            vo.setNeedManualReview(logItem.getNeedManualReview() != null && logItem.getNeedManualReview() == 1);
            vo.setCreatedAt(logItem.getCreatedAt());
            return vo;
        }).toList();
    }

    @Override
    public Page<DecisionTaskItemVO> getTasks(int page, int size, String status, String startTime, String endTime, String sortOrder) {
        Page<DecTask> pageParam = new Page<>(Math.max(page, 1), size <= 0 ? 10 : size);
        LambdaQueryWrapper<DecTask> wrapper = new LambdaQueryWrapper<>();
        if (status != null && !status.isBlank()) {
            wrapper.eq(DecTask::getTaskStatus, status);
        }

        LocalDateTime start = parseDateTime(startTime, false);
        LocalDateTime end = parseDateTime(endTime, true);
        if (start != null) {
            wrapper.ge(DecTask::getCreatedAt, start);
        }
        if (end != null) {
            wrapper.le(DecTask::getCreatedAt, end);
        }

        if ("asc".equalsIgnoreCase(sortOrder)) {
            wrapper.orderByAsc(DecTask::getCreatedAt, DecTask::getId);
        } else {
            wrapper.orderByDesc(DecTask::getCreatedAt, DecTask::getId);
        }

        Page<DecTask> taskPage = taskMapper.selectPage(pageParam, wrapper);
        Page<DecisionTaskItemVO> resultPage = new Page<>();
        resultPage.setCurrent(taskPage.getCurrent());
        resultPage.setSize(taskPage.getSize());
        resultPage.setTotal(taskPage.getTotal());
        resultPage.setRecords(taskPage.getRecords().stream().map(this::toTaskItem).toList());
        return resultPage;
    }

    @Override
    public Map<String, Long> getTaskStats(String startTime, String endTime) {
        LambdaQueryWrapper<DecTask> wrapper = new LambdaQueryWrapper<>();
        LocalDateTime start = parseDateTime(startTime, false);
        LocalDateTime end = parseDateTime(endTime, true);
        if (start != null) {
            wrapper.ge(DecTask::getCreatedAt, start);
        }
        if (end != null) {
            wrapper.le(DecTask::getCreatedAt, end);
        }

        List<DecTask> tasks = taskMapper.selectList(wrapper);
        long total = tasks.size();
        long completed = tasks.stream().filter(task -> "COMPLETED".equalsIgnoreCase(task.getTaskStatus())).count();
        long running = tasks.stream().filter(task -> "RUNNING".equalsIgnoreCase(task.getTaskStatus())).count();
        long failed = tasks.stream().filter(task -> "FAILED".equalsIgnoreCase(task.getTaskStatus())).count();
        return Map.of("total", total, "completed", completed, "running", running, "failed", failed);
    }

    @Override
    public List<DecisionComparisonVO> getTaskComparison(Long taskId) {
        return buildComparisonRows(taskId);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void applyDecision(Long resultId) {
        DecResult result = resultMapper.selectById(resultId);
        if (result == null) {
            throw new IllegalArgumentException("结果不存在");
        }
        DecTask task = taskMapper.selectById(result.getTaskId());
        if (task == null) {
            throw new IllegalArgumentException("任务不存在");
        }
        BizProduct product = productMapper.selectById(task.getProductId());
        if (product == null) {
            throw new IllegalArgumentException("商品不存在");
        }
        product.setCurrentPrice(scaleMoney(result.getFinalPrice()));
        productMapper.updateById(product);
    }

    @Override
    public void exportDecisionReport(Long taskId, HttpServletResponse response) throws IOException {
        List<DecisionComparisonVO> rows = buildComparisonRows(taskId);
        response.setContentType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
        response.setCharacterEncoding("utf-8");
        String fileName = URLEncoder.encode("DecisionReport_" + taskId, "UTF-8").replaceAll("\\+", "%20");
        response.setHeader("Content-disposition", "attachment;filename*=utf-8''" + fileName + ".xlsx");
        EasyExcel.write(response.getOutputStream(), DecisionComparisonVO.class).sheet("决策报告").doWrite(rows);
    }

    private DecisionTaskItemVO toTaskItem(DecTask task) {
        BizProduct product = productMapper.selectById(task.getProductId());
        DecResult result = getResultByTaskId(task.getId());
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
        vo.setExecuteStrategy(result == null ? null : result.getExecuteStrategy());
        vo.setCreatedAt(task.getCreatedAt());
        return vo;
    }

    private List<DecisionComparisonVO> buildComparisonRows(Long taskId) {
        DecTask task = taskMapper.selectById(taskId);
        if (task == null) {
            return new ArrayList<>();
        }
        BizProduct product = productMapper.selectById(task.getProductId());
        DecResult result = getResultByTaskId(taskId);
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
        vo.setPassStatus(result.getIsPass() != null && result.getIsPass() == 1 ? "通过" : "待审核");
        vo.setExecuteStrategy(result.getExecuteStrategy());
        vo.setResultSummary(result.getResultSummary());
        vo.setAppliedStatus(isApplied(product, result) ? "已应用" : "未应用");
        return List.of(vo);
    }

    private boolean isApplied(BizProduct product, DecResult result) {
        if (product == null || result == null || product.getCurrentPrice() == null || result.getFinalPrice() == null) {
            return false;
        }
        return product.getCurrentPrice().setScale(2, RoundingMode.HALF_UP)
                .compareTo(result.getFinalPrice().setScale(2, RoundingMode.HALF_UP)) == 0;
    }

    private DecResult getResultByTaskId(Long taskId) {
        LambdaQueryWrapper<DecResult> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(DecResult::getTaskId, taskId).last("LIMIT 1");
        return resultMapper.selectOne(wrapper);
    }

    private MetricsSnapshot loadMetrics(BizProduct product) {
        LocalDate end = LocalDate.now();
        LocalDate start = end.minusDays(29);
        LambdaQueryWrapper<BizProductDailyStat> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(BizProductDailyStat::getProductId, product.getId())
                .ge(BizProductDailyStat::getStatDate, start)
                .le(BizProductDailyStat::getStatDate, end)
                .orderByAsc(BizProductDailyStat::getStatDate);
        List<BizProductDailyStat> stats = statMapper.selectList(wrapper);
        if (stats.isEmpty()) {
            int estimatedMonthlySales = Math.max(60, safeInt(product.getStock()) / 3);
            return new MetricsSnapshot(estimatedMonthlySales, estimatedMonthlySales / 30.0, estimatedMonthlySales / 30.0, new BigDecimal("0.0400"), safeInt(product.getCurrentPrice().intValue()));
        }

        int monthlySales = stats.stream().map(BizProductDailyStat::getSalesCount).mapToInt(this::safeInt).sum();
        double avg7 = average(stats.stream()
                .skip(Math.max(0, stats.size() - 7))
                .map(BizProductDailyStat::getSalesCount)
                .mapToInt(this::safeInt)
                .boxed()
                .toList());
        int prevStart = Math.max(0, stats.size() - 14);
        int prevEnd = Math.max(prevStart, stats.size() - 7);
        double prev7 = average(stats.subList(prevStart, prevEnd).stream()
                .map(BizProductDailyStat::getSalesCount)
                .mapToInt(this::safeInt)
                .boxed()
                .toList());
        if (prev7 == 0) {
            prev7 = avg7;
        }

        BigDecimal conversionTotal = BigDecimal.ZERO;
        int validCount = 0;
        for (BizProductDailyStat stat : stats) {
            BigDecimal rate = stat.getConversionRate();
            if (rate == null || rate.compareTo(BigDecimal.ZERO) <= 0) {
                int visitors = safeInt(stat.getVisitorCount());
                int sales = safeInt(stat.getSalesCount());
                if (visitors > 0 && sales > 0) {
                    rate = BigDecimal.valueOf(sales).divide(BigDecimal.valueOf(visitors), 4, RoundingMode.HALF_UP);
                }
            }
            if (rate != null && rate.compareTo(BigDecimal.ZERO) > 0) {
                conversionTotal = conversionTotal.add(rate);
                validCount++;
            }
        }

        BigDecimal conversionRate = validCount == 0
                ? new BigDecimal("0.0400")
                : conversionTotal.divide(BigDecimal.valueOf(validCount), 4, RoundingMode.HALF_UP);
        int categoryAveragePrice = categoryAveragePrice(product).setScale(0, RoundingMode.HALF_UP).intValue();
        return new MetricsSnapshot(monthlySales, avg7, prev7, conversionRate, categoryAveragePrice);
    }

    private BigDecimal categoryAveragePrice(BizProduct product) {
        LambdaQueryWrapper<BizProduct> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(product.getCategory() != null, BizProduct::getCategory, product.getCategory());
        List<BizProduct> peers = productMapper.selectList(wrapper);
        if (peers.isEmpty()) {
            return scaleMoney(product.getCurrentPrice());
        }

        BigDecimal total = peers.stream()
                .map(BizProduct::getCurrentPrice)
                .filter(price -> price != null)
                .reduce(BigDecimal.ZERO, BigDecimal::add);
        return total.divide(BigDecimal.valueOf(Math.max(1, peers.size())), 2, RoundingMode.HALF_UP);
    }

    private AgentProposal buildDataProposal(BizProduct product, MetricsSnapshot metrics, String strategyGoal) {
        double trendScore = (metrics.avg7Sales - metrics.previous7Sales) / Math.max(metrics.previous7Sales, 1.0);
        double turnoverDays = safeInt(product.getStock()) / Math.max(metrics.monthlySales / 30.0, 1.0);
        BigDecimal currentPrice = scaleMoney(product.getCurrentPrice());
        BigDecimal price = currentPrice;
        String action = "维持价格";

        if ("CLEARANCE".equalsIgnoreCase(strategyGoal) || turnoverDays > 55 || trendScore < -0.08) {
            price = scaleMoney(currentPrice.multiply(new BigDecimal("0.94")));
            action = "建议下调价格加快动销";
        } else if ("MAX_PROFIT".equalsIgnoreCase(strategyGoal)
                && trendScore > 0.08
                && metrics.conversionRate.compareTo(new BigDecimal("0.0400")) > 0) {
            price = scaleMoney(currentPrice.multiply(new BigDecimal("1.05")));
            action = "建议适度提价释放利润空间";
        }

        String summary = String.format(
                "近7日销量 %.1f，前7日销量 %.1f，库存周转约 %.1f 天，%s。",
                metrics.avg7Sales,
                metrics.previous7Sales,
                turnoverDays,
                action
        );
        return AgentProposal.builder()
                .agentCode("DATA")
                .agentName("数据分析")
                .runOrder(1)
                .runStatus("SUCCESS")
                .summary(summary)
                .suggestedPrice(price)
                .predictedProfit(estimateProfit(price, product.getCostPrice(), metrics.monthlySales))
                .confidenceScore(new BigDecimal("0.78"))
                .riskLevel(turnoverDays > 70 ? "HIGH" : "MEDIUM")
                .manualReview(false)
                .build();
    }

    private AgentProposal buildMarketProposal(BizProduct product, MetricsSnapshot metrics, String strategyGoal) {
        BigDecimal currentPrice = scaleMoney(product.getCurrentPrice());
        BigDecimal categoryAveragePrice = BigDecimal.valueOf(metrics.categoryAveragePrice);
        BigDecimal price = currentPrice;
        String action = "建议维持价格带";

        if (currentPrice.compareTo(categoryAveragePrice.multiply(new BigDecimal("1.08"))) > 0) {
            price = scaleMoney(categoryAveragePrice.multiply(new BigDecimal("1.02")));
            action = "当前价格高于类目均价，建议回调到均价附近";
        } else if ("MAX_PROFIT".equalsIgnoreCase(strategyGoal)
                && currentPrice.compareTo(categoryAveragePrice.multiply(new BigDecimal("0.92"))) < 0) {
            price = scaleMoney(currentPrice.multiply(new BigDecimal("1.06")));
            action = "当前价格偏低，可回收部分利润空间";
        }

        String summary = String.format(
                "类目平均售价约 %s 元，当前售价 %s 元，%s。",
                categoryAveragePrice.setScale(2, RoundingMode.HALF_UP).toPlainString(),
                currentPrice.setScale(2, RoundingMode.HALF_UP).toPlainString(),
                action
        );
        return AgentProposal.builder()
                .agentCode("MARKET")
                .agentName("市场情报")
                .runOrder(2)
                .runStatus("SUCCESS")
                .summary(summary)
                .suggestedPrice(price)
                .predictedProfit(estimateProfit(price, product.getCostPrice(), metrics.monthlySales))
                .confidenceScore(new BigDecimal("0.73"))
                .riskLevel("MEDIUM")
                .manualReview(false)
                .build();
    }

    private AgentProposal buildRiskProposal(BizProduct product, ConstraintBundle bundle) {
        BigDecimal currentPrice = scaleMoney(product.getCurrentPrice());
        BigDecimal costPrice = scaleMoney(product.getCostPrice());
        BigDecimal minMargin = bundle.minProfitMargin == null ? new BigDecimal("0.15") : bundle.minProfitMargin;
        BigDecimal floorByMargin = costPrice.divide(BigDecimal.ONE.subtract(minMargin), 2, RoundingMode.HALF_UP);
        BigDecimal floor = max(costPrice.multiply(new BigDecimal("1.05")), floorByMargin, bundle.priceFloor);

        BigDecimal price = currentPrice.compareTo(floor) < 0 ? floor : currentPrice;
        if (bundle.maxDiscountRate != null) {
            BigDecimal allowedPrice = scaleMoney(currentPrice.multiply(bundle.maxDiscountRate));
            if (allowedPrice.compareTo(floor) > 0) {
                price = allowedPrice;
            }
        }
        if (bundle.priceCeiling != null && price.compareTo(bundle.priceCeiling) > 0) {
            price = bundle.priceCeiling;
        }

        boolean manualReview = bundle.priceCeiling != null && bundle.priceCeiling.compareTo(floor) < 0;
        String summary = String.format(
                "成本价 %s 元，安全底价 %s 元，%s。",
                costPrice.toPlainString(),
                floor.toPlainString(),
                manualReview ? "约束存在冲突，建议人工审核" : "风险边界清晰，可在区间内执行"
        );
        return AgentProposal.builder()
                .agentCode("RISK")
                .agentName("风险控制")
                .runOrder(3)
                .runStatus("SUCCESS")
                .summary(summary)
                .suggestedPrice(price)
                .predictedProfit(estimateProfit(price, product.getCostPrice(), Math.max(30, safeInt(product.getStock()) / 3)))
                .confidenceScore(new BigDecimal("0.86"))
                .riskLevel(manualReview ? "HIGH" : "LOW")
                .manualReview(manualReview)
                .build();
    }

    private FinalDecision buildFinalDecision(
            BizProduct product,
            MetricsSnapshot metrics,
            String strategyGoal,
            ConstraintBundle bundle,
            AgentProposal dataProposal,
            AgentProposal marketProposal,
            AgentProposal riskProposal,
            BigDecimal baselineProfit
    ) {
        BigDecimal currentPrice = scaleMoney(product.getCurrentPrice());
        BigDecimal minPrice = min(dataProposal.suggestedPrice, marketProposal.suggestedPrice, riskProposal.suggestedPrice);
        BigDecimal maxPrice = max(dataProposal.suggestedPrice, marketProposal.suggestedPrice, riskProposal.suggestedPrice);

        BigDecimal finalPrice;
        if ("CLEARANCE".equalsIgnoreCase(strategyGoal)) {
            finalPrice = min(dataProposal.suggestedPrice, marketProposal.suggestedPrice, riskProposal.suggestedPrice);
        } else if ("MARKET_SHARE".equalsIgnoreCase(strategyGoal)) {
            finalPrice = min(marketProposal.suggestedPrice, riskProposal.suggestedPrice, currentPrice);
        } else {
            List<BigDecimal> candidates = List.of(currentPrice, dataProposal.suggestedPrice, marketProposal.suggestedPrice, riskProposal.suggestedPrice);
            finalPrice = candidates.stream()
                    .max(Comparator.comparing(candidate ->
                            estimateProfit(candidate, product.getCostPrice(), estimateSales(metrics.monthlySales, currentPrice, candidate, strategyGoal))))
                    .orElse(currentPrice);
        }

        if (bundle.priceFloor != null && finalPrice.compareTo(bundle.priceFloor) < 0) {
            finalPrice = bundle.priceFloor;
        }
        if (bundle.priceCeiling != null && finalPrice.compareTo(bundle.priceCeiling) > 0) {
            finalPrice = bundle.priceCeiling;
        }
        if (riskProposal.suggestedPrice != null && finalPrice.compareTo(riskProposal.suggestedPrice) < 0) {
            finalPrice = riskProposal.suggestedPrice;
        }
        finalPrice = scaleMoney(finalPrice);

        int expectedSales = estimateSales(metrics.monthlySales, currentPrice, finalPrice, strategyGoal);
        BigDecimal expectedProfit = estimateProfit(finalPrice, product.getCostPrice(), expectedSales);
        BigDecimal profitGrowth = scaleMoney(expectedProfit.subtract(baselineProfit));
        boolean isPass = !riskProposal.manualReview && finalPrice.compareTo(riskProposal.suggestedPrice) >= 0;

        String executeStrategy;
        if (!isPass) {
            executeStrategy = "人工审核";
        } else if (profitGrowth.compareTo(BigDecimal.ZERO) > 0) {
            executeStrategy = "直接执行";
        } else {
            executeStrategy = "灰度发布";
        }

        String resultSummary = String.format(
                "综合数据、市场和风控建议后，推荐价格 %s 元，预估销量 %d，预估利润 %s 元，较基线变化 %s 元。",
                finalPrice.toPlainString(),
                expectedSales,
                expectedProfit.toPlainString(),
                profitGrowth.toPlainString()
        );

        AgentProposal managerProposal = AgentProposal.builder()
                .agentCode("MANAGER")
                .agentName("决策经理")
                .runOrder(4)
                .runStatus("SUCCESS")
                .summary(resultSummary + " 执行方式：" + executeStrategy + "。")
                .suggestedPrice(finalPrice)
                .predictedProfit(expectedProfit)
                .confidenceScore(isPass ? new BigDecimal("0.82") : new BigDecimal("0.58"))
                .riskLevel(isPass ? "LOW" : "HIGH")
                .manualReview(!isPass)
                .build();

        return new FinalDecision(minPrice, maxPrice, finalPrice, expectedSales, expectedProfit, profitGrowth, isPass, executeStrategy, resultSummary, managerProposal);
    }

    private void saveLog(Long taskId, AgentProposal proposal) {
        DecAgentLog logItem = new DecAgentLog();
        logItem.setTaskId(taskId);
        logItem.setAgentCode(proposal.agentCode);
        logItem.setAgentName(proposal.agentName);
        logItem.setRunOrder(proposal.runOrder);
        logItem.setRunStatus(proposal.runStatus);
        logItem.setOutputSummary(proposal.summary);
        logItem.setSuggestedPrice(proposal.suggestedPrice);
        logItem.setPredictedProfit(proposal.predictedProfit);
        logItem.setConfidenceScore(proposal.confidenceScore);
        logItem.setRiskLevel(proposal.riskLevel);
        logItem.setNeedManualReview(proposal.manualReview ? 1 : 0);
        logMapper.insert(logItem);
    }

    private ConstraintBundle parseConstraints(String constraints) {
        ConstraintBundle bundle = new ConstraintBundle();
        String text = constraints == null ? "" : constraints;

        java.util.regex.Matcher matcher = java.util.regex.Pattern.compile("(?:利润率|毛利率)\\D*(\\d+(?:\\.\\d+)?)\\s*%").matcher(text);
        if (matcher.find()) {
            bundle.minProfitMargin = new BigDecimal(matcher.group(1)).divide(ONE_HUNDRED, 4, RoundingMode.HALF_UP);
        }

        matcher = java.util.regex.Pattern.compile("(?:降价幅度|折扣|优惠)\\D*(\\d+(?:\\.\\d+)?)\\s*%").matcher(text);
        if (matcher.find()) {
            BigDecimal drop = new BigDecimal(matcher.group(1)).divide(ONE_HUNDRED, 4, RoundingMode.HALF_UP);
            bundle.maxDiscountRate = BigDecimal.ONE.subtract(drop);
        }

        matcher = java.util.regex.Pattern.compile("(?:最低售价|最低价格)\\D*(\\d+(?:\\.\\d+)?)").matcher(text);
        if (matcher.find()) {
            bundle.priceFloor = new BigDecimal(matcher.group(1)).setScale(2, RoundingMode.HALF_UP);
        }

        matcher = java.util.regex.Pattern.compile("(?:最高售价|最高价格)\\D*(\\d+(?:\\.\\d+)?)").matcher(text);
        if (matcher.find()) {
            bundle.priceCeiling = new BigDecimal(matcher.group(1)).setScale(2, RoundingMode.HALF_UP);
        }
        return bundle;
    }

    private BigDecimal estimateProfit(BigDecimal price, BigDecimal cost, int expectedSales) {
        return scaleMoney(scaleMoney(price).subtract(scaleMoney(cost)).multiply(BigDecimal.valueOf(Math.max(expectedSales, 0))));
    }

    private int estimateSales(int baselineMonthlySales, BigDecimal currentPrice, BigDecimal targetPrice, String strategyGoal) {
        int baseline = Math.max(baselineMonthlySales, 30);
        if (currentPrice == null || targetPrice == null || currentPrice.compareTo(BigDecimal.ZERO) <= 0) {
            return baseline;
        }

        BigDecimal ratio = targetPrice.subtract(currentPrice).divide(currentPrice, 4, RoundingMode.HALF_UP);
        BigDecimal sensitivity = switch (String.valueOf(strategyGoal).toUpperCase()) {
            case "CLEARANCE" -> new BigDecimal("1.80");
            case "MARKET_SHARE" -> new BigDecimal("1.35");
            default -> new BigDecimal("0.90");
        };
        BigDecimal factor = BigDecimal.ONE.subtract(ratio.multiply(sensitivity));
        BigDecimal raw = BigDecimal.valueOf(baseline).multiply(max(factor, new BigDecimal("0.35")));
        return raw.setScale(0, RoundingMode.HALF_UP).intValue();
    }

    private BigDecimal scaleMoney(BigDecimal value) {
        if (value == null) {
            return BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
        }
        return value.setScale(2, RoundingMode.HALF_UP);
    }

    private BigDecimal min(BigDecimal... values) {
        BigDecimal result = null;
        for (BigDecimal value : values) {
            if (value == null) {
                continue;
            }
            result = result == null || value.compareTo(result) < 0 ? value : result;
        }
        return result == null ? BigDecimal.ZERO : scaleMoney(result);
    }

    private BigDecimal max(BigDecimal... values) {
        BigDecimal result = null;
        for (BigDecimal value : values) {
            if (value == null) {
                continue;
            }
            result = result == null || value.compareTo(result) > 0 ? value : result;
        }
        return result == null ? BigDecimal.ZERO : scaleMoney(result);
    }

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

    private int safeInt(Integer value) {
        return value == null ? 0 : value;
    }

    private double average(List<Integer> values) {
        if (values == null || values.isEmpty()) {
            return 0.0;
        }
        return values.stream().mapToInt(Integer::intValue).average().orElse(0.0);
    }

    private static class ConstraintBundle {
        private BigDecimal minProfitMargin;
        private BigDecimal maxDiscountRate;
        private BigDecimal priceFloor;
        private BigDecimal priceCeiling;
    }

    private record MetricsSnapshot(
            int monthlySales,
            double avg7Sales,
            double previous7Sales,
            BigDecimal conversionRate,
            int categoryAveragePrice
    ) {
    }

    @lombok.Builder
    private static class AgentProposal {
        private String agentCode;
        private String agentName;
        private Integer runOrder;
        private String runStatus;
        private String summary;
        private BigDecimal suggestedPrice;
        private BigDecimal predictedProfit;
        private BigDecimal confidenceScore;
        private String riskLevel;
        private boolean manualReview;
    }

    private record FinalDecision(
            BigDecimal suggestedMinPrice,
            BigDecimal suggestedMaxPrice,
            BigDecimal finalPrice,
            Integer expectedSales,
            BigDecimal expectedProfit,
            BigDecimal profitGrowth,
            boolean isPass,
            String executeStrategy,
            String resultSummary,
            AgentProposal managerProposal
    ) {
    }
}
