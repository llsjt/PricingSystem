from contextlib import contextmanager

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
