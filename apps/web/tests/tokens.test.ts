import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const read = (relative: string): string => readFileSync(new URL(relative, import.meta.url), 'utf8')

/** Collect the `--name: value;` declarations of the first `:root { … }` block. */
function rootTokens(css: string): Map<string, string> {
  const block = /:root\s*\{([^}]*)\}/.exec(css)?.[1] ?? ''
  const tokens = new Map<string, string>()
  for (const [, name, value] of block.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) {
    tokens.set(name, value.trim())
  }
  return tokens
}

describe('design tokens', () => {
  const deck = rootTokens(read('../../../docs/design/regista-vision.html'))
  const ours = rootTokens(read('../src/styles/tokens.css'))

  it('finds the full token set in the vision deck', () => {
    expect(deck.size).toBeGreaterThan(40)
  })

  it('defines every vision-deck token with the same value', () => {
    const copied = Object.fromEntries([...deck.keys()].map((name) => [name, ours.get(name)]))
    expect(copied).toEqual(Object.fromEntries(deck))
  })
})
