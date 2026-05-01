package com.example.pricing.service;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.pricing.entity.PricingTask;
import com.example.pricing.mapper.PricingTaskMapper;
import com.fasterxml.jackson.databind.MapperFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.databind.json.JsonMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.List;
import java.util.UUID;

/**
 * 定价任务复用支持服务，用于基于幂等键复用可重复利用的历史任务。
 */
@Component
@RequiredArgsConstructor
public class PricingTaskReuseSupport {

    private static final ObjectMapper CANONICAL_JSON_MAPPER = JsonMapper.builder()
            .enable(MapperFeature.SORT_PROPERTIES_ALPHABETICALLY)
            .enable(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS)
            .build();

    private static final List<String> REUSABLE_TASK_STATUSES = List.of(
            "PENDING", "QUEUED", "RUNNING", "RETRYING"
    );

    private static final List<String> FAILURE_RECOVERY_TASK_STATUSES = List.of(
            "PENDING", "QUEUED", "RUNNING", "RETRYING", "FAILED"
    );

    private final PricingTaskMapper taskMapper;

    public PricingTask findReusableTask(String idempotencyKey, Long shopId) {
        return findLatestTaskByStatuses(idempotencyKey, shopId, REUSABLE_TASK_STATUSES);
    }

    public PricingTask findRecoverableTaskAfterCreateFailure(String idempotencyKey, Long shopId) {
        return findLatestTaskByStatuses(idempotencyKey, shopId, FAILURE_RECOVERY_TASK_STATUSES);
    }

    public String buildIdempotencyKey(List<Long> productIds, String strategyGoal, String constraints, Long userId) {
        String source = String.join("|",
                String.valueOf(userId),
                String.valueOf(productIds),
                String.valueOf(strategyGoal),
                normalizeConstraints(constraints)
        );
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(digest.digest(source.getBytes(StandardCharsets.UTF_8)));
        } catch (Exception e) {
            return UUID.randomUUID().toString().replace("-", "");
        }
    }

    private String normalizeConstraints(String constraints) {
        if (constraints == null || constraints.isBlank()) {
            return "";
        }
        String trimmed = constraints.trim();
        try {
            Object value = CANONICAL_JSON_MAPPER.readValue(trimmed, Object.class);
            return CANONICAL_JSON_MAPPER.writeValueAsString(value);
        } catch (Exception e) {
            return trimmed;
        }
    }

    private PricingTask findLatestTaskByStatuses(String idempotencyKey, Long shopId, List<String> statuses) {
        if (idempotencyKey == null || idempotencyKey.isBlank() || shopId == null || statuses == null || statuses.isEmpty()) {
            return null;
        }
        LambdaQueryWrapper<PricingTask> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(PricingTask::getIdempotencyKey, idempotencyKey)
                .eq(PricingTask::getShopId, shopId)
                .in(PricingTask::getTaskStatus, statuses)
                .orderByDesc(PricingTask::getId)
                .last("LIMIT 1");
        return taskMapper.selectOne(wrapper);
    }
}
