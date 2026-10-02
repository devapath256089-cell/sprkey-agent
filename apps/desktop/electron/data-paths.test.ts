import assert from 'node:assert/strict'
import os from 'node:os'
import path from 'node:path'

import { afterEach, test, vi } from 'vitest'

import { platformDefaultSprkeyHome, resolveDesktopSprkeyHome, resolveDesktopUserData } from './data-paths'
import { controlSocketPath } from './ssh-connection'

afterEach((): void => {
  vi.unstubAllEnvs()
})

test.skipIf(process.platform === 'win32')('local SSH sockets use the suffixed default root', (): void => {
  vi.stubEnv('SPRKEY_DATA_DIR_SUFFIX', 'magic-test')
  const socket: string = controlSocketPath('user', 'host', 22)

  assert.equal(path.dirname(socket), path.join(platformDefaultSprkeyHome(os.homedir()), 'desktop-ssh'))
})

test('default data roots append the suffix literally on each platform', (): void => {
  for (const platform of ['linux', 'darwin', 'win32'] as const) {
    const paths: typeof path = platform === 'win32' ? path.win32 : path.posix
    const home: string = platform === 'win32' ? 'C:\\Users\\test' : '/home/test'
    const local: string = paths.join(home, 'AppData', 'Local')
    const userData: string = paths.join(home, 'app-data', 'Sprkey')
    const base: string = platform === 'win32' ? paths.join(local, 'sprkey') : paths.join(home, '.sprkey')

    for (const suffix of ['', '-asdfasdf', 'magic-test', ' spaced ']) {
      const env: NodeJS.ProcessEnv = { LOCALAPPDATA: local, SPRKEY_DATA_DIR_SUFFIX: suffix }

      assert.equal(platformDefaultSprkeyHome(home, env, platform), base + suffix)
      assert.equal(resolveDesktopUserData(userData, env), userData + suffix)
      assert.equal(
        resolveDesktopSprkeyHome({ home, env, platform, directoryExists: (): boolean => false }),
        base + suffix
      )
    }
  }
})

test('explicit homes and userData retain precedence, and suffixed Windows homes never use legacy state', (): void => {
  const home: string = '/home/test'

  const env: NodeJS.ProcessEnv = {
    SPRKEY_DATA_DIR_SUFFIX: 'magic-test',
    SPRKEY_HOME: '/explicit/home',
    SPRKEY_DESKTOP_USER_DATA_DIR: '/explicit/electron'
  }

  assert.equal(resolveDesktopUserData('/default/electron', env), path.resolve(env.SPRKEY_DESKTOP_USER_DATA_DIR!))
  assert.equal(resolveDesktopSprkeyHome({ home, env, platform: 'linux' }), env.SPRKEY_HOME)
  delete env.SPRKEY_HOME
  assert.equal(resolveDesktopSprkeyHome({ home, env, platform: 'linux' }), '/explicit/electron/sprkey-home')

  const windowsHome: string = 'C:\\Users\\test'
  const windowsEnv: NodeJS.ProcessEnv = { SPRKEY_DATA_DIR_SUFFIX: 'magic-test' }
  const expected: string = path.win32.join(windowsHome, 'AppData', 'Local', 'sprkeymagic-test')

  assert.equal(
    resolveDesktopSprkeyHome({
      home: windowsHome,
      env: windowsEnv,
      platform: 'win32',
      directoryExists: (): boolean => true
    }),
    expected
  )
  assert.equal(
    resolveDesktopSprkeyHome({
      home: windowsHome,
      env: windowsEnv,
      platform: 'win32',
      readWindowsHome: (): string => 'C:\\custom'
    }),
    'C:\\custom'
  )
})
