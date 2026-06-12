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

/**
 * 定价任务流服务，把数据库快照和异步进度转换成前端 SSE 消息。
 */
@Service
@RequiredArgsConstructor
public class PricingTaskStreamService {

    private static final String SCHEMA_VERSION = "1.0.0";
    private static final String CHANNEL = "pricing.task.card";
    private static final String MANUAL_REVIEW_STRATEGY = "人工审核";
    private static final ObjectMapper STAGE_OBJECT_MAPPER = new ObjectMapper();

    private final PricingTaskMapper taskMapper;
    private final PricingResultMapper resultMapper;
    private final AgentRunLogMapper logMapper;
    private final DecisionTaskService decisionTaskService;
    private final EffectiveAgentTimelineProjector effectiveAgentTimelineProjector = new EffectiveAgentTimelineProjector();
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final Map<Long, CopyOnWriteArrayList<SseEmitter>> emitters = new ConcurrentHashMap<>();

    /**
     * 创建某个任务的 SSE 连接，先推一次当前快照，再把连接注册到内存订阅表中。
     */
    public SseEmitter streamTask(Long taskId, Long userId) {
        decisionTaskService.getTaskDetail(taskId, userId);
        SseEmitter emitter = new SseEmitter(0L);
        emitter.onCompletion(() -> unregister(taskId, emitter));
        emitter.onTimeout(() -> unregister(taskId, emitter));
        emitSnapshot(taskId, emitter);
        register(taskId, emitter);
        return emitter;
    }

    /**
     * 接收异步进度事件并广播给当前在线的浏览器订阅者。
     */
    public void handleProgressEvent(TaskProgressEvent event) {
        if (event == null || event.taskId() == null) {
            return;
        }
        PricingTask task = taskMapper.selectById(event.taskId());
        if (!isTerminalProgressEvent(event.eventType()) && !isCurrentExecution(task, event.executionId())) {
            return;
        }
        for (Map<String, Object> payload : payloadsForEvent(event, task)) {
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

    /**
     * 首次建立连接时把任务状态、已有智能体卡片和最终结果一次性补发，避免前端必须从零等待。
     */
    private void emitSnapshot(Long taskId, SseEmitter emitter) {
        try {
            PricingTask task = taskMapper.selectById(taskId);
            if (task == null) {
                send(emitter, baseMessage(taskId, "task_failed", Map.of("message", "task not found", "status", "FAILED")));
                return;
            }

            send(emitter, baseMessage(taskId, "task_started", Map.of("status", task.getTaskStatus())));

            List<AgentRunLog> logs = listTaskLogs(taskId);
            List<EffectiveAgentTimelineProjector.ProjectedAgentLog> effectiveLogs =
                    effectiveAgentTimelineProjector.project(task, logs);
            for (EffectiveAgentTimelineProjector.ProjectedAgentLog logItem : effectiveLogs) {
                send(emitter, toAgentCard(taskId, logItem));
            }

            PricingResult result = getResultForTask(task);
            int completedCardCount = countCompletedCards(effectiveLogs);
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

    /**
     * 把不同来源的进度事件映射成统一的前端消息结构，保证实时流和快照结构一致。
     */
    private List<Map<String, Object>> payloadsForEvent(TaskProgressEvent event, PricingTask task) {
        String eventType = String.valueOf(event.eventType()).trim().toUpperCase();
        Long taskId = event.taskId();
        return switch (eventType) {
            case "TASK_STARTED" -> List.of(baseMessage(taskId, "task_started", Map.of("status", resolveTaskStatus(taskId))));
            case "AGENT_CARD_RUNNING", "AGENT_CARD_COMPLETED" -> {
                EffectiveAgentTimelineProjector.ProjectedAgentLog log =
                        findLatestAgentLog(taskId, task, agentNameFromPayload(event.payload()));
                yield log == null ? List.of() : List.of(toAgentCard(taskId, log));
            }
            case "TASK_COMPLETED", "TASK_MANUAL_REVIEW" -> {
                PricingResult result = getResultForTask(task);
                if (task == null) {
                    yield List.of(baseMessage(taskId, "task_failed", Map.of("message", "task not found", "status", "FAILED")));
                }
                if (shouldEmitCompletedEvent(task, result, 0)) {
                    yield List.of(baseMessage(taskId, "task_completed", Map.of(
                            "status", normalizeStatus(task),
                            "result", buildResultPayload(result)
                    )));
                }
                yield shouldEmitTerminalFailure(task, result)
                        ? List.of(baseMessage(taskId, "task_failed", Map.of(
                                "message", resolveTerminalMessage(task),
                                "status", normalizeStatus(task)
                        )))
                        : List.of();
            }
            case "TASK_FAILED" -> {
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

    private EffectiveAgentTimelineProjector.ProjectedAgentLog findLatestAgentLog(Long taskId, PricingTask task, String agentName) {
        LambdaQueryWrapper<AgentRunLog> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(AgentRunLog::getTaskId, taskId);
        if (agentName != null && !agentName.isBlank()) {
            wrapper.eq(AgentRunLog::getRoleName, agentName);
        }
        wrapper.orderByAsc(AgentRunLog::getId);
        List<AgentRunLog> logs = logMapper.selectList(wrapper);
        List<EffectiveAgentTimelineProjector.ProjectedAgentLog> effectiveLogs =
                effectiveAgentTimelineProjector.project(task, logs);
        if (effectiveLogs.isEmpty()) {
            return null;
        }
        return effectiveLogs.get(effectiveLogs.size() - 1);
    }

    private boolean isCurrentExecution(PricingTask task, String executionId) {
        if (task == null) {
            return false;
        }
        String currentExecutionId = task.getCurrentExecutionId();
        if (currentExecutionId == null || currentExecutionId.isBlank()) {
            return executionId == null || executionId.isBlank();
        }
        return currentExecutionId.equals(executionId);
    }

    private static boolean isTerminalProgressEvent(String eventType) {
        String normalized = String.valueOf(eventType).trim().toUpperCase();
        return "TASK_COMPLETED".equals(normalized)
                || "TASK_MANUAL_REVIEW".equals(normalized)
                || "TASK_FAILED".equals(normalized);
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

    private List<AgentRunLog> listTaskLogs(Long taskId) {
        LambdaQueryWrapper<AgentRunLog> logWrapper = new LambdaQueryWrapper<>();
        logWrapper.eq(AgentRunLog::getTaskId, taskId).orderByAsc(AgentRunLog::getId);
        return logMapper.selectList(logWrapper);
    }

    private int countCompletedCards(List<EffectiveAgentTimelineProjector.ProjectedAgentLog> logs) {
        return (int) logs.stream()
                .map(EffectiveAgentTimelineProjector.ProjectedAgentLog::log)
                .filter(PricingTaskStreamService::isCompletedAgentCard)
                .count();
    }

    private PricingResult getResultForTask(PricingTask task) {
        if (task == null || task.getId() == null) {
            return null;
        }
        return getResultByTaskId(task.getId());
    }

    static boolean shouldEmitCompletedEvent(PricingTask task, PricingResult result, int completedCardCount) {
        String status = normalizeStatus(task);
        return result != null
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
        if ("CANCELLED".equals(status)) {
            return "任务已取消";
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

    private static boolean isTerminalStatus(PricingTask task) {
        String status = normalizeStatus(task);
        return "COMPLETED".equals(status)
                || "MANUAL_REVIEW".equals(status)
                || "FAILED".equals(status)
                || "CANCELLED".equals(status);
    }

    /**
     * 把数据库里的单条 agent_run_log 转成前端消费的 agent_card 事件载荷。
     */
    private Map<String, Object> toAgentCard(Long taskId, AgentRunLog item) {
        return toAgentCard(taskId, EffectiveAgentTimelineProjector.ProjectedAgentLog.fresh(item));
    }

    private Map<String, Object> toAgentCard(Long taskId, EffectiveAgentTimelineProjector.ProjectedAgentLog projectedLog) {
        AgentRunLog item = projectedLog.log();
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
        payload.put("runAttempt", projectedLog.runAttempt() == null ? 0 : projectedLog.runAttempt());
        payload.put("replayed", projectedLog.replayed());
        payload.put("sourceLogId", projectedLog.sourceLogId());
        payload.put("sourceExecutionId", projectedLog.sourceExecutionId());
        payload.put("sourceRunAttempt", projectedLog.sourceRunAttempt());
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
        Map<String, Object> suggestion = parseJsonObject(item.getSuggestionJson());
        Map<String, Object> agentOpinion = extractAgentOpinion(item.getRawOutputJson());
        payload.put("card", buildCardPayload(
                item.getThinkingSummary() == null || item.getThinkingSummary().isBlank() ? nullToEmpty(item.getThoughtContent()) : item.getThinkingSummary(),
                parseJsonArray(item.getEvidenceJson()),
                suggestion,
                agentOpinion,
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
            Map<String, Object> agentOpinion,
            String reasonWhy
    ) {
        Map<String, Object> normalizedSuggestion = normalizeSuggestionStrategy(sanitizeSuggestion(suggestion));
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("thinking", thinking);
        payload.put("evidence", evidence);
        payload.put("suggestion", normalizedSuggestion);
        if (agentOpinion != null && !agentOpinion.isEmpty()) {
            payload.put("agentOpinion", agentOpinion);
        }
        payload.put("reasonWhy", reasonWhy);
        return payload;
    }

    /**
     * 任务结束时只向前端暴露结果页真正需要的字段，避免把数据库实体直接透出。
     */
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
            Map<String, Object> parsed = objectMapper.readValue(json, new TypeReference<Map<String, Object>>() {
            });
            return parsed == null ? Map.of() : parsed;
        } catch (Exception ignore) {
            return Map.of();
        }
    }

    private Map<String, Object> extractAgentOpinion(String rawOutputJson) {
        Map<String, Object> rawOutput = parseJsonObject(rawOutputJson);
        if (rawOutput == null || rawOutput.isEmpty()) {
            return Map.of();
        }
        Object agentOpinion = rawOutput.get("agentOpinion");
        if (!(agentOpinion instanceof Map<?, ?> opinionMap)) {
            return Map.of();
        }
        Map<String, Object> normalized = new LinkedHashMap<>();
        opinionMap.forEach((key, value) -> normalized.put(String.valueOf(key), value));
        return normalized;
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

    private static Map<String, Object> sanitizeSuggestion(Map<String, Object> suggestion) {
        if (suggestion == null || suggestion.isEmpty()) {
            return Map.of();
        }
        Map<String, Object> sanitized = new LinkedHashMap<>(suggestion);
        sanitized.remove("agentOpinion");
        return sanitized;
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

    private static int resolveRunAttempt(AgentRunLog item) {
        return item == null || item.getRunAttempt() == null ? 0 : item.getRunAttempt();
    }
}
