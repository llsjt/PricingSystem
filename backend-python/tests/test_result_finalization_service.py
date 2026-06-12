from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql import text

from app.db.base import Base
from app.models.pricing_result import PricingResult
from app.models.pricing_task import PricingTask
from app.schemas.result import TaskFinalResult
from app.services.result_finalization_service import ExecutionOwnerChanged, ResultFinalizationService


def build_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[PricingTask.__table__])
    with engine.begin() as conn:
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


def create_task(db: Session, *, task_id: int, status: str = "RUNNING", execution_id: str | None = "exec-current") -> PricingTask:
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
        last_heartbeat_at=None,
        llm_api_key_enc="cipher",
        llm_base_url="https://persisted.example.com/v1",
        llm_model="persisted-model",
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
        isPass=True,
        executeStrategy="人工审核",
        resultSummary="summary",
        suggestedMinPrice=Decimal("29.00"),
        suggestedMaxPrice=Decimal("33.00"),
    )


def test_finalize_manual_review_writes_result_and_cleans_owner_snapshot_in_one_transaction():
    db = build_session()
    create_task(db, task_id=1)

    ResultFinalizationService(db).finalize_manual_review(final_payload(1), execution_id="exec-current")

    task = db.get(PricingTask, 1)
    result = db.query(PricingResult).filter(PricingResult.task_id == 1).one()
    assert task.task_status == "MANUAL_REVIEW"
    assert task.suggested_min_price == Decimal("29.00")
    assert task.suggested_max_price == Decimal("33.00")
    assert task.current_execution_id is None
    assert task.last_heartbeat_at is None
    assert task.llm_api_key_enc is None
    assert task.llm_base_url is None
    assert task.llm_model is None
    assert result.execution_id == "exec-current"
    assert result.execute_strategy == "人工审核"
    assert result.review_required == 1


def test_finalize_manual_review_rolls_back_when_owner_changed():
    db = build_session()
    create_task(db, task_id=2, status="CANCELLED", execution_id=None)

    try:
        ResultFinalizationService(db).finalize_manual_review(final_payload(2), execution_id="exec-current")
        raise AssertionError("expected ExecutionOwnerChanged")
    except ExecutionOwnerChanged:
        pass

    task = db.get(PricingTask, 2)
    assert task.task_status == "CANCELLED"
    assert db.query(PricingResult).count() == 0
