package com.example.pricing.controller;

import com.example.pricing.common.Result;
import com.example.pricing.dto.PricingTaskCreateDTO;
import com.example.pricing.service.DecisionTaskService;
import com.example.pricing.vo.DecisionLogVO;
import com.example.pricing.vo.PricingTaskDetailVO;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 定价任务桥接接口：
 * 1. 前端发起任务
 * 2. 查询任务详情
 * 3. 查询 Agent 卡片日志
 */
@RestController
@RequestMapping("/api/pricing/tasks")
@RequiredArgsConstructor
@Slf4j
@CrossOrigin(origins = "*")
public class PricingTaskController {

    private final DecisionTaskService decisionTaskService;

    @PostMapping
    public Result<Long> createTask(@RequestBody PricingTaskCreateDTO request) {
        try {
            if (request.getProductId() == null) {
                return Result.error("productId不能为空");
            }
            String strategyGoal = request.getStrategyGoal();
            String constraints = request.getConstraints();
            Long taskId = decisionTaskService.createPricingTask(request.getProductId(), strategyGoal, constraints);
            return Result.success(taskId);
        } catch (Exception e) {
            log.error("create pricing task failed", e);
            return Result.error(e.getMessage());
        }
    }

    @GetMapping("/{taskId}")
    public Result<PricingTaskDetailVO> getTaskDetail(@PathVariable Long taskId) {
        try {
            return Result.success(decisionTaskService.getTaskDetail(taskId));
        } catch (Exception e) {
            return Result.error(e.getMessage());
        }
    }

    @GetMapping("/{taskId}/logs")
    public Result<List<DecisionLogVO>> getTaskLogs(@PathVariable Long taskId) {
        return Result.success(decisionTaskService.getTaskLogs(taskId));
    }
}
