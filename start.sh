#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Build the static awards website for nginx. Usage: ./start.sh [https://example.org/awards/]
set -euo pipefail

if (( $# > 1 )); then
	echo "usage: ./start.sh [https://example.org/awards/]" >&2
	exit 2
fi

root="$(dirname "${BASH_SOURCE[0]}")"
base_url="${1:-}"

if [[ -z "$base_url" && -f "$root/datasets/.env" ]]; then
	base_url="$(awk -F= '$1 == "BASE_URL" { sub(/^[^=]*=/, ""); print; exit }' "$root/datasets/.env")"
fi

if [[ -z "$base_url" ]]; then
	echo "start.sh needs BASE_URL in datasets/.env or one URL argument" >&2
	exit 2
fi

cd "$root/datasets"

# The previous build's page count is the denominator. First run has no dist, so progress counts up without a percentage.
# `|| true` throughout: a failed command substitution takes the assignment down with it under `set -e`.
expected=0
[[ -d website/dist ]] && expected="$(find website/dist -name '*.html' | wc -l || true)"
log="$(mktemp)"
builder=""
# Without this, a script that exits early leaves the build orphaned and still writing a staging directory.
trap 'rm -f "$log"; if [[ -n "$builder" ]]; then kill "$builder" 2>/dev/null || true; fi' EXIT

uv run website/build.py --base-url "$base_url" >"$log" 2>&1 &
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
