#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Stop the website dev server started by startdev.sh. Usage: ./stopdev.sh [port]
set -euo pipefail

port="${1:-8000}"
pattern="http\.server ${port} --directory website/dist"

pids="$(pgrep -f "$pattern" || true)"
if [[ -z "$pids" ]]; then
	echo "website stop port=${port} status=not-running"
	exit 0
fi

kill $pids
echo "website stop port=${port} status=stopped pids=${pids//$'\n'/,}"
