import { build } from 'esbuild'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test } from 'vitest'

import { applyBundleEnvironment, environmentDefaultsBanner } from './bundle-env.mjs'

test('explicit clears beat inherited homes and prevent Windows registry fallback before spawning', async () => {
  const root = mkdtempSync(join(tmpdir(), 'sprkey-bundle-clear-'))
  const paths = fileURLToPath(new URL('../electron/data-paths.ts', import.meta.url))
  const defaults = { SPRKEY_HOME: null, SPRKEY_DATA_DIR_SUFFIX: 'magic-test' }
  try {
    const entry = join(root, 'entry.mjs')
    writeFileSync(entry, `
      import {resolveDesktopSprkeyHome} from ${JSON.stringify(paths)};
      import {execFileSync} from 'node:child_process';
      let registryReads = 0;
      const home = resolveDesktopSprkeyHome({
        home: 'C:/Users/test', platform: 'win32', env: process.env,
        readWindowsHome: () => { registryReads++; return 'C:/old-sprkey'; }
      });
      console.log(JSON.stringify({cleared: process.env.SPRKEY_HOME, home, registryReads,
        child: execFileSync(process.execPath, ['-p', 'process.env.SPRKEY_HOME'], {
          env: {...process.env, SPRKEY_HOME: home}, encoding: 'utf8'
        }).trim()}));
    `)
    const outfile = join(root, 'bundle.mjs')
    await build({ entryPoints: [entry], bundle: true, platform: 'node', format: 'esm', outfile,
      banner: { js: environmentDefaultsBanner(JSON.stringify(defaults)) } })
    const env = { ...process.env, SPRKEY_HOME: 'C:/old-sprkey', LOCALAPPDATA: 'C:/Users/test/AppData/Local' }
    delete env.SPRKEY_DATA_DIR_SUFFIX
    delete env.SPRKEY_DESKTOP_USER_DATA_DIR
    const actual = JSON.parse(execFileSync(process.execPath, [outfile], { env, encoding: 'utf8' }))
    expect(actual).toEqual({ cleared: '', home: 'C:\\Users\\test\\AppData\\Local\\sprkeymagic-test',
      child: 'C:\\Users\\test\\AppData\\Local\\sprkeymagic-test', registryReads: 0 })
  } finally {
    rmSync(root, { recursive: true, force: true })
  }
})

test('applyBundleEnvironment replays the banner semantics for defaults, runtime overrides and clears', async () => {
  const root = mkdtempSync(join(tmpdir(), 'sprkey-bundle-pure-'))
  const defaults = { SPRKEY_HOME: null, SPRKEY_DATA_DIR_SUFFIX: 'baked', SPRKEY_GUEST_ONBOARDING: '1' }
  const keys = Object.keys(defaults)
  const base = { SPRKEY_HOME: 'runtime', SPRKEY_DATA_DIR_SUFFIX: 'explicit' }
  try {
    // The bundled banner must produce the same effective environment the pure
    // function computes, so the smoke driver can predict the app's home from
    // the same bundle env data without running a child process.
    writeFileSync(join(root, 'reader.mjs'), `export const values = Object.fromEntries(${JSON.stringify(keys)}.map(key => [key, process.env[key]]));`, 'utf8')
    const entry = join(root, 'entry.mjs')
    writeFileSync(entry, `import {values} from './reader.mjs'; console.log(JSON.stringify(values));`, 'utf8')
    const outfile = join(root, 'bundle.mjs')
    await build({ entryPoints: [entry], bundle: true, platform: 'node', format: 'esm', outfile, banner: { js: environmentDefaultsBanner(JSON.stringify(defaults)) } })
    const env = { ...process.env, ...base }
    delete env.SPRKEY_GUEST_ONBOARDING
    const viaBanner = JSON.parse(execFileSync(process.execPath, [outfile], { env, encoding: 'utf8' }))
    const viaFunction = Object.fromEntries(keys.map(key => [key, applyBundleEnvironment(base, defaults)[key]]))
    expect(viaFunction).toEqual(viaBanner)
    expect(viaFunction).toEqual({
      SPRKEY_HOME: '', SPRKEY_DATA_DIR_SUFFIX: 'explicit', SPRKEY_GUEST_ONBOARDING: '1',
    })
  } finally {
    rmSync(root, { recursive: true, force: true })
  }
})

test('baked defaults precede imported module initialization and reach children without overriding explicit env', async () => {
  const root = mkdtempSync(join(tmpdir(), 'sprkey-bundle-env-'))
  const defaults = { SPRKEY_GUEST_ONBOARDING: '1', SPRKEY_DATA_DIR_SUFFIX: 'magic-test', SPRKEY_SHARED_AUTH_DIR: 'a=b "q"\n$(no)', SPRKEY_SKIP_INTRO: '' }
  const env = { ...process.env }
  for (const key of Object.keys(defaults)) {
    delete env[key]
  }
  try {
    writeFileSync(join(root, 'reader.mjs'), `export const values = Object.fromEntries(${JSON.stringify(Object.keys(defaults))}.map(key => [key, process.env[key]]));`, 'utf8')
    const entry = join(root, 'entry.mjs')
    writeFileSync(entry, `import {values} from './reader.mjs'; import {execFileSync} from 'node:child_process'; console.log(JSON.stringify({values, child: execFileSync(process.execPath, ['-p', 'process.env.SPRKEY_DATA_DIR_SUFFIX'], {encoding:'utf8'}).trim()}));`, 'utf8')
    const outfile = join(root, 'bundle.mjs')
    await build({ entryPoints: [entry], bundle: true, platform: 'node', format: 'esm', outfile, banner: { js: environmentDefaultsBanner(JSON.stringify(defaults)) } })
    const run = extra => JSON.parse(execFileSync(process.execPath, [outfile], { env: { ...env, ...extra }, encoding: 'utf8' }))
    expect(run({})).toEqual({ values: defaults, child: defaults.SPRKEY_DATA_DIR_SUFFIX })
    expect(run({ SPRKEY_DATA_DIR_SUFFIX: '-explicit', SPRKEY_GUEST_ONBOARDING: '' })).toEqual({ values: { ...defaults, SPRKEY_DATA_DIR_SUFFIX: '-explicit', SPRKEY_GUEST_ONBOARDING: '' }, child: '-explicit' })
    for (const bad of ['[]', 'null', '{"BAD-NAME":"x"}', '{"SPRKEY_HOME":1}', '{"SPRKEY_HOME":"\\u0000"}',
      '{"NODE_OPTIONS":"--require=evil"}', '{"PATH":null}', '{"SPRKEY_PYTHON":"/untrusted/python"}']) {
      expect(() => environmentDefaultsBanner(bad)).toThrow()
    }
  } finally {
    rmSync(root, { recursive: true, force: true })
  }
})
