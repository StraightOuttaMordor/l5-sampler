#!/bin/bash
# Install L5 Sampler for the current user (no root needed once deps are present).
# Deps (one time, needs sudo): python3-numpy libportaudio2 python3-cffi python3-pip  + pip3 install --user sounddevice
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
LIB=~/.local/lib/l5-sampler
mkdir -p "$LIB" ~/.local/bin ~/.local/share/applications ~/.local/share/icons/hicolor/scalable/apps
if [ "$SRC" != "$LIB" ]; then cp -r "$SRC/l5sampler" "$LIB/"; fi
cat > ~/.local/bin/l5-sampler <<'EOF'
#!/bin/sh
cd ~/.local/lib/l5-sampler && exec python3 -m l5sampler "$@"
EOF
chmod +x ~/.local/bin/l5-sampler
cp "$SRC/data/org.wingman.L5Sampler.svg" ~/.local/share/icons/hicolor/scalable/apps/
sed "s|^Exec=.*|Exec=$HOME/.local/bin/l5-sampler|" "$SRC/data/org.wingman.L5Sampler.desktop" \
  > ~/.local/share/applications/org.wingman.L5Sampler.desktop
gtk-update-icon-cache -q ~/.local/share/icons/hicolor 2>/dev/null || true
update-desktop-database -q ~/.local/share/applications 2>/dev/null || true
python3 -c "import numpy, sounddevice, gi; gi.require_version('Adw','1')" && echo "deps OK"
echo "installed: open 'Sampler' from the app grid"
