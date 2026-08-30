# resources / scripts

Persistent tools this vault needs: a script that pulls from a connected system (accounting, mail, a scraper, an export), kept because it earns its place - not the throwaway one-offs the agent writes, runs once, and discards. The script is code, so it lives here in the vault, version-controlled next to the work it serves.

Its **runtime state does not live here.** Credentials, caches, and bulk data go under `~/.paraos/`, out of the vault so secrets never sync to a cloud drive or git remote and large files never bloat it. Three buckets, named for what's safe to delete:

| Path | Holds | Safe to delete? |
|------|-------|-----------------|
| `~/.paraos/secrets/<service>.{env,json}` | credentials, one file per service | no - and never let it sync |
| `~/.paraos/cache/<service>/` | regenerable output | yes; the script rebuilds it |
| `~/.paraos/data/<name>/` | working source data | no, but not vault-worthy |

Every script resolves that root the same way, from the `PARAOS_HOME` environment variable (default `~/.paraos`), so nothing hardcodes a home path:

```python
# Python
import os
from pathlib import Path
PARAOS_HOME = Path(os.environ.get("PARAOS_HOME") or Path.home() / ".paraos")
env_path  = PARAOS_HOME / "secrets" / "SERVICE.env"
cache_dir = PARAOS_HOME / "cache" / "SERVICE"
```

```js
// Node.js
const path = require("path");
const home = process.env.USERPROFILE || process.env.HOME;
const PARAOS_HOME = process.env.PARAOS_HOME || path.join(home, ".paraos");
const authPath = path.join(PARAOS_HOME, "secrets", "SERVICE.json");
```

Write scripts in **Python by default**. Use JS only when the integration is bound to a JS/Electron source, such as a desktop app's local token.

A script installed from a para-os **integration** carries a version marker in its header - `para-os-integration: <name> <revision>` - recording the revision it was copied at. `/para-upgrade` diffs your copy against the master at that ref and reports whether it is behind, ahead, or identical; it never overwrites. **Every shipped integration keeps its vault-specific settings out of the script**, in a `<name>.config.json` beside it, with credentials in `~/.paraos/secrets/<name>.json` and the vault derived from the copy's own path - so re-syncing one is a straight copy from `integrations/<name>/`, and your config survives untouched. The two names differ by more than the folder they sit in on purpose: one is public and syncs with the vault, the other never leaves this machine, and two files sharing a name across opposite trust zones is how a credential ends up inside a synced folder. That only holds while you respect it: configure a script through its `.config.json`, never by editing the script, or the next resync silently discards the edit. Keep the marker on the line it's on: a script that loses it stops being checked. A script written for this vault alone carries no marker and is skipped.

When you add a script, add a one-line entry to the manifest at `~/.paraos/README.md` (its secret, what it writes) so "what's installed" stays answerable. On first run, `~/.paraos/` and its buckets won't exist yet - create the ones you use.
