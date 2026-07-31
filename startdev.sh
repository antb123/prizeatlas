#!/usr/bin/env bash
# Build the awards website and serve it on localhost. Usage: ./startdev.sh [port]
set -euo pipefail

port="${1:-8000}"
base="http://localhost:${port}/"

if ! python3 - "$port" <<'PY'
import socket
import sys

with socket.socket() as listener:
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        listener.bind(("127.0.0.1", int(sys.argv[1])))
    except OSError:
        raise SystemExit(1)
PY
then
	echo "website server port already in use port=$port" >&2
	exit 1
fi

cd "$(dirname "${BASH_SOURCE[0]}")/datasets"

# The previous build's page count is the denominator. First run has no dist, so progress counts up without a percentage.
# `|| true` throughout: a failed command substitution takes the assignment down with it under `set -e`.
expected=0
[[ -d website/dist ]] && expected="$(find website/dist -name '*.html' | wc -l || true)"
log="$(mktemp)"
builder=""
# Without this, a script that exits early leaves the build orphaned and still writing a staging directory.
trap 'rm -f "$log"; [[ -n "$builder" ]] && kill "$builder" 2>/dev/null; true' EXIT

uv run website/build.py --base-url "$base" >"$log" 2>&1 &
builder=$!

# build.py writes into website/.dist-staging-* and swaps it into place at the end, so the staging tree is the progress meter.
while kill -0 "$builder" 2>/dev/null; do
	# `|| true`: head exits after one line, sort takes SIGPIPE, and pipefail would otherwise kill the script here.
	staging="$(find website -maxdepth 1 -name '.dist-staging-*' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2- || true)"
	written=0
	[[ -n "$staging" ]] && written="$(find "$staging" -name '*.html' | wc -l || true)"
	if (( expected > 0 )); then
		percent=$(( written * 100 / expected ))
		(( percent > 100 )) && percent=100
		printf '\rbuilding %3d%%  %5d/%-5d pages' "$percent" "$written" "$expected"
	else
		printf '\rbuilding %5d pages' "$written"
	fi
	sleep 0.5
done

printf '\r%-40s\r' ''
if ! wait "$builder"; then
	cat "$log" >&2
	echo "website build failed" >&2
	exit 1
fi
cat "$log"

# Stats the build does not report: what actually landed on disk, and how much the map has to draw.
count_children() { [[ -d "$1" ]] && find "$1" -mindepth 1 -maxdepth 1 -type d | wc -l || echo 0; }

pages="$(find website/dist -name '*.html' | wc -l)"
affiliations="$(count_children website/dist/affiliations)"
people="$(count_children website/dist/people)"
countries="$(count_children website/dist/countries)"
subjects="$(count_children website/dist/subjects)"
size="$(du -sh website/dist | cut -f1)"

# Map points are embedded as one application/json block; count them rather than trusting the database.
map_points="$(python3 - <<'PY'
import json, pathlib, re

page = pathlib.Path("website/dist/map/index.html")
match = re.search(r'<script[^>]*application/json[^>]*>(.*?)</script>', page.read_text(encoding="utf-8"), re.S) if page.exists() else None
data = json.loads(match.group(1)) if match else {}
print(len(data.get("birth", [])), len(data.get("affiliation", [])))
PY
)"

echo "website stats pages=${pages} affiliation_pages=${affiliations} person_pages=${people} country_pages=${countries} subject_pages=${subjects} map_birth=${map_points% *} map_affiliation=${map_points#* } dist=${size}"
echo "website serving base=${base} root=datasets/website/dist"

# --directory rather than cd: the build swaps dist out from under a running server, and a cwd handle would go stale.
exec python3 -m http.server "$port" --directory website/dist
