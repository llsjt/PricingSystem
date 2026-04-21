/*
 * 定价任务桥接控制器，负责单商品任务创建、取消、详情和实时流接口。
 */

package com.example.pricing.controller;

import com.example.pricing.common.Result;
import com.example.pricing.dto.PricingTaskCreateDTO;
import com.example.pricing.service.DecisionTaskService;
import com.example.pricing.service.PricingTaskStreamService;
import com.example.pricing.vo.DecisionLogVO;
import com.example.pricing.vo.PricingTaskDetailVO;
import com.example.pricing.vo.PricingTaskSnapshotVO;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.List;

/**
 * 定价任务桥接控制器，提供单商品任务创建、详情查询和日志查看能力。
 */
@RestController
@RequestMapping("/api/pricing/tasks")
@RequiredArgsConstructor
@Slf4j
public class PricingTaskController {

    private final DecisionTaskService decisionTaskService;
    private final PricingTaskStreamService pricingTaskStreamService;

    /**
     * 为单个商品创建定价任务，供旧版前端或简化入口使用。
     */
    @PostMapping
    public Result<Long> createTask(@RequestBody PricingTaskCreateDTO request, HttpServletRequest httpRequest) {
        try {
            if (request.getProductId() == null) {
                return Result.error("商品ID不能为空");
            }
            String strategyGoal = request.getStrategyGoal();
            String constraints = request.getConstraints();
            Long taskId = decisionTaskService.createPricingTask(request.getProductId(), strategyGoal, constraints, getCurrentUserId(httpRequest));
            return Result.success(taskId);
        } catch (Exception e) {
            log.error("create pricing task failed", e);
            return Result.error(e.getMessage());
        }
    }

    /**
     * 查询任务详情，返回价格区间、最终建议和摘要信息。
     */
    @PostMapping("/{taskId}/cancel")
    public Result<Void> cancelTask(@PathVariable Long taskId, HttpServletRequest request) {
        try {
            decisionTaskService.cancelTask(taskId, getCurrentUserId(request));
            return Result.success();
        } catch (Exception e) {
            log.error("cancel pricing task failed", e);
            return Result.error(e.getMessage());
        }
    }

    @GetMapping("/{taskId}")
    public Result<PricingTaskDetailVO> getTaskDetail(@PathVariable Long taskId, HttpServletRequest request) {
        try {
            return Result.success(decisionTaskService.getTaskDetail(taskId, getCurrentUserId(request)));
        } catch (Exception e) {
            return Result.error(e.getMessage());
        }
    }

    @GetMapping("/{taskId}/snapshot")
    public Result<PricingTaskSnapshotVO> getTaskSnapshot(@PathVariable Long taskId, HttpServletRequest request) {
        try {
            return Result.success(decisionTaskService.getTaskSnapshot(taskId, getCurrentUserId(request)));
        } catch (Exception e) {
            return Result.error(e.getMessage());
        }
    }

    /**
     * 查询任务执行日志，供前端展示智能体思考过程。
     */
    @GetMapping("/{taskId}/logs")
    public Result<List<DecisionLogVO>> getTaskLogs(@PathVariable Long taskId, HttpServletRequest request) {
        return Result.success(decisionTaskService.getTaskLogs(taskId, getCurrentUserId(request)));
    }

    @GetMapping(value = "/{taskId}/events", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter streamTaskEvents(@PathVariable Long taskId, HttpServletRequest request) {
        return pricingTaskStreamService.streamTask(taskId, getCurrentUserId(request));
    }

    private Long getCurrentUserId(HttpServletRequest request) {
        Long userId = (Long) request.getAttribute("currentUserId");
        if (userId == null) {
            throw new IllegalStateException("请先登录");
        }
        return userId;
    }
}
