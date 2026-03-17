package com.example.pricing.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.example.pricing.common.Result;
import com.example.pricing.entity.SysConfig;
import com.example.pricing.mapper.SysConfigMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/config")
@RequiredArgsConstructor
@CrossOrigin(origins = "*")
public class ConfigController {

    private final SysConfigMapper configMapper;
    private final JdbcTemplate jdbcTemplate;

    @jakarta.annotation.PostConstruct
    public void ensureSysConfigTable() {
        jdbcTemplate.execute("""
                CREATE TABLE IF NOT EXISTS sys_config (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    config_key VARCHAR(100) NOT NULL UNIQUE,
                    config_value TEXT,
                    description VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
                """);
    }

    @GetMapping("/all")
    public Result<Map<String, String>> getAllConfigs() {
        List<SysConfig> configs = configMapper.selectList(null);
        Map<String, String> map = configs.stream()
                .collect(Collectors.toMap(SysConfig::getConfigKey, SysConfig::getConfigValue));
        return Result.success(map);
    }

    @PostMapping("/update")
    public Result<Void> updateConfigs(@RequestBody Map<String, String> configs) {
        configs.forEach((key, value) -> {
            LambdaQueryWrapper<SysConfig> wrapper = new LambdaQueryWrapper<>();
            wrapper.eq(SysConfig::getConfigKey, key);
            SysConfig config = configMapper.selectOne(wrapper);

            if (config != null) {
                config.setConfigValue(value);
                configMapper.updateById(config);
            } else {
                config = new SysConfig();
                config.setConfigKey(key);
                config.setConfigValue(value);
                configMapper.insert(config);
            }
        });
        return Result.success(null);
    }
}
