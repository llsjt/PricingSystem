SET NAMES utf8mb4;

ALTER TABLE pricing_result
  MODIFY COLUMN execute_strategy VARCHAR(50) NOT NULL DEFAULT '人工审核' COMMENT '执行策略';

UPDATE pricing_result
SET execute_strategy = '人工审核';
