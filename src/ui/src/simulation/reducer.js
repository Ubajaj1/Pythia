import { CROWD_STATES } from './scenarios'

export const TICKS_PER_RUN = 20
const ACCURACY_GAINS = [9, 8, 6, 5, 4, 3, 2]

export function makeInitialState(protagonists) {
  return {
    gen: 0,
    tick: 0,
    run: 1,
    templeIdx: null,
    accuracyHistory: [44],
    accuracy: 44,
    // crowdStateIndex kept for backward-compat with anything still reading
    // it directly, but it's no longer authoritative — the live classifier
    // in crowdState.js reads tick data to decide the real crowd state.
    crowdStateIndex: 0,
    protoStates: protagonists.map(() => ({
      spawned: false,
      conf: 0,
      inTemple: false,
      returning: false,
    })),
  }
}

export function simReducer(state, action) {
  switch (action.type) {
    case 'SPAWN': {
      const protoStates = state.protoStates.map((ps, i) =>
        i === action.idx ? { ...ps, spawned: true, conf: action.conf } : ps
      )
      return { ...state, protoStates }
    }

    case 'TICK': {
      const tick = state.tick + 1
      const protoStates = state.protoStates.map(ps => {
        if (!ps.spawned || ps.inTemple) return ps
        const delta = (Math.random() - 0.46) * 9
        return { ...ps, conf: Math.max(8, Math.min(97, ps.conf + delta)) }
      })
      // Keep crowdStateIndex unchanged — it's a legacy field now.
      return { ...state, tick, protoStates }
    }

    case 'SEND_TO_TEMPLE': {
      const protoStates = state.protoStates.map((ps, i) =>
        i === action.idx ? { ...ps, inTemple: true, returning: false } : ps
      )
      return { ...state, protoStates, templeIdx: action.idx }
    }

    case 'RETURN_FROM_TEMPLE': {
      if (state.templeIdx === null) return state
      const idx = state.templeIdx
      const protoStates = state.protoStates.map((ps, i) =>
        i === idx
          ? { ...ps, inTemple: false, returning: true, conf: 68 + Math.random() * 26 }
          : ps
      )
      return { ...state, protoStates, templeIdx: null }
    }

    case 'MARK_NOT_RETURNING': {
      const protoStates = state.protoStates.map((ps, i) =>
        i === action.idx ? { ...ps, returning: false } : ps
      )
      return { ...state, protoStates }
    }

    case 'END_RUN': {
      const gainIdx = Math.min(state.run - 1, ACCURACY_GAINS.length - 1)
      const gain = ACCURACY_GAINS[gainIdx]
      const newAccuracy = Math.min(97, state.accuracy + gain + (Math.random() * 1.5 - 0.75))
      return {
        ...state,
        tick: 0,
        run: state.run + 1,
        templeIdx: null,
        accuracy: newAccuracy,
        accuracyHistory: [...state.accuracyHistory, newAccuracy],
        protoStates: state.protoStates.map(ps =>
          ps.inTemple ? ps : { ...ps, conf: 28 + Math.random() * 32 }
        ),
      }
    }

    case 'RESET': {
      return { ...makeInitialState(action.protagonists), gen: state.gen + 1 }
    }

    default:
      return state
  }
}
