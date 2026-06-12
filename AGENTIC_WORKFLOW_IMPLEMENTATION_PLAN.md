# 四 Agent 轻量化优化实施方案（9 分版）

## 1. 核心结论

本方案只优化 Python 侧 4 个 Agent 的设计、架构、function calling 和 agent loop：

- `DATA_ANALYSIS`：经营测算 Agent
- `MARKET_INTEL`：市场信号 Agent
- `RISK_CONTROL`：风控解释 Agent
- `MANAGER_COORDINATOR`：经理仲裁 Agent

9 分版的核心策略是：

```text
前三个 Agent 弱 loop，经理 Agent 采用受控仲裁决策模式。
预计算是稳定底座，function calling 是条件性复核。
Agent 负责判断和解释，确定性代码负责安全边界。
```

与上一版相比，本版补齐了 6 个扣分点：

| 扣分点 | 9 分版修正 |
|------|------------|
| 业务场景不足 | 增加按 `strategy_goal` 区分的经理仲裁目标函数 |
| 触发条件偏自然语言 | 明确 Fast Path / Verification Path 的可判定条件 |
| 风控复核参数不完整 | 明确 `evaluate_risk_rules` 参数绑定，补齐 `min_price`、`max_price`、`force_manual_review` |
| `audit_summary_fields` 表述不准确 | 修正为“元数据一致性”，不再声称它决定 `toolAudit.resultSummary` |
| 工具失败降级承诺过强 | 改为“prompt 要求保守输出 + 自动化测试验证”，不承诺 runtime 自动兜底 |
| 验收偏 SQL 手查 | 增加自动化测试、fake LLM 场景、负例和演示数据集 |

本轮仍然不改：

- Java 接口、任务状态机、SSE、RabbitMQ、数据库结构。
- 前端页面、批量流程、价格应用流程。
- `OpenAICompatibleCrewAILLM.call()` 工具调用协议循环。
- 新框架、新状态表、新 memory、新外层 agent loop。

## 2. 9 分目标与验收标准

### 2.1 9 分目标定义

本轮 9 分以上的目标不是让 Agent 更像自动化黑盒，而是让运营用户和评审者都能从经理卡片和审计记录中判断：

1. **结果为什么可信**：用了哪些确定性数据、哪些 Agent 意见一致、是否经过工具复核。
2. **风险在哪里**：是否低于安全底价、利润是否下降、竞品样本是否不足、工具是否失败。
3. **下一步做什么**：确认应用、人工复核、调整约束、等待数据、重新执行或暂不调价。
4. **是否仍然克制**：所有 Agent 能力都落在现有 `AgentOpinionV1 + toolAudit + manager arbitration` 契约内。

### 2.2 9 分验收标准

本方案要达到 9 分以上，必须同时满足：

| 维度 | 9 分标准 |
|------|----------|
| 业务价值 | 能解释“为什么这个价格可信”，并区分利润、跟价、清仓、保守等策略目标 |
| Agent 特征 | 真正的自主性集中在经理 Agent 的诊断、复核、反思和仲裁 |
| Function calling | 工具调用由业务触发，不是每轮机械调用 |
| 代码收敛 | 本轮只改 Python Agent prompt、工具授权、工具 wrapper 参数和必要测试，不新造 runtime |
| 风控一致性 | 经理风控复核与预计算风控使用同一套约束口径 |
| 可验证性 | Fast Path、Verification Path、工具失败、输出异常都有自动化断言 |
| 用户可感知 | `resultSummary` / `arbitrationReason` 能说清采纳依据、关键数字、风险判断、下一步动作 |
| 决策路径 | `AgentOpinionV1.relations` 表达依赖、采纳、冲突，`decision` 表达仲裁结果，`toolAudit` 表达工具证据 |

## 3. 当前架构判断

现有链路已经适合做轻量 Agentic Workflow：

```text
DispatchService.execute_queued()
  -> OrchestrationService.run()
     -> build_pricing_crew()
        -> DATA_ANALYSIS / MARKET_INTEL / RISK_CONTROL 并行
        -> MANAGER_COORDINATOR 串行仲裁
     -> _format_opinions_for_manager_context()
     -> OpenAICompatibleCrewAILLM.call()
        -> tools 注入
        -> tool_calls 接收
        -> 工具名 / 参数 / 权限校验
        -> 工具执行
        -> toolAudit 记录
        -> 继续模型推理
     -> _normalize_output_with_agent_opinion()
     -> _validate_agent_output()
     -> _build_manager_card()
     -> _finalize_result()
     -> agent_run_log / pricing_result 写回
```

注意：`OpenAICompatibleCrewAILLM.call()` 是 OpenAI 兼容的**工具调用协议循环**，负责 `tool_calls` 解析、权限校验、超时、审计和工具结果回填。它不是完整 Agent runtime，因为它没有长期状态、目标管理、计划队列、环境观察器或跨任务记忆。本方案称为 Agentic Workflow，而不是新增完整 Agent Runtime。

因此不新增：

- `AgentLoop`
- `ManagerLoop`
- `VerificationLoop`
- `PromptTemplateService`
- Agent memory
- Agent 状态表

正确做法是复用：

- `backend-python/app/tools/tool_registry.py` 的 `get_tools_for_agent()`
- `backend-python/app/crew/crewai_runtime.py` 的 `OpenAICompatibleCrewAILLM.call()` 工具调用协议循环
- `backend-python/app/schemas/agent.py` 的 `AgentOpinionV1`
- `backend-python/app/services/orchestration_service.py` 的 `_format_opinions_for_manager_context()`
- `raw_output_json.toolAudit`
- `_precompute_data_projection()`、`_precompute_competitor_summary()`、`_precompute_risk_projection()`

## 4. 四 Agent 设计

### 4.1 `DATA_ANALYSIS`：经营测算 Agent

定位：回答“这个价格预计卖多少、赚多少”。

核心输出复用现有字段：

- `suggestedPrice`
- `expectedSales`
- `expectedProfit`
- `confidence`
- `summary`
- `agentOpinion`

不做：

- 不评价竞品可信度。
- 不做风控裁决。
- 不决定最终价格。
- 不常态重复已经预计算过的利润 / 销量测算。

Function calling 策略：

| 工具 | 使用条件 |
|------|----------|
| `summarize_product_data` | 仅在商品上下文缺少摘要时使用 |
| `estimate_sales_volume` | 需要比较多个候选价销量时使用 |
| `estimate_profit` | 利润改善不明确时使用 |

弱 loop：

```text
Observe:
  读取预计算经营数据和商品上下文。

Diagnose:
  判断历史销量、成本、当前价、基线利润是否足以支撑建议价。

Act:
  只有候选价比较或利润不确定时才调用工具。

Output:
  给出经营候选价、销量、利润、置信度和中文摘要。
```

### 4.2 `MARKET_INTEL`：市场信号 Agent

定位：回答“这个价格是否脱离市场，市场数据是否可信”。

核心输出复用现有字段：

- `suggestedPrice`
- `marketFloor`
- `marketMedian`
- `marketAverage`
- `marketCeiling`
- `validCompetitorCount`
- `sourceStatus`
- `dataQuality`
- `confidence`
- `summary`
- `agentOpinion`

不做：

- 不计算利润。
- 不调用销量 / 利润工具。
- 不做风控裁决。
- 不包装成实时外部市场智能。

Function calling 策略：

| 工具 | 使用条件 |
|------|----------|
| `query_competitor_summary` | 只读取 `ToolContext.precomputed_competitor_summary`，不外查数据 |

市场可信度规则：

```text
当 sourceStatus != OK：
  市场价格只能作为弱参考。

当 validCompetitorCount < 3：
  不输出强跟价结论。

当 dataQuality = LOW：
  市场价带不能约束 finalPrice，只能用于风险提示。

当 marketCeiling <= 0：
  不得使用“最终价不得高于市场天花板价”这类硬规则。
```

### 4.3 `RISK_CONTROL`：风控解释 Agent

定位：解释确定性风控结果，不做自由策略推理。

核心输出复用现有字段：

- `isPass`
- `safeFloorPrice`
- `suggestedPrice`
- `riskLevel`
- `needManualReview`
- `summary`
- `agentOpinion`

不做：

- 不追求利润最大化。
- 不根据市场数据调价。
- 不自由判断成本、毛利、折扣边界。
- 不新增 `violations`、`maxAllowedDiscount` 等底层工具尚未稳定返回的字段。

Function calling 策略：

| 工具 | 使用条件 |
|------|----------|
| `evaluate_risk_rules` | 风控核心能力，第一版仍以预计算结果为主；经理最终候选价存在疑问时可复核 |

弱 loop：

```text
Observe:
  读取预计算风控结果 risk_projection。

Diagnose:
  解释 isPass、safeFloorPrice、riskLevel、needManualReview。

Act:
  原则上不重复计算；需要复核候选价时调用 evaluate_risk_rules。

Output:
  输出稳定、保守、可被经理引用的风控结论。
```

### 4.4 `MANAGER_COORDINATOR`：经理仲裁 Agent

定位：读取前三个 Agent 的结构化意见，按业务目标函数仲裁，必要时 function calling 复核。

这是本轮唯一完整 agent loop。

不做：

- 不重跑上游 Agent。
- 不写库。
- 不应用价格。
- 不改变任务状态。
- 不把 `selectedAgent` 当成唯一决策依据。

经理 loop：

```text
Observe:
  读取 DATA_ANALYSIS / MARKET_INTEL / RISK_CONTROL 的 AgentOpinion 和业务字段。

Diagnose:
  判断是否存在价格分歧、利润疑问、市场数据不足、风控风险。

Plan:
  满足 Fast Path 条件时不调用工具。
  出现利润或风控疑问时进入 Verification Path。

Act:
  利润疑问 -> estimate_profit，必要时 estimate_sales_volume
  风控疑问 -> evaluate_risk_rules
  市场数据不足 -> 不查外部数据，只降低 consensusScore 并偏保守

Reflect:
  对比工具结果与三方意见。
  工具失败或冲突时，优先遵守风控底线和策略目标。

Decide:
  输出 finalPrice、expectedSales、expectedProfit、isPass、resultSummary、
  arbitrationReason、disagreementSummary、selectedAgent、selectedPrice、agentOpinion。
```

确认口径：

| 口径 | 判定 | 写入位置 |
|------|------|----------|
| 可确认 | `isPass=true`，风控通过，利润改善明确，市场数据可信或不构成反对证据 | `resultSummary` 首句 |
| 建议复核 | 存在竞品不足、利润改善弱、三方价格分歧、工具失败、约束冲突等情况 | `resultSummary` 首句 |
| 不建议确认 | `isPass=false`、低于安全底价、利润明显恶化、关键数据缺失 | `resultSummary` 首句 |

这三类口径不新增 schema，写入 `resultSummary` 首句，并在 `arbitrationReason` 中解释原因。

## 5. 业务目标函数

经理 Agent 不能只有一套“利润优先”规则。本轮不新增输入，直接复用已有 `payload.strategy_goal` / `strategy_cn`。

固定策略映射：

| `strategy_goal` 输入值 | 中文口径 | 经理优先级 | 允许的取舍 |
|------------------------|----------|------------|------------|
| `MAX_PROFIT` | 利润优先 / 日常利润优化 | 风控底线 > 利润改善 > 市场参考 | 利润不改善时不激进降价 |
| `MARKET_SHARE` | 市场份额优先 / 竞品跟价 | 风控底线 > 市场可信度 > 利润影响 | 市场数据可信时可贴近市场中位价 |
| `CLEARANCE` | 清仓促销 | 风控底线 > 销量改善 > 利润影响 | 可接受较低利润，但不得突破安全底价 |
| 空值或未知值 | 按 `MAX_PROFIT` 处理 | 风控底线 > 利润改善 > 市场参考 | 不因未知策略目标扩大降价权限 |

注意：

- 没有库存、活动、优惠券等上下文时，不得编造库存压力或活动目标。
- 只有 `strategy_goal=CLEARANCE` 时才进入清仓促销口径；不得根据销量下降、竞品低价或自然语言摘要自行推断清仓。
- `force_manual_review=true` 是风控约束，不是策略目标；经理必须输出人工复核口径。
- 当 `strategy_goal` 无法识别时，默认按 `MAX_PROFIT` / 日常利润优化处理。
- `resultSummary` 必须说明当前采用的是哪个策略目标。

## 6. Manager 可判定触发条件

### 6.1 Fast Path

满足以下条件时，经理不调用工具：

```text
1. DATA_ANALYSIS / MARKET_INTEL / RISK_CONTROL 三方建议价相对偏差 <= 2%
   或绝对差 <= 0.50 元。

2. RISK_CONTROL.isPass = true。

3. DATA_ANALYSIS.expectedProfit > baselineProfit。

4. MARKET_INTEL.sourceStatus = OK。

5. MARKET_INTEL.dataQuality != LOW。

6. DATA_ANALYSIS.confidence >= 0.6 且 MARKET_INTEL.confidence >= 0.6。
```

Fast Path 输出要求：

- 不调用 `estimate_profit`、`estimate_sales_volume`、`evaluate_risk_rules`。
- 在 `agentOpinion.decision.arbitrationDecision` 写入 `FAST_PATH`。
- `resultSummary` 说明“无需复核”的业务原因。

### 6.2 Verification Path

触发任一条件时，经理进入复核路径：

| 触发条件 | 工具行为 | 决策路径 |
|----------|----------|----------|
| `DATA_ANALYSIS.expectedProfit <= baselineProfit` | 调用 `estimate_profit` | `PROFIT_VERIFICATION` |
| 三方建议价相对偏差 > 2% 且绝对差 > 0.50 元 | 先调用 `estimate_profit`；当销量假设缺失导致利润无法解释时，再调用 `estimate_sales_volume` | `PRICE_DISAGREEMENT` |
| 最终候选价 <= `safeFloorPrice * 1.02` | 调用 `evaluate_risk_rules` | `RISK_VERIFICATION` |
| `RISK_CONTROL.isPass = false` | 调用 `evaluate_risk_rules`；工具失败时输出保守降级 | `RISK_VERIFICATION` |
| `MARKET_INTEL.sourceStatus != OK` 或 `dataQuality = LOW` | 不查外部市场，降低 `consensusScore` | `MARKET_WEAK_SIGNAL` |
| 工具失败 / 超时 / 参数错误 | 不重试无限循环，输出保守结论 | `CONSERVATIVE_DOWNGRADE` |

注意：

- 不新增 `verificationPath` 字段。
- 决策路径写入现有 `agentOpinion.decision.arbitrationDecision`。
- 复核依据写入现有 `agentOpinion.evidence`。
- 当 `CREWAI_TOOL_AUDIT_ENABLED=false` 时，不能用“无 `toolAudit`”判断 Fast Path，只能验证经理输出是否仍然合法且保守。
- Fast Path / Verification Path 是经理 Agent 的可观测决策路径，不是 `OrchestrationService` 中新增的确定性分支。自动化测试以 `toolAudit`、`arbitrationDecision`、`resultSummary` 和最终 `isPass` 作为观测口径。

## 7. Function Calling 设计

### 7.1 工具授权矩阵

| Agent | 允许工具 | 禁止工具 |
|------|----------|----------|
| `DATA_ANALYSIS` | `summarize_product_data`, `estimate_sales_volume`, `estimate_profit` | `query_competitor_summary`, `evaluate_risk_rules` |
| `MARKET_INTEL` | `query_competitor_summary` | `estimate_sales_volume`, `estimate_profit`, `evaluate_risk_rules` |
| `RISK_CONTROL` | `evaluate_risk_rules` | `summarize_product_data`, `query_competitor_summary`, `estimate_sales_volume`, `estimate_profit` |
| `MANAGER_COORDINATOR` | `estimate_sales_volume`, `estimate_profit`, `evaluate_risk_rules` | `summarize_product_data`, `query_competitor_summary` |

S1 必改：

```python
# backend-python/app/tools/tool_registry.py
ToolRegistration(
    name="evaluate_risk_rules",
    tool=evaluate_risk_rules,
    allowed_agents=frozenset({"RISK_CONTROL", "MANAGER_COORDINATOR"}),
    audit_summary_fields=("is_pass", "safe_floor_price", "suggested_price", "risk_level", "need_manual_review", "margin"),
)
```

说明：

- 使用现有 `ToolRegistration`，不新增 `ToolSpec`。
- `audit_summary_fields` 当前只是注册元数据，`OpenAICompatibleCrewAILLM._build_audit_entry()` 并不会读取它生成 `toolAudit.resultSummary`。
- 修正该字段是为了元数据一致性，不应声称它会修复 `toolAudit` 摘要为空问题。

### 7.2 风控工具参数一致性

经理调用 `evaluate_risk_rules` 时必须绑定真实约束：

```text
current_price      <- product.current_price
cost_price         <- product.cost_price
candidate_price    <- 经理裁决后的 finalPrice
min_profit_rate    <- payload.constraints.min_profit_rate
max_discount_rate  <- payload.constraints.max_discount_rate
min_price          <- payload.constraints.min_price
max_price          <- payload.constraints.max_price
force_manual_review <- payload.constraints.force_manual_review
```

当前源码事实：

- `RiskRuleTool.evaluate()` 支持并使用 `force_manual_review`。
- `crewai_tools.evaluate_risk_rules()` 当前没有暴露 `force_manual_review` 参数。

执行决策：本方案固定采用 A，不保留第二条实现路径。

必须给 `evaluate_risk_rules()` wrapper 增加带默认值的 `force_manual_review` 参数，并透传给 `RiskRuleTool.evaluate()`。这样经理复核和 `_precompute_risk_projection()` 使用同一套风控口径，避免预计算风控与经理复核出现两套结论。

### 7.3 工具失败边界

不能承诺“工具失败任务一定不崩”。

准确表述是：

```text
runtime 会把工具错误包装成 tool message 返回给 LLM。
prompt 要求经理 Agent 在看到工具错误后输出保守裁决。
当 LLM 最终输出非法 JSON 时，仍会触发 AgentOutputValidationError。
因此必须用 fake LLM / mock completion 测试工具失败后的经理输出。
```

## 8. Prompt 改造

### 8.1 前三个 Agent

前三个 Agent prompt 要短、稳、少越权。

统一原则：

```text
请优先使用已提供的预计算结果。
仅当预计算结果不足以支撑结论时，才调用授权工具。
不要分析其他 Agent 的职责。
不要编造缺失数据。
所有用户可见字段必须使用中文。
```

### 8.2 经理 Agent

经理 prompt 从强制工具调用改为条件性复核。

替换当前类似内容：

```text
使用 estimate_sales_volume 和 estimate_profit 工具验证最终价格的预期效果
```

改为：

```text
先判断是否满足 Fast Path。
满足 Fast Path 时，不调用工具，直接仲裁。

如进入 Verification Path：
- 利润疑问：调用 estimate_profit，必要时调用 estimate_sales_volume。
- 风控疑问：调用 evaluate_risk_rules。
- 市场数据不足：不要查询外部数据，只降低 consensusScore 并采用保守价格。

调用 evaluate_risk_rules 时：
- candidate_price 必须使用你裁决后的 finalPrice。
- 不得自行猜测 min_profit_rate、max_discount_rate、min_price、max_price、force_manual_review。
- 缺少约束时，不得声称已完成风控复核。
```

经理输出要求：

```text
resultSummary 必须按以下顺序组织，尽量控制在 80-140 字：

【结论】可确认 / 建议复核 / 不建议确认。
【依据】三方意见是否一致，价格偏差百分比，采用或折中的原因。
【收益】预期利润、利润变化，是否优于基线。
【风险】风控是否通过，是否低于 safeFloorPrice，竞品数据是否可靠。
【下一步】确认应用、人工复核、调整约束、等待数据、重新执行或暂不调价。

arbitrationReason 必须说明：
1. 为什么采纳或拒绝 DATA_ANALYSIS
2. 为什么采纳或拒绝 MARKET_INTEL
3. 为什么采纳或拒绝 RISK_CONTROL
4. 是否发生工具复核
5. 工具失败时为什么采用保守结论

当最终结果是折中价：
selectedAgent 和 selectedPrice 必须输出 JSON null，
不要输出字符串 "null"。
```

运营动作只能来自以下集合：

| 动作 | 触发 |
|------|------|
| 确认应用 | 风控通过、利润改善、三方分歧小 |
| 人工复核 | 利润改善弱、三方价格分歧、工具失败、市场数据不足 |
| 调整约束 | 风控不通过、候选价低于安全底价、约束冲突 |
| 等待数据 | 竞品样本不足、`sourceStatus != OK`、`dataQuality=LOW` |
| 重新执行 | 工具失败、输入数据更新、约束调整后 |
| 暂不调价 | 利润不改善且非清仓 / 跟价场景 |

### 8.3 `AgentOpinionV1` 决策路径契约

本轮 canonical contract 是 `AgentOpinionV1`。前三个 Agent 的业务字段仍保留在各自 Output 顶层用于兼容，但经理仲裁优先依赖 `AgentOpinionV1.pricing / impact / market / risk / evidence / relations / decision`，不新增 `ManagerContextDTO`，不要求 LLM 再输出一套平行字段。

不新增字段，复用现有字段：

| 目标 | 字段 |
|------|------|
| 决策路径 | `agentOpinion.decision.arbitrationDecision` |
| 决策理由 | `agentOpinion.decision.arbitrationReason` / `arbitrationReason` |
| 关键证据 | `agentOpinion.evidence` |
| 工具证据 | `raw_output_json.toolAudit` |
| 用户摘要 | `resultSummary` |
| 分歧说明 | `disagreementSummary` |

固定 `arbitrationDecision` 枚举值：

- `FAST_PATH`
- `PROFIT_VERIFICATION`
- `RISK_VERIFICATION`
- `PRICE_DISAGREEMENT`
- `MARKET_WEAK_SIGNAL`
- `CONSERVATIVE_DOWNGRADE`

`AgentOpinionV1` 使用规则：

| 字段 | 用法 |
|------|------|
| `evidence` | 放可核验证据，如 `baselineProfit`、`marketMedian`、`safeFloorPrice`、工具复核结果 |
| `rationale.thinking` | 放简短推理，不写长链路自述 |
| `rationale.assumptions` | 放假设，如“竞品样本不足时市场建议仅作弱参考” |
| `rationale.notes` | 放降级、数据不足、工具失败等说明 |
| `relations.dependsOnOpinionIds` | 经理依赖的前三个 Agent opinionId |
| `relations.acceptedOpinionIds` | 明确采纳的意见 |
| `relations.rejectedOpinionIds` | 明确不采纳的意见 |
| `relations.conflictOpinionIds` | 价格分歧或风险冲突的意见 |
| `relations.selectedOpinionIds` | 最终主要采纳的意见；折中价时可为空 |
| `decision.decisionType` | `FOLLOW` / `MERGE` / `REJECT_ALL` / `OVERRIDE` |
| `decision.arbitrationReason` | 为什么这样裁决 |

`toolAudit` 记录“工具是否被调用、调用了什么、结果如何”；`AgentOpinionV1` 记录“为什么需要或不需要采纳这些意见”。两者互补，不互相替代。

经理 Agent 折中价示例：

```json
{
  "selectedAgent": null,
  "selectedPrice": null,
  "agentOpinion": {
    "version": "v1",
    "kind": "ARBITRATION",
    "status": "MERGED",
    "summary": "数据建议价与市场建议价偏差 6.5%，风控通过，采用折中价。",
    "relations": {
      "dependsOnOpinionIds": ["...DATA...", "...MARKET...", "...RISK..."],
      "acceptedOpinionIds": ["...DATA...", "...RISK..."],
      "rejectedOpinionIds": [],
      "conflictOpinionIds": ["...DATA...", "...MARKET..."],
      "selectedOpinionIds": []
    },
    "decision": {
      "decisionType": "MERGE",
      "consensusScore": 0.72,
      "arbitrationDecision": "PRICE_DISAGREEMENT",
      "arbitrationReason": "市场样本可信但与利润目标冲突，风控底线允许折中。"
    }
  }
}
```

注意：经理不必手写完整 `agentOpinion` 才能通过。`_normalize_output_with_agent_opinion()` 已能兜底补齐；只有当 LLM 能稳定引用真实 opinionId 时，才允许它输出 `agentOpinion.relations`。

## 9. 确定性安全边界

本方案是 Agent 层优化，但必须明确：prompt 不是最终安全边界。

因此：

- `finalPrice 不得低于 safeFloorPrice` 不能只写在 prompt 中。
- 经理风控复核不能替代现有 `_finalize_result()` 和 `ResultWriterTool` 的确定性校验。
- 本方案把 Python 侧确定性安全边界列为 S3 / S6 必须验收项，复用现有风控工具，不新增安全引擎。

固定实现方案：

```text
在 OrchestrationService._finalize_result() 中，manager_parsed 已通过 Pydantic 校验后、
TaskFinalResult 构建前，复用 RiskRuleTool.evaluate() 对 manager.finalPrice 做一次确定性检查。

检查项：
- cost_price
- min_profit_rate
- max_discount_rate
- min_price
- max_price
- force_manual_review

当确定性检查不通过：
- 不让 LLM 自行覆盖安全边界。
- 保持人工审核策略。
- `isPass=false`。
- `executeStrategy=人工审核`。
- 在写入 `pricing_result.result_summary` 前追加“系统风控兜底已触发”。
```

该安全边界由 S3 的确定性安全测试和 S6 的 Python 全量回归共同覆盖；不能把 prompt 约束等同于最终安全保证。
该改动属于经理 Agent 输出后的 Python 内部最终校验，不新增任务步骤，不改变 Java / 前端 / DB / RabbitMQ / SSE 契约。

## 10. 明确执行编排

执行采用“串行关卡 + 并行子agent任务组”。串行关卡保证依赖顺序；并行子agent只处理互不冲突的文件，减少总执行时间。

### 10.1 串行总流程

| 顺序 | 关卡 | 必须完成的结果 | 进入下一关条件 |
|------|------|----------------|----------------|
| S0 | 执行前基线 | 记录当前工作区状态，确认只改 Python Agent 层和测试 | `git status --short` 已记录 |
| S1 | 工具能力闭环 | 经理获得 `evaluate_risk_rules`，`audit_summary_fields` 修正 | 工具矩阵单测通过 |
| S2 | Prompt 契约闭环 | 4 个 Agent prompt 收紧，经理 prompt 支持 Fast / Verification Path | prompt contract 单测通过 |
| S3 | 确定性安全边界 | `_finalize_result()` 复用风控工具兜底最终价 | safety 单测通过 |
| S4 | 自动化验收闭环 | fake LLM 覆盖 Fast Path、利润复核、风控复核、市场弱信号、工具失败、折中价 | acceptance 单测通过 |
| S5 | 业务样例闭环 | 6 类固定业务样例通过建议质量断言 | business cases 单测通过 |
| S6 | 全量回归 | Python 相关测试全部通过 | `python -m pytest tests -q` 通过 |

任何关卡失败都必须先修复当前关卡，不得跳到后续步骤。

### 10.2 并行子agent任务组

S1 到 S5 拆成 5 个子agent并行准备。并行阶段只允许在各自文件边界内准备实现和测试；落地合并必须按 A -> B -> C -> D -> E 串行执行。每个子agent禁止修改其他组文件。

| 子agent | 负责范围 | 允许修改文件 | 禁止修改文件 | 输出物 |
|---------|----------|--------------|--------------|--------|
| A：工具与风控参数 | 工具授权、`force_manual_review` 透传、工具返回字段一致性 | `backend-python/app/tools/tool_registry.py`、`backend-python/app/tools/crewai_tools.py`、`backend-python/tests/test_crewai_tools_context.py` | `crew_factory.py`、`orchestration_service.py`、前端、Java | 工具矩阵测试和风控参数测试 |
| B：Prompt 契约 | 4 个 Agent prompt、经理 Fast / Verification Path、输出文案协议 | `backend-python/app/crew/crew_factory.py`、新增 `backend-python/tests/test_agentic_workflow_prompt_contract.py` | `tool_registry.py`、`crewai_tools.py`、`crewai_runtime.py` | prompt contract 测试 |
| C：确定性安全边界 | 最终价风控兜底、人工复核兜底文案、异常路径单测 | `backend-python/app/services/orchestration_service.py`、新增 `backend-python/tests/test_agentic_workflow_safety.py` | `crew_factory.py`、`tool_registry.py`、`crewai_tools.py`、前端、Java | safety 单测 |
| D：Fake LLM 验收 | 自动化验收、路径断言、工具失败断言 | 新增 `backend-python/tests/test_agentic_workflow_acceptance.py` | 应用源码文件 | fake LLM 验收测试 |
| E：业务样例与回归 | 固定样例、验收 fixture、业务场景断言 | `backend-python/tests/fixtures/agentic_workflow/**`、新增 `backend-python/tests/test_agentic_workflow_business_cases.py` | 应用源码文件 | 6 类业务样例测试 |

并行合并顺序固定为：A -> B -> C -> D -> E。

原因：

- A 先合并，B / C 依赖新的工具授权和风控参数。
- B 第二合并，D 依赖最终 prompt 契约。
- C 第三合并，D / E 依赖最终价安全边界。
- E 最后合并，避免业务样例断言与 prompt 文案、安全兜底尚未稳定时反复改动。

### 10.3 串行详细步骤

#### S0：执行前基线

执行人：主 Agent。

步骤：

1. 运行 `git status --short`。
2. 记录非本任务变更，不回滚用户已有改动。
3. 确认本轮只允许修改：
   - `backend-python/app/tools/tool_registry.py`
   - `backend-python/app/tools/crewai_tools.py`
   - `backend-python/app/crew/crew_factory.py`
   - `backend-python/app/services/orchestration_service.py`
   - `backend-python/tests/**`
   - `backend-python/tests/fixtures/agentic_workflow/**`

验收命令：

```powershell
git status --short
```

#### S1：工具能力闭环

执行人：子agent A。

步骤：

1. 修改 `backend-python/app/tools/tool_registry.py`：
   - `evaluate_risk_rules.allowed_agents = frozenset({"RISK_CONTROL", "MANAGER_COORDINATOR"})`
   - `audit_summary_fields = ("is_pass", "safe_floor_price", "suggested_price", "risk_level", "need_manual_review", "margin")`
2. 确认 `backend-python/app/tools/crewai_tools.py`：
   - `evaluate_risk_rules()` 已支持 `force_manual_review: bool | None = None`（当前代码已实现，无需修改）
   - 确认调用 `RiskRuleTool.evaluate()` 时已透传 `force_manual_review`（当前代码已实现）
3. 修改 `backend-python/tests/test_crewai_tools_context.py`：
   - 断言经理工具列表为 `estimate_sales_volume`、`estimate_profit`、`evaluate_risk_rules`
   - 断言经理不能调用 `query_competitor_summary`
   - 断言 `evaluate_risk_rules` 函数签名包含 `force_manual_review` 参数

验收命令：

```powershell
cd backend-python
python -m pytest tests/test_crewai_tools_context.py -q
```

#### S2：Prompt 契约闭环

执行人：子agent B。

步骤：

1. 修改 `backend-python/app/crew/crew_factory.py` 前三个 Agent prompt：
   - 预计算优先
   - 专业输出
   - 不越权
   - 不编造缺失数据
2. 修改经理 prompt：
   - 删除“必须使用 estimate_sales_volume 和 estimate_profit 工具验证最终价格”
   - 加入 Fast Path 条件
   - 加入 Verification Path 条件
   - 注入完整风控参数：`min_profit_rate`、`max_discount_rate`、`min_price`、`max_price`、`force_manual_review`
   - 市场天花板只在 `sourceStatus=OK`、`marketCeiling>0`、`dataQuality!=LOW` 时作为约束
   - 折中价时 `selectedAgent=null`、`selectedPrice=null`
   - `resultSummary` 首句必须是“可确认 / 建议复核 / 不建议确认”
3. 新增 `backend-python/tests/test_agentic_workflow_prompt_contract.py`：
   - 断言经理 prompt 包含 `Fast Path`
   - 断言经理 prompt 包含 `Verification Path`
   - 断言经理 prompt 包含完整风控参数名
   - 断言经理 prompt 禁止字符串 `"null"`
   - 断言 prompt 不要求新增 `loopTrace`、`verificationSummary`、`verificationPath`

验收命令：

```powershell
cd backend-python
python -m pytest tests/test_agentic_workflow_prompt_contract.py -q
```

#### S3：确定性安全边界

执行人：子agent C。

步骤：

1. 修改 `backend-python/app/services/orchestration_service.py`：
   - 在 `_finalize_result()` 中，`manager_parsed` 已通过 Pydantic 校验后、`TaskFinalResult` 构建前，对 `manager.finalPrice` 调用现有 `RiskRuleTool.evaluate()`
   - 参数使用商品真实 `current_price`、`cost_price` 和 payload constraints
   - 当确定性风控不通过时，保持人工复核策略，不让 LLM 覆盖安全边界
   - 只更新最终 `TaskFinalResult.resultSummary`、`isPass`、`executeStrategy`，不回写已完成的经理 `agent_run_log.raw_output_json`
2. 新增 `backend-python/tests/test_agentic_workflow_safety.py`：
   - 断言 `finalPrice < safeFloorPrice` 时进入人工复核
   - 断言 `force_manual_review=true` 时经理结果不得自动确认
   - 断言 `pricing_result.result_summary` 包含“系统风控兜底已触发”
   - 断言安全兜底不新增数据库字段、不改变 Java / 前端契约

验收命令：

```powershell
cd backend-python
python -m pytest tests/test_agentic_workflow_safety.py -q
```

#### S4：Fake LLM 自动化验收

执行人：子agent D。

步骤：

1. 新增 `backend-python/tests/test_agentic_workflow_acceptance.py`。
2. 使用 fake LLM / monkeypatch 固定模型响应。
3. 覆盖 7 个场景：
   - Fast Path
   - 利润复核
   - 风控复核
   - 市场弱信号
   - 工具失败
   - 折中价
   - audit 关闭
4. 每个场景断言：
   - 经理完成卡片满足 `display_order == 4` 且 `stage == "completed"`
   - `manager_log.raw_output_json.agentOpinion.agentCode == "MANAGER_COORDINATOR"`
   - `raw_output_json.toolAudit` 与预期一致
   - `agentOpinion.decision.arbitrationDecision` 与预期一致
   - `resultSummary` 首句为“可确认 / 建议复核 / 不建议确认”
   - `selectedAgent` / `selectedPrice` 在折中价场景为 JSON null

验收命令：

```powershell
cd backend-python
python -m pytest tests/test_agentic_workflow_acceptance.py -q
```

#### S5：业务样例验收

执行人：子agent E。

步骤：

1. 新增目录 `backend-python/tests/fixtures/agentic_workflow/`。
2. 新增 6 个固定样例：
   - `fast_path_normal_product.json`
   - `profit_review_low_margin_product.json`
   - `risk_review_below_safe_floor_product.json`
   - `market_low_quality_product.json`
   - `force_manual_review_product.json`
   - `profit_not_improved_product.json`
3. 新增 `backend-python/tests/test_agentic_workflow_business_cases.py`。
4. 每个样例断言：
   - `finalPrice`
   - `expectedProfit`
   - `profitGrowth`
   - `isPass`
   - `resultSummary`
   - `arbitrationReason`
   - `agentOpinion.decision.arbitrationDecision`
   - `raw_output_json.toolAudit`

验收命令：

```powershell
cd backend-python
python -m pytest tests/test_agentic_workflow_business_cases.py -q
```

#### S6：全量回归

执行人：主 Agent。

步骤：

1. 运行专项测试：

```powershell
cd backend-python
python -m pytest tests/test_crewai_tools_context.py tests/test_crewai_runtime.py tests/test_agentic_workflow_prompt_contract.py tests/test_agentic_workflow_safety.py tests/test_agentic_workflow_acceptance.py tests/test_agentic_workflow_business_cases.py -q
```

2. 运行 Python 全量测试：

```powershell
cd backend-python
python -m pytest tests -q
```

3. 汇总失败项。所有失败必须修复；不得以“LLM 偶发”作为通过理由，因为本轮验收使用 fake LLM。

## 11. 自动化验收矩阵

| 场景 | 输入 | 断言 |
|------|------|------|
| Fast Path | 三方价格接近、风控通过、利润改善、市场数据可信 | 经理不调用工具，`toolAudit` 为空，`arbitrationDecision=FAST_PATH` |
| 利润复核 | `expectedProfit <= baselineProfit` | 调用 `estimate_profit`，`arbitrationDecision=PROFIT_VERIFICATION` |
| 风控复核 | 候选价接近 `safeFloorPrice` 或 `RISK_CONTROL.isPass=false` | 调用 `evaluate_risk_rules`，参数包含完整 constraints |
| 市场弱信号 | `sourceStatus != OK` 或 `dataQuality=LOW` | 不把 `marketCeiling` 当硬约束，`arbitrationDecision=MARKET_WEAK_SIGNAL` |
| 工具失败 | tool 返回 `error/timeout` | 经理输出合法 JSON，`arbitrationDecision=CONSERVATIVE_DOWNGRADE` |
| 折中价 | 无单一上游 Agent 被采纳 | `selectedAgent=null`，不是字符串 `"null"` |
| audit 关闭 | `CREWAI_TOOL_AUDIT_ENABLED=false` | 不用“无 toolAudit”判断 Fast Path，只验证任务不崩 |

测试方式：

- 使用 fake LLM / mock completion，不依赖真实模型随机性。
- 复用已有 fake bundle / fake tool context 测试结构。
- 不使用 SQL 手查作为验收标准。

## 12. 业务验收样例

9 分版不能只验证工具路径，还要验证建议质量。

固定准备 6 类样例：

| 样例 | 预期 |
|------|------|
| 正常利润商品 | Fast Path，利润改善，输出清楚下一步动作 |
| 低毛利商品 | 触发风控或保守裁决，不突破安全底价 |
| 无竞品商品 | 市场只作为弱参考，不编造市场价带 |
| 竞品异常低价商品 | 不盲目跟价，解释竞品数据风险 |
| 强制人工复核商品 | 复核口径与 `force_manual_review` 一致 |
| 利润不改善商品 | 触发利润复核或建议暂不调价 |

每个样例检查：

- `finalPrice`
- `expectedProfit`
- `profitGrowth`
- `isPass`
- `resultSummary`
- `arbitrationReason`
- `agentOpinion.decision.arbitrationDecision`
- `raw_output_json.toolAudit`

固定业务硬断言：

- `finalPrice < safeFloorPrice` 时，不得输出“可确认”。
- `expectedProfit <= baselineProfit` 且 `strategy_goal != CLEARANCE` 时，不得输出“可确认”。
- `MARKET_INTEL.dataQuality=LOW` 或 `sourceStatus != OK` 时，不得强跟市场价。
- 工具失败 / 超时 / 参数错误时，必须输出“建议复核”或“不建议确认”。
- `resultSummary` 必须包含结论、策略目标、关键依据、风险、下一步动作。

## 13. 用户可感知输出

不改前端的前提下，经理 Agent 必须把用户价值写进已有字段。

用户可感知字段映射：

| 用户关心的问题 | 复用字段 | 经理输出要求 |
|---|---|---|
| 能不能确认 | `isPass`, `resultSummary` | `resultSummary` 首句必须给出“可确认 / 建议复核 / 不建议确认” |
| 为什么可信 | `arbitrationReason`, `acceptedOpinions`, `consensusScore` | 写明采纳了谁、拒绝了谁、偏差多少 |
| 风险在哪里 | `disagreementSummary`, `rejectedOpinions`, `resultSummary` | 写明安全底价、利润、竞品样本、工具失败等风险 |
| 下一步做什么 | `resultSummary` | 给出确认应用、人工复核、调整约束、等待数据、重新执行或暂不调价 |
| 是否经过复核 | `raw_output_json.toolAudit`, `arbitrationReason` | 进入 Verification Path 时，必须说明复核工具和结果 |

### 13.1 `resultSummary` 模板

```text
【{可确认/建议复核/不建议确认}】本次按【{利润优先/市场份额优先/清仓促销/日常利润优化}】处理，建议价为 {finalPrice} 元，下一步：{确认应用/人工复核/调整约束/等待数据/重新执行/暂不调价}。
主要依据是：{采纳依据}。
预计月利润 {expectedProfit} 元，较基线变化 {profitGrowth} 元。
风控结论：{isPass/needManualReview/safeFloorPrice}。
```

### 13.2 `arbitrationReason` 模板

```text
数据分析意见：{采纳/部分采纳/未采纳}，原因是 {reason}。
市场情报意见：{采纳/弱参考/未采纳}，原因是 {reason}。
风控意见：{采纳/触发底线/需复核}，原因是 {reason}。
工具复核：{未复核/利润复核/风控复核/复核失败后保守处理}。
最终裁决：{final decision}。
```

这样即使前端不改，现有展示也能让运营看到：

- 这个价能不能用。
- 为什么选这个价。
- 风险在哪里。
- 下一步该确认、复核、暂不调价还是补数据。

## 14. 最终判断

这版方案按 9 分标准收敛后，定位是：

```text
受控 Agentic Workflow，不是全自主 Agent 系统。
```

它的强项是：

- 角色分工真实贴合电商定价团队。
- function calling 有明确业务触发条件。
- 不新增 runtime，不制造重复代码。
- 经理 Agent 有真正的诊断、行动、反思和仲裁。
- 风控工具口径和预计算口径对齐。
- 验收从 SQL 手查升级为自动化断言和固定业务样例。

按 S0 到 S6 执行并通过全部自动化验收后，本方案达到 9 分以上的评审标准。
