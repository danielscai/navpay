#!/usr/bin/env bash
set -euo pipefail

for p in 19090 3000 3100; do
  ids=$(lsof -ti ":$p" || true)
  if [ -n "${ids}" ]; then
    kill ${ids} || true
  fi
done

