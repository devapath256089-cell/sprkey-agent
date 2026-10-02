import { contextBridge, ipcRenderer, webFrame, webUtils } from 'electron'

import type { DesktopProfileRoute } from './desktop-profile'
import type { HudModifierApi, HudModifierStatus } from './hud-modifier-types'
import { customWindowControlsEnabled } from './window-controls'

// Which translucency the OS can back. Asked synchronously because the renderer
// needs it before its first paint, and answered by main because deciding it
// needs `os.release()` — a sandboxed preload may only require electron, events,
// timers and url, so importing node:os here throws before contextBridge runs
// and takes the ENTIRE bridge down with it (window.sprkeyDesktop undefined =>
// "Desktop IPC bridge is unavailable"). No reply means no glass, which degrades
// to an ordinary opaque window rather than a page thinned over nothing.
const translucencySupport = ipcRenderer.sendSync('sprkey:translucency:support')
const hudWindowing = ipcRenderer.sendSync('sprkey:hud:windowing')
const hudNativeDrag = hudWindowing?.nativeDrag === true

const launchFlags: { localModels?: boolean; guestOnboarding?: boolean } | undefined =
  ipcRenderer.sendSync('sprkey:feature-flags')

// Local, sanitized skin payload for the first renderer theme paint. This does
// not wait on `gateway.ready`, so an unreachable remote primary cannot force
// the built-in palette over the skin configured on this machine.
const localSkin = ipcRenderer.sendSync('sprkey:skin:local')

import { unwrapExpectedNotFound } from './api-expected-404'

contextBridge.exposeInMainWorld('sprkeyDesktop', {
  glassSupported: translucencySupport?.glass === true,
  translucencySupported: translucencySupport?.translucency === true,
  // Launch-flag fact: the app was started with --local, so the renderer may
  // show the local-models surfaces. Static for the window's lifetime.
  localModelsEnabled: launchFlags?.localModels === true,
  // Launch-flag fact: the Nous free tier is on for this launch
  // (SPRKEY_GUEST_ONBOARDING=1 or --guest-onboarding). Read-only; the same
  // decision is stamped onto every backend the app spawns.
  guestOnboardingEnabled: launchFlags?.guestOnboarding === true,
  localSkin: localSkin && typeof localSkin === 'object' ? localSkin : null,
  getConnection: (profile, opts) => ipcRenderer.invoke('sprkey:connection', profile, opts),
  // Loopback origin that hosts YouTube's player for the file:// renderer.
  getEmbedHostOrigin: () => ipcRenderer.invoke('sprkey:embed-host:origin'),
  // Registry-scoped backend resolution: { connectionId, profile } → descriptor.
  getConnectionFor: payload => ipcRenderer.invoke('sprkey:connection:for', payload),
  getProfileRoutes: profiles => ipcRenderer.invoke('sprkey:plugin-profile-routes', profiles),
  revalidateConnection: () => ipcRenderer.invoke('sprkey:connection:revalidate'),
  touchBackend: (profile, options) => ipcRenderer.invoke('sprkey:backend:touch', profile, options),
  getPoolLimits: () => ipcRenderer.invoke('sprkey:pool-limits:get'),
  setPoolLimits: limits => ipcRenderer.invoke('sprkey:pool-limits:set', limits),
  getGatewayWsUrl: profile => ipcRenderer.invoke('sprkey:gateway:ws-url', profile),
  // Registry-scoped fresh WS URL: { connectionId, profile } → result shape of
  // getGatewayWsUrl, minted against that connection's backend.
  getGatewayWsUrlFor: payload => ipcRenderer.invoke('sprkey:gateway:ws-url-for', payload),
  // Union agent roster across every registered connection.
  getAgentRoster: () => ipcRenderer.invoke('sprkey:agents:roster'),
  openSessionWindow: (sessionId, opts) => ipcRenderer.invoke('sprkey:window:openSession', sessionId, opts),
  openSessionInTerminal: (sessionId, opts) => ipcRenderer.invoke('sprkey:window:openInTerminal', sessionId, opts),
  openWindow: (options?: DesktopProfileRoute) => ipcRenderer.invoke('sprkey:window:openInstance', options),
  openBrowserWindow: tabId => ipcRenderer.invoke('sprkey:window:openBrowser', tabId),
  windowRelay: {
    send: payload => ipcRenderer.send('sprkey:window:relay', payload),
    onMessage: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('sprkey:window:relay', listener)

      return () => ipcRenderer.removeListener('sprkey:window:relay', listener)
    }
  },
  onBrowserPopoutClosed: callback => {
    const listener = (_event, tabId) => callback(tabId)
    ipcRenderer.on('sprkey:browser-popout:closed', listener)

    return () => ipcRenderer.removeListener('sprkey:browser-popout:closed', listener)
  },
  claimAmbientCue: key => ipcRenderer.invoke('sprkey:ambient:claim', key),
  windowControls: {
    custom: customWindowControlsEnabled(),
    minimize: () => ipcRenderer.send('sprkey:window-control', 'minimize'),
    toggleMaximize: () => ipcRenderer.send('sprkey:window-control', 'toggle-maximize'),
    close: () => ipcRenderer.send('sprkey:window-control', 'close')
  },
  wakeIndicator: {
    getState: () => ipcRenderer.invoke('sprkey:wake-indicator:get'),
    setState: state => ipcRenderer.send('sprkey:wake-indicator:set', state),
    onState: callback => {
      const listener = (_event, state) => callback(state)
      ipcRenderer.on('sprkey:wake-indicator:state', listener)

      return () => ipcRenderer.removeListener('sprkey:wake-indicator:state', listener)
    }
  },
  chatOnboarding: {
    grow: request => ipcRenderer.send('sprkey:chat-onboarding:grow', request),
    soloBoot: () => ipcRenderer.send('sprkey:chat-onboarding:solo-boot')
  },
  petOverlay: {
    // Main renderer → main process: window lifecycle + drag. `request` is
    // `{ bounds, screen }`; resolves with the screen bounds it actually used.
    open: request => ipcRenderer.invoke('sprkey:pet-overlay:open', request),
    close: () => ipcRenderer.invoke('sprkey:pet-overlay:close'),
    setBounds: bounds => ipcRenderer.send('sprkey:pet-overlay:set-bounds', bounds),
    setIgnoreMouse: ignore => ipcRenderer.send('sprkey:pet-overlay:ignore-mouse', ignore),
    // Flip the overlay focusable (and focus it) while the composer needs keys.
    setFocusable: focusable => ipcRenderer.send('sprkey:pet-overlay:set-focusable', focusable),
    // Main renderer → overlay (forwarded by main): push the latest pet state.
    pushState: payload => ipcRenderer.send('sprkey:pet-overlay:state', payload),
    // Overlay → main renderer (forwarded by main): pop back in / composer submit.
    control: payload => ipcRenderer.send('sprkey:pet-overlay:control', payload),
    // Overlay subscribes to state pushes.
    onState: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('sprkey:pet-overlay:state', listener)

      return () => ipcRenderer.removeListener('sprkey:pet-overlay:state', listener)
    },
    // Main renderer subscribes to overlay control messages.
    onControl: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('sprkey:pet-overlay:control', listener)

      return () => ipcRenderer.removeListener('sprkey:pet-overlay:control', listener)
    }
  },
  // HUD mode: the chrome-free floating chat. A full app renderer (own gateway)
  // sized as a floating bar, so it mounts the real composer. Main owns the
  // window; `onChanged` keeps every window's toggle truthful.
  hud: {
    nativeDrag: hudNativeDrag,
    windowing: {
      clientPlacement: hudWindowing?.clientPlacement !== false,
      controlDrag: hudWindowing?.controlDrag === true,
      nativeDrag: hudNativeDrag,
      solid: hudWindowing?.solid === true,
      workspaceTransfer: hudWindowing?.workspaceTransfer === true
    },
    open: request => ipcRenderer.invoke('sprkey:hud:open', request),
    close: () => ipcRenderer.invoke('sprkey:hud:close'),
    setIgnoreMouse: ignore => ipcRenderer.send('sprkey:hud:ignore-mouse', ignore),
    beginMove: () => ipcRenderer.send('sprkey:hud:begin-move'),
    endMove: () => ipcRenderer.send('sprkey:hud:end-move'),
    moveBy: delta => ipcRenderer.send('sprkey:hud:move-by', delta),
    setWorkspaceTransfer: transferring => ipcRenderer.send('sprkey:hud:workspace-transfer', transferring),
    setBounds: bounds => ipcRenderer.send('sprkey:hud:set-bounds', bounds),
    resetLayout: () => ipcRenderer.invoke('sprkey:hud:reset-layout'),
    // Whether the band covers the window below the bar. Main pairs it with the
    // user's translucency setting to decide the native frost (macOS vibrancy /
    // Windows 11 DWM backdrop) — see hudFrostFor.
    setFrost: showing => ipcRenderer.invoke('sprkey:hud:frost', showing),
    // The HUD tells main which session it is on; main hands that back to the
    // app window when the HUD closes, so the app can re-home onto it.
    setSession: sessionId => ipcRenderer.send('sprkey:hud:session', sessionId),
    onGoto: callback => {
      const listener = (_event, sessionId) => callback(sessionId)
      ipcRenderer.on('sprkey:hud:goto', listener)

      return () => ipcRenderer.removeListener('sprkey:hud:goto', listener)
    },
    onChanged: callback => {
      const listener = (_event, state) => callback(state)
      ipcRenderer.on('sprkey:hud:changed', listener)

      return () => ipcRenderer.removeListener('sprkey:hud:changed', listener)
    },
    // Linux only, and silent elsewhere: where the cursor is, in page
    // coordinates, or null when it has left the window. Stands in for the
    // mousemove that `setIgnoreMouseEvents(true, { forward: true })` delivers on
    // macOS and Windows but not here.
    onCursor: callback => {
      const listener = (_event, point) => callback(point)
      ipcRenderer.on('sprkey:hud:cursor', listener)

      return () => ipcRenderer.removeListener('sprkey:hud:cursor', listener)
    },
    // Main's game-overlay watch: whether a fullscreen app (a game) is under
    // the HUD, so the renderer can step back to the low-opacity overlay
    // treatment while one owns the screen.
    onGameOverlay: callback => {
      const listener = (_event, state) => callback(state)
      ipcRenderer.on('sprkey:hud:game-overlay', listener)

      return () => ipcRenderer.removeListener('sprkey:hud:game-overlay', listener)
    }
  },
  hudModifier: {
    getSettings: () => ipcRenderer.invoke('sprkey:hud-modifier:settings:get'),
    setEnabled: enabled => ipcRenderer.invoke('sprkey:hud-modifier:settings:set', enabled),
    openPermissionSettings: () => ipcRenderer.invoke('sprkey:hud-modifier:permission'),
    onStatus: callback => {
      const listener = (_event: Electron.IpcRendererEvent, status: HudModifierStatus) => callback(status)
      ipcRenderer.on('sprkey:hud-modifier:status', listener)

      return () => ipcRenderer.removeListener('sprkey:hud-modifier:status', listener)
    }
  } satisfies HudModifierApi,
  // macOS native screenshot gesture; captures require a main-issued request.
  screenshot:
    process.platform === 'darwin'
      ? {
          getSettings: () => ipcRenderer.invoke('sprkey:screenshot:settings:get'),
          setEnabled: enabled => ipcRenderer.invoke('sprkey:screenshot:settings:set', enabled),
          openPermissionSettings: kind => ipcRenderer.invoke('sprkey:screenshot:permission', kind),
          capture: requestId => ipcRenderer.invoke('sprkey:screenshot:capture', requestId),
          onStatus: callback => {
            const listener = (_event, status) => callback(status)
            ipcRenderer.on('sprkey:screenshot:status', listener)

            return () => ipcRenderer.removeListener('sprkey:screenshot:status', listener)
          },
          onRequest: callback => {
            const channel = 'sprkey:screenshot:request'
            const listener = (_event, requestId) => callback(requestId)

            if (ipcRenderer.listenerCount(channel) === 0) {
              ipcRenderer.send('sprkey:screenshot:subscribe', true)
            }

            ipcRenderer.on(channel, listener)

            return () => {
              ipcRenderer.removeListener(channel, listener)

              if (ipcRenderer.listenerCount(channel) === 0) {
                ipcRenderer.send('sprkey:screenshot:subscribe', false)
              }
            }
          }
        }
      : undefined,
  // Quick Entry: the global-hotkey mini composer window. Main owns the OS
  // shortcut + the persisted preference; the quick window only captures text
  // and hands it back, and the primary renderer submits it through the normal
  // prompt path.
  quickEntry: {
    getSettings: () => ipcRenderer.invoke('sprkey:quick-entry:settings:get'),
    setSettings: patch => ipcRenderer.invoke('sprkey:quick-entry:settings:set', patch),
    // Invoke returns the delivery result so the draft is not lost (#85590).
    submit: payload => ipcRenderer.invoke('sprkey:quick-entry:submit', payload),
    // Main cannot invoke the primary renderer, so it receives this ack (#85590).
    ackSubmit: (correlationId, result) => ipcRenderer.send('sprkey:quick-entry:ack', { correlationId, result }),
    dismiss: () => ipcRenderer.send('sprkey:quick-entry:dismiss'),
    // Primary renderer → main → quick window: gateway connection state + the
    // recent-session options the target picker offers. Main caches the latest
    // payload so a freshly spawned quick window starts from truth.
    pushState: payload => ipcRenderer.send('sprkey:quick-entry:state', payload),
    // Quick window subscribes to those pushes.
    onState: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('sprkey:quick-entry:state', listener)

      return () => ipcRenderer.removeListener('sprkey:quick-entry:state', listener)
    },
    // Main → primary renderer: a submit captured by the quick window.
    onSubmit: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('sprkey:quick-entry:submit', listener)

      return () => ipcRenderer.removeListener('sprkey:quick-entry:submit', listener)
    },
    // Main → quick window: you were just summoned (reset draft + refocus).
    onShown: callback => {
      const listener = () => callback()
      ipcRenderer.on('sprkey:quick-entry:shown', listener)

      return () => ipcRenderer.removeListener('sprkey:quick-entry:shown', listener)
    },
    // Main → quick window: the outcome of a submit whose relay already timed
    // out. Delivery is now KNOWN — reconcile the unknown state instead of
    // leaving the user to resend a prompt that may already be delivered.
    onLateResult: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('sprkey:quick-entry:late-result', listener)

      return () => ipcRenderer.removeListener('sprkey:quick-entry:late-result', listener)
    }
  },
  getBootProgress: () => ipcRenderer.invoke('sprkey:boot-progress:get'),
  getConnectionConfig: profile => ipcRenderer.invoke('sprkey:connection-config:get', profile),
  saveConnectionConfig: payload => ipcRenderer.invoke('sprkey:connection-config:save', payload),
  applyConnectionConfig: payload => ipcRenderer.invoke('sprkey:connection-config:apply', payload),
  testConnectionConfig: payload => ipcRenderer.invoke('sprkey:connection-config:test', payload),
  // Opt-in OS-keychain encryption for stored gateway secrets (default off —
  // see secret-storage-policy.ts). get never touches the OS keychain.
  getSecretStorageEncryption: () => ipcRenderer.invoke('sprkey:secret-storage:get'),
  setSecretStorageEncryption: (on: boolean) => ipcRenderer.invoke('sprkey:secret-storage:set', on),
  // v2 multi-connection registry: named agent sources (local / remote / cloud / ssh).
  connections: {
    list: () => ipcRenderer.invoke('sprkey:connections:list'),
    save: payload => ipcRenderer.invoke('sprkey:connections:save', payload),
    remove: id => ipcRenderer.invoke('sprkey:connections:remove', id),
    setPrimary: id => ipcRenderer.invoke('sprkey:connections:set-primary', id),
    setLaunchMode: mode => ipcRenderer.invoke('sprkey:connections:set-launch-mode', mode),
    setLastUsed: id => ipcRenderer.invoke('sprkey:connections:set-last-used', id),
    test: id => ipcRenderer.invoke('sprkey:connections:test', id),
    updateManaged: id => ipcRenderer.invoke('sprkey:connections:update-managed', id),
    // Fan out `sprkey update` to every eligible registered connection.
    // Optional excludeIds skips rows the caller updates through another path.
    updateAll: options => ipcRenderer.invoke('sprkey:connections:update-all', options),
    // Registry lifecycle push (main → renderer): a connection was removed or
    // materially edited, so secondaries scoped to it must be disposed (and,
    // for edits, re-dialed at the new target).
    onChanged: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('sprkey:connections:changed', listener)

      return () => ipcRenderer.removeListener('sprkey:connections:changed', listener)
    }
  },
  sshConfigHosts: () => ipcRenderer.invoke('sprkey:ssh-config:hosts'),
  sshResolveHost: host => ipcRenderer.invoke('sprkey:ssh-config:resolve', host),
  probeConnectionConfig: remoteUrl => ipcRenderer.invoke('sprkey:connection-config:probe', remoteUrl),
  // `options` lets a registry-editor draft sign in BEFORE it is saved: the
  // main process settles the draft's connection id up front so the login
  // window writes into the per-connection cookie jar the saved entry will
  // read (not the legacy shared jar an unsaved URL would fall back to).
  oauthLoginConnectionConfig: (remoteUrl, options) =>
    ipcRenderer.invoke('sprkey:connection-config:oauth-login', remoteUrl, options),
  oauthLogoutConnectionConfig: remoteUrl => ipcRenderer.invoke('sprkey:connection-config:oauth-logout', remoteUrl),
  // Sprkey Cloud: one portal login powers discovery + silent per-agent sign-in
  // (cloud-auto-discovery Phase 3).
  cloud: {
    status: () => ipcRenderer.invoke('sprkey:cloud:status'),
    login: () => ipcRenderer.invoke('sprkey:cloud:login'),
    logout: () => ipcRenderer.invoke('sprkey:cloud:logout'),
    discover: org => ipcRenderer.invoke('sprkey:cloud:discover', org),
    agentSignIn: dashboardUrl => ipcRenderer.invoke('sprkey:cloud:agent-sign-in', dashboardUrl)
  },
  profile: {
    getDefault: () => ipcRenderer.invoke('sprkey:profile:default:get'),
    setDefault: (route: DesktopProfileRoute) => ipcRenderer.invoke('sprkey:profile:default:set', route),
    onDefaultChanged: (callback: (route: DesktopProfileRoute | null) => void) => {
      const listener = (_event: Electron.IpcRendererEvent, route: DesktopProfileRoute | null) => callback(route)
      ipcRenderer.on('sprkey:profile:default:changed', listener)

      return () => ipcRenderer.removeListener('sprkey:profile:default:changed', listener)
    },
    get: () => ipcRenderer.invoke('sprkey:profile:get'),
    remember: name => ipcRenderer.invoke('sprkey:profile:remember', name),
    set: name => ipcRenderer.invoke('sprkey:profile:set', name)
  },
  // The handler resolves an expected 404 with a sentinel instead of rejecting
  // (Electron logs a stack for every rejected invoke). Turn it back into the
  // rejection the renderer expects — see electron/api-expected-404.ts.
  api: request => ipcRenderer.invoke('sprkey:api', request).then(unwrapExpectedNotFound),
  notify: payload => ipcRenderer.invoke('sprkey:notify', payload),
  claimStartupLatency: () => ipcRenderer.invoke('sprkey:startup-latency:claim'),
  requestMicrophoneAccess: () => ipcRenderer.invoke('sprkey:requestMicrophoneAccess'),
  readWindowBelow: () => ipcRenderer.invoke('sprkey:window:readBelow'),
  readFileDataUrl: filePath => ipcRenderer.invoke('sprkey:readFileDataUrl', filePath),
  readFileDataUrlForAttach: filePath => ipcRenderer.invoke('sprkey:readFileDataUrlForAttach', filePath),
  dataUrlReadMax: {
    get: () => ipcRenderer.invoke('sprkey:data-url-read-max:get'),
    set: maxMb => ipcRenderer.invoke('sprkey:data-url-read-max:set', maxMb)
  },
  readFileText: filePath => ipcRenderer.invoke('sprkey:readFileText', filePath),
  readPluginSource: (filePath: string) => ipcRenderer.invoke('sprkey:readPluginSource', filePath),
  selectPaths: options => ipcRenderer.invoke('sprkey:selectPaths', options),
  selectSavePath: options => ipcRenderer.invoke('sprkey:selectSavePath', options),
  writeClipboard: text => ipcRenderer.invoke('sprkey:writeClipboard', text),
  readClipboard: () => ipcRenderer.invoke('sprkey:readClipboard'),
  saveGatewayFile: payload => ipcRenderer.invoke('sprkey:saveGatewayFile', payload),
  saveImageFromUrl: url => ipcRenderer.invoke('sprkey:saveImageFromUrl', url),
  contextMenuEdit: command => ipcRenderer.invoke('sprkey:context-menu:edit', command),
  contextMenuCopyImage: () => ipcRenderer.invoke('sprkey:context-menu:copy-image'),
  contextMenuSpellcheck: action => ipcRenderer.invoke('sprkey:context-menu:spellcheck', action),
  contextMenuGuestAddWord: payload => ipcRenderer.invoke('sprkey:context-menu:guest-add-word', payload),
  onContextMenuSpellcheck: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('sprkey:context-menu-spellcheck', listener)

    return () => ipcRenderer.removeListener('sprkey:context-menu-spellcheck', listener)
  },
  saveImageBuffer: (data, ext, name) => ipcRenderer.invoke('sprkey:saveImageBuffer', { data, ext, name }),
  capturePreview: payload => ipcRenderer.invoke('sprkey:capturePreview', payload),
  savePastedText: text => ipcRenderer.invoke('sprkey:savePastedText', { text }),
  saveClipboardImage: () => ipcRenderer.invoke('sprkey:saveClipboardImage'),
  getPathForFile: file => {
    try {
      return webUtils.getPathForFile(file) || ''
    } catch {
      return ''
    }
  },
  normalizePreviewTarget: (target, baseDir) => ipcRenderer.invoke('sprkey:normalizePreviewTarget', target, baseDir),
  watchPreviewFile: url => ipcRenderer.invoke('sprkey:watchPreviewFile', url),
  watchDirectory: dir => ipcRenderer.invoke('sprkey:watchDirectory', dir),
  stopPreviewFileWatch: id => ipcRenderer.invoke('sprkey:stopPreviewFileWatch', id),
  setActiveWork: payload => ipcRenderer.send('sprkey:active-work', payload),
  setTitleBarTheme: payload => ipcRenderer.send('sprkey:titlebar-theme', payload),
  setNativeTheme: mode => ipcRenderer.send('sprkey:native-theme', mode),
  setTranslucency: payload => ipcRenderer.send('sprkey:translucency', payload),
  setKeepAwake: on => ipcRenderer.send('sprkey:keep-awake', on),
  minimizeToTray: {
    get: () => ipcRenderer.invoke('sprkey:minimize-to-tray:get'),
    set: on => ipcRenderer.invoke('sprkey:minimize-to-tray:set', on),
    onChanged: callback => {
      const listener = (_event, status) => callback(status)
      ipcRenderer.on('sprkey:minimize-to-tray:changed', listener)

      return () => ipcRenderer.removeListener('sprkey:minimize-to-tray:changed', listener)
    }
  },
  setDisableF12: blocked => ipcRenderer.send('sprkey:devtools:disable-f12', blocked),
  setF12ShortcutActive: active => ipcRenderer.send('sprkey:f12ShortcutActive', Boolean(active)),
  onF12Shortcut: callback => {
    const listener = (_event, input) => callback(input)
    ipcRenderer.on('sprkey:f12-shortcut', listener)

    return () => ipcRenderer.removeListener('sprkey:f12-shortcut', listener)
  },
  setPreviewShortcutActive: active => ipcRenderer.send('sprkey:previewShortcutActive', Boolean(active)),
  openExternal: url => ipcRenderer.invoke('sprkey:openExternal', url),
  mcpOauth: {
    // One-shot loopback listener for MCP OAuth against remote backends: bind
    // on this machine, hand redirectUri to mcp.servers.oauth.start, then wait
    // for the provider redirect and relay code/state via oauth.callback.
    listen: () => ipcRenderer.invoke('sprkey:mcp-oauth:listen'),
    wait: (id, timeoutMs) => ipcRenderer.invoke('sprkey:mcp-oauth:wait', id, timeoutMs),
    cancel: id => ipcRenderer.invoke('sprkey:mcp-oauth:cancel', id)
  },
  openPreviewInBrowser: url => ipcRenderer.invoke('sprkey:openPreviewInBrowser', url),
  reachPreviewUrl: url => ipcRenderer.invoke('sprkey:preview:reach', url),
  setActiveConnectionRoute: route => ipcRenderer.send('sprkey:connection:active-route', route),
  fetchLinkTitle: url => ipcRenderer.invoke('sprkey:fetchLinkTitle', url),
  resolveFavicon: url => ipcRenderer.invoke('sprkey:resolveFavicon', url),
  sanitizeWorkspaceCwd: cwd => ipcRenderer.invoke('sprkey:workspace:sanitize', cwd),
  settings: {
    getDefaultProjectDir: () => ipcRenderer.invoke('sprkey:setting:defaultProjectDir:get'),
    setDefaultProjectDir: dir => ipcRenderer.invoke('sprkey:setting:defaultProjectDir:set', dir),
    pickDefaultProjectDir: () => ipcRenderer.invoke('sprkey:setting:defaultProjectDir:pick')
  },
  zoom: {
    // Current zoom of this window, as { level, percent }.
    get: () => ipcRenderer.invoke('sprkey:zoom:get'),
    // Synchronous zoom factor (1 = 100%). Coordinate math needs it in the
    // same tick as the event it converts, so no IPC round-trip here.
    factor: () => webFrame.getZoomFactor(),
    setPercent: percent => ipcRenderer.send('sprkey:zoom:set-percent', percent),
    // Fires on every zoom change, including the Ctrl/Cmd +/-/0 shortcuts,
    // so the settings UI can stay in sync with the keyboard.
    onChanged: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('sprkey:zoom:changed', listener)

      return () => ipcRenderer.removeListener('sprkey:zoom:changed', listener)
    }
  },
  revealLogs: () => ipcRenderer.invoke('sprkey:logs:reveal'),
  getRecentLogs: () => ipcRenderer.invoke('sprkey:logs:recent'),
  // Fire-and-forget: persists a renderer error-boundary catch (with component
  // stack) to desktop.log so crashes survive the window (#79428).
  reportRendererError: report => ipcRenderer.send('sprkey:logs:renderer-error', report),
  logLine: (line: string): void => ipcRenderer.send('sprkey:logs:renderer-line', line),
  readDir: dirPath => ipcRenderer.invoke('sprkey:fs:readDir', dirPath),
  gitRoot: startPath => ipcRenderer.invoke('sprkey:fs:gitRoot', startPath),
  revealPath: targetPath => ipcRenderer.invoke('sprkey:fs:reveal', targetPath),
  openDir: dirPath => ipcRenderer.invoke('sprkey:fs:openDir', dirPath),
  desktopPluginsRoot: () => ipcRenderer.invoke('sprkey:fs:desktopPluginsRoot'),
  reconcileDesktopPlugins: () => ipcRenderer.invoke('sprkey:fs:reconcileDesktopPlugins'),
  logsRoot: (profile?: string) => ipcRenderer.invoke('sprkey:fs:logsRoot', profile),
  renamePath: (targetPath, newName) => ipcRenderer.invoke('sprkey:fs:rename', targetPath, newName),
  writeTextFile: (filePath, content) => ipcRenderer.invoke('sprkey:fs:writeText', filePath, content),
  trashPath: targetPath => ipcRenderer.invoke('sprkey:fs:trash', targetPath),
  git: {
    worktreeList: repoPath => ipcRenderer.invoke('sprkey:git:worktreeList', repoPath),
    worktreeAdd: (repoPath, options) => ipcRenderer.invoke('sprkey:git:worktreeAdd', repoPath, options),
    worktreeRemove: (repoPath, worktreePath, options) =>
      ipcRenderer.invoke('sprkey:git:worktreeRemove', repoPath, worktreePath, options),
    branchSwitch: (repoPath, branch) => ipcRenderer.invoke('sprkey:git:branchSwitch', repoPath, branch),
    branchList: repoPath => ipcRenderer.invoke('sprkey:git:branchList', repoPath),
    baseBranchList: repoPath => ipcRenderer.invoke('sprkey:git:baseBranchList', repoPath),
    repoStatus: repoPath => ipcRenderer.invoke('sprkey:git:repoStatus', repoPath),
    fileDiff: (repoPath, filePath) => ipcRenderer.invoke('sprkey:git:fileDiff', repoPath, filePath),
    scanRepos: (roots, options) => ipcRenderer.invoke('sprkey:git:scanRepos', roots, options),
    review: {
      list: (repoPath, scope, baseRef) => ipcRenderer.invoke('sprkey:git:review:list', repoPath, scope, baseRef),
      diff: (repoPath, filePath, scope, baseRef, staged) =>
        ipcRenderer.invoke('sprkey:git:review:diff', repoPath, filePath, scope, baseRef, staged),
      stage: (repoPath, filePath) => ipcRenderer.invoke('sprkey:git:review:stage', repoPath, filePath),
      unstage: (repoPath, filePath) => ipcRenderer.invoke('sprkey:git:review:unstage', repoPath, filePath),
      revert: (repoPath, filePath) => ipcRenderer.invoke('sprkey:git:review:revert', repoPath, filePath),
      revParse: (repoPath, ref) => ipcRenderer.invoke('sprkey:git:review:revParse', repoPath, ref),
      commit: (repoPath, message, push) => ipcRenderer.invoke('sprkey:git:review:commit', repoPath, message, push),
      commitContext: repoPath => ipcRenderer.invoke('sprkey:git:review:commitContext', repoPath),
      push: repoPath => ipcRenderer.invoke('sprkey:git:review:push', repoPath),
      shipInfo: repoPath => ipcRenderer.invoke('sprkey:git:review:shipInfo', repoPath),
      prList: (repoPath, branches, numbers) =>
        ipcRenderer.invoke('sprkey:git:review:prList', repoPath, branches, numbers),
      createPr: repoPath => ipcRenderer.invoke('sprkey:git:review:createPr', repoPath)
    }
  },
  terminal: {
    attach: id => ipcRenderer.invoke('sprkey:terminal:attach', id),
    cwd: id => ipcRenderer.invoke('sprkey:terminal:cwd', id),
    dispose: id => ipcRenderer.invoke('sprkey:terminal:dispose', id),
    resize: (id, size) => ipcRenderer.invoke('sprkey:terminal:resize', id, size),
    start: options => ipcRenderer.invoke('sprkey:terminal:start', options),
    write: (id, data) => ipcRenderer.invoke('sprkey:terminal:write', id, data),
    onData: (id, callback) => {
      const channel = `sprkey:terminal:${id}:data`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)

      return () => ipcRenderer.removeListener(channel, listener)
    },
    onExit: (id, callback) => {
      const channel = `sprkey:terminal:${id}:exit`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)

      return () => ipcRenderer.removeListener(channel, listener)
    }
  },
  onClosePreviewRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('sprkey:close-preview-requested', listener)

    return () => ipcRenderer.removeListener('sprkey:close-preview-requested', listener)
  },
  onPreviewNav: callback => {
    const listener = (_event, command) => callback(command)
    ipcRenderer.on('sprkey:preview-nav', listener)

    return () => ipcRenderer.removeListener('sprkey:preview-nav', listener)
  },
  onOpenFolderRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('sprkey:open-folder-requested', listener)

    return () => ipcRenderer.removeListener('sprkey:open-folder-requested', listener)
  },
  onOpenUpdatesRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('sprkey:open-updates', listener)

    return () => ipcRenderer.removeListener('sprkey:open-updates', listener)
  },
  onDeepLink: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('sprkey:deep-link', listener)

    return () => ipcRenderer.removeListener('sprkey:deep-link', listener)
  },
  signalDeepLinkReady: () => ipcRenderer.invoke('sprkey:deep-link-ready'),
  probePluginRepo: payload => ipcRenderer.invoke('sprkey:plugin:probe', payload),
  installDesktopPlugin: payload => ipcRenderer.invoke('sprkey:plugin:installDesktop', payload),
  removeDesktopPlugin: payload => ipcRenderer.invoke('sprkey:plugin:removeDesktop', payload),
  onWindowStateChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('sprkey:window-state-changed', listener)

    return () => ipcRenderer.removeListener('sprkey:window-state-changed', listener)
  },
  onFocusSession: callback => {
    const listener = (_event, sessionId) => callback(sessionId)
    ipcRenderer.on('sprkey:focus-session', listener)

    return () => ipcRenderer.removeListener('sprkey:focus-session', listener)
  },
  onNotificationAction: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('sprkey:notification-action', listener)

    return () => ipcRenderer.removeListener('sprkey:notification-action', listener)
  },
  onNotificationActivate: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('sprkey:notification-activate', listener)

    return () => ipcRenderer.removeListener('sprkey:notification-activate', listener)
  },
  onExternalOpenFailed: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('sprkey:external-open-failed', listener)

    return () => ipcRenderer.removeListener('sprkey:external-open-failed', listener)
  },
  onPreviewFileChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('sprkey:preview-file-changed', listener)

    return () => ipcRenderer.removeListener('sprkey:preview-file-changed', listener)
  },
  onBackendExit: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('sprkey:backend-exit', listener)

    return () => ipcRenderer.removeListener('sprkey:backend-exit', listener)
  },
  // Cooperative pool retirement (main → renderer): the pooled backend under
  // `poolKey` is being stopped for a foreground open. Park that scope; do not
  // redial into the slot it vacated.
  onPoolBackendRetiring: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('sprkey:pool:retiring', listener)

    return () => ipcRenderer.removeListener('sprkey:pool:retiring', listener)
  },
  // Soft gateway-mode apply finished tearing down the primary backend. Renderer
  // should wipe session lists + re-dial without a window reload.
  onConnectionApplied: callback => {
    const listener = () => callback()
    ipcRenderer.on('sprkey:connection:applied', listener)

    return () => ipcRenderer.removeListener('sprkey:connection:applied', listener)
  },
  onPowerResume: callback => {
    const listener = () => callback()
    ipcRenderer.on('sprkey:power-resume', listener)

    return () => ipcRenderer.removeListener('sprkey:power-resume', listener)
  },
  // AC ↔ battery transitions; renderers slow their backstop polls on battery.
  getOnBattery: () => ipcRenderer.invoke('sprkey:power-battery:get'),
  onBatteryChanged: callback => {
    const listener = (_event, onBattery) => callback(Boolean(onBattery))
    ipcRenderer.on('sprkey:power-battery', listener)

    return () => ipcRenderer.removeListener('sprkey:power-battery', listener)
  },
  onBootProgress: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('sprkey:boot-progress', listener)

    return () => ipcRenderer.removeListener('sprkey:boot-progress', listener)
  },
  // First-launch bootstrap progress -- emitted by the install.ps1 stage
  // runner in main.ts (apps/desktop/electron/bootstrap-runner.ts).
  // Renderer's install overlay subscribes to live events and queries the
  // current snapshot via getBootstrapState() to recover after a devtools
  // reload mid-bootstrap.
  getBootstrapState: () => ipcRenderer.invoke('sprkey:bootstrap:get'),
  probeLocalBackend: () => ipcRenderer.invoke('sprkey:local-backend:probe'),
  continueBootstrapLocal: () => ipcRenderer.invoke('sprkey:bootstrap:continue-local'),
  recycleBackend: profile => ipcRenderer.invoke('sprkey:backend:recycle', profile),
  resetBootstrap: () => ipcRenderer.invoke('sprkey:bootstrap:reset'),
  repairBootstrap: () => ipcRenderer.invoke('sprkey:bootstrap:repair'),
  cancelBootstrap: () => ipcRenderer.invoke('sprkey:bootstrap:cancel'),
  onBootstrapEvent: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('sprkey:bootstrap:event', listener)

    return () => ipcRenderer.removeListener('sprkey:bootstrap:event', listener)
  },
  getVersion: () => ipcRenderer.invoke('sprkey:version'),
  relaunchApp: () => ipcRenderer.invoke('sprkey:app:relaunch'),
  getMachineProfile: () => ipcRenderer.invoke('sprkey:machine:profile'),
  getRemoteDisplayReason: () => ipcRenderer.invoke('sprkey:get-remote-display-reason'),
  uninstall: {
    summary: () => ipcRenderer.invoke('sprkey:uninstall:summary'),
    run: mode => ipcRenderer.invoke('sprkey:uninstall:run', { mode })
  },
  updates: {
    check: opts => ipcRenderer.invoke('sprkey:updates:check', opts),
    apply: opts => ipcRenderer.invoke('sprkey:updates:apply', opts),
    getBranch: () => ipcRenderer.invoke('sprkey:updates:branch:get'),
    setBranch: name => ipcRenderer.invoke('sprkey:updates:branch:set', name),
    onProgress: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('sprkey:updates:progress', listener)

      return () => ipcRenderer.removeListener('sprkey:updates:progress', listener)
    },
    takePendingRun: () => ipcRenderer.invoke('sprkey:updates:metric:take'),
    ackPendingRun: sent => ipcRenderer.invoke('sprkey:updates:metric:ack', sent),
    onPendingRun: callback => {
      const listener = () => callback()
      ipcRenderer.on('sprkey:updates:metric:pending', listener)

      return () => ipcRenderer.removeListener('sprkey:updates:metric:pending', listener)
    }
  },
  desktopMetrics: {
    setEnabled: (on, profile) => ipcRenderer.invoke('sprkey:desktop-metrics:set-enabled', on, profile),
    takeRendererCrashes: () => ipcRenderer.invoke('sprkey:desktop-metrics:crash:take'),
    ackRendererCrashes: sent => ipcRenderer.invoke('sprkey:desktop-metrics:crash:ack', sent)
  },
  themes: {
    fetchMarketplace: id => ipcRenderer.invoke('sprkey:vscode-theme:fetch', id),
    searchMarketplace: query => ipcRenderer.invoke('sprkey:vscode-theme:search', query)
  },
  // Find-in-page (Ctrl/Cmd+F): delegates to Electron's
  // webContents.findInPage on the IPC sender's window so a Cmd+F pressed
  // in a secondary session window searches THAT window, not the primary.
  // `onFoundInPage` returns the unsubscribe fn; the renderer wires it via
  // `initFindInPageListener` in store/find-in-page.ts and tears it down
  // when the FindBar unmounts.
  findInPage: (query, options) => ipcRenderer.invoke('sprkey:find-in-page', query, options),
  stopFindInPage: () => ipcRenderer.invoke('sprkey:stop-find-in-page'),
  onFoundInPage: callback => {
    const listener = (_event, result) => callback(result)
    ipcRenderer.on('sprkey:found-in-page', listener)

    return () => ipcRenderer.removeListener('sprkey:found-in-page', listener)
  },
  // Main-process `before-input-event` forwards Ctrl/Cmd+F here so renderer
  // can open the FindBar even when the GTK compositor has already grabbed
  // the chord at the windowing layer (#81727).
  onOpenFindBarRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('sprkey:open-find-bar', listener)

    return () => ipcRenderer.removeListener('sprkey:open-find-bar', listener)
  }
})
