#!/bin/bash
# Fresh test profile -> seed (first launch) -> library v2 migration -> full device test. Runs ON the phone.
set -e
export L5S_HOME=$HOME/.local/share/l5-sampler-test
cd ~/.local/lib/l5-sampler
rm -rf "$L5S_HOME"
HEADLESS=1 bash tools/run-test.sh >/dev/null
sleep 7
bash tools/stop-test.sh >/dev/null 2>&1 || true
for f in /tmp/l5s-app.pid /tmp/l5s-weston.pid; do [ -f $f ] && kill $(cat $f) 2>/dev/null; rm -f $f; done
sleep 1
python3 tools/migrate-electro.py ~/.cache/l5elec --home "$L5S_HOME" | grep -v '^[0-9]*/[0-9]*$'
rm -f ~/l5-sampler-test-backup-*.tgz
HEADLESS=1 bash tools/run-test.sh
sleep 9
python3 tests/test_device.py || true
for f in /tmp/l5s-app.pid /tmp/l5s-weston.pid; do [ -f $f ] && kill $(cat $f) 2>/dev/null; rm -f $f; done
grep -c Traceback /tmp/l5s.log || true
