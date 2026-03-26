package com.example.pricing.controller;

import com.example.pricing.common.Result;
import org.springframework.web.bind.annotation.*;

import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Properties;

@RestController
@RequestMapping("/api/config")
@CrossOrigin(origins = "*")
public class ConfigController {

    private final Path configPath = Paths.get("runtime", "app-config.properties");

    @GetMapping("/all")
    public Result<Map<String, String>> getAllConfigs() {
        try {
            return Result.success(readConfig());
        } catch (IOException e) {
            return Result.error("读取配置失败: " + e.getMessage());
        }
    }

    @PostMapping("/update")
    public Result<Void> updateConfigs(@RequestBody Map<String, String> configs) {
        try {
            Map<String, String> current = readConfig();
            current.putAll(configs);
            writeConfig(current);
            return Result.success();
        } catch (IOException e) {
            return Result.error("保存配置失败: " + e.getMessage());
        }
    }

    private Map<String, String> readConfig() throws IOException {
        ensureConfigFile();
        Properties properties = new Properties();
        try (InputStream inputStream = Files.newInputStream(configPath)) {
            properties.load(inputStream);
        }
        Map<String, String> result = new LinkedHashMap<>();
        for (String key : properties.stringPropertyNames()) {
            result.put(key, properties.getProperty(key, ""));
        }
        result.putIfAbsent("DASHSCOPE_API_KEY", "");
        result.putIfAbsent("AGENT_MODEL", "qwen-plus");
        return result;
    }

    private void writeConfig(Map<String, String> config) throws IOException {
        ensureConfigFile();
        Properties properties = new Properties();
        properties.putAll(config);
        try (OutputStream outputStream = Files.newOutputStream(configPath)) {
            properties.store(outputStream, "local runtime config");
        }
    }

    private void ensureConfigFile() throws IOException {
        if (Files.notExists(configPath.getParent())) {
            Files.createDirectories(configPath.getParent());
        }
        if (Files.notExists(configPath)) {
            Files.createFile(configPath);
        }
    }
}
