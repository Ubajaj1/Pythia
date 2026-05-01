import { useReducer, useEffect, useCallback, useRef, useState } from 'react'
import { simReducer, makeInitialState, TICKS_PER_RUN } from './reducer'
import { CROWD_STATES, classifyCrowdState } from './crowdState'

const TICK_MS = 2300

export function useSimulation(protagonists, amendments) {
  const [state, dispatch] = useReducer(simReducer, protagonists, makeInitialState)
  const timerRef = useRef(null)
  const [paused, setPaused] = useState(false)
  const togglePause = useCallback(() => setPaused(p => !p), [])

  useEffect(() => {
    const timeouts = protagonists.map((_, i) =>
      setTimeout(() => {
        dispatch({ type: 'SPAWN', idx: i, conf: 28 + Math.random() * 28 })
      }, 600 + i * 320)
    )
    return () => timeouts.forEach(clearTimeout)
  }, [state.gen, protagonists.length])

  useEffect(() => {
    if (paused) return
    timerRef.current = setInterval(() => { dispatch({ type: 'TICK' }) }, TICK_MS)
    return () => clearInterval(timerRef.current)
  }, [state.gen, paused])

  useEffect(() => {
    if (state.tick !== 9 || state.templeIdx !== null) return
    const active = state.protoStates.map((ps, i) => (ps.spawned && !ps.inTemple ? i : -1)).filter(i => i >= 0)
    if (!active.length) return
    dispatch({ type: 'SEND_TO_TEMPLE', idx: active[Math.floor(Math.random() * active.length)] })
  }, [state.tick])

  useEffect(() => {
    if (state.tick !== 16 || state.templeIdx === null) return
    dispatch({ type: 'RETURN_FROM_TEMPLE' })
  }, [state.tick])

  useEffect(() => {
    const idx = state.protoStates.findIndex(ps => ps.returning)
    if (idx === -1) return
    const t = setTimeout(() => dispatch({ type: 'MARK_NOT_RETURNING', idx }), 1600)
    return () => clearTimeout(t)
  }, [state.protoStates])

  useEffect(() => {
    if (state.tick <= TICKS_PER_RUN) return
    dispatch({ type: 'END_RUN' })
  }, [state.tick])

  const restart = useCallback(() => {
    clearInterval(timerRef.current)
    setPaused(false)
    dispatch({ type: 'RESET', protagonists })
  }, [protagonists])

  return {
    tick: state.tick,
    run: state.run,
    progressPercent: (state.tick / TICKS_PER_RUN) * 100,
    // Legacy mock hook — no real tick data flowing in, so we can't classify
    // the crowd honestly. Default to Scattered (index 0). The data-driven
    // hooks below use the live classifier.
    crowdStateIndex: 0,
    crowdStateName: CROWD_STATES[0],
    templeIdx: state.templeIdx,
    protoStates: state.protoStates,
    accuracyHistory: state.accuracyHistory,
    amendments,
    paused,
    togglePause,
    restart,
  }
}

export function useApiSimulation(scenario) {
  const [state, dispatch] = useReducer(simReducer, scenario.protagonists, makeInitialState)
  const timerRef = useRef(null)
  const tickDataRef = useRef(scenario.ticks || [])
  const totalTicks = scenario.tickCount || scenario.ticks?.length || TICKS_PER_RUN
  const [paused, setPaused] = useState(false)
  const togglePause = useCallback(() => setPaused(p => !p), [])

  useEffect(() => {
    const timeouts = scenario.protagonists.map((_, i) =>
      setTimeout(() => {
        const agentData = scenario.agents?.[i]
        const initialConf = agentData ? agentData.initial_stance * 100 : 28 + Math.random() * 28
        dispatch({ type: 'SPAWN', idx: i, conf: initialConf })
      }, 600 + i * 320)
    )
    return () => timeouts.forEach(clearTimeout)
  }, [state.gen, scenario.protagonists.length])

  useEffect(() => {
    if (paused) return
    timerRef.current = setInterval(() => { dispatch({ type: 'TICK' }) }, TICK_MS)
    return () => clearInterval(timerRef.current)
  }, [state.gen, paused])

  useEffect(() => {
    const tickData = tickDataRef.current[state.tick - 1]
    if (!tickData || !tickData.events) return
    tickData.events.forEach(event => {
      const idx = scenario.protagonists.findIndex(p => p.id === event.agent_id)
      if (idx >= 0) dispatch({ type: 'SPAWN', idx, conf: event.stance * 100 })
    })
  }, [state.tick])

  useEffect(() => {
    const idx = state.protoStates.findIndex(ps => ps.returning)
    if (idx === -1) return
    const t = setTimeout(() => dispatch({ type: 'MARK_NOT_RETURNING', idx }), 1600)
    return () => clearTimeout(t)
  }, [state.protoStates])

  useEffect(() => {
    if (state.tick <= totalTicks) return
    dispatch({ type: 'END_RUN' })
  }, [state.tick, totalTicks])

  const restart = useCallback(() => {
    clearInterval(timerRef.current)
    setPaused(false)
    dispatch({ type: 'RESET', protagonists: scenario.protagonists })
  }, [scenario.protagonists])

  const tickData = tickDataRef.current[state.tick - 1]
  const aggregateStance = tickData?.aggregate_stance ?? null

  // Live crowd classification from real tick data + influence edges.
  const influenceEdges = scenario.influenceEdges || []
  const crowd = classifyCrowdState(tickDataRef.current, state.tick, influenceEdges)

  return {
    tick: state.tick,
    run: state.run,
    progressPercent: (state.tick / totalTicks) * 100,
    crowdStateIndex: crowd.index,
    crowdStateName: crowd.name,
    templeIdx: state.templeIdx,
    protoStates: state.protoStates,
    accuracyHistory: state.accuracyHistory,
    amendments: scenario.amendments,
    aggregateStance,
    paused,
    togglePause,
    restart,
  }
}

export function useStreamingSimulation(scenario, externalTicksRef) {
  const [state, dispatch] = useReducer(simReducer, scenario.protagonists, makeInitialState)
  const timerRef = useRef(null)
  const totalTicks = scenario.tickCount || TICKS_PER_RUN
  const [paused, setPaused] = useState(false)
  const togglePause = useCallback(() => setPaused(p => !p), [])
  const tickRef = useRef(0)
  tickRef.current = state.tick
  const lastTickTimeRef = useRef(Date.now() - TICK_MS)

  useEffect(() => {
    const timeouts = scenario.protagonists.map((_, i) =>
      setTimeout(() => {
        const agent = scenario.agents?.[i]
        dispatch({ type: 'SPAWN', idx: i, conf: agent ? agent.initial_stance * 100 : 50 })
      }, 600 + i * 320)
    )
    return () => timeouts.forEach(clearTimeout)
  }, [state.gen, scenario.protagonists.length])

  useEffect(() => {
    if (paused) return
    timerRef.current = setInterval(() => {
      const currentTick = tickRef.current
      if (currentTick >= totalTicks) return
      const dataReady = externalTicksRef.current.length > currentTick
      const timeReady = Date.now() - lastTickTimeRef.current >= TICK_MS
      if (dataReady && timeReady) {
        dispatch({ type: 'TICK' })
        lastTickTimeRef.current = Date.now()
      }
    }, 200)
    return () => clearInterval(timerRef.current)
  }, [state.gen, paused, externalTicksRef, totalTicks])

  useEffect(() => {
    const tickData = externalTicksRef.current[state.tick - 1]
    if (!tickData?.events) return
    tickData.events.forEach(event => {
      const idx = scenario.protagonists.findIndex(p => p.id === event.agent_id)
      if (idx >= 0) dispatch({ type: 'SPAWN', idx, conf: event.stance * 100 })
    })
  }, [state.tick])

  // Temple-of-Learning schedule for streaming runs.
  // At ~60% of total ticks, pick the most-active agent (largest stance delta
  // over the run so far) and send them to the temple for a "reflection". At
  // ~85%, return them. The temple animation is purely visual — it doesn't
  // mutate tick data.
  const templeSendTick = Math.max(4, Math.floor(totalTicks * 0.6))
  const templeReturnTick = Math.max(templeSendTick + 3, Math.floor(totalTicks * 0.85))

  useEffect(() => {
    if (state.tick !== templeSendTick || state.templeIdx !== null) return
    // Pick the agent whose stance has shifted the most so far.
    const ticksSoFar = externalTicksRef.current.slice(0, state.tick)
    const initial = Object.fromEntries(
      (scenario.agents || []).map(a => [a.id, a.initial_stance]),
    )
    let bestIdx = -1
    let bestShift = -Infinity
    scenario.protagonists.forEach((p, i) => {
      // Use the latest event for this agent we have.
      let latest = null
      for (let t = ticksSoFar.length - 1; t >= 0; t--) {
        const ev = ticksSoFar[t]?.events?.find(e => e.agent_id === p.id)
        if (ev) { latest = ev; break }
      }
      if (!latest || state.protoStates[i]?.inTemple) return
      const shift = Math.abs(latest.stance - (initial[p.id] ?? 0.5))
      if (shift > bestShift) { bestShift = shift; bestIdx = i }
    })
    if (bestIdx >= 0) dispatch({ type: 'SEND_TO_TEMPLE', idx: bestIdx })
  }, [state.tick, templeSendTick, state.templeIdx, scenario])

  useEffect(() => {
    if (state.tick !== templeReturnTick || state.templeIdx === null) return
    dispatch({ type: 'RETURN_FROM_TEMPLE' })
  }, [state.tick, templeReturnTick, state.templeIdx])

  useEffect(() => {
    const idx = state.protoStates.findIndex(ps => ps.returning)
    if (idx === -1) return
    const t = setTimeout(() => dispatch({ type: 'MARK_NOT_RETURNING', idx }), 1600)
    return () => clearTimeout(t)
  }, [state.protoStates])

  const restart = useCallback(() => {
    clearInterval(timerRef.current)
    setPaused(false)
    lastTickTimeRef.current = Date.now() - TICK_MS
    dispatch({ type: 'RESET', protagonists: scenario.protagonists })
  }, [scenario.protagonists])

  const streamTickData = externalTicksRef.current[state.tick - 1]
  const aggregateStance = streamTickData?.aggregate_stance ?? null

  // Live crowd classification from the streaming tick buffer. Influence
  // edges aren't available until the stream completes (done event carries
  // the full graph), so we classify on stances + aggregate only for now.
  const crowd = classifyCrowdState(externalTicksRef.current, state.tick, [])

  return {
    tick: state.tick,
    run: state.run,
    progressPercent: (state.tick / totalTicks) * 100,
    crowdStateIndex: crowd.index,
    crowdStateName: crowd.name,
    templeIdx: state.templeIdx,
    protoStates: state.protoStates,
    accuracyHistory: state.accuracyHistory,
    amendments: scenario.amendments || [],
    aggregateStance,
    paused,
    togglePause,
    restart,
  }
}

export function useOracleSimulation(oracleScenario) {
  const sim = useApiSimulation(oracleScenario)
  const amendedIdx = oracleScenario.protagonists.findIndex(p => p.amended)

  return {
    ...sim,
    accuracyHistory: oracleScenario.coherenceHistory,
    templeIdx: amendedIdx >= 0 ? amendedIdx : sim.templeIdx,
  }
}
