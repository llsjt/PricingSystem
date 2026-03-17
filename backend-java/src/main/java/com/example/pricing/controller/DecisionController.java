package com.example.pricing.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.common.Result;
import com.example.pricing.dto.DecisionTaskDTO;
import com.example.pricing.entity.DecResult;
import com.example.pricing.entity.DecTask;
import com.example.pricing.mapper.DecResultMapper;
import com.example.pricing.mapper.DecTaskMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import com.alibaba.excel.EasyExcel;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
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
        return Result.success(resultMapper.selectList(wrapper));
    }

    @GetMapping("/logs/{taskId}")
    public Result<List<com.example.pricing.entity.DecAgentLog>> getTaskLogs(@PathVariable Long taskId) {
        LambdaQueryWrapper<com.example.pricing.entity.DecAgentLog> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(com.example.pricing.entity.DecAgentLog::getTaskId, taskId);
        wrapper.orderByAsc(com.example.pricing.entity.DecAgentLog::getSpeakOrder);
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
        
        if (status != null && !status.isEmpty()) {
            wrapper.eq(DecTask::getStatus, status);
        }
        if (strategyType != null && !strategyType.isEmpty()) {
            wrapper.eq(DecTask::getStrategyType, strategyType);
        }
        if (startTime != null && !startTime.isEmpty()) {
            wrapper.ge(DecTask::getCreatedAt, startTime);
        }
        if (endTime != null && !endTime.isEmpty()) {
            wrapper.le(DecTask::getCreatedAt, endTime);
        }
        
        if ("asc".equalsIgnoreCase(sortOrder)) {
            wrapper.orderByAsc(DecTask::getCreatedAt);
        } else {
            wrapper.orderByDesc(DecTask::getCreatedAt);
        }
        
        return Result.success(taskMapper.selectPage(pageParam, wrapper));
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
                vo.setProductId(product.getId());
                vo.setProductTitle(product.getTitle());
                vo.setOriginalPrice(product.getCurrentPrice());
                vo.setSuggestedPrice(result.getSuggestedPrice());
                
                // Mock original profit = (current_price - cost_price) * monthly_sales
                java.math.BigDecimal cost = product.getCostPrice() != null ? product.getCostPrice() : java.math.BigDecimal.ZERO;
                java.math.BigDecimal originalProfit = product.getCurrentPrice().subtract(cost)
                        .multiply(new java.math.BigDecimal(product.getMonthlySales() != null ? product.getMonthlySales() : 0));
                vo.setOriginalProfit(originalProfit);
                
                // Mock new profit
                java.math.BigDecimal newProfit = result.getProfitChange() != null 
                        ? originalProfit.add(result.getProfitChange()) 
                        : originalProfit;
                vo.setNewProfit(newProfit);
                
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
