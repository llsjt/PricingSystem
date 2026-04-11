SET NAMES utf8mb4;

ALTER TABLE sys_user
  ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'USER' COMMENT '用户角色' AFTER status,
  ADD COLUMN token_version INT NOT NULL DEFAULT 0 COMMENT '令牌版本号' AFTER role;

UPDATE sys_user
SET role = CASE
    WHEN LOWER(COALESCE(NULLIF(account, ''), username)) = 'admin' OR LOWER(COALESCE(username, '')) = 'admin' THEN 'ADMIN'
    WHEN role IS NULL OR role = '' THEN 'USER'
    ELSE role
  END,
  token_version = COALESCE(token_version, 0);

ALTER TABLE pricing_task
  MODIFY COLUMN task_status VARCHAR(20) NOT NULL DEFAULT 'QUEUED' COMMENT '任务状态',
  ADD COLUMN requested_by_user_id BIGINT NULL COMMENT '发起用户ID' AFTER task_status,
  ADD COLUMN trace_id VARCHAR(64) NULL COMMENT '链路追踪ID' AFTER requested_by_user_id,
  ADD COLUMN idempotency_key VARCHAR(128) NULL COMMENT '幂等键' AFTER trace_id,
  ADD COLUMN retry_count INT NOT NULL DEFAULT 0 COMMENT '重试次数' AFTER idempotency_key,
  ADD COLUMN failure_reason VARCHAR(255) NULL COMMENT '失败原因' AFTER retry_count,
  ADD COLUMN started_at DATETIME NULL COMMENT '开始时间' AFTER failure_reason,
  ADD COLUMN completed_at DATETIME NULL COMMENT '完成时间' AFTER started_at,
  ADD KEY idx_pricing_task_trace_id (trace_id),
  ADD KEY idx_pricing_task_idempotency_key (idempotency_key),
  ADD KEY idx_pricing_task_requested_user (requested_by_user_id);

UPDATE pricing_task
SET task_status = 'QUEUED'
WHERE task_status = 'PENDING';

ALTER TABLE pricing_result
  ADD COLUMN review_required TINYINT NOT NULL DEFAULT 1 COMMENT '是否需要人工审核' AFTER result_summary,
  ADD COLUMN applied_previous_price DECIMAL(10,2) NULL COMMENT '应用前价格' AFTER review_required,
  ADD COLUMN applied_at DATETIME NULL COMMENT '应用时间' AFTER applied_previous_price,
  ADD COLUMN applied_by_user_id BIGINT NULL COMMENT '应用操作人ID' AFTER applied_at;

CREATE TABLE IF NOT EXISTS auth_refresh_session (
  id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '刷新会话ID',
  user_id BIGINT NOT NULL COMMENT '用户ID',
  token_hash CHAR(64) NOT NULL COMMENT '刷新令牌哈希',
  expires_at DATETIME NOT NULL COMMENT '过期时间',
  revoked_at DATETIME NULL COMMENT '撤销时间',
  last_used_at DATETIME NULL COMMENT '最后使用时间',
  ip_address VARCHAR(64) NULL COMMENT '客户端IP',
  user_agent VARCHAR(255) NULL COMMENT '客户端标识',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  UNIQUE KEY uk_auth_refresh_session_token_hash (token_hash),
  KEY idx_auth_refresh_session_user_id (user_id),
  KEY idx_auth_refresh_session_expires_at (expires_at),
  CONSTRAINT fk_auth_refresh_session_user FOREIGN KEY (user_id) REFERENCES sys_user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='刷新令牌会话表';

CREATE TABLE IF NOT EXISTS login_audit_log (
  id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '登录审计ID',
  user_id BIGINT NULL COMMENT '用户ID',
  username VARCHAR(50) NULL COMMENT '登录用户名',
  ip_address VARCHAR(64) NULL COMMENT '客户端IP',
  user_agent VARCHAR(255) NULL COMMENT '客户端标识',
  login_status VARCHAR(20) NOT NULL COMMENT '登录结果状态',
  failure_reason VARCHAR(255) NULL COMMENT '失败原因',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  KEY idx_login_audit_log_user_id (user_id),
  KEY idx_login_audit_log_username (username),
  KEY idx_login_audit_log_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='登录审计日志表';
