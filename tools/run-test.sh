#!/bin/bash
# Launch the app for testing (runs ON the phone).
#   HEADLESS=1 -> private headless weston compositor at 360x720 (screen can be off/locked)
#   default    -> the phone's live phosh session
# Previous test instances are stopped via their pidfiles, never by name-matching:
# a name pattern also matches the ssh command line that launched this script and kills the session.
export XDG_RUNTIME_DIR=/run/user/1000
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus
export L5S_CTL=/tmp/l5s.sock
export L5S_HOME=${L5S_HOME:-$HOME/.local/share/l5-sampler-test}
for f in /tmp/l5s-app.pid /tmp/l5s-weston.pid; do
  [ -f "$f" ] && kill "$(cat "$f")" 2>/dev/null
  rm -f "$f"
done
sleep 0.5
if [ -n "$HEADLESS" ]; then
  nohup weston --backend=headless-backend.so --width=360 --height=720 --socket=wayland-l5test --idle-time=0 > /tmp/weston.log 2>&1 &
  echo $! > /tmp/l5s-weston.pid
  sleep 2
  export WAYLAND_DISPLAY=wayland-l5test
else
  export WAYLAND_DISPLAY=wayland-0
fi
cd ~/.local/lib/l5-sampler
nohup python3 -m l5sampler > /tmp/l5s.log 2>&1 &
echo $! > /tmp/l5s-app.pid
echo started $! on $WAYLAND_DISPLAY
