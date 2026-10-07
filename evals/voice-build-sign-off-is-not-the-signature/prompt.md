---
max_turns: 40
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep]
append_system_prompt: "A session started in this folder loads ./CLAUDE.md, the vault's conventions, and this one has not: read ./CLAUDE.md before you answer."
---

Build my voice profile, so your drafts sound like me. I'm Noor Visser and I send from owner@example.com; my mailbox isn't connected here, so I exported my last six sent mails to sent-export/. Don't save anything yet: show me the whole profile file exactly as you would save it, and the paragraph you would add to CLAUDE.md.
