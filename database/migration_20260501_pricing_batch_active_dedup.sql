-- Add an active-batch idempotency guard for batch pricing creation.
-- Existing rows are intentionally left with NULL idempotency_key; the guard applies to new requests.

ALTER TABLE pricing_batch
  ADD COLUMN idempotency_key VARCHAR(128) DEFAULT NULL COMMENT 'Batch idempotency key' AFTER constraint_text,
  ADD COLUMN active_idempotency_key VARCHAR(128)
    GENERATED ALWAYS AS (
      CASE
        WHEN batch_status IN ('PENDING','RUNNING','RETRYING') THEN idempotency_key
        ELSE NULL
      END
    ) STORED COMMENT 'Active batch idempotency key' AFTER idempotency_key,
  ADD UNIQUE KEY uk_pricing_batch_active_idem (requested_by_user_id, active_idempotency_key),
  ADD KEY idx_pricing_batch_idempotency_key (idempotency_key);
