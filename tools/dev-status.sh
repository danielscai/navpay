#!/usr/bin/env bash
set -euo pipefail

for p in 19090 3000 3100; do
  if lsof -ti ":$p" >/dev/null 2>&1; then
    echo "$p: up"
  else
    echo "$p: down"
  fi
done

