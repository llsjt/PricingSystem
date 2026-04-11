SET NAMES utf8mb4;

-- 用户自备大模型 API Key 功能
-- 1. 新建用户 LLM 配置表（个人中心管理，Java 端加密写入）
CREATE TABLE IF NOT EXISTS user_llm_config (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id         BIGINT NOT NULL,
    llm_api_key_enc VARCHAR(512) NOT NULL COMMENT 'AES-256-GCM 加密的 API Key',
    llm_base_url    VARCHAR(255) NOT NULL COMMENT 'LLM API Base URL',
    llm_model       VARCHAR(100) NOT NULL COMMENT '模型名称',
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_user_llm_config_user (user_id),
    CONSTRAINT fk_user_llm_config_user FOREIGN KEY (user_id) REFERENCES sys_user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户LLM配置';

-- 2. pricing_task 表增加 LLM 配置列（Python 端加密存储，供任务重试时恢复 Key）
ALTER TABLE pricing_task
    ADD COLUMN llm_api_key_enc VARCHAR(512) DEFAULT NULL COMMENT 'Fernet 加密的用户 API Key（重试用）',
    ADD COLUMN llm_base_url    VARCHAR(255) DEFAULT NULL COMMENT '用户 LLM Base URL',
    ADD COLUMN llm_model       VARCHAR(100) DEFAULT NULL COMMENT '用户 LLM 模型名称';
