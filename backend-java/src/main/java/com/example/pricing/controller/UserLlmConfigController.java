package com.example.pricing.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.pricing.common.AesGcmUtil;
import com.example.pricing.common.Result;
import com.example.pricing.dto.UserLlmConfigDTO;
import com.example.pricing.entity.UserLlmConfig;
import com.example.pricing.mapper.UserLlmConfigMapper;
import com.example.pricing.vo.UserLlmConfigVO;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.time.LocalDateTime;

/**
 * 用户 LLM 配置管理控制器，提供查询、保存、删除和连接验证能力。
 */
@RestController
@RequestMapping("/api/user/llm-config")
@RequiredArgsConstructor
@Slf4j
public class UserLlmConfigController {

    private final UserLlmConfigMapper userLlmConfigMapper;

    @Value("${app.llm-key-encryption-secret:}")
    private String encryptionSecret;

    /**
     * 查询当前用户的 LLM 配置（API Key 仅返回脱敏预览）。
     */
    @GetMapping
    public Result<UserLlmConfigVO> getConfig(HttpServletRequest request) {
        try {
            Long userId = getCurrentUserId(request);
            UserLlmConfig config = userLlmConfigMapper.selectOne(
                    new LambdaQueryWrapper<UserLlmConfig>().eq(UserLlmConfig::getUserId, userId)
            );
            if (config == null) {
                return Result.success(null);
            }

            UserLlmConfigVO vo = new UserLlmConfigVO();
            vo.setBaseUrl(config.getLlmBaseUrl());
            vo.setModel(config.getLlmModel());
            vo.setHasApiKey(config.getLlmApiKeyEnc() != null && !config.getLlmApiKeyEnc().isEmpty());
            if (vo.isHasApiKey()) {
                String rawKey = AesGcmUtil.decrypt(config.getLlmApiKeyEnc(), encryptionSecret);
                vo.setApiKeyPreview(AesGcmUtil.maskApiKey(rawKey));
                vo.setApiKey(rawKey);
            }
            return Result.success(vo);
        } catch (Exception e) {
            log.error("get llm config failed", e);
            return Result.error(e.getMessage());
        }
    }

    /**
     * 保存或更新当前用户的 LLM 配置。
     */
    @PutMapping
    public Result<Void> saveConfig(@RequestBody UserLlmConfigDTO dto, HttpServletRequest request) {
        try {
            if (isBlank(dto.getBaseUrl()) || isBlank(dto.getModel())) {
                return Result.error("baseUrl、model 不能为空");
            }

            Long userId = getCurrentUserId(request);

            UserLlmConfig existing = userLlmConfigMapper.selectOne(
                    new LambdaQueryWrapper<UserLlmConfig>().eq(UserLlmConfig::getUserId, userId)
            );

            if (existing != null) {
                // 仅当用户提供了新 Key 时才更新加密字段，否则保留原值
                if (!isBlank(dto.getApiKey())) {
                    existing.setLlmApiKeyEnc(AesGcmUtil.encrypt(dto.getApiKey(), encryptionSecret));
                }
                existing.setLlmBaseUrl(dto.getBaseUrl());
                existing.setLlmModel(dto.getModel());
                existing.setUpdatedAt(LocalDateTime.now());
                userLlmConfigMapper.updateById(existing);
            } else {
                if (isBlank(dto.getApiKey())) {
                    return Result.error("首次配置时 apiKey 不能为空");
                }
                UserLlmConfig config = new UserLlmConfig();
                config.setUserId(userId);
                config.setLlmApiKeyEnc(AesGcmUtil.encrypt(dto.getApiKey(), encryptionSecret));
                config.setLlmBaseUrl(dto.getBaseUrl());
                config.setLlmModel(dto.getModel());
                config.setCreatedAt(LocalDateTime.now());
                config.setUpdatedAt(LocalDateTime.now());
                userLlmConfigMapper.insert(config);
            }

            return Result.success();
        } catch (Exception e) {
            log.error("save llm config failed", e);
            return Result.error(e.getMessage());
        }
    }

    /**
     * 删除当前用户的 LLM 配置。
     */
    @DeleteMapping
    public Result<Void> deleteConfig(HttpServletRequest request) {
        try {
            Long userId = getCurrentUserId(request);
            userLlmConfigMapper.delete(
                    new LambdaQueryWrapper<UserLlmConfig>().eq(UserLlmConfig::getUserId, userId)
            );
            return Result.success();
        } catch (Exception e) {
            log.error("delete llm config failed", e);
            return Result.error(e.getMessage());
        }
    }

    /**
     * 验证用户提供的 LLM 配置是否可连通（向 baseUrl 发送轻量级请求）。
     */
    @PostMapping("/verify")
    public Result<String> verifyConfig(@RequestBody UserLlmConfigDTO dto, HttpServletRequest request) {
        try {
            getCurrentUserId(request); // ensure authenticated

            if (isBlank(dto.getApiKey()) || isBlank(dto.getBaseUrl()) || isBlank(dto.getModel())) {
                return Result.error("apiKey、baseUrl、model 均不能为空");
            }

            String url = dto.getBaseUrl().replaceAll("/+$", "") + "/chat/completions";
            String body = """
                    {
                      "model": "%s",
                      "max_tokens": 1,
                      "messages": [{"role": "user", "content": "hi"}]
                    }
                    """.formatted(dto.getModel());

            HttpClient client = HttpClient.newBuilder()
                    .connectTimeout(Duration.ofSeconds(5))
                    .build();

            java.net.http.HttpRequest httpRequest = java.net.http.HttpRequest.newBuilder()
                    .uri(URI.create(url))
                    .timeout(Duration.ofSeconds(10))
                    .header("Content-Type", "application/json")
                    .header("Authorization", "Bearer " + dto.getApiKey())
                    .POST(java.net.http.HttpRequest.BodyPublishers.ofString(body))
                    .build();

            HttpResponse<String> response = client.send(httpRequest, HttpResponse.BodyHandlers.ofString());

            if (response.statusCode() >= 200 && response.statusCode() < 300) {
                return Result.success("连接验证成功");
            } else {
                return Result.error("连接验证失败: HTTP " + response.statusCode() + " - " + response.body());
            }
        } catch (Exception e) {
            log.error("verify llm config failed", e);
            return Result.error("连接验证失败: " + e.getMessage());
        }
    }

    private Long getCurrentUserId(HttpServletRequest request) {
        Long userId = (Long) request.getAttribute("currentUserId");
        if (userId == null) {
            throw new IllegalStateException("请先登录");
        }
        return userId;
    }

    private boolean isBlank(String s) {
        return s == null || s.trim().isEmpty();
    }
}
