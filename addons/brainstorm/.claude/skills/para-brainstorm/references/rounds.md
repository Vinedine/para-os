# The rounds (Steps 2 to 6)

Referenced from [SKILL.md](../SKILL.md). Each round ends by waiting for the operator. A round the `<path>` input already answers is skipped, and the run says which ones it skipped and why.

## Step 2 - Frame

One `AskUserQuestion` call, closed questions only, `header` naming each decision. Skip a question the request or the vault already answers (a budget the `README.md` states, a no the `CLAUDE.md` records) and say where the answer came from; with all four answered, go straight to the harvest.

| `header` | Question | Options |
|---|---|---|
| `Kind` | What are we brainstorming? | a new offering someone would pay for · an improvement to my own work |
| `Time` | How much time a week could a test take? | an hour or two · half a day · a day or more |
| `Budget` | What could a first test cost? | nothing · a small amount · a real budget |
| `No-go` | Anything off the table? | nothing · I'll name it |

These are facts only the operator holds, so no option is `(Recommended)`. Where the operator gave a topic or none, the first message says which topic the run is on; with no argument and no clear topic in the request, ask it as one open line before the frame.

## Step 3 - Harvest

One short numbered message, never a tool call: its answers are open and the agent has nothing to suggest.

1. Three things that went wrong or wasted time recently.
2. What is still manual, or full of back-and-forth?
3. What do people keep asking you for help with?

Notes or a recording dropped in `triage/` answer it just as well; read them from there. **Offer no idea, example or solution in this message.** A frustration answered with a fix is a judgment in the generating round.

## Step 4 - Cluster and pick

Rewrite the harvest as problem statements, merging those that share a cause:

> For *who*, *task* is painful because *reason*, leading to *cost*.

Put them to the operator as one message, each numbered, for confirming or correcting; a statement the operator rewrites is taken as rewritten. Then pick **three**, on three questions asked of each: is it painful, is it frequent, is it costly enough to act on? Present the three picks with a line each on those questions and let the operator swap any of them. With three or fewer statements, all go forward and the run says so.

## Step 5 - Ideate

Per picked problem, in turn:

1. **The operator goes first.** Ask for their ideas, however rough, as one open line. Wait.
2. **Then the agent adds its own**, one per prompt at most, under these prompts only:
   - *Solve it badly but cheaply.*
   - *Do it for a niche*: one kind of customer, one case.
   - *The manual version before any automation.*
   - *What becomes trivial with an agent.*

   Each is marked `(agent)`. Nothing is scored, ranked or dismissed in this round, the operator's ideas included.

## Step 6 - Shortlist

Every idea from Step 5 gets one line on three criteria only:

- **Pain** - how much of the problem it removes.
- **What it is worth** - for an offering, whether someone would pay and roughly what; for an improvement, what the problem costs today, in time or money.
- **Four weeks** - whether a first test can start within four weeks, in the time and budget the frame gave.

Order them into a ranking and put it to the operator to approve or reorder. No score is summed or shown: the reasons are the ranking. The top two or three go to Step 7.
