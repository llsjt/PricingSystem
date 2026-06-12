from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql import text

from app.db.base import Base
from app.models.pricing_task import PricingTask
from app.schemas.result import TaskFinalResult


def build_result_session() -> Session:
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


def create_pricing_task(
    db: Session,
    *,
    task_id: int,
    status: str = "RUNNING",
    execution_id: str | None = "exec-current",
) -> PricingTask:
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


def final_result(task_id: int) -> TaskFinalResult:
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
