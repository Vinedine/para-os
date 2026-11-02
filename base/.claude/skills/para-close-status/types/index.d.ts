// What the files half found at the last scan.
export type Files = {
  isGit: boolean
  // Uncommitted paths in the session's folder, and those this session's file tools wrote.
  uncommitted: number
  fromSession: number
  // Items waiting in triage/; null where the folder has none (not a vault).
  triage: number | null
  startedAt: number
}

// Claude's verdict from the last line of its last reply.
export type Chat = { ready: boolean; note: string }

// The vault's health card as the daily brief's scan gives it: the overall level and
// the signals at watch or care, by the card's own names.
export type Health = { level: 'ok' | 'watch' | 'care' | 'unknown'; flagged: string[]; at: number }

declare module 'claude-code' {
  interface PluginState {
    'para-close-status': {
      files: Files | null
      chat: Chat | null
      hasReplied: boolean
      // Absolute paths, lowercased with forward slashes, that Edit, Write or NotebookEdit wrote.
      touched: string[]
      // Null until the first scan answers, and where the folder is not a vault.
      health: Health | null
    }
  }
}
