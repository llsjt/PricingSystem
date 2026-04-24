from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.agent_run_log import AgentRunLog
from app.models.pricing_task import PricingTask
from app.models.user_llm_config import UserLlmConfig
from app.repos.task_repo import TaskRepo
from app.schemas.task import DispatchTaskRequest
from app.services.dispatch_service import DispatchService
from app.utils.crypto_utils import decrypt_api_key, encrypt_api_key


class StubQueueService:
    def can_accept(self) -> bool:
        return True

    def queue_size(self) -> int:
        return 0


def build_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[PricingTask.__table__, AgentRunLog.__table__, UserLlmConfig.__table__])
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)()


def create_task(
    db: Session,
    *,
    task_id: int,
    status: str,
    strategy_goal: str = "MAX_PROFIT",
    constraint_text: str = "",
    retry_count: int = 0,
) -> PricingTask:
    task = PricingTask(
        id=task_id,
        task_code=f"TASK-{task_id}",
        shop_id=1,
        product_id=1000 + task_id,
        current_price=Decimal("19.90"),
        baseline_profit=Decimal("10.00"),
        task_status=status,
        strategy_goal=strategy_goal,
        constraint_text=constraint_text,
        trace_id=f"trace-{task_id}",
        retry_count=retry_count,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def test_recover_pending_tasks_keeps_persisted_payload_available_for_claiming():
    db = build_session()
    queued = create_task(
        db,
        task_id=101,
        status="QUEUED",
        strategy_goal="CLEARANCE",
        constraint_text="最低利润率不低于5%",
    )
    running = create_task(
        db,
        task_id=102,
        status="RUNNING",
        strategy_goal="MARKET_SHARE",
        constraint_text="最大降价幅度不超过10%",
    )
    queue = StubQueueService()
    service = DispatchService(db)

    recovered = service.recover_pending_tasks(queue, max_retries=3)
    repo = TaskRepo(db)
    first_claim = repo.claim_next_dispatchable()
    second_claim = repo.claim_next_dispatchable()

    assert recovered == 2
    assert first_claim is not None
    assert second_claim is not None

    first_request = service.build_dispatch_request(first_claim)
    second_request = service.build_dispatch_request(second_claim)
    assert [first_request.task_id, second_request.task_id] == [queued.id, running.id]
    assert first_request.strategy_goal == "CLEARANCE"
    assert first_request.constraints == "最低利润率不低于5%"
    assert second_request.strategy_goal == "MARKET_SHARE"
    assert second_request.constraints == "最大降价幅度不超过10%"

    refreshed_running = db.get(PricingTask, running.id)
    assert refreshed_running is not None
    assert refreshed_running.task_status == "RUNNING"
    assert refreshed_running.retry_count == 1
    assert "worker restarted" in str(refreshed_running.failure_reason)


def test_handle_worker_failure_requeues_until_retry_budget_then_marks_failed():
    db = build_session()
    task = create_task(
        db,
        task_id=201,
        status="RUNNING",
        strategy_goal="CLEARANCE",
        constraint_text="最低售价不低于69元",
    )
    request = DispatchTaskRequest(
        taskId=task.id,
        productId=task.product_id,
        productIds=[task.product_id],
        strategyGoal=task.strategy_goal,
        constraints=task.constraint_text,
        traceId=task.trace_id,
    )
    service = DispatchService(db)

    first = service.handle_worker_failure(request, "first boom", max_retries=1)
    refreshed = db.get(PricingTask, task.id)

    assert first.accepted is True
    assert first.status == "RETRYING"
    assert refreshed is not None
    assert refreshed.task_status == "RETRYING"
    assert refreshed.retry_count == 1
    assert refreshed.failure_reason == "first boom"

    second = service.handle_worker_failure(request, "second boom", max_retries=1)
    refreshed = db.get(PricingTask, task.id)

    assert second.accepted is False
    assert second.status == "FAILED"
    assert refreshed is not None
    assert refreshed.task_status == "FAILED"
    assert refreshed.retry_count == 1
    assert refreshed.failure_reason == "second boom"


def test_recover_pending_tasks_marks_stale_running_failed_after_retry_budget():
    db = build_session()
    task = create_task(
        db,
        task_id=202,
        status="RUNNING",
        retry_count=2,
    )
    service = DispatchService(db)

    recovered = service.recover_pending_tasks(StubQueueService(), max_retries=2)
    refreshed = db.get(PricingTask, task.id)

    assert recovered == 0
    assert refreshed is not None
    assert refreshed.task_status == "FAILED"
    assert refreshed.failure_reason == "worker restarted after retry budget exhausted"


def test_dispatch_keeps_persisted_llm_snapshot_for_already_queued_task():
    db = build_session()
    task = create_task(
        db,
        task_id=301,
        status="QUEUED",
        strategy_goal="MARKET_SHARE",
        constraint_text="利润率不低于10%",
    )
    task.llm_api_key_enc = encrypt_api_key("sk-persisted")
    task.llm_base_url = "https://persisted.example.com/v1"
    task.llm_model = "persisted-model"
    db.add(task)
    db.commit()
    db.refresh(task)
    request = DispatchTaskRequest(
        taskId=task.id,
        productId=task.product_id,
        productIds=[task.product_id],
        strategyGoal=task.strategy_goal,
        constraints=task.constraint_text,
        traceId=task.trace_id,
        llmApiKey="sk-current",
        llmBaseUrl="https://dashscope.aliyuncs.com/compatible-mode/v1",
        llmModel="qwen3.5-122b-a10b",
    )
    service = DispatchService(db)

    response = service.dispatch(request, StubQueueService())
    refreshed = db.get(PricingTask, task.id)

    assert response.accepted is True
    assert response.status == "QUEUED"
    assert refreshed is not None
    assert refreshed.llm_api_key_enc is not None
    assert decrypt_api_key(refreshed.llm_api_key_enc) == "sk-persisted"
    assert refreshed.llm_base_url == "https://persisted.example.com/v1"
    assert refreshed.llm_model == "persisted-model"


def test_execute_queued_by_task_id_builds_request_and_passes_execution_id():
    db = build_session()
    task = create_task(
        db,
        task_id=401,
        status="QUEUED",
        strategy_goal="MARKET_SHARE",
        constraint_text="利润率不低于10%",
    )
    task.llm_api_key_enc = encrypt_api_key("sk-current")
    task.llm_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    task.llm_model = "qwen3.5-122b-a10b"
    db.add(task)
    db.commit()
    db.refresh(task)

    service = DispatchService(db)
    captured = {}

    def _fake_execute_queued(req, worker_id=None, execution_id=None):  # noqa: ANN001
        captured["req"] = req
        captured["execution_id"] = execution_id

    service.execute_queued = _fake_execute_queued  # type: ignore[method-assign]

    service.execute_queued_by_task_id(task.id, "exec-401")

    assert captured["req"].task_id == task.id
    assert captured["execution_id"] == "exec-401"


def test_execute_queued_uses_persisted_llm_snapshot_from_task(monkeypatch):
    db = build_session()
    task = create_task(
        db,
        task_id=402,
        status="QUEUED",
        strategy_goal="MARKET_SHARE",
        constraint_text="利润率不低于10%",
    )
    task.llm_api_key_enc = encrypt_api_key("sk-persisted")
    task.llm_base_url = "https://persisted.example.com/v1"
    task.llm_model = "persisted-model"
    db.add(task)
    db.commit()
    db.refresh(task)

    request = DispatchTaskRequest(
        taskId=task.id,
        productId=task.product_id,
        productIds=[task.product_id],
        strategyGoal=task.strategy_goal,
        constraints=task.constraint_text,
        traceId=task.trace_id,
        llmApiKey="sk-request",
        llmBaseUrl="https://request.example.com/v1",
        llmModel="request-model",
    )
    service = DispatchService(db)
    captured = {}

    class StubContextService:
        def __init__(self, db_session):  # noqa: ANN001
            self.db_session = db_session

        def load_product_context(self, product_id):  # noqa: ANN001
            return SimpleNamespace(
                product_id=product_id,
                current_price=Decimal("19.90"),
                cost_price=Decimal("10.00"),
                stock=100,
            )

        def load_daily_metrics(self, product_id, limit=30):  # noqa: ANN001
            return []

        def load_traffic(self, product_id, limit=30):  # noqa: ANN001
            return []

        def infer_baseline_sales(self, metrics, stock):  # noqa: ANN001
            return 12

        def infer_baseline_profit(self, current_price, cost_price, monthly_sales):  # noqa: ANN001
            return Decimal("118.80")

    class StubOrchestrationService:
        def __init__(self, db_session, execution_id=None):  # noqa: ANN001
            self.db_session = db_session
            self.execution_id = execution_id

        def run(self, payload):  # noqa: ANN001
            captured["payload"] = payload
            return None

    monkeypatch.setattr("app.services.dispatch_service.ContextService", StubContextService)
    monkeypatch.setattr("app.services.dispatch_service.OrchestrationService", StubOrchestrationService)

    service.execute_queued(request, execution_id="exec-402")

    payload = captured["payload"]
    assert payload.llm_api_key == "sk-persisted"
    assert payload.llm_base_url == "https://persisted.example.com/v1"
    assert payload.llm_model == "persisted-model"


def test_handle_worker_failure_clears_llm_snapshot_when_retry_budget_exhausted():
    db = build_session()
    task = create_task(
        db,
        task_id=501,
        status="RUNNING",
        strategy_goal="MARKET_SHARE",
        constraint_text="利润率不低于10%",
        retry_count=1,
    )
    task.llm_api_key_enc = encrypt_api_key("sk-persisted")
    task.llm_base_url = "https://persisted.example.com/v1"
    task.llm_model = "persisted-model"
    db.add(task)
    db.commit()
    db.refresh(task)

    request = DispatchTaskRequest(
        taskId=task.id,
        productId=task.product_id,
        productIds=[task.product_id],
        strategyGoal=task.strategy_goal,
        constraints=task.constraint_text,
        traceId=task.trace_id,
    )
    service = DispatchService(db)

    response = service.handle_worker_failure(request, "boom", max_retries=1)
    refreshed = db.get(PricingTask, task.id)

    assert response.accepted is False
    assert response.status == "FAILED"
    assert refreshed is not None
    assert refreshed.task_status == "FAILED"
    assert refreshed.llm_api_key_enc is None
    assert refreshed.llm_base_url is None
    assert refreshed.llm_model is None
