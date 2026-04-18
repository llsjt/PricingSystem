import logging

from sqlalchemy import text

from app.db.session import engine

logger = logging.getLogger(__name__)


def _list_columns(table_name: str, schema_name: str) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT COLUMN_NAME
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = :schema_name
                  AND TABLE_NAME = :table_name
                """
            ),
            {"schema_name": schema_name, "table_name": table_name},
        ).fetchall()
    return {str(row[0]) for row in rows}


def _has_index(table_name: str, schema_name: str, index_name: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT 1
                FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA = :schema_name
                  AND TABLE_NAME = :table_name
                  AND INDEX_NAME = :index_name
                LIMIT 1
                """
            ),
            {
                "schema_name": schema_name,
                "table_name": table_name,
                "index_name": index_name,
            },
        ).first()
    return row is not None


def ensure_agent_run_log_schema(schema_name: str) -> None:
    """启动时兜底迁移：保证 agent_run_log 具备卡片化字段。"""
    table_name = "agent_run_log"
    existing = _list_columns(table_name, schema_name)

    statements: list[str] = []
    if "thinking_summary" not in existing:
        statements.append("ADD COLUMN thinking_summary TEXT NULL COMMENT '思考过程摘要'")
    if "evidence_json" not in existing:
        statements.append("ADD COLUMN evidence_json JSON NULL COMMENT '依据(JSON数组)'")
    if "suggestion_json" not in existing:
        statements.append("ADD COLUMN suggestion_json JSON NULL COMMENT '建议(JSON对象)'")
    if "final_reason" not in existing:
        statements.append("ADD COLUMN final_reason TEXT NULL COMMENT '最终建议原因(经理Agent)'")
    if "display_order" not in existing:
        statements.append("ADD COLUMN display_order INT NULL COMMENT '卡片展示顺序(1-4)'")
    if "stage" not in existing:
        statements.append("ADD COLUMN stage VARCHAR(20) NOT NULL DEFAULT 'completed' COMMENT '卡片阶段: running=正在分析, completed=已完成, failed=执行失败'")
    if "run_attempt" not in existing:
        statements.append("ADD COLUMN run_attempt INT NOT NULL DEFAULT 0 COMMENT 'Agent 执行轮次，从0开始，对应任务 retry_count'")

    if statements:
        ddl = "ALTER TABLE agent_run_log " + ", ".join(statements)
        with engine.begin() as conn:
            conn.execute(text(ddl))
            conn.execute(
                text(
                    """
                    UPDATE agent_run_log
                    SET thinking_summary = thought_content
                    WHERE thinking_summary IS NULL
                      AND thought_content IS NOT NULL
                    """
                )
            )
        logger.info("Applied startup migration for agent_run_log columns: %s", ", ".join(statements))

    if not _has_index(table_name, schema_name, "idx_task_display_order"):
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE agent_run_log ADD INDEX idx_task_display_order (task_id, display_order)"))
        logger.info("Applied startup migration index idx_task_display_order")

    if not _has_index(table_name, schema_name, "idx_task_run_attempt_display_order"):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE agent_run_log ADD INDEX idx_task_run_attempt_display_order "
                    "(task_id, run_attempt, display_order)"
                )
            )
        logger.info("Applied startup migration index idx_task_run_attempt_display_order")

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE agent_run_log
                SET stage = 'failed'
                WHERE stage <> 'failed'
                  AND (
                    JSON_UNQUOTE(JSON_EXTRACT(suggestion_json, '$.error')) = 'true'
                    OR thinking_summary LIKE 'Agent 执行失败:%'
                    OR thought_content LIKE 'Agent 执行失败:%'
                  )
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE pricing_task t
                LEFT JOIN pricing_result r ON r.task_id = t.id
                SET t.task_status = 'FAILED'
                WHERE t.task_status = 'MANUAL_REVIEW'
                  AND r.id IS NULL
                  AND (
                    t.failure_reason IS NOT NULL
                    OR EXISTS (
                      SELECT 1
                      FROM agent_run_log l
                      WHERE l.task_id = t.id
                        AND l.stage = 'failed'
                    )
                  )
                """
            )
        )
