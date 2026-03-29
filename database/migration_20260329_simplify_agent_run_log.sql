USE `pricing_system2.0`;
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

ALTER TABLE agent_run_log
  CHANGE COLUMN agent_name role_name VARCHAR(50) NOT NULL COMMENT '角色名',
  CHANGE COLUMN run_order speak_order INT NOT NULL COMMENT '发言顺序',
  CHANGE COLUMN output_summary thought_content TEXT NULL COMMENT '思考内容';

UPDATE agent_run_log
SET thought_content = CONCAT_WS(
  '\n',
  NULLIF(thought_content, ''),
  CASE WHEN run_status IS NOT NULL AND UPPER(run_status) <> 'SUCCESS' THEN CONCAT('[status] ', run_status) ELSE NULL END,
  CASE WHEN suggested_price IS NOT NULL THEN CONCAT('[suggested_price] ', suggested_price) ELSE NULL END,
  CASE WHEN predicted_profit IS NOT NULL THEN CONCAT('[predicted_profit] ', predicted_profit) ELSE NULL END,
  CASE WHEN confidence_score IS NOT NULL THEN CONCAT('[confidence] ', confidence_score) ELSE NULL END,
  CASE WHEN risk_level IS NOT NULL AND risk_level <> '' THEN CONCAT('[risk_level] ', risk_level) ELSE NULL END,
  CASE WHEN need_manual_review = 1 THEN '[manual_review] true' ELSE NULL END,
  CASE WHEN error_message IS NOT NULL AND error_message <> '' THEN CONCAT('[error] ', error_message) ELSE NULL END
);

ALTER TABLE agent_run_log
  DROP COLUMN agent_code,
  DROP COLUMN run_status,
  DROP COLUMN input_summary,
  DROP COLUMN output_payload,
  DROP COLUMN suggested_price,
  DROP COLUMN predicted_profit,
  DROP COLUMN confidence_score,
  DROP COLUMN risk_level,
  DROP COLUMN need_manual_review,
  DROP COLUMN error_message;

ALTER TABLE agent_run_log
  MODIFY COLUMN created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录时间';

ALTER TABLE agent_run_log
  DROP INDEX idx_task_order,
  ADD INDEX idx_task_order (task_id, speak_order);

SET FOREIGN_KEY_CHECKS = 1;
