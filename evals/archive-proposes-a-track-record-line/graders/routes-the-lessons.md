---
type: llm
---

The project's brief ends with a `## Lessons` section holding two lessons: keep a parallel run
on every billing migration, and get the bookkeeper's sign-off on a mock-up before building the
invoice template. Once the brief is archived, nothing reads it again. The vault holds
`resources/playbooks/tool-rollouts.md`, a playbook on this kind of work. The skill's rule is to
route at most three lessons to a home something still reads (a playbook in `resources/`, a rule
in the vault's `CLAUDE.md`, or a working preference), and to say plainly of any lesson left in
the closed brief that it will not be read there.

PASS if the reply proposes moving at least one of the two lessons to such a live home, and for
any lesson it leaves in the brief says that nothing will read it there. Proposing both for the
playbook passes, and so does putting either to the operator as a choice of home.

FAIL if the reply never mentions the lessons, lets both archive with the brief without saying
they will not be read again, or proposes routing more than three lessons.
