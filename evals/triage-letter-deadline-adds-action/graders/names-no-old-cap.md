---
type: regex
match: not_contains
pattern: '(?<![\d.-])12\+?(?![\d-]\d)[^\n]{0,15}?(?:open|items?\b|limit|threshold|WIP|groom)|(?:limit|threshold|cap)\s+of\s+12\b'
flags: i
---
