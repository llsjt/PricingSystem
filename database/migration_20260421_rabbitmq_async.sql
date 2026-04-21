SET NAMES utf8mb4;

ALTER TABLE pricing_task
    ADD COLUMN consumer_retry_count INT NOT NULL DEFAULT 0 COMMENT 'RabbitMQ 消费层重试次数' AFTER retry_count,
    ADD COLUMN current_execution_id VARCHAR(64) DEFAULT NULL COMMENT '当前占用执行 id，用于 execution fencing' AFTER consumer_retry_count,
    ADD INDEX idx_pricing_task_execution (current_execution_id),
    ADD INDEX idx_pricing_task_status_created (task_status, created_at);

ALTER TABLE agent_run_log
    ADD COLUMN execution_id VARCHAR(64) DEFAULT NULL COMMENT '产生该日志的 execution id' AFTER task_id;

ALTER TABLE pricing_result
    ADD COLUMN execution_id VARCHAR(64) DEFAULT NULL COMMENT '产生该结果的 execution id' AFTER task_id;
