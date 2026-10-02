import { describe, expect, it } from 'vitest'

import {
  normalizeSprkeyOpenString,
  pathFromSprkeyDeepLink,
  pathFromOpenDeepLink,
  resolveSprkeyOpenPath
} from './sprkey-open-target'

describe('normalizeSprkeyOpenString', () => {
  it('accepts hash-router paths and strips a leading hash', () => {
    expect(normalizeSprkeyOpenString('/index-network/intent/1')).toBe('/index-network/intent/1')
    expect(normalizeSprkeyOpenString('#/index-network/intent/1')).toBe('/index-network/intent/1')
  })

  it('maps plugin-scoped sprkey:// deep links to the same path', () => {
    expect(normalizeSprkeyOpenString('sprkey://index-network/intent/1')).toBe('/index-network/intent/1')
    expect(normalizeSprkeyOpenString('sprkey://index-network/intent/1?focus=true')).toBe(
      '/index-network/intent/1?focus=true'
    )
  })

  it('maps sprkey://open/… deep links by stripping the open host', () => {
    expect(normalizeSprkeyOpenString('sprkey://open/index-network/intent/1')).toBe('/index-network/intent/1')
    expect(normalizeSprkeyOpenString('sprkey://open/settings/plugins')).toBe('/settings/plugins')
  })

  it('rejects reserved sprkey kinds and unsafe paths', () => {
    expect(normalizeSprkeyOpenString('sprkey://blueprint/morning-brief')).toBeNull()
    expect(normalizeSprkeyOpenString('sprkey://plugin/install')).toBeNull()
    expect(normalizeSprkeyOpenString('https://example.com/x')).toBeNull()
    expect(normalizeSprkeyOpenString('/../etc/passwd')).toBeNull()
    expect(normalizeSprkeyOpenString('index-network')).toBeNull()
  })
})

describe('resolveSprkeyOpenPath', () => {
  it('merges structured path + params', () => {
    expect(resolveSprkeyOpenPath({ path: '/index-network/intent/1', params: { focus: 'true' } })).toBe(
      '/index-network/intent/1?focus=true'
    )
  })

  it('resolves href the same as a bare string', () => {
    expect(resolveSprkeyOpenPath({ href: 'sprkey://index-network/intent/1' })).toBe('/index-network/intent/1')
  })
})

describe('pathFromSprkeyDeepLink', () => {
  it('builds the navigate path from a plugin-scoped deep-link payload', () => {
    expect(pathFromSprkeyDeepLink('index-network', 'intent/1')).toBe('/index-network/intent/1')
  })

  it('builds the navigate path from sprkey://open/… payloads', () => {
    expect(pathFromOpenDeepLink('index-network/intent/1')).toBe('/index-network/intent/1')
    expect(pathFromSprkeyDeepLink('open', 'agent/42')).toBe('/agent/42')
  })

  it('ignores reserved kinds', () => {
    expect(pathFromSprkeyDeepLink('blueprint', 'morning-brief')).toBeNull()
    expect(pathFromSprkeyDeepLink('plugin', 'install')).toBeNull()
    expect(pathFromSprkeyDeepLink('skill', 'install')).toBeNull()
  })
})
