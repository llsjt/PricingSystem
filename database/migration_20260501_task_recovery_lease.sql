SET NAMES utf8mb4;

ALTER TABLE pricing_task
    ADD COLUMN last_heartbeat_at DATETIME DEFAULT NULL COMMENT '当前执行租约心跳时间' AFTER current_execution_id,
    ADD COLUMN recovery_count INT NOT NULL DEFAULT 0 COMMENT '自动恢复次数' AFTER last_heartbeat_at,
    ADD COLUMN last_recovered_at DATETIME DEFAULT NULL COMMENT '最近自动恢复时间' AFTER recovery_count,
    ADD INDEX idx_pricing_task_status_heartbeat (task_status, last_heartbeat_at);
