"""Import a folder of WAV files into the library.

    python3 -m l5sampler.importer <dir> [--home <data dir>]

<dir> may contain a manifest.json:
    [{"file": "rel/path.wav", "folder": "Roland TR-8", "name": "Kick 01", "kind": "hit"|"loop", "bpm": 125}, ...]
Without a manifest, each top-level sub-folder becomes a library folder, and files whose
name contains "(<n> BPM)" are treated as loops at that tempo.

Files must be 16-bit PCM WAV (any rate, mono or stereo). They are stored as 48 kHz mono.
"""
import json
import os
import re
import sys
import time

import numpy as np

from . import engine as E
from .store import Store, new_id

BPM_RE = re.compile(r'\(?\s*(\d{2,3})\s*bpm\s*\)?', re.I)
PEAKS_N = 56


def scan(root):
    man = os.path.join(root, 'manifest.json')
    if os.path.exists(man):
        with open(man) as f:
            items = json.load(f)
        for it in items:
            it['path'] = os.path.join(root, it['file'])
        return items
    items = []
    for top in sorted(os.listdir(root)):
        tp = os.path.join(root, top)
        if not os.path.isdir(tp):
            continue
        for dp, _, fs in os.walk(tp):
            for fn in sorted(fs):
                if not fn.lower().endswith('.wav'):
                    continue
                stem = fn[:-4]
                m = BPM_RE.search(stem)
                bpm = int(m.group(1)) if m else None
                name = BPM_RE.sub('', stem).strip(' -_') or stem
                items.append({'path': os.path.join(dp, fn), 'folder': top, 'name': name,
                              'kind': 'loop' if bpm else 'hit', 'bpm': bpm})
    return items


def run(root, home=None):
    st = Store(home) if home else Store()
    sounds = st.load_sounds()
    have = set((s.get('folder'), s['name']) for s in sounds.values())
    items = scan(root)
    t0, added, skipped = time.time(), 0, 0
    now = time.time()
    for i, it in enumerate(items):
        key = (it['folder'], it['name'])
        if key in have:
            skipped += 1
            continue
        try:
            data = E.read_wav(it['path'])
        except Exception as e:
            print('skip %s: %s' % (it['path'], e))
            skipped += 1
            continue
        if len(data) < 32:
            skipped += 1
            continue
        sid = new_id()
        pk = E.peaks(data, PEAKS_N)
        top = float(pk.max()) or 1.0
        s = {'id': sid, 'name': it['name'], 'folder': it['folder'], 'kind': it.get('kind', 'hit'),
             'bpm': it.get('bpm'), 'peaks': [round(float(v) / top, 3) for v in pk],
             'data': data, 'start': 0.0, 'end': len(data) / E.SR, 'vol': 1.0, 'pitch': 0,
             'created': now - i * 1e-3}
        E.write_wav(st.wav_path(sid), data)
        s['data'] = None
        sounds[sid] = s
        have.add(key)
        added += 1
        if added % 100 == 0:
            print('%d/%d' % (i + 1, len(items)))
            sys.stdout.flush()
    st._write_lib(sounds)
    print('imported %d, skipped %d, library now %d sounds (%.1f s)' % (added, skipped, len(sounds), time.time() - t0))


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    home = None
    if '--home' in argv:
        i = argv.index('--home')
        home = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    run(argv[0], home)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
