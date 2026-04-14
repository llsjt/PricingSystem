export interface RevealQueueState<T extends string = string> {
  active: T | null
  queue: T[]
}

export interface PendingRevealRequest<TCard, TStage extends string = string> {
  card: TCard | null
  stage: TStage
}

export const createRevealQueueState = <T extends string>(): RevealQueueState<T> => ({
  active: null,
  queue: []
})

const orderIndex = <T extends string>(code: T, order: readonly T[]) => {
  const index = order.indexOf(code)
  return index >= 0 ? index : Number.MAX_SAFE_INTEGER
}

export const enqueueReveal = <T extends string>(
  state: RevealQueueState<T>,
  code: T,
  order: readonly T[]
) => {
  if (state.active === code || state.queue.includes(code)) {
    return state.active
  }

  if (!state.active) {
    state.active = code
    return state.active
  }

  state.queue.push(code)
  state.queue.sort((left, right) => orderIndex(left, order) - orderIndex(right, order))
  return state.active
}

export const queueRevealCardRequest = <
  T extends string,
  TCard,
  TStage extends string = string
>(
  state: RevealQueueState<T>,
  pending: Partial<Record<T, PendingRevealRequest<TCard, TStage>>>,
  code: T,
  request: PendingRevealRequest<TCard, TStage>,
  order: readonly T[]
) => {
  pending[code] = request

  if (state.active === code) {
    return 'replace-active' as const
  }

  if (state.queue.includes(code)) {
    return 'replace-queued' as const
  }

  const active = enqueueReveal(state, code, order)
  return active === code ? ('activate' as const) : ('queued' as const)
}

export const finishReveal = <T extends string>(
  state: RevealQueueState<T>,
  code: T
) => {
  if (state.active !== code) {
    return state.active
  }

  state.active = state.queue.shift() || null
  return state.active
}

export const isActiveReveal = <T extends string>(
  state: RevealQueueState<T>,
  code: T
) => state.active === code

export const clearRevealQueue = <T extends string>(state: RevealQueueState<T>) => {
  state.active = null
  state.queue.splice(0, state.queue.length)
}
