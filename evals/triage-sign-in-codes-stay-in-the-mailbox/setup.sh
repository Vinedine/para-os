#!/usr/bin/env bash
set -e
. "$(dirname "$0")/../_fixture/vault.sh"
. "$(dirname "$0")/../_fixture/triage.sh"
rm -f triage/*.md
. "$(dirname "$0")/../_fixture/mailbox.sh"
