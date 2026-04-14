SET NAMES utf8mb4;

ALTER TABLE agent_run_log
  MODIFY COLUMN stage VARCHAR(20) NOT NULL DEFAULT 'completed'
  COMMENT '卡片阶段: running=正在分析, completed=已完成, failed=执行失败';

UPDATE agent_run_log
SET stage = 'failed'
WHERE stage <> 'failed'
  AND (
    JSON_UNQUOTE(JSON_EXTRACT(suggestion_json, '$.error')) = 'true'
    OR thinking_summary LIKE 'Agent 执行失败:%'
    OR thought_content LIKE 'Agent 执行失败:%'
  );

UPDATE pricing_task t
LEFT JOIN pricing_result r ON r.task_id = t.id
SET t.task_status = 'FAILED'
WHERE t.task_status = 'MANUAL_REVIEW'
  AND r.id IS NULL
  AND (
    t.failure_reason IS NOT NULL
    OR EXISTS (
      SELECT 1
      FROM agent_run_log l
      WHERE l.task_id = t.id
        AND l.stage = 'failed'
    )
  );
