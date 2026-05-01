package com.example.pricing.service;

import com.example.pricing.entity.AgentRunLog;
import com.example.pricing.entity.PricingTask;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class EffectiveAgentTimelineProjector {

    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();
    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {
    };

    public List<ProjectedAgentLog> project(PricingTask task, List<AgentRunLog> allLogs) {
        if (allLogs == null || allLogs.isEmpty()) {
            return List.of();
        }

        String currentExecutionId = normalizeExecutionId(task == null ? null : task.getCurrentExecutionId());
        if (currentExecutionId == null) {
            return projectWithoutCurrentExecution(task, allLogs);
        }

        Map<Integer, List<AgentRunLog>> logsByOrder = groupByDisplayOrder(allLogs);
        int effectiveRunAttempt = resolveCurrentRunAttempt(task, allLogs, currentExecutionId);
        List<ProjectedAgentLog> projected = new ArrayList<>();
        for (Map.Entry<Integer, List<AgentRunLog>> entry : logsByOrder.entrySet()) {
            int displayOrder = entry.getKey();
            List<AgentRunLog> sameOrderLogs = entry.getValue();

            AgentRunLog currentLog = latestForExecution(sameOrderLogs, currentExecutionId);
            if (currentLog != null) {
                projected.add(ProjectedAgentLog.fresh(currentLog));
                continue;
            }

            if (!canReplayFromHistory(displayOrder)) {
                continue;
            }

            AgentRunLog replayableHistory = latestReplayableHistory(sameOrderLogs, currentExecutionId);
            if (replayableHistory != null) {
                projected.add(ProjectedAgentLog.replayed(replayableHistory, effectiveRunAttempt));
            }
        }
        return projected;
    }

    private List<ProjectedAgentLog> projectWithoutCurrentExecution(PricingTask task, List<AgentRunLog> allLogs) {
        if (isTerminalStatus(task)) {
            int latestRunAttempt = allLogs.stream()
                    .map(this::resolveRunAttempt)
                    .max(Integer::compareTo)
                    .orElse(0);
            return groupByDisplayOrder(allLogs).values().stream()
                    .map(logs -> latestForRunAttempt(logs, latestRunAttempt))
                    .filter(log -> log != null)
                    .map(ProjectedAgentLog::fresh)
                    .toList();
        }
        return groupByDisplayOrder(allLogs).values().stream()
                .map(this::latestLog)
                .filter(log -> log != null)
                .map(ProjectedAgentLog::fresh)
                .toList();
    }

    private Map<Integer, List<AgentRunLog>> groupByDisplayOrder(List<AgentRunLog> allLogs) {
        Map<Integer, List<AgentRunLog>> grouped = new LinkedHashMap<>();
        allLogs.stream()
                .filter(log -> resolveDisplayOrder(log) > 0)
                .sorted(Comparator.comparingInt(this::resolveDisplayOrder).thenComparingLong(this::sortKey))
                .forEach(log -> grouped.computeIfAbsent(resolveDisplayOrder(log), ignored -> new ArrayList<>()).add(log));
        return grouped;
    }

    private AgentRunLog latestForExecution(List<AgentRunLog> logs, String executionId) {
        return logs.stream()
                .filter(log -> executionId.equals(normalizeExecutionId(log.getExecutionId())))
                .max(Comparator.comparingLong(this::sortKey))
                .orElse(null);
    }

    private AgentRunLog latestReplayableHistory(List<AgentRunLog> logs, String currentExecutionId) {
        return logs.stream()
                .filter(log -> !currentExecutionId.equals(normalizeExecutionId(log.getExecutionId())))
                .filter(this::isReplayableCompleted)
                .max(Comparator.comparingLong(this::sortKey))
                .orElse(null);
    }

    private AgentRunLog latestForRunAttempt(List<AgentRunLog> logs, int runAttempt) {
        return logs.stream()
                .filter(log -> resolveRunAttempt(log) == runAttempt)
                .max(Comparator.comparingLong(this::sortKey))
                .orElse(null);
    }

    private AgentRunLog latestLog(List<AgentRunLog> logs) {
        return logs.stream().max(Comparator.comparingLong(this::sortKey)).orElse(null);
    }

    private boolean canReplayFromHistory(int displayOrder) {
        return displayOrder >= 1 && displayOrder <= 3;
    }

    private int resolveCurrentRunAttempt(PricingTask task, List<AgentRunLog> allLogs, String currentExecutionId) {
        Integer currentLogAttempt = allLogs.stream()
                .filter(log -> currentExecutionId.equals(normalizeExecutionId(log.getExecutionId())))
                .map(this::resolveRunAttempt)
                .max(Integer::compareTo)
                .orElse(null);
        if (currentLogAttempt != null) {
            return currentLogAttempt;
        }
        if (task != null && task.getRetryCount() != null) {
            return Math.max(task.getRetryCount(), 0);
        }
        return 0;
    }

    private boolean isReplayableCompleted(AgentRunLog log) {
        return "completed".equals(normalizeStage(log)) && hasReplayableRawOutput(log.getRawOutputJson());
    }

    private boolean hasReplayableRawOutput(String rawOutputJson) {
        Map<String, Object> rawOutput = parseJsonObject(rawOutputJson);
        return rawOutput != null && !rawOutput.isEmpty();
    }

    private Map<String, Object> parseJsonObject(String json) {
        if (json == null || json.isBlank()) {
            return Map.of();
        }
        try {
            Map<String, Object> parsed = OBJECT_MAPPER.readValue(json, MAP_TYPE);
            return parsed == null ? Map.of() : parsed;
        } catch (Exception ignore) {
            return Map.of();
        }
    }

    private String normalizeStage(AgentRunLog log) {
        boolean suggestionError = hasSuggestionError(log == null ? null : log.getSuggestionJson());
        String stage = log == null ? null : log.getStage();
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

    private boolean hasSuggestionError(String suggestionJson) {
        if (suggestionJson == null || suggestionJson.isBlank()) {
            return false;
        }
        try {
            Map<String, Object> suggestion = OBJECT_MAPPER.readValue(suggestionJson, MAP_TYPE);
            return Boolean.TRUE.equals(suggestion.get("error"));
        } catch (Exception ignore) {
            return false;
        }
    }

    private boolean isTerminalStatus(PricingTask task) {
        String status = String.valueOf(task == null ? null : task.getTaskStatus()).toUpperCase();
        return "COMPLETED".equals(status)
                || "MANUAL_REVIEW".equals(status)
                || "FAILED".equals(status)
                || "CANCELLED".equals(status);
    }

    private int resolveDisplayOrder(AgentRunLog log) {
        if (log == null) {
            return 0;
        }
        if (log.getDisplayOrder() != null) {
            return log.getDisplayOrder();
        }
        return log.getSpeakOrder() == null ? 0 : log.getSpeakOrder();
    }

    private int resolveRunAttempt(AgentRunLog log) {
        return log == null || log.getRunAttempt() == null ? 0 : log.getRunAttempt();
    }

    private long sortKey(AgentRunLog log) {
        if (log != null && log.getId() != null) {
            return log.getId();
        }
        return Long.MIN_VALUE;
    }

    private String normalizeExecutionId(String executionId) {
        if (executionId == null || executionId.isBlank()) {
            return null;
        }
        return executionId;
    }

    public record ProjectedAgentLog(
            AgentRunLog log,
            Integer runAttempt,
            boolean replayed,
            Long sourceLogId,
            String sourceExecutionId,
            Integer sourceRunAttempt
    ) {
        public static ProjectedAgentLog fresh(AgentRunLog log) {
            return new ProjectedAgentLog(log, log == null || log.getRunAttempt() == null ? 0 : log.getRunAttempt(), false, null, null, null);
        }

        public static ProjectedAgentLog replayed(AgentRunLog log, int effectiveRunAttempt) {
            Integer runAttempt = log == null ? null : log.getRunAttempt();
            return new ProjectedAgentLog(
                    log,
                    effectiveRunAttempt,
                    true,
                    log == null ? null : log.getId(),
                    log == null ? null : log.getExecutionId(),
                    runAttempt
            );
        }
    }
}
