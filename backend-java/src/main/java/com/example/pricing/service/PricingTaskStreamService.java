package com.example.pricing.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.pricing.entity.AgentRunLog;
import com.example.pricing.entity.PricingResult;
import com.example.pricing.entity.PricingTask;
import com.example.pricing.mapper.AgentRunLogMapper;
import com.example.pricing.mapper.PricingResultMapper;
import com.example.pricing.mapper.PricingTaskMapper;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

@Service
@RequiredArgsConstructor
public class PricingTaskStreamService {

    private static final String SCHEMA_VERSION = "1.0.0";
    private static final String CHANNEL = "pricing.task.card";
    private static final String MANUAL_REVIEW_STRATEGY = "人工审核";
    private static final int EXPECTED_AGENT_CARD_COUNT = 4;
    private static final ExecutorService STREAM_EXECUTOR = Executors.newCachedThreadPool(runnable -> {
        Thread thread = new Thread(runnable, "pricing-task-stream");
        thread.setDaemon(true);
        return thread;
    });

    private final PricingTaskMapper taskMapper;
    private final PricingResultMapper resultMapper;
    private final AgentRunLogMapper logMapper;
    private final DecisionTaskService decisionTaskService;
    private final ObjectMapper objectMapper = new ObjectMapper();
    @Value("${app.pricing.stream-poll-ms:400}")
    private long streamPollIntervalMs;

    public SseEmitter streamTask(Long taskId, Long userId) {
        decisionTaskService.getTaskDetail(taskId, userId);
        SseEmitter emitter = new SseEmitter(0L);
        emitter.onTimeout(emitter::complete);
        STREAM_EXECUTOR.execute(() -> streamLoop(taskId, emitter));
        return emitter;
    }

    private void streamLoop(Long taskId, SseEmitter emitter) {
        long lastLogId = 0L;
        boolean started = false;
        Set<Integer> completedOrders = new HashSet<>();
        try {
            while (true) {
                PricingTask task = taskMapper.selectById(taskId);
                if (task == null) {
                    send(emitter, baseMessage(taskId, "task_failed", Map.of("message", "task not found", "status", "FAILED")));
                    break;
                }

                if (!started) {
                    send(emitter, baseMessage(taskId, "task_started", Map.of("status", task.getTaskStatus())));
                    started = true;
                }

                LambdaQueryWrapper<AgentRunLog> logWrapper = new LambdaQueryWrapper<>();
                logWrapper.eq(AgentRunLog::getTaskId, taskId)
                        .gt(AgentRunLog::getId, lastLogId)
                        .orderByAsc(AgentRunLog::getId);
                List<AgentRunLog> logs = logMapper.selectList(logWrapper);
                for (AgentRunLog logItem : logs) {
                    send(emitter, toAgentCard(taskId, logItem));
                    int order = resolveDisplayOrder(logItem);
                    if (order >= 1 && order <= EXPECTED_AGENT_CARD_COUNT) {
                        completedOrders.add(order);
                    }
                    lastLogId = logItem.getId() == null ? lastLogId : logItem.getId();
                }

                String status = normalizeStatus(task);
                int completedCardCount = completedOrders.size();
                PricingResult result = getResultByTaskId(taskId);
                if (shouldEmitCompletedEvent(task, result, completedCardCount)) {
                    send(emitter, baseMessage(taskId, "task_completed", Map.of(
                            "status", status,
                            "result", buildResultPayload(result)
                    )));
                    break;
                }

                if (shouldEmitTerminalFailure(task, result)) {
                    String message = resolveTerminalMessage(task);
                    send(emitter, baseMessage(taskId, "task_failed", Map.of("message", message, "status", status)));
                    break;
                }

                Thread.sleep(resolvePollIntervalMs());
            }
        } catch (Exception e) {
            try {
                send(emitter, baseMessage(taskId, "task_failed", Map.of("message", resolveExceptionMessage(e), "status", "FAILED")));
            } catch (Exception ignore) {
            }
        } finally {
            emitter.complete();
        }
    }

    static boolean shouldEmitCompletedEvent(PricingTask task, PricingResult result, int completedCardCount) {
        String status = normalizeStatus(task);
        return result != null
                && completedCardCount >= EXPECTED_AGENT_CARD_COUNT
                && ("COMPLETED".equals(status) || "MANUAL_REVIEW".equals(status));
    }

    static boolean shouldEmitTerminalFailure(PricingTask task, PricingResult result) {
        String status = normalizeStatus(task);
        if ("FAILED".equals(status) || "CANCELLED".equals(status)) {
            return true;
        }
        return result == null && "MANUAL_REVIEW".equals(status);
    }

    static String resolveTerminalMessage(PricingTask task) {
        String status = normalizeStatus(task);
        String failureReason = task.getFailureReason();
        if (failureReason != null && !failureReason.isBlank()) {
            return failureReason;
        }
        if ("MANUAL_REVIEW".equals(status)) {
            return "需要人工审核";
        }
        return "task failed";
    }

    static String resolveExceptionMessage(Exception exception) {
        if (exception == null) {
            return "stream failed";
        }
        String message = exception.getMessage();
        if (message == null || message.isBlank() || "null".equalsIgnoreCase(message.trim())) {
            return "stream failed";
        }
        return message;
    }

    private static String normalizeStatus(PricingTask task) {
        return String.valueOf(task == null ? null : task.getTaskStatus()).toUpperCase();
    }

    private Map<String, Object> toAgentCard(Long taskId, AgentRunLog item) {
        int order = resolveDisplayOrder(item);
        String agentCode = switch (order) {
            case 1 -> "DATA_ANALYSIS";
            case 2 -> "MARKET_INTEL";
            case 3 -> "RISK_CONTROL";
            case 4 -> "MANAGER_COORDINATOR";
            default -> "AGENT_" + order;
        };
        Map<String, Object> payload = new LinkedHashMap<>(baseMessage(taskId, "agent_card", Map.of()));
        payload.put("agentCode", agentCode);
        payload.put("agentName", item.getRoleName());
        payload.put("displayOrder", order);
        payload.put("stage", "completed");
        payload.put("card", buildCardPayload(
                item.getThinkingSummary() == null || item.getThinkingSummary().isBlank() ? nullToEmpty(item.getThoughtContent()) : item.getThinkingSummary(),
                parseJsonArray(item.getEvidenceJson()),
                parseJsonObject(item.getSuggestionJson()),
                item.getFinalReason()
        ));
        return payload;
    }

    static Map<String, Object> buildCardPayload(
            String thinking,
            List<Map<String, Object>> evidence,
            Map<String, Object> suggestion,
            String reasonWhy
    ) {
        Map<String, Object> normalizedSuggestion = normalizeSuggestionStrategy(suggestion);
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("thinking", thinking);
        payload.put("evidence", evidence);
        payload.put("suggestion", normalizedSuggestion);
        payload.put("reasonWhy", reasonWhy);
        return payload;
    }

    static Map<String, Object> buildResultPayload(PricingResult result) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("finalPrice", scaleMoney(result.getFinalPrice()));
        payload.put("expectedSales", result.getExpectedSales() == null ? 0 : result.getExpectedSales());
        payload.put("expectedProfit", scaleMoney(result.getExpectedProfit()));
        payload.put("strategy", resolveExecuteStrategy(result));
        payload.put("summary", result.getResultSummary());
        return payload;
    }

    private Map<String, Object> baseMessage(Long taskId, String type, Map<String, Object> extra) {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("schemaVersion", SCHEMA_VERSION);
        payload.put("channel", CHANNEL);
        payload.put("type", type);
        payload.put("taskId", taskId);
        payload.put("timestamp", Instant.now().toString());
        payload.putAll(extra);
        return payload;
    }

    private void send(SseEmitter emitter, Map<String, Object> payload) throws IOException {
        emitter.send(SseEmitter.event().name("message").data(payload));
    }

    private PricingResult getResultByTaskId(Long taskId) {
        LambdaQueryWrapper<PricingResult> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(PricingResult::getTaskId, taskId).last("LIMIT 1");
        return resultMapper.selectOne(wrapper);
    }

    private long resolvePollIntervalMs() {
        if (streamPollIntervalMs < 100L) {
            return 100L;
        }
        return streamPollIntervalMs;
    }

    private int resolveDisplayOrder(AgentRunLog item) {
        if (item.getDisplayOrder() != null) {
            return item.getDisplayOrder();
        }
        return item.getSpeakOrder() == null ? 0 : item.getSpeakOrder();
    }

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

    private Map<String, Object> parseJsonObject(String json) {
        if (json == null || json.isBlank()) {
            return Map.of();
        }
        try {
            return objectMapper.readValue(json, new TypeReference<Map<String, Object>>() {
            });
        } catch (Exception ignore) {
            return Map.of();
        }
    }

    private static String resolveExecuteStrategy(PricingResult result) {
        return MANUAL_REVIEW_STRATEGY;
    }

    private static Map<String, Object> normalizeSuggestionStrategy(Map<String, Object> suggestion) {
        if (suggestion == null || suggestion.isEmpty()) {
            return suggestion;
        }
        Map<String, Object> normalized = new LinkedHashMap<>(suggestion);
        if (normalized.containsKey("strategy")) {
            normalized.put("strategy", MANUAL_REVIEW_STRATEGY);
        }
        return normalized;
    }

    private static BigDecimal scaleMoney(BigDecimal value) {
        if (value == null) {
            return BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
        }
        return value.setScale(2, RoundingMode.HALF_UP);
    }

    private static String nullToEmpty(String value) {
        return value == null ? "" : value;
    }
}
