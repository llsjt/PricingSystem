USE `pricing_system2.0`;
SET NAMES utf8mb4;

SET @status_on_sale = CONVERT(0xE587BAE594AEE4B8AD USING utf8mb4);
SET @status_off_shelf = CONVERT(0xE4B88BE69EB6 USING utf8mb4);

UPDATE product
SET status = CASE
    WHEN TRIM(COALESCE(status, '')) IN (@status_off_shelf, 'OFF_SHELF') THEN @status_off_shelf
    ELSE @status_on_sale
END;

SET @alter_sql = CONCAT(
    'ALTER TABLE product MODIFY COLUMN status VARCHAR(20) NOT NULL DEFAULT ''',
    @status_on_sale,
    ''' COMMENT ''product status'''
);

PREPARE stmt FROM @alter_sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
