---
type: regex
target: trace
pattern: '<p2@mail\.example>\\",(?:\\n| )*\\"received\\": \\"(\d{4}-\d{2}-\d{2})T[\s\S]*?\\"after\\": \\"\1\\",(?:\\n| )*\\"weekday\\": \\"Wednesday\\",(?:\\n| )*\\"date\\": \\"(\d{4}-\d{2}-\d{2})\\"[\s\S]*?"type":\s*"text",\s*"text":\s*"(?:[^"\\]|\\.)*?(?:📅|\\ud83d\\udcc5) ?\2\b'
---
