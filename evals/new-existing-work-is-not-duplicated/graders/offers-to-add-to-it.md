---
type: llm
---

The vault already holds `projects/acme-website/`, whose `actions.md` has a `## Launch`
section with the launch work in it. The operator asked for a new project for the acme site
launch, which is that same work under another name. The skill's rule is to report a
near-match, ask whether to add to it instead, and never create a second folder for the same
work.

PASS if the reply names `projects/acme-website` as existing work that matches the request and
asks whether to add to it (or use it) rather than create a new project.

FAIL if the reply proposes or creates a new project folder for the launch without first
asking about `projects/acme-website`, or presents the existing project and a new one as
separate work without asking.
