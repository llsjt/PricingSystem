package com.example.pricing.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.common.Result;
import com.example.pricing.entity.DecResult;
import com.example.pricing.entity.DecTask;
import com.example.pricing.mapper.DecResultMapper;
import com.example.pricing.mapper.DecTaskMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

import com.alibaba.excel.EasyExcel;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.net.URLEncoder;

@RestController
@RequestMapping("/api/decision")
@RequiredArgsConstructor
@Slf4j
@CrossOrigin(origins = "*")
public class DecisionController {

    private final DecTaskMapper taskMapper;
    private final DecResultMapper resultMapper;
    private final com.example.pricing.mapper.BizProductMapper productMapper;
    private final com.example.pricing.mapper.DecAgentLogMapper logMapper;
    private final RestTemplate restTemplate = new RestTemplate();

    @PostMapping("/start")
    public Result<Long> startDecisionTask(@RequestBody Map<String, Object> body) {
        // Adapt input to map because Frontend sends productIds, strategyGoal, constraints
        List<Number> productIdsObj = (List<Number>) body.get("productIds");
        List<Long> productIds = new java.util.ArrayList<>();
        if (productIdsObj != null) {
            for (Number id : productIdsObj) {
                productIds.add(id.longValue());
            }
        }
        String strategyGoal = (String) body.get("strategyGoal");
        String constraints = (String) body.get("constraints");
        if (strategyGoal == null || strategyGoal.isBlank()) {
            return Result.error("请选择策略目标");
        }
        if (constraints == null) {
            constraints = "";
        }

        List<String> validStrategies = java.util.Arrays.asList("MAX_PROFIT", "CLEARANCE", "MARKET_SHARE");
        if (strategyGoal != null && !validStrategies.contains(strategyGoal)) {
            // Convert legacy names for compatibility if needed, or throw error
            if ("利润最大化".equals(strategyGoal)) strategyGoal = "MAX_PROFIT";
            else if ("清仓大甩卖".equals(strategyGoal) || "销量最大化".equals(strategyGoal)) strategyGoal = "CLEARANCE";
            else if ("市场份额优先".equals(strategyGoal)) strategyGoal = "MARKET_SHARE";
            else return Result.error("无效的策略目标");
        }

        // 1. Create Task
        DecTask task = new DecTask();
        task.setTaskNo(UUID.randomUUID().toString());
        task.setStrategyType(strategyGoal);
        task.setConstraints(constraints);
        task.setStatus("RUNNING");

        // Fetch product names for snapshot
        if (!productIds.isEmpty()) {
            List<com.example.pricing.entity.BizProduct> products = productMapper.selectBatchIds(productIds);
            String names = products.stream()
                .map(com.example.pricing.entity.BizProduct::getTitle)
                .collect(java.util.stream.Collectors.joining(", "));
            if (names.length() > 1000) names = names.substring(0, 997) + "...";
            task.setProductNames(names);
        }

        taskMapper.insert(task);

        // 2. Call Python Agent Service
        String pythonServiceUrl = "http://localhost:8000/api/decision/start";
        Map<String, Object> request = new HashMap<>();
        request.put("task_id", task.getId());
        request.put("product_ids", productIds);
        request.put("strategy_goal", strategyGoal);
        request.put("constraints", constraints);

        try {
            // Note: In production, use async call or message queue
            restTemplate.postForObject(pythonServiceUrl, request, Map.class);
        } catch (Exception e) {
            log.error("Failed to call Python service", e);
            task.setStatus("FAILED");
            taskMapper.updateById(task);
            return Result.error("Failed to start agent service: " + e.getMessage());
        }

        return Result.success(task.getId());
    }

    @GetMapping("/result/{taskId}")
    public Result<List<DecResult>> getTaskResult(@PathVariable Long taskId) {
        LambdaQueryWrapper<DecResult> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(DecResult::getTaskId, taskId);
        List<DecResult> results = resultMapper.selectList(wrapper);
        if (results.isEmpty()) {
            return Result.success(results);
        }

        Set<Long> productIds = results.stream()
                .map(DecResult::getProductId)
                .filter(id -> id != null && id > 0)
                .collect(Collectors.toSet());
        if (productIds.isEmpty()) {
            return Result.success(results);
        }

        Map<Long, String> titleMap = productMapper.selectBatchIds(productIds).stream()
                .collect(Collectors.toMap(
                        com.example.pricing.entity.BizProduct::getId,
                        com.example.pricing.entity.BizProduct::getTitle,
                        (left, right) -> left
                ));
        results.forEach(item -> item.setProductTitle(titleMap.get(item.getProductId())));
        return Result.success(results);
    }

    @GetMapping("/logs/{taskId}")
    public Result<List<com.example.pricing.entity.DecAgentLog>> getTaskLogs(@PathVariable Long taskId) {
        LambdaQueryWrapper<com.example.pricing.entity.DecAgentLog> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(com.example.pricing.entity.DecAgentLog::getTaskId, taskId);
        wrapper.orderByAsc(com.example.pricing.entity.DecAgentLog::getSpeakOrder, com.example.pricing.entity.DecAgentLog::getId);
        return Result.success(logMapper.selectList(wrapper));
    }

    @GetMapping("/tasks")
    public Result<Page<DecTask>> getTasks(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String strategyType,
            @RequestParam(required = false) String startTime,
            @RequestParam(required = false) String endTime,
            @RequestParam(defaultValue = "desc") String sortOrder) {
        
        Page<DecTask> pageParam = new Page<>(page, size);
        LambdaQueryWrapper<DecTask> wrapper = new LambdaQueryWrapper<>();
        applyCommonFilters(wrapper, strategyType, startTime, endTime);
        if (status != null && !status.isEmpty()) {
            wrapper.eq(DecTask::getStatus, status);
        }
        
        if ("asc".equalsIgnoreCase(sortOrder)) {
            wrapper.orderByAsc(DecTask::getCreatedAt);
        } else {
            wrapper.orderByDesc(DecTask::getCreatedAt);
        }
        
        return Result.success(taskMapper.selectPage(pageParam, wrapper));
    }

    @GetMapping("/tasks/stats")
    public Result<Map<String, Long>> getTaskStats(
            @RequestParam(required = false) String strategyType,
            @RequestParam(required = false) String startTime,
            @RequestParam(required = false) String endTime) {
        LambdaQueryWrapper<DecTask> totalWrapper = new LambdaQueryWrapper<>();
        applyCommonFilters(totalWrapper, strategyType, startTime, endTime);
        long totalCount = taskMapper.selectCount(totalWrapper);

        LambdaQueryWrapper<DecTask> completedWrapper = new LambdaQueryWrapper<>();
        applyCommonFilters(completedWrapper, strategyType, startTime, endTime);
        completedWrapper.eq(DecTask::getStatus, "COMPLETED");
        long completedCount = taskMapper.selectCount(completedWrapper);

        LambdaQueryWrapper<DecTask> runningWrapper = new LambdaQueryWrapper<>();
        applyCommonFilters(runningWrapper, strategyType, startTime, endTime);
        runningWrapper.eq(DecTask::getStatus, "RUNNING");
        long runningCount = taskMapper.selectCount(runningWrapper);

        Map<String, Long> stats = new HashMap<>();
        stats.put("total", totalCount);
        stats.put("completed", completedCount);
        stats.put("running", runningCount);
        return Result.success(stats);
    }

    @GetMapping("/comparison/{taskId}")
    public Result<List<com.example.pricing.vo.DecisionComparisonVO>> getComparison(@PathVariable Long taskId) {
        LambdaQueryWrapper<DecResult> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(DecResult::getTaskId, taskId);
        List<DecResult> results = resultMapper.selectList(wrapper);
        
        List<com.example.pricing.vo.DecisionComparisonVO> comparisonList = new java.util.ArrayList<>();
        for (DecResult result : results) {
            com.example.pricing.entity.BizProduct product = productMapper.selectById(result.getProductId());
            if (product != null) {
                com.example.pricing.vo.DecisionComparisonVO vo = new com.example.pricing.vo.DecisionComparisonVO();
                vo.setResultId(result.getId());
                vo.setProductId(product.getId());
                vo.setProductTitle(product.getTitle());
                BigDecimal suggestedPrice = result.getSuggestedPrice() != null ? result.getSuggestedPrice() : BigDecimal.ZERO;
                BigDecimal originalPrice = normalizeOriginalPrice(
                        product.getCurrentPrice(),
                        suggestedPrice,
                        result.getDiscountRate()
                );
                BigDecimal cost = product.getCostPrice() != null ? product.getCostPrice() : BigDecimal.ZERO;
                int monthlySales = product.getMonthlySales() != null ? product.getMonthlySales() : 0;

                vo.setOriginalPrice(originalPrice);
                vo.setSuggestedPrice(suggestedPrice);

                BigDecimal originalProfit = calculateProfit(originalPrice, cost, monthlySales);
                vo.setOriginalProfit(originalProfit);

                BigDecimal newProfit = calculateProfit(suggestedPrice, cost, monthlySales);
                vo.setNewProfit(newProfit);
                vo.setProfitChange(calculateProfitChange(originalProfit, newProfit));
                
                vo.setDiscountRate(result.getDiscountRate());
                vo.setIsAccepted(result.getIsAccepted());
                vo.setAdoptStatus(result.getAdoptStatus());
                vo.setRejectReason(result.getRejectReason());

                comparisonList.add(vo);
            }
        }
        return Result.success(comparisonList);
    }

    @PostMapping("/apply/{resultId}")
    public Result<Void> applyDecision(@PathVariable Long resultId) {
        DecResult result = resultMapper.selectById(resultId);
        if (result == null) {
            return Result.error("Result not found");
        }
        
        // Update product price
        com.example.pricing.entity.BizProduct product = productMapper.selectById(result.getProductId());
        if (product != null) {
            product.setCurrentPrice(result.getSuggestedPrice());
            productMapper.updateById(product);
        }
        
        // Update result status
        result.setIsAccepted(true);
        result.setAdoptStatus("ADOPTED");
        resultMapper.updateById(result);
        
        return Result.success(null);
    }

    @PostMapping("/reject/{resultId}")
    public Result<Void> rejectDecision(@PathVariable Long resultId, @RequestBody Map<String, String> body) {
        DecResult result = resultMapper.selectById(resultId);
        if (result == null) {
            return Result.error("Result not found");
        }
        
        // Update result status
        result.setIsAccepted(false);
        result.setAdoptStatus("REJECTED");
        result.setRejectReason(body.get("reason"));
        resultMapper.updateById(result);
        
        return Result.success(null);
    }

    private void applyCommonFilters(
            LambdaQueryWrapper<DecTask> wrapper,
            String strategyType,
            String startTime,
            String endTime) {
        if (strategyType != null && !strategyType.isEmpty()) {
            wrapper.eq(DecTask::getStrategyType, strategyType);
        }
        if (startTime != null && !startTime.isEmpty()) {
            wrapper.ge(DecTask::getCreatedAt, startTime);
        }
        if (endTime != null && !endTime.isEmpty()) {
            wrapper.le(DecTask::getCreatedAt, endTime);
        }
    }

    private BigDecimal normalizeOriginalPrice(BigDecimal currentPrice, BigDecimal suggestedPrice, BigDecimal discountRate) {
        if (suggestedPrice != null && discountRate != null && discountRate.compareTo(BigDecimal.ZERO) > 0) {
            return suggestedPrice.divide(discountRate, 2, RoundingMode.HALF_UP);
        }
        if (currentPrice != null) {
            return currentPrice.setScale(2, RoundingMode.HALF_UP);
        }
        if (suggestedPrice != null) {
            return suggestedPrice.setScale(2, RoundingMode.HALF_UP);
        }
        return BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
    }

    private BigDecimal calculateProfit(BigDecimal price, BigDecimal cost, int monthlySales) {
        BigDecimal safePrice = price != null ? price : BigDecimal.ZERO;
        BigDecimal safeCost = cost != null ? cost : BigDecimal.ZERO;
        return safePrice
                .subtract(safeCost)
                .multiply(BigDecimal.valueOf(Math.max(monthlySales, 0)))
                .setScale(2, RoundingMode.HALF_UP);
    }

    private BigDecimal calculateProfitChange(BigDecimal originalProfit, BigDecimal newProfit) {
        BigDecimal safeOriginalProfit = originalProfit != null ? originalProfit : BigDecimal.ZERO;
        BigDecimal safeNewProfit = newProfit != null ? newProfit : BigDecimal.ZERO;
        return safeNewProfit.subtract(safeOriginalProfit).setScale(2, RoundingMode.HALF_UP);
    }

    @GetMapping("/export/{taskId}")
    public void exportDecisionReport(@PathVariable Long taskId, HttpServletResponse response) throws IOException {
        // Fetch comparison data
        List<com.example.pricing.vo.DecisionComparisonVO> comparisonList = getComparison(taskId).getData();
        
        response.setContentType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
        response.setCharacterEncoding("utf-8");
        String fileName = URLEncoder.encode("DecisionReport_" + taskId, "UTF-8").replaceAll("\\+", "%20");
        response.setHeader("Content-disposition", "attachment;filename*=utf-8''" + fileName + ".xlsx");
        
        EasyExcel.write(response.getOutputStream(), com.example.pricing.vo.DecisionComparisonVO.class)
                .sheet("决策报告")
                .doWrite(comparisonList);
    }
}
