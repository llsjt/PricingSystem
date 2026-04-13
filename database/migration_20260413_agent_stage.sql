SET NAMES utf8mb4;

ALTER TABLE agent_run_log
  ADD COLUMN stage VARCHAR(20) NOT NULL DEFAULT 'completed'
  COMMENT '卡片阶段: running=正在分析, completed=已完成'
  AFTER display_order;
