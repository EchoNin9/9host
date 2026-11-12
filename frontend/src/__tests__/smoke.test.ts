import { describe, it, expect } from 'vitest'

describe('Smoke test', () => {
  it('runs cleanly in jsdom environment', () => {
    expect(true).toBe(true)
    const el = document.createElement('div')
    el.textContent = '9host'
    expect(el.textContent).toBe('9host')
  })
})
