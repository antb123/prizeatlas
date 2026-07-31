#!/usr/bin/env bash
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
exec uv run website/build.py --base-url "$base_url"
