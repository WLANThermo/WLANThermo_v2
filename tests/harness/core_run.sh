#!/bin/bash
# Usage: core_run.sh
# End-to-end test of wlanthermo-core (src/ of the working tree) with fake hardware.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
PY=${PYTHON:-python3}
VAR=$(mktemp -d)
trap 'rm -rf "$VAR"' EXIT
unshare -rm bash -c "mount --bind '$VAR' /var && exec '$PY' -I -W ignore '$HERE/core_inner.py' '$REPO/src' '$REPO/software/var/www/conf'"
