CREATE DATABASE IF NOT EXISTS `pricing_system2.0`
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE `pricing_system2.0`;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS schema_migration_history;
CREATE TABLE schema_migration_history (
    version VARCHAR(128) PRIMARY KEY COMMENT '迁移版本',
    checksum CHAR(64) NOT NULL COMMENT '校验值（SHA256）',
    description VARCHAR(255) NOT NULL COMMENT '迁移说明',
    applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '应用时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据库迁移历史';

DROP TABLE IF EXISTS login_audit_log;
DROP TABLE IF EXISTS auth_refresh_session;
DROP TABLE IF EXISTS pricing_batch_item;
DROP TABLE IF EXISTS pricing_batch;
DROP TABLE IF EXISTS pricing_result;
DROP TABLE IF EXISTS agent_run_log;
DROP TABLE IF EXISTS pricing_task;
DROP TABLE IF EXISTS traffic_promo_daily;
DROP TABLE IF EXISTS product_daily_metric;
DROP TABLE IF EXISTS product_sku;
DROP TABLE IF EXISTS product;
DROP TABLE IF EXISTS upload_batch;
DROP TABLE IF EXISTS shop;
DROP TABLE IF EXISTS sys_user;

CREATE TABLE sys_user (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '用户ID',
    username VARCHAR(50) NOT NULL COMMENT '登录用户名',
    account VARCHAR(50) NOT NULL COMMENT '账号别名',
    password VARCHAR(255) NOT NULL COMMENT '密码哈希（BCrypt）',
    email VARCHAR(100) NOT NULL COMMENT '邮箱地址',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态：1启用，0禁用',
    role VARCHAR(20) NOT NULL DEFAULT 'USER' COMMENT '用户角色',
    token_version INT NOT NULL DEFAULT 0 COMMENT '令牌版本号',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_sys_user_username (username),
    UNIQUE KEY uk_sys_user_account (account),
    UNIQUE KEY uk_sys_user_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统用户表';

CREATE TABLE shop (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '店铺ID',
    user_id BIGINT NOT NULL COMMENT '所属用户ID',
    shop_name VARCHAR(100) NOT NULL COMMENT '店铺名称',
    platform VARCHAR(20) NOT NULL DEFAULT '淘宝' COMMENT '电商平台',
    seller_nick VARCHAR(100) DEFAULT NULL COMMENT '卖家昵称',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    KEY idx_shop_user_id (user_id),
    CONSTRAINT fk_shop_user FOREIGN KEY (user_id) REFERENCES sys_user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='店铺表';

CREATE TABLE upload_batch (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '上传批次ID',
    shop_id BIGINT NOT NULL COMMENT '店铺ID',
    batch_no VARCHAR(50) NOT NULL COMMENT '批次编号',
    file_name VARCHAR(255) NOT NULL COMMENT '源文件名',
    data_type VARCHAR(50) NOT NULL COMMENT '导入数据类型',
    start_date DATE DEFAULT NULL COMMENT '源数据开始日期',
    end_date DATE DEFAULT NULL COMMENT '源数据结束日期',
    row_count INT NOT NULL DEFAULT 0 COMMENT '总行数',
    success_count INT NOT NULL DEFAULT 0 COMMENT '成功行数',
    fail_count INT NOT NULL DEFAULT 0 COMMENT '失败行数',
    upload_status VARCHAR(20) NOT NULL DEFAULT 'SUCCESS' COMMENT '批次状态',
    uploaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
    KEY idx_upload_batch_shop_id (shop_id),
    UNIQUE KEY uk_upload_batch_batch_no (batch_no),
    CONSTRAINT fk_upload_batch_shop FOREIGN KEY (shop_id) REFERENCES shop(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Excel上传批次表';

CREATE TABLE product (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '商品ID',
    shop_id BIGINT NOT NULL COMMENT '店铺ID',
    external_product_id VARCHAR(64) NOT NULL COMMENT '平台商品ID',
    product_name VARCHAR(255) DEFAULT NULL COMMENT '商品名称',
    short_title VARCHAR(100) DEFAULT NULL COMMENT '短标题',
    sub_title VARCHAR(255) DEFAULT NULL COMMENT '副标题',
    category_name VARCHAR(100) DEFAULT NULL COMMENT '类目名称',
    primary_category_name VARCHAR(100) DEFAULT NULL COMMENT '一级类目名称',
    secondary_category_name VARCHAR(100) DEFAULT NULL COMMENT '二级类目名称',
    sale_price DECIMAL(10,2) DEFAULT NULL COMMENT '当前售价',
    cost_price DECIMAL(10,2) DEFAULT NULL COMMENT '单位成本价',
    stock INT NOT NULL DEFAULT 0 COMMENT '可售库存',
    status VARCHAR(20) NOT NULL DEFAULT '出售中' COMMENT '商品状态',
    profile_status VARCHAR(20) NOT NULL DEFAULT 'COMPLETE' COMMENT '档案完整度状态',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_product_shop_external (shop_id, external_product_id),
    KEY idx_product_shop_profile_status (shop_id, profile_status),
    CONSTRAINT fk_product_shop FOREIGN KEY (shop_id) REFERENCES shop(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品表';

CREATE TABLE product_sku (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '规格主键ID',
    product_id BIGINT NOT NULL COMMENT '商品ID',
    external_sku_id VARCHAR(64) NOT NULL COMMENT '平台规格ID',
    sku_name VARCHAR(255) DEFAULT NULL COMMENT '规格名称',
    sku_attr VARCHAR(255) DEFAULT NULL COMMENT '规格属性描述',
    sale_price DECIMAL(10,2) NOT NULL COMMENT '规格售价',
    cost_price DECIMAL(10,2) NOT NULL COMMENT '规格成本价',
    stock INT NOT NULL DEFAULT 0 COMMENT '规格库存',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_product_sku_external (product_id, external_sku_id),
    CONSTRAINT fk_product_sku_product FOREIGN KEY (product_id) REFERENCES product(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品SKU表';

CREATE TABLE product_daily_metric (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '日指标ID',
    shop_id BIGINT NOT NULL COMMENT '店铺ID',
    product_id BIGINT NOT NULL COMMENT '商品ID',
    stat_date DATE NOT NULL COMMENT '统计日期',
    visitor_count INT NOT NULL DEFAULT 0 COMMENT '访客数',
    add_cart_count INT NOT NULL DEFAULT 0 COMMENT '加购人数',
    pay_buyer_count INT NOT NULL DEFAULT 0 COMMENT '支付买家数',
    pay_item_qty INT NOT NULL DEFAULT 0 COMMENT '支付件数',
    pay_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '支付金额',
    refund_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '退款金额',
    convert_rate DECIMAL(8,4) DEFAULT 0.0000 COMMENT '转化率',
    upload_batch_id BIGINT DEFAULT NULL COMMENT '上传批次ID',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    UNIQUE KEY uk_product_daily_metric_product_date (product_id, stat_date),
    KEY idx_product_daily_metric_shop_date (shop_id, stat_date),
    CONSTRAINT fk_product_daily_metric_shop FOREIGN KEY (shop_id) REFERENCES shop(id),
    CONSTRAINT fk_product_daily_metric_product FOREIGN KEY (product_id) REFERENCES product(id),
    CONSTRAINT fk_product_daily_metric_batch FOREIGN KEY (upload_batch_id) REFERENCES upload_batch(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品日指标表';

CREATE TABLE traffic_promo_daily (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '流量推广指标ID',
    shop_id BIGINT NOT NULL COMMENT '店铺ID',
    product_id BIGINT DEFAULT NULL COMMENT '商品ID',
    stat_date DATE NOT NULL COMMENT '统计日期',
    traffic_source VARCHAR(50) NOT NULL COMMENT '流量来源',
    impression_count INT NOT NULL DEFAULT 0 COMMENT '曝光量',
    click_count INT NOT NULL DEFAULT 0 COMMENT '点击量',
    visitor_count INT NOT NULL DEFAULT 0 COMMENT '访客数',
    cost_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '推广花费',
    pay_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '支付金额',
    roi DECIMAL(10,4) DEFAULT 0.0000 COMMENT '投入产出比',
    upload_batch_id BIGINT DEFAULT NULL COMMENT '上传批次ID',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    KEY idx_traffic_promo_daily_shop_date (shop_id, stat_date),
    UNIQUE KEY uk_traffic_promo_daily_product_date_source (product_id, stat_date, traffic_source),
    CONSTRAINT fk_traffic_promo_daily_shop FOREIGN KEY (shop_id) REFERENCES shop(id),
    CONSTRAINT fk_traffic_promo_daily_product FOREIGN KEY (product_id) REFERENCES product(id),
    CONSTRAINT fk_traffic_promo_daily_batch FOREIGN KEY (upload_batch_id) REFERENCES upload_batch(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='流量与推广日指标表';

CREATE TABLE pricing_task (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '定价任务ID',
    task_code VARCHAR(50) NOT NULL COMMENT '任务编码',
    shop_id BIGINT NOT NULL COMMENT '店铺ID',
    product_id BIGINT NOT NULL COMMENT '商品ID',
    sku_id BIGINT DEFAULT NULL COMMENT '规格ID',
    current_price DECIMAL(10,2) NOT NULL COMMENT '当前价格',
    baseline_profit DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '基线利润',
    suggested_min_price DECIMAL(10,2) DEFAULT NULL COMMENT '建议最低价',
    suggested_max_price DECIMAL(10,2) DEFAULT NULL COMMENT '建议最高价',
    strategy_goal VARCHAR(50) NOT NULL DEFAULT 'MAX_PROFIT' COMMENT '策略目标',
    constraint_text VARCHAR(1000) DEFAULT NULL COMMENT '约束条件文本',
    task_status VARCHAR(20) NOT NULL DEFAULT 'QUEUED' COMMENT '任务状态',
    requested_by_user_id BIGINT DEFAULT NULL COMMENT '发起用户ID',
    trace_id VARCHAR(64) DEFAULT NULL COMMENT '链路追踪ID',
    idempotency_key VARCHAR(128) DEFAULT NULL COMMENT '幂等键',
    retry_count INT NOT NULL DEFAULT 0 COMMENT '重试次数',
    consumer_retry_count INT NOT NULL DEFAULT 0 COMMENT 'RabbitMQ 消费层重试次数',
    current_execution_id VARCHAR(64) DEFAULT NULL COMMENT '当前占用执行 id，用于 execution fencing',
    failure_reason VARCHAR(255) DEFAULT NULL COMMENT '失败原因',
    started_at DATETIME DEFAULT NULL COMMENT '开始时间',
    completed_at DATETIME DEFAULT NULL COMMENT '完成时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_pricing_task_task_code (task_code),
    KEY idx_pricing_task_shop_product (shop_id, product_id),
    KEY idx_pricing_task_trace_id (trace_id),
    KEY idx_pricing_task_idempotency_key (idempotency_key),
    KEY idx_pricing_task_requested_user (requested_by_user_id),
    KEY idx_pricing_task_execution (current_execution_id),
    KEY idx_pricing_task_status_created (task_status, created_at),
    CONSTRAINT fk_pricing_task_shop FOREIGN KEY (shop_id) REFERENCES shop(id),
    CONSTRAINT fk_pricing_task_product FOREIGN KEY (product_id) REFERENCES product(id),
    CONSTRAINT fk_pricing_task_sku FOREIGN KEY (sku_id) REFERENCES product_sku(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='定价任务表';

CREATE TABLE agent_run_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '日志ID',
    task_id BIGINT NOT NULL COMMENT '定价任务ID',
    execution_id VARCHAR(64) DEFAULT NULL COMMENT '产生该日志的 execution id',
    role_name VARCHAR(50) NOT NULL COMMENT '智能体角色名称',
    speak_order INT NOT NULL COMMENT '发言顺序',
    thought_content TEXT DEFAULT NULL COMMENT '完整思考内容',
    thinking_summary TEXT DEFAULT NULL COMMENT '思考摘要',
    evidence_json JSON DEFAULT NULL COMMENT '依据结构化内容',
    suggestion_json JSON DEFAULT NULL COMMENT '建议结构化内容',
    raw_output_json JSON DEFAULT NULL COMMENT 'Agent 输出的完整 Pydantic 校验后 JSON，用于失败重试时回放下游 context',
    final_reason TEXT DEFAULT NULL COMMENT '最终结论原因',
    display_order INT DEFAULT NULL COMMENT '界面展示顺序',
    stage VARCHAR(20) NOT NULL DEFAULT 'completed' COMMENT '卡片阶段: running=正在分析, completed=已完成, failed=执行失败',
    run_attempt INT NOT NULL DEFAULT 0 COMMENT 'Agent执行轮次，从0开始，对应任务retry_count',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    KEY idx_agent_run_log_task_id (task_id),
    KEY idx_agent_run_log_task_order (task_id, speak_order),
    KEY idx_agent_run_log_task_display_order (task_id, display_order),
    KEY idx_task_run_attempt_display_order (task_id, run_attempt, display_order),
    CONSTRAINT fk_agent_run_log_task FOREIGN KEY (task_id) REFERENCES pricing_task(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent运行日志表';

CREATE TABLE pricing_result (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '定价结果ID',
    task_id BIGINT NOT NULL COMMENT '定价任务ID',
    execution_id VARCHAR(64) DEFAULT NULL COMMENT '产生该结果的 execution id',
    final_price DECIMAL(10,2) NOT NULL COMMENT '最终建议价',
    expected_sales INT DEFAULT NULL COMMENT '预期销量',
    expected_profit DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '预期利润',
    profit_growth DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '利润增长值',
    is_pass TINYINT NOT NULL DEFAULT 0 COMMENT '是否通过风控',
    execute_strategy VARCHAR(50) NOT NULL DEFAULT '人工审核' COMMENT '执行策略',
    result_summary TEXT DEFAULT NULL COMMENT '结果摘要',
    review_required TINYINT NOT NULL DEFAULT 1 COMMENT '是否需要人工审核',
    applied_previous_price DECIMAL(10,2) DEFAULT NULL COMMENT '应用前价格',
    applied_at DATETIME DEFAULT NULL COMMENT '应用时间',
    applied_by_user_id BIGINT DEFAULT NULL COMMENT '应用操作人ID',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_pricing_result_task_id (task_id),
    CONSTRAINT fk_pricing_result_task FOREIGN KEY (task_id) REFERENCES pricing_task(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='定价结果表';

CREATE TABLE pricing_batch (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '批量定价批次ID',
    batch_code VARCHAR(50) NOT NULL COMMENT '批次编号',
    requested_by_user_id BIGINT NOT NULL COMMENT '发起用户ID',
    strategy_goal VARCHAR(50) NOT NULL COMMENT '定价策略目标',
    constraint_text VARCHAR(1000) DEFAULT NULL COMMENT '定价约束条件文本',
    total_count INT NOT NULL DEFAULT 0 COMMENT '批次商品总数',
    completed_count INT NOT NULL DEFAULT 0 COMMENT '已完成任务数',
    manual_review_count INT NOT NULL DEFAULT 0 COMMENT '待人工审核任务数',
    failed_count INT NOT NULL DEFAULT 0 COMMENT '失败商品数',
    cancelled_count INT NOT NULL DEFAULT 0 COMMENT '已取消任务数',
    batch_status VARCHAR(20) NOT NULL DEFAULT 'RUNNING' COMMENT '批次状态',
    finalized_at DATETIME DEFAULT NULL COMMENT '批次首次结束时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_pricing_batch_code (batch_code),
    KEY idx_pricing_batch_user_created (requested_by_user_id, created_at),
    KEY idx_pricing_batch_status (batch_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='批量定价汇总表';

CREATE TABLE pricing_batch_item (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '批量定价明细ID',
    batch_id BIGINT NOT NULL COMMENT '批次ID',
    product_id BIGINT NOT NULL COMMENT '商品ID',
    item_order INT NOT NULL COMMENT '批次内显示顺序',
    task_id BIGINT DEFAULT NULL COMMENT '关联定价任务ID',
    item_status VARCHAR(20) NOT NULL DEFAULT 'TASK_LINKED' COMMENT '明细创建状态',
    error_message VARCHAR(255) DEFAULT NULL COMMENT '明细级创建失败原因',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_batch_product (batch_id, product_id),
    KEY idx_batch_item_batch_order (batch_id, item_order),
    KEY idx_batch_item_batch_status (batch_id, item_status),
    KEY idx_batch_item_task (task_id),
    CONSTRAINT fk_batch_item_batch FOREIGN KEY (batch_id) REFERENCES pricing_batch(id) ON DELETE CASCADE,
    CONSTRAINT fk_batch_item_product FOREIGN KEY (product_id) REFERENCES product(id) ON DELETE RESTRICT,
    CONSTRAINT fk_batch_item_task FOREIGN KEY (task_id) REFERENCES pricing_task(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='批量定价明细表';

CREATE TABLE auth_refresh_session (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '刷新会话ID',
    user_id BIGINT NOT NULL COMMENT '用户ID',
    token_hash CHAR(64) NOT NULL COMMENT '刷新令牌哈希',
    expires_at DATETIME NOT NULL COMMENT '过期时间',
    revoked_at DATETIME DEFAULT NULL COMMENT '撤销时间',
    last_used_at DATETIME DEFAULT NULL COMMENT '最后使用时间',
    ip_address VARCHAR(64) DEFAULT NULL COMMENT '客户端IP',
    user_agent VARCHAR(255) DEFAULT NULL COMMENT '客户端标识',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_auth_refresh_session_token_hash (token_hash),
    KEY idx_auth_refresh_session_user_id (user_id),
    KEY idx_auth_refresh_session_expires_at (expires_at),
    CONSTRAINT fk_auth_refresh_session_user FOREIGN KEY (user_id) REFERENCES sys_user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='刷新令牌会话表';

CREATE TABLE login_audit_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '登录审计ID',
    user_id BIGINT DEFAULT NULL COMMENT '用户ID',
    username VARCHAR(50) DEFAULT NULL COMMENT '登录用户名',
    ip_address VARCHAR(64) DEFAULT NULL COMMENT '客户端IP',
    user_agent VARCHAR(255) DEFAULT NULL COMMENT '客户端标识',
    login_status VARCHAR(20) NOT NULL COMMENT '登录结果状态',
    failure_reason VARCHAR(255) DEFAULT NULL COMMENT '失败原因',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    KEY idx_login_audit_log_user_id (user_id),
    KEY idx_login_audit_log_username (username),
    KEY idx_login_audit_log_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='登录审计日志表';

INSERT INTO schema_migration_history (version, checksum, description, applied_at) VALUES
    ('migration_20260327_external_product', REPEAT('0', 64), 'baseline schema includes external product migration', CURRENT_TIMESTAMP),
    ('migration_20260329_agent_card_mvp', REPEAT('0', 64), 'baseline schema includes agent card fields', CURRENT_TIMESTAMP),
    ('migration_20260329_simplify_agent_run_log', REPEAT('0', 64), 'baseline schema includes simplified agent log model', CURRENT_TIMESTAMP),
    ('migration_20260405_product_status_cn', REPEAT('0', 64), 'baseline schema includes localized product status', CURRENT_TIMESTAMP),
    ('migration_20260407_launch_hardening', REPEAT('0', 64), 'baseline schema includes launch hardening fields', CURRENT_TIMESTAMP),
    ('migration_20260408_task_recovery', REPEAT('0', 64), 'baseline schema includes persisted task payload for recovery', CURRENT_TIMESTAMP),
    ('migration_20260413_agent_stage', REPEAT('0', 64), 'baseline schema includes agent run log stage', CURRENT_TIMESTAMP),
    ('migration_20260413_stage_failed_backfill', REPEAT('0', 64), 'baseline schema includes failed agent stage backfill', CURRENT_TIMESTAMP),
    ('migration_20260418_agent_run_attempt', REPEAT('0', 64), 'baseline schema includes agent run retry attempt', CURRENT_TIMESTAMP),
    ('migration_20260418_product_category_titles', REPEAT('0', 64), 'baseline schema includes product category and title profile fields', CURRENT_TIMESTAMP),
    ('migration_20260419_agent_raw_output', REPEAT('0', 64), 'baseline schema includes per-Agent raw output JSON for partial retry', CURRENT_TIMESTAMP),
    ('migration_20260420_pricing_batch', REPEAT('0', 64), 'baseline schema includes batch pricing tables', CURRENT_TIMESTAMP),
    ('migration_20260421_rabbitmq_async', REPEAT('0', 64), 'baseline schema includes RabbitMQ async task columns', CURRENT_TIMESTAMP),
    ('migration_20260423_pricing_batch_comment_cn', REPEAT('0', 64), 'baseline schema includes localized batch pricing comments', CURRENT_TIMESTAMP);

SET FOREIGN_KEY_CHECKS = 1;
