#!/usr/bin/env bash
# A mailbox whose row asks for the sent pass, sourced from a vault root after vault.sh. The
# vault declares one fetch-script mailbox, `resources/scripts/mail.py fetch`, which prints
# received mail only, and with `--sent` the owner's own messages too, as `outlook.py` does.
# `SENT_THREADS` names the threads it holds (default: both), dated at fetch time:
#
# - promise: Rosa asks for a price on the Thursday before the last Friday before the run;
#   the owner answers that Friday, "price to you Wednesday"; Rosa's later reply that Friday
#   is about something else. Due: the Wednesday five days after the owner's message.
# - proposal: the owner sent Ivo a site-care proposal seven days before the run, and nobody
#   has answered. Seven days always hold five working days: a wait, since that day.
set -e

cat >> CLAUDE.md <<'EOF2'

## Triage sources

| Source | Type | Endpoint | Relevant when |
|---|---|---|---|
| work | fetch-script 📤 sent | `owner@example.com` via `resources/scripts/mail.py fetch` (prints candidates, writes nothing) | Client and prospect threads. |
EOF2

cat > areas/network/rosa-okafor.md <<'EOF2'
# Rosa Okafor

**Kind:** prospect

Runs operations at Orchard Labs ([idea](../../resources/ideas/orchard-labs/brief.md)),
rosa@orchard-labs.example.
EOF2

cat > areas/network/ivo-brandt.md <<'EOF2'
# Ivo Brandt

**Kind:** prospect

Practice manager at Fernhill Dental, ivo@fernhill.example. Met on a discovery call about
their website.
EOF2

mkdir -p resources/scripts
printf '# A mailbox fixture: the threads this case holds.\nKEEP = "%s".split()\n' \
  "${SENT_THREADS:-promise proposal}" > resources/scripts/mail.py
cat >> resources/scripts/mail.py <<'EOF2'
# `fetch [--days N] [--sent]` prints threads as JSON, as a fetch script does: received mail
# only, and with --sent the owner's own messages from Sent as well.
import json
import sys
from datetime import datetime, time, timedelta, timezone

OWNER = "owner@example.com"
ROSA, IVO = "rosa@orchard-labs.example", "ivo@fernhill.example"
today = datetime.now(timezone.utc).date()
friday = today - timedelta(days=(today.weekday() - 4) % 7 or 7)   # the last Friday before today


def at(day, hour, minute=0):
    return datetime.combine(day, time(hour, minute), tzinfo=timezone.utc).isoformat()


def msg(mid, when, sender, name, to, subject, preview):
    return {"id": mid, "message_id": f"<{mid}@mail.example>", "received": when,
            "from": sender, "from_name": name, "from_owner": sender == OWNER, "to": [to],
            "cc": [], "subject": subject, "preview": preview,
            "link": f"https://mail.example/{mid}"}


THREADS = {
    "promise": [
        msg("p1", at(friday - timedelta(days=1), 9), ROSA, "Rosa Okafor", OWNER,
            "Price for the quoting flow",
            "Hi, could you send me a price for rebuilding our quoting flow? We want to "
            "decide this month."),
        msg("p2", at(friday, 10, 17), OWNER, "Fixture Studio", ROSA,
            "RE: Price for the quoting flow",
            "Thanks Rosa, happy to. I am pulling the numbers together now: price to you "
            "Wednesday."),
        msg("p3", at(friday, 15), ROSA, "Rosa Okafor", OWNER,
            "RE: Price for the quoting flow",
            "Great, thanks. Unrelated: I enjoyed your talk at the meetup, the slides were "
            "very clear."),
    ],
    "proposal": [
        msg("s1", at(today - timedelta(days=7), 10), OWNER, "Fixture Studio", IVO,
            "Proposal: monthly site care for Fernhill Dental",
            "Hi Ivo, as discussed on our call, here is my proposal for monthly care of the "
            "Fernhill Dental site: updates, backups and an hour of changes a month, at 180 a "
            "month. Could you let me know whether you would like to go ahead?"),
    ],
}

args = sys.argv[1:]
if args[:1] != ["fetch"]:
    sys.exit("usage: mail.py fetch [--days N] [--sent]")
sent = "--sent" in args
records = []
for name in KEEP:
    messages = sorted((m for m in THREADS[name] if sent or not m["from_owner"]),
                      key=lambda m: m["received"], reverse=True)
    if not messages:
        continue
    newest = messages[0]
    records.append(dict(newest, account=OWNER, thread_id=f"thread-{name}",
                        message_count=len(messages), messages=messages,
                        participants=sorted({m["from"] for m in messages
                                             if not m["from_owner"]}),
                        read=f"py resources/scripts/mail.py raw {newest['id']}"))
print(json.dumps(records, indent=1))
print(f"work: {sum(r['message_count'] for r in records)} messages, {len(records)} threads"
      f"{', Sent included' if sent else ''}", file=sys.stderr)
EOF2
