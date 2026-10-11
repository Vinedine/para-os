#!/usr/bin/env bash
# The example vault as it ships. The operator asks for a draft, and in passing states three
# things no file holds: an action finished, a milestone moved, and the reason it moved. The
# draft is the task; whether any of the three is written back is the case.
set -e
. "$(dirname "$0")/../_fixture/example.sh"
