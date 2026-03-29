USE `pricing_system2.0`;
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- Agent 卡片化日志字段：一条记录=一个 Agent 完整卡片
ALTER TABLE agent_run_log
  ADD COLUMN thinking_summary TEXT NULL COMMENT '思考过程摘要' AFTER thought_content,
  ADD COLUMN evidence_json JSON NULL COMMENT '依据(JSON数组)' AFTER thinking_summary,
  ADD COLUMN suggestion_json JSON NULL COMMENT '建议(JSON对象)' AFTER evidence_json,
  ADD COLUMN final_reason TEXT NULL COMMENT '最终建议原因(经理Agent)' AFTER suggestion_json,
  ADD COLUMN display_order INT NULL COMMENT '卡片展示顺序(1-4)' AFTER final_reason;

-- 历史数据兼容：将旧思考内容回填到 thinking_summary
UPDATE agent_run_log
SET thinking_summary = thought_content
WHERE thinking_summary IS NULL AND thought_content IS NOT NULL;

-- 展示顺序索引，便于按固定 1-4 卡片顺序读取
ALTER TABLE agent_run_log
  ADD INDEX idx_task_display_order (task_id, display_order);

SET FOREIGN_KEY_CHECKS = 1;
