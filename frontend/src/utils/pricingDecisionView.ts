import type { PricingAgentCode } from '../api/decision'
import type { AgentTimelineCardState } from './agentTimeline'

export const ANALYSIS_AGENT_CODES = ['DATA_ANALYSIS', 'MARKET_INTEL', 'RISK_CONTROL'] as const
export const MANAGER_AGENT_CODE = 'MANAGER_COORDINATOR' as const satisfies PricingAgentCode

type DecisionCardMap = Partial<Record<PricingAgentCode, AgentTimelineCardState>>

const stageOf = (card: AgentTimelineCardState) => String(card?.__stage || '').trim().toLowerCase()

export const buildDecisionStatusOverview = (
  cards: DecisionCardMap,
  finalPrice: number | null
) => {
  const analysisCompletedCount = ANALYSIS_AGENT_CODES.filter((code) => stageOf(cards[code]) === 'completed').length
  const analysisRunningCount = ANALYSIS_AGENT_CODES.filter((code) => stageOf(cards[code]) === 'running').length
  const managerStage = stageOf(cards[MANAGER_AGENT_CODE])
  const isTimelineInconsistent = managerStage === 'completed' && analysisCompletedCount < ANALYSIS_AGENT_CODES.length
  const canShowManagerCompleted = managerStage === 'completed' && !isTimelineInconsistent

  let primaryStatusText = '等待三个分析席位启动'
  let managerStatusText = '等待经理仲裁'

  if (isTimelineInconsistent) {
    primaryStatusText = '结果同步中'
    managerStatusText = '等待快照对齐'
  } else if (canShowManagerCompleted) {
    primaryStatusText = '经理已完成'
    managerStatusText = '经理已完成'
  } else if (managerStage === 'running') {
    primaryStatusText = '经理仲裁中'
    managerStatusText = '经理仲裁中'
  } else if (analysisCompletedCount === ANALYSIS_AGENT_CODES.length) {
    primaryStatusText = '3/3 完成，等待经理仲裁'
  } else if (analysisRunningCount > 0) {
    primaryStatusText = '三个分析并行中'
  }

  return {
    analysisCompletedCount,
    analysisRunningCount,
    isTimelineInconsistent,
    canShowManagerCompleted,
    analysisStatusText: `${analysisCompletedCount}/3 已完成`,
    managerStatusText,
    primaryStatusText,
    finalPrice,
    finalPriceLabel: '最终建议价'
  }
}
