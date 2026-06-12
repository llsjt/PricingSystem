from contextlib import contextmanager

from app.core.config import Settings
from app.db import migrations


def test_ensure_agent_run_log_schema_adds_raw_output_json_column(monkeypatch):
    executed_sql: list[str] = []

    monkeypatch.setattr(
        migrations,
        "_list_columns",
        lambda table_name, schema_name: {
            "id",
            "task_id",
            "role_name",
            "speak_order",
            "thought_content",
            "thinking_summary",
            "evidence_json",
            "suggestion_json",
            "final_reason",
            "display_order",
            "stage",
            "run_attempt",
            "created_at",
        },
    )
    monkeypatch.setattr(migrations, "_has_index", lambda *args, **kwargs: True)

    class _FakeConn:
        def execute(self, clause, *args, **kwargs):  # noqa: ANN001
            executed_sql.append(str(clause))
            return None

    @contextmanager
    def _fake_begin():
        yield _FakeConn()

    monkeypatch.setattr(migrations.engine, "begin", _fake_begin)

    migrations.ensure_agent_run_log_schema("pricing_system2.0")

    assert any("ADD COLUMN raw_output_json" in sql for sql in executed_sql)


def test_check_agent_run_log_schema_accepts_baseline_index_alias(monkeypatch):
    monkeypatch.setattr(migrations, "_list_columns", lambda table_name, schema_name: set(migrations.AGENT_RUN_LOG_REQUIRED_COLUMNS))
    monkeypatch.setattr(
        migrations,
        "_has_index",
        lambda table_name, schema_name, index_name: index_name
        in {"idx_agent_run_log_task_display_order", "idx_task_run_attempt_display_order"},
    )

    migrations.check_agent_run_log_schema("pricing_system2.0")


def test_production_rejects_auto_schema_patch():
    settings = Settings(
        APP_ENV="prod",
        INTERNAL_API_TOKEN="internal-token",
        MYSQL_PASSWORD="strong-password",
        PYTHON_AUTO_SCHEMA_PATCH=True,
    )

    try:
        settings.validate_production_safety()
        raise AssertionError("expected production safety validation to fail")
    except RuntimeError as exc:
        assert "python auto schema patch must be disabled" in str(exc)


def test_backup_llm_enabled_requires_complete_provider_config_in_prod():
    settings = Settings(
        APP_ENV="prod",
        INTERNAL_API_TOKEN="internal-token",
        MYSQL_PASSWORD="strong-password",
        BACKUP_LLM_ENABLED=True,
        BACKUP_LLM_MODEL="fallback-model",
    )

    try:
        settings.validate_production_safety()
        raise AssertionError("expected production safety validation to fail")
    except RuntimeError as exc:
        assert "backup llm is enabled without a complete audited provider config" in str(exc)
