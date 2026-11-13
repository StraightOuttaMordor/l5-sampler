#!/usr/bin/env python3
"""Library v2 migration (runs ON the phone, with the app closed).

1. Backs up ~/.local/share/l5-sampler to ~/l5-sampler-backup-<date>.tgz
2. Removes every sound that isn't in "My recordings" or "Starter kit" (the old machine folders + loops)
3. Imports the electronic kits from <dir> (built on the Mac by tools/build-electro.py)
4. Installs the preset beats, and puts a default kit on any pad the prune emptied

    python3 tools/migrate-electro.py ~/.cache/l5elec [--home <data dir>]
"""
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from l5sampler import importer, presets  # noqa: E402
from l5sampler.store import Store  # noqa: E402

KEEP = ('My recordings', 'Starter kit')
DEFAULT_PADS = [('TR-808', 'Kick short 05'), ('TR-808', 'Clap 02'), ('TR-808', 'Hat 02'), ('TR-808', 'Cowbell 02')]

src = os.path.expanduser(sys.argv[1])
home = sys.argv[sys.argv.index('--home') + 1] if '--home' in sys.argv else None
st = Store(home) if home else Store()

bk = os.path.expanduser('~/%s-backup-%s.tgz' % (os.path.basename(st.base), time.strftime('%Y%m%d-%H%M%S')))
subprocess.check_call(['tar', 'czf', bk, '-C', os.path.dirname(st.base), os.path.basename(st.base)])
print('backup', bk, '%.0f MB' % (os.path.getsize(bk) / 1e6))

sounds = st.load_sounds()
gone = [sid for sid, s in sounds.items() if (s.get('folder') or 'My recordings') not in KEEP]
for sid in gone:
    del sounds[sid]
    try:
        os.remove(st.wav_path(sid))
    except OSError:
        pass
st._write_lib(sounds)
print('removed %d old sounds, kept %d' % (len(gone), len(sounds)))

importer.run(src, home)
presets.install(st)

sounds = st.load_sounds()
idx = {(s.get('folder'), s['name']): sid for sid, s in sounds.items()}
state = st.load_state()
pads = (state.get('pads') or [None] * 4) + [None] * 4
pads = [p if p in sounds else None for p in pads[:4]]
for i in range(4):
    if pads[i] is None:
        pads[i] = idx.get(DEFAULT_PADS[i])
state['pads'] = pads
d = state.get('draft')
if d:
    d['rows'] = [r for r in d.get('rows', []) if r['soundId'] in sounds]
st.save_state(state)
print('pads', [sounds[p]['folder'] + '/' + sounds[p]['name'] if p else None for p in pads])
print(json.dumps({'folders': sorted(set(s.get('folder') for s in sounds.values())), 'sounds': len(sounds)}))
