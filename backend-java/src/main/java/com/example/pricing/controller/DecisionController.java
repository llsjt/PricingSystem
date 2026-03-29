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
import org.springframework.web.bind.annotation.*;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/decision")
@RequiredArgsConstructor
@Slf4j
@CrossOrigin(origins = "*")
public class DecisionController {

    private final DecisionTaskService decisionTaskService;

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

    @GetMapping("/result/{taskId}")
    public Result<List<DecisionComparisonVO>> getTaskResult(@PathVariable Long taskId) {
        return Result.success(decisionTaskService.getTaskResult(taskId));
    }

    @GetMapping("/logs/{taskId}")
    public Result<List<DecisionLogVO>> getTaskLogs(@PathVariable Long taskId) {
        return Result.success(decisionTaskService.getTaskLogs(taskId));
    }

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

    @GetMapping("/tasks/stats")
    public Result<Map<String, Long>> getTaskStats(
            @RequestParam(required = false) String startTime,
            @RequestParam(required = false) String endTime
    ) {
        return Result.success(decisionTaskService.getTaskStats(startTime, endTime));
    }

    @GetMapping("/comparison/{taskId}")
    public Result<List<DecisionComparisonVO>> getComparison(@PathVariable Long taskId) {
        return Result.success(decisionTaskService.getTaskComparison(taskId));
    }

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

    @GetMapping("/export/{taskId}")
    public void exportDecisionReport(@PathVariable Long taskId, HttpServletResponse response) throws IOException {
        decisionTaskService.exportDecisionReport(taskId, response);
    }

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
