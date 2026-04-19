-- Persist the per-Agent raw output JSON so partial retries can replay upstream context
-- without re-calling the LLM for already-completed Agents.
SET NAMES utf8mb4;

ALTER TABLE agent_run_log
  ADD COLUMN raw_output_json JSON NULL
  COMMENT 'Agent 输出的完整 Pydantic 校验后 JSON，用于失败重试时回放下游 context'
  AFTER suggestion_json;
