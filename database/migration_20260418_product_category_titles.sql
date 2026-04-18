SET NAMES utf8mb4;

ALTER TABLE product
    ADD COLUMN primary_category_name VARCHAR(100) DEFAULT NULL COMMENT '一级类目名称' AFTER category_name,
    ADD COLUMN secondary_category_name VARCHAR(100) DEFAULT NULL COMMENT '二级类目名称' AFTER primary_category_name,
    ADD COLUMN short_title VARCHAR(100) DEFAULT NULL COMMENT '短标题' AFTER product_name,
    ADD COLUMN sub_title VARCHAR(255) DEFAULT NULL COMMENT '副标题' AFTER short_title;
