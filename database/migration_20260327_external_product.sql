USE `pricing_system2.0`;
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

ALTER TABLE shop
  MODIFY COLUMN platform VARCHAR(20) NOT NULL DEFAULT '淘宝' COMMENT '平台名称：淘宝/京东/拼多多等';

ALTER TABLE product
  DROP INDEX uk_shop_item,
  DROP INDEX idx_shop_id,
  CHANGE COLUMN item_id external_product_id VARCHAR(64) NOT NULL COMMENT '平台商品ID',
  MODIFY COLUMN product_name VARCHAR(255) NULL COMMENT '商品名称',
  MODIFY COLUMN category_name VARCHAR(100) NULL COMMENT '类目名称',
  MODIFY COLUMN sale_price DECIMAL(10,2) NULL COMMENT '当前售价',
  MODIFY COLUMN cost_price DECIMAL(10,2) NULL COMMENT '成本价',
  MODIFY COLUMN stock INT NOT NULL DEFAULT 0 COMMENT '库存',
  MODIFY COLUMN status VARCHAR(20) NOT NULL DEFAULT '出售中' COMMENT '商品状态',
  ADD COLUMN profile_status VARCHAR(20) NOT NULL DEFAULT 'COMPLETE' COMMENT '商品档案状态：PLACEHOLDER/COMPLETE' AFTER status,
  ADD UNIQUE KEY uk_shop_external_product (shop_id, external_product_id),
  ADD KEY idx_shop_profile_status (shop_id, profile_status);

UPDATE product
SET profile_status = 'COMPLETE'
WHERE profile_status IS NULL OR profile_status = '';

ALTER TABLE product_sku
  DROP INDEX uk_product_sku,
  DROP INDEX idx_product_id,
  CHANGE COLUMN sku_id external_sku_id VARCHAR(64) NOT NULL COMMENT '平台SKU ID',
  ADD UNIQUE KEY uk_product_external_sku (product_id, external_sku_id);

ALTER TABLE traffic_promo_daily
  DROP INDEX idx_product_date,
  ADD UNIQUE KEY uk_product_date_source (product_id, stat_date, traffic_source);

SET FOREIGN_KEY_CHECKS = 1;
