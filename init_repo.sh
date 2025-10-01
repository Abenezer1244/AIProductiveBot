#!/usr/bin/env bash
set -euo pipefail
if [ $# -lt 1 ]; then
  echo "Usage: $0 <repo_url>"
  exit 1
fi
REPO_URL="$1"
git init
git add .
git commit -m "init ai-productivity-bot"
git branch -M main
git remote add origin "$REPO_URL" || true
git push -u origin main
echo "Pushed to $REPO_URL"
