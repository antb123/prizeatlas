#!/usr/bin/env bash
# Build the awards website and serve it on localhost. Usage: ./start.sh [port]
set -euo pipefail

port="${1:-8000}"
base="http://localhost:${port}/"
cd "$(dirname "${BASH_SOURCE[0]}")/datasets"

uv run --with jinja2 python -m website.build --base-url "$base"
echo "website serving base=${base} root=datasets/website/dist"

# --directory rather than cd: the build swaps dist out from under a running server, and a cwd handle would go stale.
exec python3 -m http.server "$port" --directory website/dist
