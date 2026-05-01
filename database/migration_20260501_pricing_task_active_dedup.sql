-- Add an active-task idempotency guard for pricing task creation.
--
-- Preflight before applying in production:
-- SELECT shop_id, idempotency_key, COUNT(*) AS cnt,
--        GROUP_CONCAT(CONCAT(id, ':', task_status) ORDER BY id DESC) AS task_ids
--   FROM pricing_task
--  WHERE task_status IN ('PENDING','QUEUED','RUNNING','RETRYING')
--    AND idempotency_key IS NOT NULL
--  GROUP BY shop_id, idempotency_key
-- HAVING COUNT(*) > 1;
--
-- SELECT id, shop_id, product_id, task_status, requested_by_user_id
--   FROM pricing_task
--  WHERE task_status IN ('PENDING','QUEUED','RUNNING','RETRYING')
--    AND (idempotency_key IS NULL OR idempotency_key = '');

ALTER TABLE pricing_task
  ADD COLUMN active_idempotency_key VARCHAR(128)
    GENERATED ALWAYS AS (
      CASE
        WHEN task_status IN ('PENDING','QUEUED','RUNNING','RETRYING') THEN idempotency_key
        ELSE NULL
      END
    ) STORED COMMENT 'Active task idempotency key' AFTER idempotency_key,
  ADD UNIQUE KEY uk_pricing_task_active_idem (shop_id, active_idempotency_key);
