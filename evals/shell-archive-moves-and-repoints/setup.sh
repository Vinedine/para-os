#!/usr/bin/env bash
# harborlight-crm from archive.sh, archived for real: the prompt carries the operator's
# answers to the preview, so the run goes through Steps 6 to 8. Priya's contact file links
# the brief, so the move has one inbound link to repoint.
set -e
. "$(dirname "$0")/../_fixture/vault.sh"
. "$(dirname "$0")/../_fixture/archive.sh"
