import { useReducer, useEffect, useCallback, useRef, useState } from 'react'
import { simReducer, makeInitialState, TICKS_PER_RUN } from './reducer'
import { CROWD_STATES } from './scenarios'

const TICK_MS = 2300

export function useSimulation(protagonists, amendments) {
  const [state, dispatch] = useReducer(simReducer, protagonists, makeInitialState)
  const timerRef = useRef(null)
  const [paused, setPaused] = useState(false)
  const togglePause = useCallback(() => setPaused(p => !p), [])

  // Spawn stagger on mount and after reset
  useEffect(() => {
    const timeouts = protagonists.map((_, i) =>
      setTimeout(() => {
        dispatch({
          type: 'SPAWN',
          idx: i,
          conf: 28 + Math.random() * 28,
        })
      }, 600 + i * 320)
    )
    return () => timeouts.forEach(clearTimeout)
  }, [state.gen, protagonists.length])

  // Tick interval
  useEffect(() => {
    if (paused) return
    timerRef.current = setInterval(() => {
      dispatch({ type: 'TICK' })
    }, TICK_MS)
    return () => clearInterval(timerRef.current)
  }, [state.gen, paused])

  // Temple entry at tick 9
  useEffect(() => {
    if (state.tick !== 9 || state.templeIdx !== null) return
    const active = state.protoStates
      .map((ps, i) => (ps.spawned && !ps.inTemple ? i : -1))
      .filter(i => i >= 0)
    if (active.length === 0) return
    const idx = active[Math.floor(Math.random() * active.length)]
    dispatch({ type: 'SEND_TO_TEMPLE', idx })
  }, [state.tick])

  // Temple exit at tick 16
  useEffect(() => {
    if (state.tick !== 16 || state.templeIdx === null) return
    dispatch({ type: 'RETURN_FROM_TEMPLE' })
  }, [state.tick])

  // Clear returning flag after animation
  useEffect(() => {
    const returningIdx = state.protoStates.findIndex(ps => ps.returning)
    if (returningIdx === -1) return
    const t = setTimeout(() => {
      dispatch({ type: 'MARK_NOT_RETURNING', idx: returningIdx })
    }, 1600)
    return () => clearTimeout(t)
  }, [state.protoStates])

  // End of run
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
    crowdStateIndex: state.crowdStateIndex,
    crowdStateName: CROWD_STATES[state.crowdStateIndex],
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
  const [paused, setPaused] = useState(false)
  const togglePause = useCallback(() => setPaused(p => !p), [])

  // Spawn stagger on mount
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

  // Tick interval — replay API data
  useEffect(() => {
    if (paused) return
    timerRef.current = setInterval(() => {
      dispatch({ type: 'TICK' })
    }, TICK_MS)
    return () => clearInterval(timerRef.current)
  }, [state.gen, paused])

  // Update confidence from API tick data
  useEffect(() => {
    const tickData = tickDataRef.current[state.tick - 1]
    if (!tickData || !tickData.events) return
    tickData.events.forEach(event => {
      const idx = scenario.protagonists.findIndex(p => p.id === event.agent_id)
      if (idx >= 0) {
        dispatch({ type: 'SPAWN', idx, conf: event.stance * 100 })
      }
    })
  }, [state.tick])

  // No fake temple for API single runs — temple only activates in Oracle Loop

  // Clear returning flag
  useEffect(() => {
    const returningIdx = state.protoStates.findIndex(ps => ps.returning)
    if (returningIdx === -1) return
    const t = setTimeout(() => {
      dispatch({ type: 'MARK_NOT_RETURNING', idx: returningIdx })
    }, 1600)
    return () => clearTimeout(t)
  }, [state.protoStates])

  // End of run
  useEffect(() => {
    if (state.tick <= TICKS_PER_RUN) return
    dispatch({ type: 'END_RUN' })
  }, [state.tick])

  const restart = useCallback(() => {
    clearInterval(timerRef.current)
    setPaused(false)
    dispatch({ type: 'RESET', protagonists: scenario.protagonists })
  }, [scenario.protagonists])

  // Compute aggregate stance from tick data
  const tickData = tickDataRef.current[state.tick - 1]
  const aggregateStance = tickData?.aggregate_stance ?? null

  return {
    tick: state.tick,
    run: state.run,
    progressPercent: (state.tick / TICKS_PER_RUN) * 100,
    crowdStateIndex: state.crowdStateIndex,
    crowdStateName: CROWD_STATES[state.crowdStateIndex],
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
      if (currentTick >= TICKS_PER_RUN) return
      const dataReady = externalTicksRef.current.length > currentTick
      const timeReady = Date.now() - lastTickTimeRef.current >= TICK_MS
      if (dataReady && timeReady) {
        dispatch({ type: 'TICK' })
        lastTickTimeRef.current = Date.now()
      }
    }, 200)
    return () => clearInterval(timerRef.current)
  }, [state.gen, paused, externalTicksRef])

  useEffect(() => {
    const tickData = externalTicksRef.current[state.tick - 1]
    if (!tickData?.events) return
    tickData.events.forEach(event => {
      const idx = scenario.protagonists.findIndex(p => p.id === event.agent_id)
      if (idx >= 0) dispatch({ type: 'SPAWN', idx, conf: event.stance * 100 })
    })
  }, [state.tick])

  // No fake temple for streaming single runs — temple only activates in Oracle Loop

  useEffect(() => {
    const returningIdx = state.protoStates.findIndex(ps => ps.returning)
    if (returningIdx === -1) return
    const t = setTimeout(() => dispatch({ type: 'MARK_NOT_RETURNING', idx: returningIdx }), 1600)
    return () => clearTimeout(t)
  }, [state.protoStates])

  const restart = useCallback(() => {
    clearInterval(timerRef.current)
    setPaused(false)
    lastTickTimeRef.current = Date.now() - TICK_MS
    dispatch({ type: 'RESET', protagonists: scenario.protagonists })
  }, [scenario.protagonists])

  // Compute aggregate stance from streaming tick data
  const streamTickData = externalTicksRef.current[state.tick - 1]
  const aggregateStance = streamTickData?.aggregate_stance ?? null

  return {
    tick: state.tick,
    run: state.run,
    progressPercent: (state.tick / TICKS_PER_RUN) * 100,
    crowdStateIndex: state.crowdStateIndex,
    crowdStateName: CROWD_STATES[state.crowdStateIndex],
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

  // Override temple behavior: use real amended agent data instead of random tick-9 selection
  // Find the first amended agent from the oracle result to show in the temple
  const amendedIdx = oracleScenario.protagonists.findIndex(p => p.amended)

  return {
    ...sim,
    accuracyHistory: oracleScenario.coherenceHistory,
    // If we have real amendment data, override the random temple selection
    templeIdx: amendedIdx >= 0 ? amendedIdx : sim.templeIdx,
  }
}
