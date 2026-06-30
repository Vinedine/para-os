# Prompt - monthly steering committee update

Reusable spec. Paste into a Claude Code session in this vault to generate the monthly steering-committee update. It reads the vault; it invents nothing.

---

Produce the BelFoot IT modernisation steering-committee update for the current month. Work only from this vault - do not invent status.

**Sources to read:**

- Each `projects/*/brief.md` for scope, deadline, and the Status section.
- Each `projects/*/actions.md` and `areas/stadium/actions.md` for live and overdue tasks (use the same parse as `/para-daily-brief`).
- `archive/meetings/` entries dated in the reporting month for decisions taken.

**Output (one page, in this order):**

1. **Headline** - one sentence per project: on track / at risk / blocked, with the single most important reason.
2. **Per project** - 3-4 bullets: progress this month, what's next, and any decision or budget ask for the committee.
3. **Risks & decisions needed** - only items that need a committee decision or are off-track. Pull budget overruns straight from the briefs (e.g. the cashless Q3 overrun).
4. **Milestones, next 60 days** - a table of upcoming dated deliverables across all projects.

**Rules:**

- Every number and date must trace to a file. If a figure isn't in the vault, write "not yet confirmed" - don't estimate.
- Audience is the BelFoot board: plain business language, no IT jargon.
- This is a derived output. Don't save it as a standalone source of truth; regenerate it next month from the vault.
