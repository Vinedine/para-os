---
type: regex
match: not_contains
pattern: '^(?=(?:> ?)?(?:Hi|Hello|Dear|Hey|Good (?:morning|afternoon))\b)(?:[^\n]*\n(?:(?![ \t]*```)(?!(?:> ?)?(?:Thanks|Thank you|Many thanks|Best|Kind regards|Regards|Warm regards|Cheers|All the best|Speak soon|Sincerely)\b[^\n]{0,15}$)[^\n]*\n)*?)?(?![ \t]*```)[^\n]*?(?:\*\*|__|\]\(|`|^(?:> ?)?#{1,6} |(?:^|\s)[*_][^\s*_])'
flags: m
---
