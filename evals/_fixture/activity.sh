#!/usr/bin/env bash
# Extra fixture for the activity-review cases, sourced after vault.sh (which defines
# `day()`). Writes the ledger the activity integration would have left: one JSONL file per
# session under resources/logs/sessions/, in the field shape addons/activity/pipeline/activity.py
# writes, dated relative to the day of the run.
#
# The shape is deliberate. The vault's CLAUDE.md names four skills. Over thirteen days two
# people invoke /para-daily-brief steadily, /para-new once early, and /para-triage and
# /para-archive never, while triage/ holds six notes and one session files a note by hand.
# So the biggest finding is an absence, which a report built only from what the log shows
# never reaches. Three of the eleven session files hold no prompt at all, a window opened
# and closed, so a count taken from file names overstates the work by three.
set -e

cat >> CLAUDE.md <<'EOF'

## Layout

- **triage/** - unprocessed items, emptied via `/para-triage`.
- `/para-new` creates a project, area, idea, or contact.
- An entity archives whole via `/para-archive`.
- `/para-daily-brief` opens the day.
EOF

for n in 3 5 6 9 12; do
  stamp=$(day -"$n" | tr -d '-')
  case $n in
    3) name="Supplier - Price list for the hosting renewal" ;;
    5) name="Acme - Feedback on the pricing page" ;;
    6) name="Meetup - Contact list" ;;
    9) name="Bank - Statement" ;;
    12) name="Orchard labs - Quote request" ;;
  esac
  printf 'A note waiting to be filed.\n' > "triage/${stamp} ${name}.md"
done

mkdir -p resources/logs/sessions

# session USER SESSION-ID DAYS-AGO: the file this session writes, with its opening line.
session() {
  d=$(day -"$3")
  f="resources/logs/sessions/$(printf '%s' "$d" | tr -d '-')-$1-${2:0:8}.jsonl"
  printf '{"at": "%sT09:00:00", "event": "SessionStart", "session": "%s", "mode": "default", "source": "startup"}\n' "$d" "$2" > "$f"
}

# ev JSON-TAIL: one more line for the current session, at a time after its start.
ev() {
  printf '{"at": "%sT09:%s", "session": "%s", %s}\n' "$d" "$1" "$sid" "$2" >> "$f"
}

# end PROMPTS TOOLS WRITES: the SessionEnd line with the summary activity.py counts.
end() {
  printf '{"at": "%sT09:20:00", "event": "SessionEnd", "session": "%s", "reason": "other", "summary": {"prompts": %s, "tools": %s, "writes": %s, "failures": 0, "denials": 0, "last_prompt_tools": %s, "duration_s": 1200}}\n' \
    "$d" "$sid" "$1" "$2" "$3" "$2" >> "$f"
}

brief_by_command() {
  ev "01:00" '"event": "UserPromptExpansion", "prompt_id": "p1", "prompt": "/para-daily-brief"'
  ev "01:00" '"event": "UserPromptSubmit", "prompt_id": "p1", "prompt": "/para-daily-brief"'
  ev "01:30" '"event": "PostToolUse", "prompt_id": "p1", "tool": "Read", "target": "projects/acme-website/actions.md"'
  ev "01:40" '"event": "PostToolUse", "prompt_id": "p1", "tool": "Read", "target": "areas/business/actions.md"'
  end 1 2 0
}

sid=5f2a9c01-7d3e-4b1a-9c2e-0a1b2c3d4e5f; session sam "$sid" 13; brief_by_command

sid=a41c7e22-1b9d-4f60-8e3a-5d6c7b8a9f00; session robin "$sid" 12
ev "02:00" '"event": "UserPromptExpansion", "prompt_id": "p1", "prompt": "/para-new orchard labs"'
ev "02:00" '"event": "UserPromptSubmit", "prompt_id": "p1", "prompt": "/para-new orchard labs"'
ev "03:10" '"event": "PostToolUse", "prompt_id": "p1", "tool": "Glob", "target": "resources/ideas/*"'
ev "04:20" '"event": "PostToolUse", "prompt_id": "p1", "tool": "Write", "target": "resources/ideas/orchard-labs/brief.md"'
end 1 2 1

sid=0c9e3b7d-2a41-4e8f-b6d5-3e2f1a0b9c8d; session sam "$sid" 11; end 0 0 0

sid=6b8d1f4a-9e2c-4a7b-8d3f-1c2b3a4d5e6f; session sam "$sid" 10; brief_by_command

sid=d2e5a8c1-4f7b-4c3e-9a1d-7e6f5d4c3b2a; session robin "$sid" 8
ev "02:00" '"event": "UserPromptSubmit", "prompt_id": "p1", "prompt": "add a line to the acme project that the host called back about the redirects"'
ev "02:30" '"event": "PostToolUse", "prompt_id": "p1", "tool": "Read", "target": "projects/acme-website/actions.md"'
ev "03:00" '"event": "PostToolUse", "prompt_id": "p1", "tool": "Edit", "target": "projects/acme-website/actions.md"'
end 1 2 1

sid=91f0c6e3-5b2d-4d8a-a7e4-2f3e4d5c6b7a; session robin "$sid" 7; end 0 0 0

sid=3a7c5e9b-8d1f-4b2c-9e6a-4b5c6d7e8f90; session sam "$sid" 6; brief_by_command

sid=e8b2d4f6-3c5a-4e7d-8f1b-9a0b1c2d3e4f; session robin "$sid" 5
ev "02:00" '"event": "UserPromptSubmit", "prompt_id": "p1", "prompt": "what is overdue this week?"'
ev "02:10" '"event": "PostToolUse", "prompt_id": "p1", "tool": "Skill", "target": "para-daily-brief"'
ev "02:40" '"event": "PostToolUse", "prompt_id": "p1", "tool": "Read", "target": "projects/acme-website/actions.md"'
end 1 2 0

sid=7d4f2b8e-6a3c-4f1d-b9e7-5c6d7e8f9a0b; session sam "$sid" 3; brief_by_command

sid=2f6a9d3c-7e5b-4a8f-8c2d-6d7e8f9a0b1c; session sam "$sid" 2; end 0 0 0

sid=b5c8e1a4-9f6d-4b3e-a2c7-8e9f0a1b2c3d; session robin "$sid" 1
ev "02:00" '"event": "UserPromptSubmit", "prompt_id": "p1", "prompt": "put the meetup contact list somewhere sensible"'
ev "02:30" '"event": "PostToolUse", "prompt_id": "p1", "tool": "Glob", "target": "areas/network/*"'
ev "03:40" '"event": "PostToolUse", "prompt_id": "p1", "tool": "Write", "target": "areas/network/meetup-contacts.md"'
end 1 2 1
