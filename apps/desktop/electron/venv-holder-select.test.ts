import assert from 'node:assert/strict'

import { test } from 'vitest'

import { hasWindowsPathPrefix, isExternalVenvHolder, isSprkeyOwnedVenvDaemon } from './venv-holder-select'

const SCRIPTS = 'C:\\Sprkey\\venv\\Scripts'

test('matches the hindsight daemon shim (exe under venv Scripts + hindsight cmdline)', () => {
  assert.equal(
    isSprkeyOwnedVenvDaemon(
      'C:\\Sprkey\\venv\\Scripts\\pythonw.exe',
      'C:\\Sprkey\\venv\\Scripts\\pythonw.exe -m hindsight_api.main --daemon --idle-timeout 300 --port 9177',
      SCRIPTS
    ),
    true
  )
})

test('Windows path prefix match is ordinal case-insensitive', () => {
  assert.equal(
    isSprkeyOwnedVenvDaemon(
      'c:\\sprkey\\venv\\scripts\\python.exe',
      'python.exe -m hindsight_api.main --daemon',
      'C:\\Sprkey\\venv\\Scripts'
    ),
    true
  )
})

test('excludes external venv holders that are not the hindsight daemon', () => {
  // a user terminal running the sprkey CLI from the venv — must NOT be killed
  assert.equal(isSprkeyOwnedVenvDaemon('C:\\Sprkey\\venv\\Scripts\\sprkey.exe', 'sprkey chat -q "hi"', SCRIPTS), false)
  // an unrelated python script using the venv interpreter
  assert.equal(
    isSprkeyOwnedVenvDaemon('C:\\Sprkey\\venv\\Scripts\\python.exe', 'python C:\\tools\\import.py', SCRIPTS),
    false
  )
})

test('excludes exes outside the venv even when the cmdline mentions hindsight', () => {
  assert.equal(
    isSprkeyOwnedVenvDaemon('C:\\Other\\pythonw.exe', 'pythonw -m hindsight_api.main --daemon', SCRIPTS),
    false
  )
})

test('prefix boundary: sibling dirs (ScriptsX) do not match', () => {
  assert.equal(hasWindowsPathPrefix('C:\\Sprkey\\venv\\ScriptsX\\python.exe', SCRIPTS), false)
  assert.equal(hasWindowsPathPrefix('C:\\Sprkey\\venv\\Scripts\\python.exe', SCRIPTS), true)
})

test('null/undefined fields never match', () => {
  assert.equal(isSprkeyOwnedVenvDaemon(null, 'x', SCRIPTS), false)
  assert.equal(isSprkeyOwnedVenvDaemon('C:\\Sprkey\\venv\\Scripts\\pythonw.exe', null, SCRIPTS), false)
  assert.equal(isSprkeyOwnedVenvDaemon(undefined, undefined, SCRIPTS), false)
})

// --- isExternalVenvHolder (#62311) ------------------------------------------

test('matches the autostart gateway shim (sprkey.exe under venv Scripts)', () => {
  assert.equal(
    isExternalVenvHolder(
      'C:\\Sprkey\\venv\\Scripts\\sprkey.exe',
      '"C:\\Sprkey\\venv\\Scripts\\sprkey.exe" gateway run --external-supervisor',
      SCRIPTS
    ),
    true
  )
})

test('matches the dashboard scheduled task (python -m sprkey_cli / -m sprkey)', () => {
  assert.equal(
    isExternalVenvHolder(
      'C:\\Sprkey\\venv\\Scripts\\python.exe',
      '"C:\\Sprkey\\venv\\Scripts\\python.exe" -m sprkey_cli.main dashboard',
      SCRIPTS
    ),
    true
  )
  assert.equal(
    isExternalVenvHolder('C:\\Sprkey\\venv\\Scripts\\pythonw.exe', 'pythonw.exe -m sprkey serve', SCRIPTS),
    true
  )
})

test('never matches an unrelated process that merely borrows the venv interpreter', () => {
  // a user's own script running on the venv python — NOT Sprkey, must NOT be killed
  assert.equal(
    isExternalVenvHolder('C:\\Sprkey\\venv\\Scripts\\python.exe', 'python C:\\tools\\import.py', SCRIPTS),
    false
  )
  // hindsight daemon is selected by isSprkeyOwnedVenvDaemon, not here
  assert.equal(
    isExternalVenvHolder('C:\\Sprkey\\venv\\Scripts\\pythonw.exe', 'pythonw -m hindsight_api.main --daemon', SCRIPTS),
    false
  )
})

test('never matches a process outside the venv, even with sprkey in the cmdline', () => {
  // an editor / shell whose command line mentions the install root (#62445 regression guard)
  assert.equal(
    isExternalVenvHolder('C:\\Windows\\System32\\cmd.exe', 'cmd /c cd C:\\Sprkey\\venv\\Scripts && dir', SCRIPTS),
    false
  )
  assert.equal(isExternalVenvHolder('C:\\Other\\sprkey.exe', 'sprkey gateway run', SCRIPTS), false)
})

test('sibling-dir and boundary safety for the external selector', () => {
  assert.equal(isExternalVenvHolder('C:\\Sprkey\\venv\\ScriptsX\\sprkey.exe', 'sprkey gateway run', SCRIPTS), false)
  assert.equal(isExternalVenvHolder(null, 'sprkey gateway run', SCRIPTS), false)
  assert.equal(isExternalVenvHolder('C:\\Sprkey\\venv\\Scripts\\sprkey.exe', null, SCRIPTS), false)
})
