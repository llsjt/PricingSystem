SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS schema_migration_history (
  version VARCHAR(128) PRIMARY KEY COMMENT '迁移版本',
  checksum CHAR(64) NOT NULL COMMENT '校验值（SHA256）',
  description VARCHAR(255) NOT NULL COMMENT '迁移说明',
  applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '应用时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据库迁移历史表';

ALTER TABLE pricing_task
  ADD COLUMN strategy_goal VARCHAR(50) NOT NULL DEFAULT 'MAX_PROFIT' COMMENT '策略目标' AFTER suggested_max_price,
  ADD COLUMN constraint_text VARCHAR(1000) NULL COMMENT '约束条件文本' AFTER strategy_goal;

UPDATE pricing_task
SET strategy_goal = COALESCE(NULLIF(strategy_goal, ''), 'MAX_PROFIT'),
    constraint_text = COALESCE(constraint_text, '');

INSERT INTO schema_migration_history (version, checksum, description, applied_at)
SELECT 'migration_20260408_task_recovery',
       REPEAT('0', 64),
       'persist task payload for queue recovery',
       CURRENT_TIMESTAMP
WHERE NOT EXISTS (
    SELECT 1 FROM schema_migration_history WHERE version = 'migration_20260408_task_recovery'
);
