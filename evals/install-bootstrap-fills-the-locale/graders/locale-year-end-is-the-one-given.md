---
type: regex
target:
  source: file
  path: CLAUDE.md
pattern: '^\*\*Locale:\*\*[^\n]*\bfinancial year ends (?:31 March|March 31|--03-31|03-31)\b'
flags: m
---
