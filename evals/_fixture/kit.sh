#!/usr/bin/env bash
# The para-os kit as this checkout has it, for the install-* cases. `kit/base` and
# `kit/INSTALL.md` are symlinks to the repo's own, and tools/eval.py's copy of evals/
# follows them into real files, so a case reads the INSTALL.md and bootstrap-prompt.md
# under review rather than a copy of them that drifts.
#
# A checkout made with symlinks off (Git for Windows' default) holds a one-line text file
# at each of those paths instead. Stop with that reason rather than build a vault from it.
set -e
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/kit"
if [ ! -f "$KIT/base/bootstrap-prompt.md" ] || [ ! -f "$KIT/INSTALL.md" ]; then
  echo "evals/_fixture/kit holds no kit: this checkout has symlinks off." >&2
  echo "Enable git's core.symlinks and check out again, or run the case under WSL2." >&2
  exit 1
fi

# INSTALL.md step 3: everything inside base/, hidden items included, into the folder
# named, leaving out the caches a test run leaves behind in a checkout.
copy_base() {
  cp -R "$KIT/base/." "$1"
  find "$1" -type d \( -name __pycache__ -o -name .pytest_cache \) -prune -exec rm -rf {} +
}

# INSTALL.md step 2, already done: the kit where the operator cloned it.
copy_kit() {
  mkdir -p "$1"
  cp "$KIT/INSTALL.md" "$1/INSTALL.md"
  mkdir -p "$1/base"
  copy_base "$1/base"
}
