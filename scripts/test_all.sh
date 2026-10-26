#!/bin/sh
# Every suite in one command.
#
# The two environments exist for different reasons: the main one has the
# benchmark dependencies, the desktop one has Qt. Running only the first
# silently skips every interface test, which is how a window that could not
# start reached a packaged build.
#
# The third line is here for the same reason as the second. desktop/tests held
# the terminal command and the journal, and nothing ran it: thirteen passing
# tests that the one command anybody runs never touched. A suite outside the
# runner is a suite that is not kept.
set -e
here=$(cd "$(dirname "$0")/.." && pwd)

echo "=== движок, бенчмарк, сайт ==="
"$here/.venv/bin/python" -m pytest "$here/tests" -q --ignore="$here/tests/test_window.py"

echo
echo "=== интерфейс (Qt) ==="
"$here/desktop/.venv/bin/python" -m pytest "$here/tests/test_window.py" -q -p no:cacheprovider

echo
echo "=== команда в терминале и журнал ==="
cd "$here/desktop" && "$here/desktop/.venv/bin/python" -m pytest tests -q -p no:cacheprovider
