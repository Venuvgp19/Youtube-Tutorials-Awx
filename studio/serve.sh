#!/usr/bin/env bash
cd "$(dirname "$0")" && (xdg-open http://localhost:8765/index.html >/dev/null 2>&1 || open http://localhost:8765/index.html) & python3 -m http.server 8765
