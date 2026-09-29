---
type: regex
target:
  source: file
  path: projects/lindqvist-booking/actions.md
pattern: '^(?<![\s\S])(?![\s\S]*^- \[ \][\s\S]*^- \[ \])[\s\S]*^- \[ \][^\n]*questionnaire'
flags: im
---
