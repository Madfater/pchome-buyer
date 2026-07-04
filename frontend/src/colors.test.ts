import { describe, expect, it } from 'vitest'
import { groupColor, saleTimeKey } from './colors'

describe('saleTimeKey', () => {
  it('converts sale time to a gid-compatible key', () => {
    expect(saleTimeKey('2026-03-06 12:00')).toBe('2026-03-06_1200')
  })

  it('maps empty string (立即監控) to "now"', () => {
    expect(saleTimeKey('')).toBe('now')
  })
})

describe('groupColor', () => {
  it('assigns the same color to the same key on repeated calls', () => {
    const key = `test-key-${Math.random()}`
    const first = groupColor(key)
    const second = groupColor(key)
    expect(first).toBe(second)
  })

  it('assigns different colors to different keys until the palette wraps', () => {
    const a = groupColor(`a-${Math.random()}`)
    const b = groupColor(`b-${Math.random()}`)
    expect(a).not.toBe(b)
  })
})
