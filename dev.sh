#!/usr/bin/env bash
# dev.sh — start the webapp stack locally without Docker
# Usage: bash dev.sh
# Runs:
#   - FastAPI API on http://localhost:8080  (SQLite, no Postgres needed)
#   - Vue dev server on http://localhost:3000

set -e

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
API_DIR="$REPO_ROOT/webapp/api"
FRONTEND_DIR="$REPO_ROOT/webapp/frontend"

# ── 1. Init SQLite database ──────────────────────────────────────────────────
echo "→ Initialising SQLite database..."
cd "$API_DIR"
PYTHONPATH="$REPO_ROOT" DATABASE_URL="sqlite:///./fair_dev.db" python init_db.py

# ── 2. Start FastAPI backend in background ───────────────────────────────────
echo "→ Starting FastAPI on http://localhost:8080 ..."
PYTHONPATH="$REPO_ROOT" DATABASE_URL="sqlite:///./fair_dev.db" \
  uvicorn main:app --port 8080 --reload --app-dir "$API_DIR" &
API_PID=$!

# ── 3. Install frontend deps if needed ───────────────────────────────────────
cd "$FRONTEND_DIR"
if [ ! -d node_modules ]; then
  echo "→ Installing frontend npm packages..."
  npm install
fi

# ── 4. Start Vue dev server ──────────────────────────────────────────────────
echo "→ Starting Vue dev server on http://localhost:3000 ..."
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅  Stack is up:"
echo "   Frontend → http://localhost:3000"
echo "   API      → http://localhost:8080/api"
echo "   API docs → http://localhost:8080/docs"
echo ""
echo "   Press Ctrl+C to stop everything."

# Trap Ctrl+C and kill both processes
trap "echo 'Stopping...'; kill $API_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
