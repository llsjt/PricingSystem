-- Track retry rounds for Agent card logs.
SET NAMES utf8mb4;

ALTER TABLE agent_run_log
  ADD COLUMN run_attempt INT NOT NULL DEFAULT 0 COMMENT 'Agent执行轮次，从0开始，对应任务retry_count' AFTER stage;

ALTER TABLE agent_run_log
  ADD INDEX idx_task_run_attempt_display_order (task_id, run_attempt, display_order);
