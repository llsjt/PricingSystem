SET NAMES utf8mb4;

CREATE TABLE pricing_batch (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT 'Batch pricing request id',
    batch_code VARCHAR(50) NOT NULL COMMENT 'Batch code',
    requested_by_user_id BIGINT NOT NULL COMMENT 'Requester user id',
    strategy_goal VARCHAR(50) NOT NULL COMMENT 'Strategy goal',
    constraint_text VARCHAR(1000) DEFAULT NULL COMMENT 'Serialized pricing constraints',
    total_count INT NOT NULL DEFAULT 0 COMMENT 'Total item count',
    completed_count INT NOT NULL DEFAULT 0 COMMENT 'Completed task count',
    manual_review_count INT NOT NULL DEFAULT 0 COMMENT 'Manual review task count',
    failed_count INT NOT NULL DEFAULT 0 COMMENT 'Failed item count',
    cancelled_count INT NOT NULL DEFAULT 0 COMMENT 'Cancelled task count',
    batch_status VARCHAR(20) NOT NULL DEFAULT 'RUNNING' COMMENT 'Batch status',
    finalized_at DATETIME DEFAULT NULL COMMENT 'First terminal timestamp',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Created time',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Updated time',
    UNIQUE KEY uk_pricing_batch_code (batch_code),
    KEY idx_pricing_batch_user_created (requested_by_user_id, created_at),
    KEY idx_pricing_batch_status (batch_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Batch pricing summary';

CREATE TABLE pricing_batch_item (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT 'Batch pricing item id',
    batch_id BIGINT NOT NULL COMMENT 'Batch id',
    product_id BIGINT NOT NULL COMMENT 'Product id',
    item_order INT NOT NULL COMMENT 'Display order inside the batch',
    task_id BIGINT DEFAULT NULL COMMENT 'Linked pricing task id',
    item_status VARCHAR(20) NOT NULL DEFAULT 'TASK_LINKED' COMMENT 'Batch item creation status',
    error_message VARCHAR(255) DEFAULT NULL COMMENT 'Batch-level creation failure message',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Created time',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Updated time',
    UNIQUE KEY uk_batch_product (batch_id, product_id),
    KEY idx_batch_item_batch_order (batch_id, item_order),
    KEY idx_batch_item_batch_status (batch_id, item_status),
    KEY idx_batch_item_task (task_id),
    CONSTRAINT fk_batch_item_batch FOREIGN KEY (batch_id) REFERENCES pricing_batch(id) ON DELETE CASCADE,
    CONSTRAINT fk_batch_item_product FOREIGN KEY (product_id) REFERENCES product(id) ON DELETE RESTRICT,
    CONSTRAINT fk_batch_item_task FOREIGN KEY (task_id) REFERENCES pricing_task(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Batch pricing detail';
