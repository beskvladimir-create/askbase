#!/bin/sh
# Both suites in one command.
#
# The two environments exist for different reasons: the main one has the
# benchmark dependencies, the desktop one has Qt. Running only the first
# silently skips every interface test, which is how a window that could not
# start reached a packaged build.
set -e
here=$(cd "$(dirname "$0")/.." && pwd)

echo "=== движок, бенчмарк, сайт ==="
"$here/.venv/bin/python" -m pytest "$here/tests" -q --ignore="$here/tests/test_window.py"

echo
echo "=== интерфейс (Qt) ==="
"$here/desktop/.venv/bin/python" -m pytest "$here/tests/test_window.py" -q -p no:cacheprovider
