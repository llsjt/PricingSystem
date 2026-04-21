package com.example.pricing.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.pricing.dto.TaskProgressEvent;
import com.example.pricing.entity.AgentRunLog;
import com.example.pricing.entity.PricingResult;
import com.example.pricing.entity.PricingTask;
import com.example.pricing.mapper.AgentRunLogMapper;
import com.example.pricing.mapper.PricingResultMapper;
import com.example.pricing.mapper.PricingTaskMapper;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

@Service
@RequiredArgsConstructor
public class PricingTaskStreamService {

    private static final String SCHEMA_VERSION = "1.0.0";
    private static final String CHANNEL = "pricing.task.card";
    private static final String MANUAL_REVIEW_STRATEGY = "人工审核";
    private static final int EXPECTED_AGENT_CARD_COUNT = 4;
    private static final ObjectMapper STAGE_OBJECT_MAPPER = new ObjectMapper();

    private final PricingTaskMapper taskMapper;
    private final PricingResultMapper resultMapper;
    private final AgentRunLogMapper logMapper;
    private final DecisionTaskService decisionTaskService;
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final Map<Long, CopyOnWriteArrayList<SseEmitter>> emitters = new ConcurrentHashMap<>();

    public SseEmitter streamTask(Long taskId, Long userId) {
        decisionTaskService.getTaskDetail(taskId, userId);
        SseEmitter emitter = new SseEmitter(0L);
        emitter.onCompletion(() -> unregister(taskId, emitter));
        emitter.onTimeout(() -> unregister(taskId, emitter));
        emitSnapshot(taskId, emitter);
        register(taskId, emitter);
        return emitter;
    }

    public void handleProgressEvent(TaskProgressEvent event) {
        if (event == null || event.taskId() == null) {
            return;
        }
        if (!isCurrentExecution(event.taskId(), event.executionId())) {
            return;
        }
        for (Map<String, Object> payload : payloadsForEvent(event)) {
            for (SseEmitter emitter : emitters.getOrDefault(event.taskId(), new CopyOnWriteArrayList<>())) {
                try {
                    send(emitter, payload);
                } catch (IOException ex) {
                    unregister(event.taskId(), emitter);
                }
            }
        }
    }

    void register(Long taskId, SseEmitter emitter) {
        emitters.computeIfAbsent(taskId, ignored -> new CopyOnWriteArrayList<>()).add(emitter);
    }

    void unregister(Long taskId, SseEmitter emitter) {
        CopyOnWriteArrayList<SseEmitter> registered = emitters.get(taskId);
        if (registered == null) {
            return;
        }
        registered.remove(emitter);
        if (registered.isEmpty()) {
            emitters.remove(taskId);
        }
    }

    private void emitSnapshot(Long taskId, SseEmitter emitter) {
        try {
            PricingTask task = taskMapper.selectById(taskId);
            if (task == null) {
                send(emitter, baseMessage(taskId, "task_failed", Map.of("message", "task not found", "status", "FAILED")));
                return;
            }

            send(emitter, baseMessage(taskId, "task_started", Map.of("status", task.getTaskStatus())));

            LambdaQueryWrapper<AgentRunLog> logWrapper = new LambdaQueryWrapper<>();
            logWrapper.eq(AgentRunLog::getTaskId, taskId).orderByAsc(AgentRunLog::getId);
            List<AgentRunLog> logs = logMapper.selectList(logWrapper);
            for (AgentRunLog logItem : logs) {
                send(emitter, toAgentCard(taskId, logItem));
            }

            PricingResult result = getResultByTaskId(taskId);
            int completedCardCount = (int) logs.stream().filter(PricingTaskStreamService::isCompletedAgentCard).count();
            if (shouldEmitCompletedEvent(task, result, completedCardCount)) {
                send(emitter, baseMessage(taskId, "task_completed", Map.of(
                        "status", normalizeStatus(task),
                        "result", buildResultPayload(result)
                )));
                return;
            }

            if (shouldEmitTerminalFailure(task, result)) {
                send(emitter, baseMessage(taskId, "task_failed", Map.of(
                        "message", resolveTerminalMessage(task),
                        "status", normalizeStatus(task)
                )));
            }
        } catch (Exception ex) {
            try {
                send(emitter, baseMessage(taskId, "task_failed", Map.of("message", resolveExceptionMessage(ex), "status", "FAILED")));
            } catch (IOException ignore) {
            }
        }
    }

    private List<Map<String, Object>> payloadsForEvent(TaskProgressEvent event) {
        String eventType = String.valueOf(event.eventType()).trim().toUpperCase();
        Long taskId = event.taskId();
        return switch (eventType) {
            case "TASK_STARTED" -> List.of(baseMessage(taskId, "task_started", Map.of("status", resolveTaskStatus(taskId))));
            case "AGENT_CARD_RUNNING", "AGENT_CARD_COMPLETED" -> {
                AgentRunLog log = findLatestAgentLog(taskId, agentNameFromPayload(event.payload()));
                yield log == null ? List.of() : List.of(toAgentCard(taskId, log));
            }
            case "TASK_COMPLETED", "TASK_MANUAL_REVIEW" -> {
                PricingTask task = taskMapper.selectById(taskId);
                PricingResult result = getResultByTaskId(taskId);
                if (task == null || result == null) {
                    yield List.of();
                }
                yield List.of(baseMessage(taskId, "task_completed", Map.of(
                        "status", normalizeStatus(task),
                        "result", buildResultPayload(result)
                )));
            }
            case "TASK_FAILED" -> {
                PricingTask task = taskMapper.selectById(taskId);
                if (task == null) {
                    yield List.of(baseMessage(taskId, "task_failed", Map.of("message", "task not found", "status", "FAILED")));
                }
                yield List.of(baseMessage(taskId, "task_failed", Map.of(
                        "message", resolveTerminalMessage(task),
                        "status", normalizeStatus(task)
                )));
            }
            default -> List.of();
        };
    }

    private AgentRunLog findLatestAgentLog(Long taskId, String agentName) {
        LambdaQueryWrapper<AgentRunLog> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentRunLog::getTaskId, taskId);
        if (agentName != null && !agentName.isBlank()) {
            wrapper.eq(AgentRunLog::getRoleName, agentName);
        }
        wrapper.orderByDesc(AgentRunLog::getId).last("LIMIT 1");
        return logMapper.selectOne(wrapper);
    }

    private boolean isCurrentExecution(Long taskId, String executionId) {
        if (executionId == null || executionId.isBlank()) {
            return true;
        }
        PricingTask task = taskMapper.selectById(taskId);
        return task != null && executionId.equals(task.getCurrentExecutionId());
    }

    private String resolveTaskStatus(Long taskId) {
        PricingTask task = taskMapper.selectById(taskId);
        return task == null ? "FAILED" : normalizeStatus(task);
    }

    private String agentNameFromPayload(Map<String, Object> payload) {
        if (payload == null) {
            return null;
        }
        Object agentName = payload.get("agentName");
        return agentName == null ? null : String.valueOf(agentName);
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
        payload.put("runAttempt", item.getRunAttempt() == null ? 0 : item.getRunAttempt());
        String stage = normalizeLogStage(item);
        payload.put("stage", stage);
        if ("running".equals(stage)) {
            payload.put("card", Map.of(
                    "thinking", "",
                    "evidence", List.of(),
                    "suggestion", Map.of()
            ));
            return payload;
        }
        payload.put("card", buildCardPayload(
                item.getThinkingSummary() == null || item.getThinkingSummary().isBlank() ? nullToEmpty(item.getThoughtContent()) : item.getThinkingSummary(),
                parseJsonArray(item.getEvidenceJson()),
                parseJsonObject(item.getSuggestionJson()),
                item.getFinalReason()
        ));
        return payload;
    }

    static boolean isCompletedAgentCard(AgentRunLog item) {
        return "completed".equals(normalizeLogStage(item));
    }

    private static String normalizeLogStage(AgentRunLog item) {
        boolean suggestionError = hasSuggestionError(item == null ? null : item.getSuggestionJson());
        String stage = item == null ? null : item.getStage();
        if (stage == null || stage.isBlank()) {
            return suggestionError ? "failed" : "completed";
        }
        String normalized = stage.trim().toLowerCase();
        if ("running".equals(normalized) || "failed".equals(normalized)) {
            return normalized;
        }
        if (suggestionError) {
            return "failed";
        }
        return "completed";
    }

    private static boolean hasSuggestionError(String suggestionJson) {
        if (suggestionJson == null || suggestionJson.isBlank()) {
            return false;
        }
        try {
            Map<String, Object> suggestion = STAGE_OBJECT_MAPPER.readValue(
                    suggestionJson,
                    new TypeReference<Map<String, Object>>() {
                    }
            );
            return Boolean.TRUE.equals(suggestion.get("error"));
        } catch (Exception ignore) {
            return false;
        }
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
