package com.example.pricing.controller;

import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.example.pricing.common.Result;
import com.example.pricing.service.DecisionTaskService;
import com.example.pricing.vo.DecisionComparisonVO;
import com.example.pricing.vo.DecisionLogVO;
import com.example.pricing.vo.DecisionTaskItemVO;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 决策任务控制器，负责启动多商品定价分析、查看结果、日志与统计信息。
 */
@RestController
@RequestMapping("/api/decision")
@RequiredArgsConstructor
@Slf4j
@CrossOrigin(origins = "*")
public class DecisionController {

    private final DecisionTaskService decisionTaskService;

    /**
     * 启动一次定价决策任务，并将任务下发给后端分析流程。
     */
    @PostMapping("/start")
    public Result<Long> startDecisionTask(@RequestBody Map<String, Object> body) {
        try {
            List<Long> productIds = parseProductIds(body.get("productIds"));
            String strategyGoal = String.valueOf(body.getOrDefault("strategyGoal", "")).trim();
            String constraints = String.valueOf(body.getOrDefault("constraints", "")).trim();
            if (productIds.isEmpty()) {
                return Result.error("请至少选择一个商品");
            }
            if (strategyGoal.isBlank()) {
                return Result.error("请选择策略目标");
            }
            return Result.success(decisionTaskService.startTask(productIds, strategyGoal, constraints));
        } catch (Exception e) {
            log.error("启动定价任务失败", e);
            return Result.error(e.getMessage());
        }
    }

    /**
     * 查询指定任务的最终决策结果。
     */
    @GetMapping("/result/{taskId}")
    public Result<List<DecisionComparisonVO>> getTaskResult(@PathVariable Long taskId) {
        return Result.success(decisionTaskService.getTaskResult(taskId));
    }

    /**
     * 查询指定任务的多智能体执行日志。
     */
    @GetMapping("/logs/{taskId}")
    public Result<List<DecisionLogVO>> getTaskLogs(@PathVariable Long taskId) {
        return Result.success(decisionTaskService.getTaskLogs(taskId));
    }

    /**
     * 分页查询历史决策任务，支持状态、时间和排序条件。
     */
    @GetMapping("/tasks")
    public Result<Page<DecisionTaskItemVO>> getTasks(
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "10") int size,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String startTime,
            @RequestParam(required = false) String endTime,
            @RequestParam(defaultValue = "desc") String sortOrder
    ) {
        return Result.success(decisionTaskService.getTasks(page, size, status, startTime, endTime, sortOrder));
    }

    /**
     * 统计指定时间范围内的任务总数及各状态数量。
     */
    @GetMapping("/tasks/stats")
    public Result<Map<String, Long>> getTaskStats(
            @RequestParam(required = false) String startTime,
            @RequestParam(required = false) String endTime
    ) {
        return Result.success(decisionTaskService.getTaskStats(startTime, endTime));
    }

    /**
     * 获取任务的价格对比结果，供对比页面直接展示。
     */
    @GetMapping("/comparison/{taskId}")
    public Result<List<DecisionComparisonVO>> getComparison(@PathVariable Long taskId) {
        return Result.success(decisionTaskService.getTaskComparison(taskId));
    }

    /**
     * 将某条定价结果应用回商品当前售价。
     */
    @PostMapping("/apply/{resultId}")
    public Result<Void> applyDecision(@PathVariable Long resultId) {
        try {
            decisionTaskService.applyDecision(resultId);
            return Result.success();
        } catch (Exception e) {
            log.error("应用价格建议失败", e);
            return Result.error(e.getMessage());
        }
    }

    /**
     * 导出指定任务的决策报告 Excel。
     */
    @GetMapping("/export/{taskId}")
    public void exportDecisionReport(@PathVariable Long taskId, HttpServletResponse response) throws IOException {
        decisionTaskService.exportDecisionReport(taskId, response);
    }

    /**
     * 将请求体中的商品 ID 列表统一转换为 Long 集合。
     */
    private List<Long> parseProductIds(Object payload) {
        List<Long> productIds = new ArrayList<>();
        if (payload instanceof List<?> values) {
            for (Object value : values) {
                if (value instanceof Number number) {
                    productIds.add(number.longValue());
                } else if (value != null) {
                    try {
                        productIds.add(Long.parseLong(String.valueOf(value)));
                    } catch (Exception ignore) {
                    }
                }
            }
        }
        return productIds;
    }
}
