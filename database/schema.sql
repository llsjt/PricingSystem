-- 数据库初始化脚本
-- 目标数据库: MySQL 8.0+

CREATE DATABASE IF NOT EXISTS pricing_system DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE pricing_system;

-- 1. 商品基础表 (合并了原经营指标表，增加了市场价、库存等字段)
CREATE TABLE IF NOT EXISTS biz_product (
    id BIGINT AUTO_INCREMENT COMMENT '商品ID (主键)',
    title VARCHAR(255) NOT NULL COMMENT '商品标题',
    category VARCHAR(100) COMMENT '商品类别',
    cost_price DECIMAL(10, 2) NOT NULL COMMENT '成本价',
    market_price DECIMAL(10, 2) COMMENT '市场价',
    current_price DECIMAL(10, 2) NOT NULL COMMENT '当前售价',
    stock INT DEFAULT 0 COMMENT '库存数量',
    monthly_sales INT DEFAULT 0 COMMENT '月销售量',
    click_rate DECIMAL(5, 4) DEFAULT 0.0000 COMMENT '点击率 (小数)',
    conversion_rate DECIMAL(5, 4) DEFAULT 0.0000 COMMENT '转化率 (小数)',
    source VARCHAR(50) NOT NULL COMMENT '数据来源(导入/手动)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品信息表';

-- 2. 导入批次表
CREATE TABLE IF NOT EXISTS sys_import_batch (
    id BIGINT AUTO_INCREMENT COMMENT '批次ID',
    batch_no VARCHAR(64) NOT NULL UNIQUE COMMENT '批次号',
    file_name VARCHAR(255) NOT NULL COMMENT '文件名',
    success_count INT DEFAULT 0 COMMENT '成功行数',
    fail_count INT DEFAULT 0 COMMENT '失败行数',
    error_log TEXT COMMENT '错误日志',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '导入时间',
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='导入批次表';

-- 3. 决策任务表
CREATE TABLE IF NOT EXISTS dec_task (
    id BIGINT AUTO_INCREMENT COMMENT '任务ID',
    task_no VARCHAR(64) NOT NULL UNIQUE COMMENT '任务编号',
    product_names TEXT COMMENT '商品名称快照',
    strategy_type VARCHAR(50) NOT NULL COMMENT '策略类型',
    constraints TEXT COMMENT '约束配置',
    status VARCHAR(20) NOT NULL COMMENT '状态(PENDING/RUNNING/COMPLETED/FAILED)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='决策任务表';

-- 4. 决策结果表
CREATE TABLE IF NOT EXISTS dec_result (
    id BIGINT AUTO_INCREMENT COMMENT '结果ID',
    task_id BIGINT NOT NULL COMMENT '关联任务ID',
    product_id BIGINT NOT NULL COMMENT '关联商品ID',
    suggested_price DECIMAL(10, 2) NOT NULL COMMENT '建议价格',
    profit_change DECIMAL(10, 2) COMMENT '预期利润变化',
    discount_rate DECIMAL(5, 4) COMMENT '折扣率',
    core_reasons TEXT COMMENT '核心理由',
    is_accepted TINYINT(1) DEFAULT 0 COMMENT '采纳状态(0:未采纳, 1:已采纳)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '生成时间',
    PRIMARY KEY (id),
    INDEX idx_task_product (task_id, product_id),
    FOREIGN KEY (task_id) REFERENCES dec_task(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES biz_product(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='决策结果表';

-- 5. Agent协作日志表
CREATE TABLE IF NOT EXISTS dec_agent_log (
    id BIGINT AUTO_INCREMENT COMMENT '日志ID',
    task_id BIGINT NOT NULL COMMENT '关联任务ID',
    role_name VARCHAR(50) NOT NULL COMMENT '角色名(AnalysisAgent/PricingAgent等)',
    speak_order INT NOT NULL COMMENT '发言顺序',
    input_context TEXT COMMENT '输入上下文',
    thought_content TEXT COMMENT '思考内容',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '记录时间',
    PRIMARY KEY (id),
    INDEX idx_task_order (task_id, speak_order),
    FOREIGN KEY (task_id) REFERENCES dec_task(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent协作日志表';

-- 6. 用户表
CREATE TABLE IF NOT EXISTS sys_user (
    id BIGINT AUTO_INCREMENT COMMENT '用户ID',
    username VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
    password VARCHAR(100) NOT NULL COMMENT '密码(加密)',
    email VARCHAR(100) COMMENT '邮箱',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- 7. 商品日经营数据统计
CREATE TABLE `biz_product_daily_stat` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '主键',
  `product_id` bigint NOT NULL COMMENT '商品ID',
  `stat_date` date NOT NULL COMMENT '统计日期',
  `visitor_count` int DEFAULT '0' COMMENT '访客数',
  `sales_count` int DEFAULT '0' COMMENT '销量',
  `turnover` decimal(10,2) DEFAULT '0.00' COMMENT '销售额',
  `conversion_rate` decimal(5,4) DEFAULT '0.0000' COMMENT '转化率',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `idx_product_date` (`product_id`,`stat_date`),
  CONSTRAINT `biz_product_daily_stat_ibfk_1` FOREIGN KEY (`product_id`) REFERENCES `biz_product` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=275 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='商品日经营数据统计';
-- Supplemental table for runtime configuration
CREATE TABLE IF NOT EXISTS sys_config (
  id BIGINT NOT NULL AUTO_INCREMENT COMMENT '配置ID',
  config_key VARCHAR(100) NOT NULL COMMENT '配置键',
  config_value TEXT COMMENT '配置值',
  description VARCHAR(255) COMMENT '配置说明',
  created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_config_key (config_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统配置表';
