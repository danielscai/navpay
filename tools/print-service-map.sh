#!/usr/bin/env bash
set -euo pipefail
cat ref/service-map.v1.json | python3 -m json.tool

