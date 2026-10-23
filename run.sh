#!/usr/bin/env bash
# Run backend (:8000) and frontend (:3000). Ctrl-C stops both.
set -euo pipefail
root=$(cd "$(dirname "$0")" && pwd)

(cd "$root/backend" && .venv/bin/uvicorn app.main:app --reload) &
(cd "$root/frontend" && npm run dev) &
wait
