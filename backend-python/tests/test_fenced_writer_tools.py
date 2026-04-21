from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql import text

from app.db.base import Base
from app.models.agent_run_log import AgentRunLog
from app.models.pricing_result import PricingResult
from app.models.pricing_task import PricingTask
from app.schemas.result import TaskFinalResult
from app.tools.log_writer_tool import LogWriterTool
from app.tools.result_writer_tool import ResultWriterTool


def build_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[PricingTask.__table__])
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE agent_run_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id BIGINT NOT NULL,
                    execution_id VARCHAR(64) DEFAULT NULL,
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
        conn.execute(
            text(
                """
                CREATE TABLE pricing_result (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id BIGINT NOT NULL UNIQUE,
                    execution_id VARCHAR(64) DEFAULT NULL,
                    final_price DECIMAL(10, 2) NOT NULL,
                    expected_sales INT DEFAULT NULL,
                    expected_profit DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
                    profit_growth DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
                    is_pass INT NOT NULL DEFAULT 0,
                    execute_strategy VARCHAR(50) NOT NULL DEFAULT '人工审核',
                    result_summary TEXT DEFAULT NULL,
                    review_required INT NOT NULL DEFAULT 1,
                    applied_previous_price DECIMAL(10, 2) DEFAULT NULL,
                    applied_at DATETIME DEFAULT NULL,
                    applied_by_user_id BIGINT DEFAULT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)()


def create_task(db: Session, *, task_id: int, status: str = "RUNNING", execution_id: str | None = None) -> PricingTask:
    task = PricingTask(
        id=task_id,
        task_code=f"TASK-{task_id}",
        shop_id=1,
        product_id=1000 + task_id,
        current_price=Decimal("29.90"),
        baseline_profit=Decimal("10.00"),
        task_status=status,
        strategy_goal="MAX_PROFIT",
        constraint_text="",
        trace_id=f"trace-{task_id}",
        retry_count=0,
        consumer_retry_count=0,
        current_execution_id=execution_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def final_payload(task_id: int) -> TaskFinalResult:
    return TaskFinalResult(
        taskId=task_id,
        finalPrice=Decimal("31.00"),
        expectedSales=120,
        expectedProfit=Decimal("1100.00"),
        profitGrowth=Decimal("300.00"),
        isPass=False,
        executeStrategy="人工审核",
        resultSummary="summary",
        suggestedMinPrice=Decimal("29.00"),
        suggestedMaxPrice=Decimal("33.00"),
    )


def test_log_writer_skips_when_execution_id_is_not_current_owner():
    db = build_session()
    create_task(db, task_id=1, execution_id="exec-current")

    LogWriterTool(db, execution_id="exec-stale").write_running_card(task_id=1, agent_name="数据分析Agent", display_order=1)

    assert db.query(AgentRunLog).count() == 0


def test_result_writer_skips_when_execution_id_is_not_current_owner():
    db = build_session()
    create_task(db, task_id=2, execution_id="exec-current")

    ResultWriterTool(db, execution_id="exec-stale").write_final_result(final_payload(2))

    assert db.query(PricingResult).count() == 0
    assert db.get(PricingTask, 2).task_status == "RUNNING"


def test_result_writer_persists_when_execution_id_matches_current_owner():
    db = build_session()
    create_task(db, task_id=3, execution_id="exec-current")

    ResultWriterTool(db, execution_id="exec-current").write_final_result(final_payload(3))

    result = db.query(PricingResult).filter(PricingResult.task_id == 3).one()
    task = db.get(PricingTask, 3)
    assert result.execution_id == "exec-current"
    assert task.task_status == "MANUAL_REVIEW"
