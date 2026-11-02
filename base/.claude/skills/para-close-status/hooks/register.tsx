import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Chat, Files, Health } from '../types'

// Can this session be closed? The verdict joins two checks. Files: the uncommitted
// files this session's file tools wrote, read by the mod and shown only when there are
// some (a vault without git, or a clean one, has nothing to say). Chat: Claude's own
// verdict, the last "Close:" line of each reply, which the vault's Memory rule asks
// for (a mod's prompt.compose does not reach the main conversation in the desktop
// app). Beside the verdict, for the operator: how long the session has been open,
// what waits in triage/, and the vault's health card.

const files = atom({ plugin: 'para-close-status', key: 'files' } as const, null)
const chat = atom({ plugin: 'para-close-status', key: 'chat' } as const, null)
const hasReplied = atom({ plugin: 'para-close-status', key: 'hasReplied' } as const, false)
const touched = atom({ plugin: 'para-close-status', key: 'touched' } as const, [])
const health = atom({ plugin: 'para-close-status', key: 'health' } as const, null)

const FILE_TOOLS = ['Edit', 'Write', 'NotebookEdit']

// Health is the daily brief's own card (brief_scan.py's health()), so the band and
// the brief never disagree on what healthy means. The scan takes seconds, so it runs
// on a timer, off the turn's path: at the start, after a reply once two minutes have
// passed since the last one, and every fifteen minutes while the session sits idle.
const HEALTH_AFTER_REPLY_MS = 2 * 60000
const HEALTH_IDLE_MS = 15 * 60000
// The signals that count toward the card's level, by their names in the band.
const SIGNALS: Record<string, string> = {
  last_edit: 'quiet',
  triage: 'triage',
  deep_clean: 'deep clean',
  template: 'template',
  waits: 'waits',
}
let healthRunning = false

const norm = (p: string) => p.replace(/\\/g, '/').replace(/\/+$/, '').toLowerCase()

// The last "Close:" line of a reply, or null when there is none.
function verdict(answer: string): Chat | null {
  const lines = answer.split('\n').map((l) => l.replace(/^[\s*_`>-]+|[\s*_`]+$/g, ''))
  for (let i = lines.length - 1; i >= 0; i--) {
    const m = /^Close:\s*(ready|not yet)\b[\s,:.]*(.*)$/i.exec(lines[i] ?? '')
    if (m) return { ready: (m[1] ?? '').toLowerCase() === 'ready', note: (m[2] ?? '').trim() }
  }
  return null
}

// git status -z: "XY path" entries split on NUL; a rename or copy is followed by
// its source path, which is skipped.
function paths(stdout: string): string[] {
  const out: string[] = []
  const parts = stdout.split('\0')
  for (let i = 0; i < parts.length; i++) {
    const p = parts[i] ?? ''
    if (p.length < 4) continue
    out.push(p.slice(3))
    if (p[0] === 'R' || p[0] === 'C') i++
  }
  return out
}

async function scan($: EngineInterface): Promise<Files> {
  const cwd = await $.session.cwd()
  const { startedAt } = await $.session.usage()
  const git = await $.process
    .run(['git', 'status', '--porcelain', '-z', '--untracked-files=all'], { cwd, timeoutMs: 10000 })
    .catch(() => null)
  const isGit = !!git && git.exitCode === 0
  const changed = isGit ? paths(git.stdout) : []
  const mine = new Set(await read($, touched))
  const fromSession = changed.filter((p) => mine.has(norm(`${cwd}/${p}`))).length
  let triage: number | null = null
  const entries = await $.fs.list(`${cwd}/triage`).catch(() => null)
  if (entries) triage = entries.filter((x) => x.kind === 'file' && !x.name.startsWith('.') && x.name !== 'README.md').length
  return { isGit, uncommitted: changed.length, fromSession, triage, startedAt }
}

async function refresh($: EngineInterface) {
  const found = await scan($).catch(() => null)
  await update($, files, () => found)
}

// Runs the daily brief's scan on the session's folder and keeps its health card. Only
// in a vault (a folder with triage/); a scan that fails reads unknown, never healthy.
// The scan sits beside this mod, as every kit skill does, in whichever skills folder
// the kit was installed to.
async function scanHealth($: EngineInterface) {
  const f = await read($, files)
  if (!f || f.triage === null || healthRunning) return
  healthRunning = true
  try {
    const cwd = await $.session.cwd()
    const skills = $.plugin.root.replace(/\\/g, '/').replace(/\/(\.claude-plugin\/?)?$/, '').replace(/\/[^/]+$/, '')
    const script = `${skills}/para-daily-brief/scripts/brief_scan.py`
    const init = { cwd, timeoutMs: 60000, env: { PYTHONIOENCODING: 'utf-8' } }
    const run = await $.process
      .run(['py', '-3', script, '--vault', cwd], init)
      .catch(() => $.process.run(['python3', script, '--vault', cwd], init))
      .catch(() => null)
    const now = await $.clock.now()
    let found: Health = { level: 'unknown', flagged: ['scan failed'], at: now }
    if (run && run.exitCode === 0) {
      try {
        const card = JSON.parse(run.stdout).health as { level: Health['level']; signals: Record<string, { level: string }> }
        const flagged = Object.entries(SIGNALS)
          .filter(([k]) => ['watch', 'care'].includes(card.signals[k]?.level ?? ''))
          .map(([, name]) => name)
        found = { level: card.level, flagged, at: now }
      } catch {
        // An answer that does not parse stays unknown.
      }
    }
    await update($, health, () => found)
  } finally {
    healthRunning = false
  }
}

function age(ms: number): string {
  const h = ms / 3600000
  if (h < 1) return `${Math.max(1, Math.round(ms / 60000))}m`
  if (h < 48) return `${Math.round(h)}h`
  return `${Math.round(h / 24)} days`
}

const HEALTH_WORDS: Record<Health['level'], string> = { ok: 'ok', watch: 'watch', care: 'needs care', unknown: 'unknown' }
const HEALTH_COLORS = { ok: 'success', watch: 'warning', care: 'error', unknown: 'subtle' } as const

// What the band says.
function summary(f: Files, c: Chat | null, replied: boolean, card: Health | null, now: number) {
  const filesClear = !f.isGit || f.fromSession === 0
  // Empty when there is nothing to say: no git, or nothing of this session's left.
  const filesText = filesClear ? '' : `${f.fromSession} edited, not committed`
  const chatClear = !!c && c.ready
  const chatText = c
    ? c.ready
      ? 'ready'
      : `not yet${c.note ? `: ${c.note}` : ''}`
    : replied
      ? 'no verdict in the last reply'
      : 'waiting for a reply'
  const sinceYesterday = new Date(f.startedAt).toDateString() !== new Date(now).toDateString()
  const ageText = sinceYesterday ? `since yesterday (${age(now - f.startedAt)})` : age(now - f.startedAt)
  const healthText = card ? HEALTH_WORDS[card.level] + (card.flagged.length ? ` (${card.flagged.join(', ')})` : '') : ''
  const canClose = filesClear && chatClear && !sinceYesterday
  return { canClose, filesClear, filesText, chatClear, chatText, sinceYesterday, ageText, healthText }
}

export const register: Register = (on) => {
  on('session.start', async ($, e, next) => {
    const result = await next(e)
    await refresh($)
    $.clock.after(1, () => void scanHealth($))
    $.clock.every(HEALTH_IDLE_MS, () => void scanHealth($))
    return result
  })

  on('tool.call', async ($, e, next) => {
    const result = await next(e)
    if (FILE_TOOLS.includes(e.tool)) {
      // A tool's arguments sit on the event itself (e.file_path).
      const args = e as { file_path?: string; notebook_path?: string }
      const p = args.file_path ?? args.notebook_path
      if (typeof p === 'string') {
        await update($, touched, (t) => (t.includes(norm(p)) ? t : [...t, norm(p)]))
        await refresh($)
      }
    }
    return result
  })

  on('turn.complete', async ($, e, next) => {
    if (!e.agentId) {
      const found = verdict(e.answer)
      await update($, chat, () => found)
      await update($, hasReplied, () => true)
      await refresh($)
      const card = await read($, health)
      if (!card || (await $.clock.now()) - card.at >= HEALTH_AFTER_REPLY_MS) $.clock.after(1, () => void scanHealth($))
    }
    return next(e)
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const f = await read($, files)
    if (e.props.hasSurvey || f === null) return next(e)
    const card = await read($, health)
    const s = summary(f, await read($, chat), await read($, hasReplied), card, await $.clock.now())
    const { Box, Text } = $.ui.resolve(e)
    // One Text holds every piece, so a long note cuts the line short instead of
    // wrapping each piece in a column of its own; Claude's note goes last, where
    // the cut falls (the whole line stays in the reply above). JSX compiles to the
    // global h(), so no name in this hook may be h.
    return (
      <Box>
        <Text wrap="truncate-end">
          <Text color={s.canClose ? 'success' : 'warning'} weight="semibold">
            {s.canClose ? 'Can close' : 'Not yet'}
          </Text>
          {s.filesText ? <Text dimColor> · </Text> : null}
          {s.filesText ? <Text color="warning">{s.filesText}</Text> : null}
          <Text dimColor> · open </Text>
          <Text color={s.sinceYesterday ? 'warning' : 'subtle'}>{s.ageText}</Text>
          {f.triage ? <Text dimColor>{` · ${f.triage} in triage`}</Text> : null}
          {card ? <Text dimColor> · health </Text> : null}
          {card ? <Text color={HEALTH_COLORS[card.level]}>{s.healthText}</Text> : null}
          <Text dimColor>{' · Claude: '}</Text>
          <Text color={s.chatClear ? 'success' : 'warning'}>{s.chatText}</Text>
        </Text>
      </Box>
    )
  })
}
