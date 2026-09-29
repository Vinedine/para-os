---
type: regex
target:
  source: file
  path: vault/.claude/rules/actions.md
pattern: 'paths:[ \t]*\r?\n(?:[ \t]*-[^\n]*\n)*?[ \t]*-[ \t]*["\x27]?areas/\*/actions\.md["\x27]?[ \t]*\r?$|paths:[ \t]*\[[^\]\n]*areas/\*/actions\.md'
flags: m
---
