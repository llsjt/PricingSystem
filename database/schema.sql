CREATE DATABASE IF NOT EXISTS `pricing_system2.0`
    DEFAULT CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE `pricing_system2.0`;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- =========================
-- 1. 用户表
-- =========================
DROP TABLE IF EXISTS sys_user;
CREATE TABLE sys_user (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '用户ID',
    username VARCHAR(50) NOT NULL COMMENT '用户名',
    account VARCHAR(50) NOT NULL COMMENT '账号',
    password VARCHAR(255) NOT NULL COMMENT '密码（建议存加密后的哈希值）',
    email VARCHAR(100) NOT NULL COMMENT '邮箱',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态：1启用，0禁用',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_account (account),
    UNIQUE KEY uk_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- =========================
-- 2. 店铺表
-- =========================
DROP TABLE IF EXISTS shop;
CREATE TABLE shop (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '店铺ID',
    user_id BIGINT NOT NULL COMMENT '所属用户ID',
    shop_name VARCHAR(100) NOT NULL COMMENT '店铺名称',
    platform VARCHAR(20) NOT NULL DEFAULT '淘宝' COMMENT '平台名称',
    seller_nick VARCHAR(100) DEFAULT NULL COMMENT '卖家昵称',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    KEY idx_user_id (user_id),
    CONSTRAINT fk_shop_user FOREIGN KEY (user_id) REFERENCES sys_user(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='店铺表';

-- =========================
-- 3. Excel上传批次表
-- =========================
DROP TABLE IF EXISTS upload_batch;
CREATE TABLE upload_batch (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '批次ID',
    shop_id BIGINT NOT NULL COMMENT '店铺ID',
    batch_no VARCHAR(50) NOT NULL COMMENT '批次编号',
    file_name VARCHAR(255) NOT NULL COMMENT '文件名',
    data_type VARCHAR(50) NOT NULL COMMENT '数据类型：商品/流量/推广/日指标等',
    start_date DATE DEFAULT NULL COMMENT '数据开始日期',
    end_date DATE DEFAULT NULL COMMENT '数据结束日期',
    row_count INT NOT NULL DEFAULT 0 COMMENT '总行数',
    success_count INT NOT NULL DEFAULT 0 COMMENT '成功行数',
    fail_count INT NOT NULL DEFAULT 0 COMMENT '失败行数',
    upload_status VARCHAR(20) NOT NULL DEFAULT 'SUCCESS' COMMENT '上传状态',
    uploaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
    KEY idx_shop_id (shop_id),
    UNIQUE KEY uk_batch_no (batch_no),
    CONSTRAINT fk_upload_batch_shop FOREIGN KEY (shop_id) REFERENCES shop(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Excel上传批次表';

-- =========================
-- 4. 商品表
-- =========================
DROP TABLE IF EXISTS product;
CREATE TABLE product (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '商品ID',
    shop_id BIGINT NOT NULL COMMENT '店铺ID',
    item_id BIGINT NOT NULL COMMENT '淘宝商品ID',
    product_name VARCHAR(255) NOT NULL COMMENT '商品名称',
    category_name VARCHAR(100) DEFAULT NULL COMMENT '类目名称',
    sale_price DECIMAL(10,2) NOT NULL COMMENT '当前售价',
    cost_price DECIMAL(10,2) NOT NULL COMMENT '成本价',
    stock INT NOT NULL DEFAULT 0 COMMENT '库存',
    status VARCHAR(20) DEFAULT 'ON_SALE' COMMENT '商品状态',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_shop_item (shop_id, item_id),
    KEY idx_shop_id (shop_id),
    CONSTRAINT fk_product_shop FOREIGN KEY (shop_id) REFERENCES shop(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品表';

-- =========================
-- 5. SKU表
-- =========================
DROP TABLE IF EXISTS product_sku;
CREATE TABLE product_sku (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT 'SKU主键ID',
    product_id BIGINT NOT NULL COMMENT '商品ID',
    sku_id BIGINT NOT NULL COMMENT '淘宝SKU ID',
    sku_name VARCHAR(255) DEFAULT NULL COMMENT 'SKU名称',
    sku_attr VARCHAR(255) DEFAULT NULL COMMENT 'SKU属性，如颜色/尺码',
    sale_price DECIMAL(10,2) NOT NULL COMMENT 'SKU售价',
    cost_price DECIMAL(10,2) NOT NULL COMMENT 'SKU成本价',
    stock INT NOT NULL DEFAULT 0 COMMENT 'SKU库存',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_product_sku (product_id, sku_id),
    KEY idx_product_id (product_id),
    CONSTRAINT fk_product_sku_product FOREIGN KEY (product_id) REFERENCES product(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='SKU表';

-- =========================
-- 6. 商品日指标表
-- =========================
DROP TABLE IF EXISTS product_daily_metric;
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
    convert_rate DECIMAL(8,4) DEFAULT 0.0000 COMMENT '支付转化率',
    upload_batch_id BIGINT DEFAULT NULL COMMENT '上传批次ID',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    UNIQUE KEY uk_product_date (product_id, stat_date),
    KEY idx_shop_date (shop_id, stat_date),
    CONSTRAINT fk_product_daily_metric_shop FOREIGN KEY (shop_id) REFERENCES shop(id),
    CONSTRAINT fk_product_daily_metric_product FOREIGN KEY (product_id) REFERENCES product(id),
    CONSTRAINT fk_product_daily_metric_batch FOREIGN KEY (upload_batch_id) REFERENCES upload_batch(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品日指标表';

-- =========================
-- 7. 流量与推广日指标表
-- =========================
DROP TABLE IF EXISTS traffic_promo_daily;
CREATE TABLE traffic_promo_daily (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '流量推广ID',
    shop_id BIGINT NOT NULL COMMENT '店铺ID',
    product_id BIGINT DEFAULT NULL COMMENT '商品ID',
    stat_date DATE NOT NULL COMMENT '统计日期',
    traffic_source VARCHAR(50) NOT NULL COMMENT '流量来源',
    impression_count INT NOT NULL DEFAULT 0 COMMENT '展现量',
    click_count INT NOT NULL DEFAULT 0 COMMENT '点击量',
    visitor_count INT NOT NULL DEFAULT 0 COMMENT '访客数',
    cost_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '推广花费',
    pay_amount DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '支付金额',
    roi DECIMAL(10,4) DEFAULT 0.0000 COMMENT 'ROI',
    upload_batch_id BIGINT DEFAULT NULL COMMENT '上传批次ID',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    KEY idx_shop_date (shop_id, stat_date),
    KEY idx_product_date (product_id, stat_date),
    CONSTRAINT fk_traffic_promo_daily_shop FOREIGN KEY (shop_id) REFERENCES shop(id),
    CONSTRAINT fk_traffic_promo_daily_product FOREIGN KEY (product_id) REFERENCES product(id),
    CONSTRAINT fk_traffic_promo_daily_batch FOREIGN KEY (upload_batch_id) REFERENCES upload_batch(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='流量与推广日指标表';

-- =========================
-- 8. 定价任务表
-- =========================
DROP TABLE IF EXISTS pricing_task;
CREATE TABLE pricing_task (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '任务ID',
    task_code VARCHAR(50) NOT NULL COMMENT '任务编号',
    shop_id BIGINT NOT NULL COMMENT '店铺ID',
    product_id BIGINT NOT NULL COMMENT '商品ID',
    sku_id BIGINT DEFAULT NULL COMMENT 'SKU主键ID，可为空',
    current_price DECIMAL(10,2) NOT NULL COMMENT '当前售价',
    baseline_profit DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '当前基线利润',
    suggested_min_price DECIMAL(10,2) DEFAULT NULL COMMENT '建议最低价',
    suggested_max_price DECIMAL(10,2) DEFAULT NULL COMMENT '建议最高价',
    task_status VARCHAR(20) NOT NULL DEFAULT 'PENDING' COMMENT '任务状态',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_task_code (task_code),
    KEY idx_shop_product (shop_id, product_id),
    CONSTRAINT fk_pricing_task_shop FOREIGN KEY (shop_id) REFERENCES shop(id),
    CONSTRAINT fk_pricing_task_product FOREIGN KEY (product_id) REFERENCES product(id),
    CONSTRAINT fk_pricing_task_sku FOREIGN KEY (sku_id) REFERENCES product_sku(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='定价任务表';

-- =========================
-- 9. Agent运行日志表
-- =========================
DROP TABLE IF EXISTS agent_run_log;
CREATE TABLE agent_run_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '日志ID',
    task_id BIGINT NOT NULL COMMENT '定价任务ID',
    agent_code VARCHAR(30) NOT NULL COMMENT 'Agent编码',
    agent_name VARCHAR(50) NOT NULL COMMENT 'Agent名称',
    run_order INT NOT NULL COMMENT '执行顺序',
    run_status VARCHAR(20) NOT NULL COMMENT '执行状态',
    input_summary TEXT DEFAULT NULL COMMENT '输入摘要',
    output_summary TEXT DEFAULT NULL COMMENT '输出内容摘要',
    output_payload JSON DEFAULT NULL COMMENT '输出结果JSON',
    suggested_price DECIMAL(10,2) DEFAULT NULL COMMENT '建议售价',
    predicted_profit DECIMAL(12,2) DEFAULT NULL COMMENT '预测利润',
    confidence_score DECIMAL(8,4) DEFAULT NULL COMMENT '置信度',
    risk_level VARCHAR(20) DEFAULT NULL COMMENT '风险等级',
    need_manual_review TINYINT NOT NULL DEFAULT 0 COMMENT '是否需要人工审核：1是，0否',
    error_message VARCHAR(1000) DEFAULT NULL COMMENT '错误信息',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    KEY idx_task_id (task_id),
    KEY idx_task_order (task_id, run_order),
    CONSTRAINT fk_agent_run_log_task FOREIGN KEY (task_id) REFERENCES pricing_task(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent运行日志表';

-- =========================
-- 10. 定价结果表
-- =========================
DROP TABLE IF EXISTS pricing_result;
CREATE TABLE pricing_result (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '结果ID',
    task_id BIGINT NOT NULL COMMENT '定价任务ID',
    final_price DECIMAL(10,2) NOT NULL COMMENT '最终建议售价',
    expected_sales INT DEFAULT NULL COMMENT '预期销量',
    expected_profit DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '预期利润',
    profit_growth DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT '较基线利润提升值',
    is_pass TINYINT NOT NULL DEFAULT 0 COMMENT '是否通过风控：1通过，0不通过',
    execute_strategy VARCHAR(50) DEFAULT NULL COMMENT '执行策略：直接执行/灰度发布/A_B测试/人工审核',
    result_summary TEXT DEFAULT NULL COMMENT '结果说明',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_task_id (task_id),
    CONSTRAINT fk_pricing_result_task FOREIGN KEY (task_id) REFERENCES pricing_task(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='定价结果表';

SET FOREIGN_KEY_CHECKS = 1;
