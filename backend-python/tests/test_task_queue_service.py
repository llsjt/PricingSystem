from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.pricing_result import PricingResult
from app.models.pricing_task import PricingTask
from app.repos.task_repo import TaskRepo
from app.schemas.result import TaskFinalResult
from app.tools.result_writer_tool import ResultWriterTool


def build_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[PricingTask.__table__, PricingResult.__table__])
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)()


def create_task(db: Session, *, task_id: int, status: str) -> PricingTask:
    task = PricingTask(
        id=task_id,
        task_code=f"TASK-{task_id}",
        shop_id=1,
        product_id=1000 + task_id,
        current_price=Decimal("19.90"),
        baseline_profit=Decimal("10.00"),
        task_status=status,
        strategy_goal="MAX_PROFIT",
        constraint_text="",
        trace_id=f"trace-{task_id}",
        retry_count=0,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def test_claim_next_dispatchable_promotes_oldest_task_to_running():
    db = build_session()
    create_task(db, task_id=101, status="QUEUED")
    create_task(db, task_id=102, status="RETRYING")
    repo = TaskRepo(db)

    first = repo.claim_next_dispatchable()
    second = repo.claim_next_dispatchable()

    assert first is not None
    assert second is not None
    assert first.id == 101
    assert second.id == 102
    assert db.get(PricingTask, 101).task_status == "RUNNING"
    assert db.get(PricingTask, 102).task_status == "RUNNING"
    assert repo.claim_next_dispatchable() is None


def test_write_final_result_skips_cancelled_task():
    db = build_session()
    task = create_task(db, task_id=201, status="CANCELLED")

    ResultWriterTool(db).write_final_result(
        TaskFinalResult(
            taskId=task.id,
            finalPrice=Decimal("25.50"),
            expectedSales=120,
            expectedProfit=Decimal("300.00"),
            profitGrowth=Decimal("80.00"),
            isPass=True,
            executeStrategy="直接执行",
            resultSummary="should be ignored",
            suggestedMinPrice=Decimal("24.00"),
            suggestedMaxPrice=Decimal("26.00"),
        )
    )

    assert db.get(PricingTask, task.id).task_status == "CANCELLED"
    assert db.query(PricingResult).count() == 0


def test_write_final_result_forces_manual_review_strategy():
    db = build_session()
    task = create_task(db, task_id=202, status="RUNNING")
    db.add(
        PricingResult(
            id=1,
            task_id=task.id,
            final_price=Decimal("20.00"),
            expected_sales=100,
            expected_profit=Decimal("200.00"),
            profit_growth=Decimal("20.00"),
            is_pass=1,
            execute_strategy="直接执行",
            result_summary="existing",
            review_required=0,
        )
    )
    db.commit()

    ResultWriterTool(db).write_final_result(
        TaskFinalResult(
            taskId=task.id,
            finalPrice=Decimal("25.50"),
            expectedSales=120,
            expectedProfit=Decimal("300.00"),
            profitGrowth=Decimal("80.00"),
            isPass=True,
            executeStrategy="直接执行",
            resultSummary="requires review",
            suggestedMinPrice=Decimal("24.00"),
            suggestedMaxPrice=Decimal("26.00"),
        )
    )

    refreshed = db.get(PricingTask, task.id)
    result = db.query(PricingResult).one()

    assert refreshed.task_status == "MANUAL_REVIEW"
    assert result.execute_strategy == "人工审核"
    assert result.review_required == 1
