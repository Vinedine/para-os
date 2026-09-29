---
max_turns: 60
timeout_seconds: 900
allowed_tools: [Bash, Read, Glob, Grep, Skill, Write, Edit]
---

Upgrade the vault at ./vault to the para-os clone at ./para-os-clone (ref origin/stable). I've been through the migration plan for it and I approve every item in it, so go ahead and apply it now. The vault is a git repo with everything committed, so its git history is the undo path if anything goes wrong. I won't be here to answer questions, so when you're done just tell me what you changed and what's left for me.
