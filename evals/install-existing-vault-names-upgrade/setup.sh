#!/usr/bin/env bash
# A folder that is already a vault, and the kit cloned beside it: INSTALL.md step 1 has to
# stop here, before anything is copied over the vault's own CLAUDE.md.
set -e
fixture="$(cd "$(dirname "$0")/../_fixture" && pwd)"
. "$fixture/kit.sh"
copy_kit para-os
mkdir vault
(cd vault && . "$fixture/vault.sh")
