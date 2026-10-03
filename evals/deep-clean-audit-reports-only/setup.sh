#!/usr/bin/env bash
set -e
. "$(dirname "$0")/../_fixture/vault.sh"
. "$(dirname "$0")/../_fixture/clean.sh"

# A reference document loose at the resources root, beside the kind folders.
cat > "resources/Pricing playbook.md" <<'DOC'
# Pricing playbook

How Fixture Studio quotes a job.
DOC
