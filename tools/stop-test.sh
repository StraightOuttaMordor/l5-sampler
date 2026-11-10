#!/bin/bash
# Stop test instances started by run-test.sh (pidfile-based).
for f in /tmp/l5s-app.pid /tmp/l5s-weston.pid; do
  [ -f "$f" ] && kill "$(cat "$f")" 2>/dev/null
  rm -f "$f"
done
echo stopped
