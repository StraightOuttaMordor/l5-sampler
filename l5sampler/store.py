"""On-device storage. Everything lives under ~/.local/share/l5-sampler/.

sounds/<id>.wav   full recording / sample (48 kHz, 16-bit mono); trim/vol/pitch are metadata
library.json      {id: {name, folder, kind, bpm, peaks, start, end, vol, pitch, created}}
beats.json        [beat, ...]
state.json        {draft, dirty, pads}

Audio is loaded lazily (load_data) so a library of thousands of samples
costs only its metadata at startup.
"""
import json
import os
import time
import uuid

from .engine import read_wav, write_wav

BASE = os.path.expanduser(os.environ.get('L5S_HOME', '~/.local/share/l5-sampler'))
META_KEYS = ('name', 'folder', 'kind', 'bpm', 'peaks', 'start', 'end', 'vol', 'pitch', 'created')
DEFAULTS = {'folder': 'My recordings', 'kind': 'hit', 'bpm': None, 'peaks': None}


def _atomic_write(path, text):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _read_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (IOError, OSError, ValueError):
        return default


def new_id():
    return uuid.uuid4().hex[:12]


class Store(object):
    def __init__(self, base=BASE):
        self.base = base
        self.sdir = os.path.join(base, 'sounds')
        os.makedirs(self.sdir, exist_ok=True)
        self.lib_path = os.path.join(base, 'library.json')
        self.beats_path = os.path.join(base, 'beats.json')
        self.state_path = os.path.join(base, 'state.json')

    @property
    def fresh(self):
        return not os.path.exists(self.lib_path)

    def wav_path(self, sid):
        return os.path.join(self.sdir, sid + '.wav')

    # ---- sounds (metadata only; audio via load_data)
    def load_sounds(self):
        meta = _read_json(self.lib_path, {})
        sounds = {}
        for sid, m in meta.items():
            if not os.path.exists(self.wav_path(sid)):
                continue
            s = dict(DEFAULTS)
            s.update(m)
            s['id'] = sid
            s['data'] = None
            s['buf'] = None
            sounds[sid] = s
        return sounds

    def load_data(self, sid):
        return read_wav(self.wav_path(sid))

    def _write_lib(self, sounds):
        meta = {}
        for sid, s in sounds.items():
            meta[sid] = {k: s.get(k, DEFAULTS.get(k)) for k in META_KEYS}
        _atomic_write(self.lib_path, json.dumps(meta, separators=(',', ':')))

    def save_sound(self, sounds, s, write_audio):
        if write_audio:
            write_wav(self.wav_path(s['id']), s['data'])
        self._write_lib(sounds)

    def delete_sound(self, sounds, sid):
        try:
            os.remove(self.wav_path(sid))
        except OSError:
            pass
        self._write_lib(sounds)

    # ---- beats
    def load_beats(self):
        return _read_json(self.beats_path, [])

    def save_beats(self, beats):
        _atomic_write(self.beats_path, json.dumps(beats, indent=1))

    # ---- state
    def load_state(self):
        return _read_json(self.state_path, {})

    def save_state(self, st):
        _atomic_write(self.state_path, json.dumps(st))

    def now(self):
        return time.time()
