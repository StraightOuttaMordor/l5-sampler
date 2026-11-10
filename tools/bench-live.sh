#!/bin/bash
# Measure output underruns in the LIVE phosh session for several buffer configs.
# Each run: launch app on wayland-0, idle 4 s, play beat 6 s, read xrun counter.
CTL=~/.local/lib/l5-sampler/tools/ctl.py
for cfg in ${CFGS:-"256 -" "512 0.03" "1024 0.04"}; do
  set -- $cfg
  export L5S_BLOCK=$1
  if [ "$2" = "-" ]; then unset L5S_LATENCY; else export L5S_LATENCY=$2; fi
  rm -rf ~/.local/share/l5-sampler-test
  bash ~/.local/lib/l5-sampler/tools/run-test.sh >/dev/null
  sleep 8
  a=$(python3 $CTL '{"cmd":"state"}' | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["xruns"],"%.1f"%d["latency_ms"])')
  sleep 4
  b=$(python3 $CTL '{"cmd":"state"}' | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["xruns"])')
  python3 $CTL '{"cmd":"call","args":{"name":"start_beat"}}' >/dev/null
  sleep ${PLAY_S:-6}
  c=$(python3 $CTL '{"cmd":"state"}' | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["xruns"])')
  set -- $a
  echo "block=$L5S_BLOCK lat=${L5S_LATENCY:-low} -> ${2}ms | boot xruns=$1 idle4s=+$((b-$1)) playing${PLAY_S:-6}s=+$((c-b))"
done
bash ~/.local/lib/l5-sampler/tools/stop-test.sh >/dev/null
