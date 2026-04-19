"""ResumeService 单元测试

覆盖 compute_resume_point 的核心分支：
- 空 task：无任何历史 → 全量执行
- 单前缀已完成：DATA_ANALYSIS completed → 从 MARKET_INTEL 开始
- 连续前缀完成：DATA + MARKET completed → 从 RISK_CONTROL 开始
- 断点（非连续）：MARKET completed 但 DATA 缺失 → 仍从 DATA 开始（连续前缀规则）
- raw_output_json 为空视作未完成：DATA 有 completed 行但 raw_output_json=NULL → 从 DATA 开始
- 全部完成：4 个 Agent 全部 completed → start_from=5（调用方不应进入此分支执行重试）
- 多轮 run_attempt：同一 order 多条 completed，取最新 run_attempt 那条的 raw_output
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql import text

from app.models.agent_run_log import AgentRunLog
from app.repos.log_repo import LogRepo
from app.services.resume_service import ResumeService


def _build_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE agent_run_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id BIGINT NOT NULL,
                    role_name VARCHAR(50) NOT NULL,
                    speak_order INT NOT NULL,
                    thought_content TEXT DEFAULT NULL,
                    thinking_summary TEXT DEFAULT NULL,
                    evidence_json JSON DEFAULT NULL,
                    suggestion_json JSON DEFAULT NULL,
                    raw_output_json JSON DEFAULT NULL,
                    final_reason TEXT DEFAULT NULL,
                    display_order INT DEFAULT NULL,
                    stage VARCHAR(20) NOT NULL DEFAULT 'completed',
                    run_attempt INT NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)()


def _add_completed(
    db: Session,
    task_id: int,
    order: int,
    raw: dict | None,
    run_attempt: int = 0,
) -> None:
    repo = LogRepo(db)
    repo.append_card(
        task_id=task_id,
        agent_name=f"Agent-{order}",
        display_order=order,
        thinking_summary="ok",
        evidence=[],
        suggestion={"summary": "ok"},
        run_attempt=run_attempt,
        raw_output=raw,
    )


def _add_failed(db: Session, task_id: int, order: int, run_attempt: int = 0) -> None:
    repo = LogRepo(db)
    repo.append_card(
        task_id=task_id,
        agent_name=f"Agent-{order}",
        display_order=order,
        thinking_summary="boom",
        evidence=[],
        suggestion={"error": True, "message": "boom"},
        stage="failed",
        run_attempt=run_attempt,
    )


def test_empty_task_returns_full_run():
    db = _build_session()
    svc = ResumeService(db)
    start_from, prior = svc.compute_resume_point(task_id=1)
    assert start_from == 1
    assert prior == {}


def test_data_done_resumes_from_market():
    db = _build_session()
    _add_completed(db, task_id=1, order=1, raw={"suggestedPrice": "29.90"})
    svc = ResumeService(db)
    start_from, prior = svc.compute_resume_point(task_id=1)
    assert start_from == 2
    assert prior == {1: {"suggestedPrice": "29.90"}}


def test_data_and_market_done_resumes_from_risk():
    db = _build_session()
    _add_completed(db, task_id=1, order=1, raw={"agent": "data"})
    _add_completed(db, task_id=1, order=2, raw={"agent": "market"})
    svc = ResumeService(db)
    start_from, prior = svc.compute_resume_point(task_id=1)
    assert start_from == 3
    assert prior == {1: {"agent": "data"}, 2: {"agent": "market"}}


def test_non_contiguous_prefix_breaks_at_first_gap():
    """MARKET 已 completed 但 DATA 缺失 → 仍从 DATA 开始（连续前缀规则）。

    MANAGER_COORDINATOR.context=[data, market, risk] 依赖上游全部可用，所以即使
    MARKET 已完成也不能跳过 DATA。
    """
    db = _build_session()
    _add_completed(db, task_id=1, order=2, raw={"agent": "market"})
    svc = ResumeService(db)
    start_from, prior = svc.compute_resume_point(task_id=1)
    assert start_from == 1
    assert prior == {}


def test_completed_without_raw_output_treated_as_incomplete():
    """老数据或中间态 completed 行若 raw_output_json 为空，视作未完成。

    因为没有 raw_output 就无法在下游 Task 的 context 里回放这段输出。
    """
    db = _build_session()
    _add_completed(db, task_id=1, order=1, raw=None)  # 无 raw_output
    svc = ResumeService(db)
    start_from, prior = svc.compute_resume_point(task_id=1)
    assert start_from == 1
    assert prior == {}


def test_all_four_done_returns_past_last_order():
    db = _build_session()
    for order in (1, 2, 3, 4):
        _add_completed(db, task_id=1, order=order, raw={"order": order})
    svc = ResumeService(db)
    start_from, prior = svc.compute_resume_point(task_id=1)
    assert start_from == 5  # 超过 4 → 调用方走 finalize 分支
    assert sorted(prior.keys()) == [1, 2, 3, 4]


def test_latest_run_attempt_wins_when_multiple_completed_rows_for_same_order():
    """历史数据可能同一 order 多次 completed（理论不会发生但 schema 允许）。

    应按 run_attempt 倒序取第一条非空 raw_output_json。
    """
    db = _build_session()
    _add_completed(db, task_id=1, order=1, raw={"v": "old"}, run_attempt=0)
    _add_completed(db, task_id=1, order=1, raw={"v": "new"}, run_attempt=1)
    svc = ResumeService(db)
    start_from, prior = svc.compute_resume_point(task_id=1)
    assert start_from == 2
    assert prior[1] == {"v": "new"}


def test_failed_rows_do_not_count_as_completed():
    db = _build_session()
    _add_completed(db, task_id=1, order=1, raw={"agent": "data"}, run_attempt=0)
    _add_failed(db, task_id=1, order=2, run_attempt=0)  # MARKET failed
    svc = ResumeService(db)
    start_from, prior = svc.compute_resume_point(task_id=1)
    assert start_from == 2
    assert prior == {1: {"agent": "data"}}


def test_different_tasks_are_isolated():
    db = _build_session()
    _add_completed(db, task_id=100, order=1, raw={"agent": "data-100"})
    _add_completed(db, task_id=200, order=1, raw={"agent": "data-200"})
    _add_completed(db, task_id=200, order=2, raw={"agent": "market-200"})

    svc = ResumeService(db)

    start_100, prior_100 = svc.compute_resume_point(task_id=100)
    start_200, prior_200 = svc.compute_resume_point(task_id=200)

    assert start_100 == 2
    assert prior_100 == {1: {"agent": "data-100"}}

    assert start_200 == 3
    assert prior_200 == {1: {"agent": "data-200"}, 2: {"agent": "market-200"}}
