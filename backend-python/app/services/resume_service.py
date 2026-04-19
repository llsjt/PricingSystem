"""
Agent 级断点续跑判定服务
=======================

当某个 Agent 失败时，dispatch 层会让 worker 重新执行整条 Crew。本服务查询
agent_run_log 的历史记录，决定"本次重跑应该从哪个 Agent 开始执行"。

规则：
- 按 display_order 升序遍历 4 个 Agent（DATA_ANALYSIS=1, MARKET_INTEL=2,
  RISK_CONTROL=3, MANAGER_COORDINATOR=4）
- 每个 Agent 若存在 stage=completed 且 raw_output_json 非空的历史记录，视作
  "已完成"
- 找到第一个"未完成"的 Agent，从它的 order 开始执行；它之前的 Agent 直接复用
  DB 里的 raw_output_json 注入下游 context，不再调用 LLM
- 必须是**连续前缀**：即使 order=3 已 completed、order=2 未完成，也要从
  order=2 重跑，因为 MANAGER_COORDINATOR 的 Task.context 依赖上游所有 Agent

返回值说明：
- start_from_order:  1~5 的整数，1 表示全量执行，5 表示全部已完成（不应进入重试）
- prior_outputs_by_order: {order: raw_output_dict}，只含 start_from 之前的已完成 Agent
"""

from typing import Any

from sqlalchemy.orm import Session

from app.repos.log_repo import LogRepo


# 与 OrchestrationService._AGENT_META 保持一致的顺序
AGENT_ORDER: list[tuple[str, int]] = [
    ("DATA_ANALYSIS", 1),
    ("MARKET_INTEL", 2),
    ("RISK_CONTROL", 3),
    ("MANAGER_COORDINATOR", 4),
]


class ResumeService:
    """决定一次（重新）执行从哪个 Agent 开始。"""

    def __init__(self, db: Session):
        self.log_repo = LogRepo(db)

    def compute_resume_point(self, task_id: int) -> tuple[int, dict[int, dict[str, Any]]]:
        """根据 agent_run_log 历史记录计算续跑断点。

        返回 (start_from_order, prior_outputs_by_order)：
        - start_from_order=1: 全新任务或历史记录不可用，全量执行
        - start_from_order=3: DATA/MARKET 已完成，从 RISK_CONTROL 开始重跑
        - start_from_order=5: 4 个 Agent 全部已完成（理论上不会进入重试）

        prior_outputs_by_order 是 {display_order: raw_output_dict}，只含断点之前的记录。
        """
        completed_rows = self.log_repo.list_completed_raw_outputs(task_id)

        prior: dict[int, dict[str, Any]] = {}
        start_from = 1
        found_break = False
        for _agent_code, order in AGENT_ORDER:
            raw = completed_rows.get(order)
            if raw is None:
                start_from = order
                found_break = True
                break
            prior[order] = raw

        if not found_break:
            # 全部 4 个 Agent 都已完成
            start_from = len(AGENT_ORDER) + 1

        return start_from, prior
