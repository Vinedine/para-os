// The para-close-status mod, run by tools/check.py with `claude plugin test` from a copy of
// the mod, so base/ ships only what a vault receives. Each hook here stands for the engine.

import { expect, mock, test } from 'claude-code/testing'

const BAND = {
  plugin: 'para-close-status',
  component: 'AbovePrompt',
  props: { hasSurvey: false, isWorking: false, maxRows: 10, bodyColumns: 300, scroll: { offset: 0, bodyRows: 10 }, view: {} },
} as const

const VAULT = 'C:/vault'
const START = Date.UTC(2026, 10, 2, 9, 0)

function card(level: string, signals: Record<string, string>) {
  const s: Record<string, { level: string }> = {}
  for (const [k, v] of Object.entries(signals)) s[k] = { level: v }
  return JSON.stringify({ health: { level, signals: s } })
}

// The world beneath the mod: a vault folder, its triage/, git or not, and the scan.
function world(on: any, opts: { git: string | null; triage: number; scan: string | null }) {
  const clock = mock.clock(on, { now: START + 60000 })
  on('session.start', (_: any, e: any) => ({ cwd: e.cwd }))
  on('session.cwd', () => ({ value: VAULT }))
  on('session.usage', () => ({ value: { startedAt: START } }))
  on('tool.register', () => ({ value: {} }))
  on('tool.call', () => ({ result: {} }))
  on('turn.complete', (_: any, e: any) => ({ text: e.text }))
  on('fs.list', () => ({
    value: Array.from({ length: opts.triage }, (_, i) => ({ name: `item ${i}.md`, kind: 'file', path: `${VAULT}/triage/item ${i}.md` })),
  }))
  const runs: string[][] = []
  on('process.run', (_: any, e: any) => {
    runs.push(e.argv)
    const out = (stdout: string, exitCode = 0) => ({ value: { exitCode, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false } })
    if (e.argv[0] === 'git') return opts.git === null ? out('', 128) : out(opts.git)
    return opts.scan === null ? out('', 1) : out(opts.scan)
  })
  return { clock, runs }
}

async function band($: any) {
  const ui = await $.ui.mount({ ...BAND, surface: 'desktop' })
  const t = await ui.find({ type: 'Text', text: /^(Not yet|Can close)/ })
  await ui.unmount()
  return t?.text
}

test('a vault without git: no files text, triage, health with its flags', async ($, on) => {
  const { clock, runs } = world(on, { git: null, triage: 22, scan: card('watch', { last_edit: 'ok', triage: 'ok', deep_clean: 'watch', template: 'ok', waits: 'ok', auto_triage: 'watch' }) })
  await $.session.start({ cwd: VAULT, surface: 'desktop', isInteractive: true } as any)
  await clock.advance(5)
  // The scan is the daily brief's own, found beside the mod in its skills folder.
  expect(runs.some((a) => a[0] === 'py' && (a[2] ?? '').endsWith('/para-daily-brief/scripts/brief_scan.py') && a.includes('--vault'))).toBe(true)
  expect(await band($)).toBe('Not yet · open 1m · 22 in triage · health watch (deep clean) · Claude: waiting for a reply')
})

test('a git vault: this session\'s uncommitted edit shows, and clears the verdict only when gone', async ($, on) => {
  const w = { git: ' M notes.md\0?? other.md\0', triage: 0, scan: card('ok', { last_edit: 'ok', triage: 'ok', deep_clean: 'ok', template: 'ok', waits: 'ok' }) }
  const { clock } = world(on, w)
  await $.session.start({ cwd: VAULT, surface: 'desktop', isInteractive: true } as any)
  await clock.advance(5)
  await $.turn.complete({ answer: 'Done.\n\nClose: ready', text: 'Done.\n\nClose: ready', reason: 'end_turn' } as any)
  expect(await band($)).toBe('Can close · open 1m · health ok · Claude: ready')
  await $.tool.call({ tool: 'Edit', file_path: `${VAULT}/notes.md`, old_string: 'a', new_string: 'b' } as any)
  expect(await band($)).toBe('Not yet · 1 edited, not committed · open 1m · health ok · Claude: ready')
})

test('a scan that fails reads unknown, never healthy', async ($, on) => {
  const { clock } = world(on, { git: '', triage: 3, scan: null })
  await $.session.start({ cwd: VAULT, surface: 'desktop', isInteractive: true } as any)
  await clock.advance(5)
  await $.turn.complete({ answer: 'Working on it.\nClose: not yet, the draft is only in chat', text: '', reason: 'end_turn' } as any)
  expect(await band($)).toBe('Not yet · open 1m · 3 in triage · health unknown (scan failed) · Claude: not yet: the draft is only in chat')
})
