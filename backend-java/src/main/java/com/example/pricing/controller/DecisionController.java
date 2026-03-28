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
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

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

    @GetMapping(value = "/stream/{taskId}", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter streamTaskLogs(@PathVariable Long taskId) {
        SseEmitter emitter = new SseEmitter(10 * 60 * 1000L);
        ScheduledExecutorService scheduler = Executors.newSingleThreadScheduledExecutor();
        AtomicLong lastLogId = new AtomicLong(0);
        AtomicBoolean completed = new AtomicBoolean(false);

        Runnable tick = () -> {
            if (completed.get()) {
                return;
            }
            try {
                List<DecisionLogVO> logs = decisionTaskService.getTaskLogs(taskId);
                for (DecisionLogVO logItem : logs) {
                    if (logItem == null || logItem.getId() == null) {
                        continue;
                    }
                    if (logItem.getId() <= lastLogId.get()) {
                        continue;
                    }
                    sendEvent(emitter, "log", logItem);
                    lastLogId.set(logItem.getId());
                    if ("FAILED".equalsIgnoreCase(logItem.getRunStatus())) {
                        sendEvent(emitter, "failed", Map.of("taskId", taskId, "message", "task failed"));
                        completed.set(true);
                        emitter.complete();
                        return;
                    }
                }

                List<DecisionComparisonVO> result = decisionTaskService.getTaskResult(taskId);
                if (result != null && !result.isEmpty()) {
                    sendEvent(emitter, "result", result);
                    sendEvent(emitter, "done", Map.of("taskId", taskId, "status", "COMPLETED"));
                    completed.set(true);
                    emitter.complete();
                    return;
                }

                sendEvent(
                        emitter,
                        "heartbeat",
                        Map.of("taskId", taskId, "lastLogId", lastLogId.get(), "logCount", logs.size())
                );
            } catch (Exception ex) {
                log.warn("stream task logs failed, taskId={}", taskId, ex);
                if (completed.compareAndSet(false, true)) {
                    try {
                        sendEvent(emitter, "failed", Map.of("taskId", taskId, "message", ex.getMessage()));
                    } catch (Exception ignore) {
                    }
                    emitter.completeWithError(ex);
                }
            }
        };

        scheduler.scheduleAtFixedRate(tick, 0, 1, TimeUnit.SECONDS);

        emitter.onCompletion(() -> {
            completed.set(true);
            scheduler.shutdownNow();
        });
        emitter.onTimeout(() -> {
            completed.set(true);
            scheduler.shutdownNow();
            emitter.complete();
        });
        emitter.onError((ex) -> {
            completed.set(true);
            scheduler.shutdownNow();
        });

        return emitter;
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

    private void sendEvent(SseEmitter emitter, String event, Object payload) throws IOException {
        emitter.send(SseEmitter.event().name(event).data(payload));
    }
}
