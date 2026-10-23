# Absolute import on purpose: a relative one works under "python -m askbase"
# but not when a packaged build runs this file as the entry script.
from askbase.app import main

raise SystemExit(main())
