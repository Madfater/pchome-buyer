import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { addProduct, fetchState, importAuth } from './api'

function mockFetch(response: { ok: boolean; status?: number; statusText?: string; json: () => Promise<unknown> }) {
  const fn = vi.fn().mockResolvedValue(response)
  vi.stubGlobal('fetch', fn)
  return fn
}

describe('api()', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('sends GET without a body or Content-Type header', async () => {
    const fetchMock = mockFetch({ ok: true, json: async () => ({ auth: {}, products: [], groups: {}, checkouts: [] }) })

    await fetchState()

    expect(fetchMock).toHaveBeenCalledWith('/api/state', { method: 'GET', headers: undefined, body: undefined })
  })

  it('serializes the body as JSON and sets Content-Type when a body is given', async () => {
    const fetchMock = mockFetch({ ok: true, json: async () => ({}) })

    await addProduct('DGCQ39-A900JESMM', '2026-03-06 12:00')

    expect(fetchMock).toHaveBeenCalledWith('/api/products', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ref: 'DGCQ39-A900JESMM', sale_time: '2026-03-06 12:00' }),
    })
  })

  it('throws the server-provided detail message on a JSON error response', async () => {
    mockFetch({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: async () => ({ detail: '無法辨識商品編號' }),
    })

    await expect(importAuth('bad')).rejects.toThrow('無法辨識商品編號')
  })

  it('falls back to the status text when the error response is not JSON', async () => {
    mockFetch({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: async () => {
        throw new SyntaxError('not json')
      },
    })

    await expect(importAuth('bad')).rejects.toThrow('500 Internal Server Error')
  })
})
