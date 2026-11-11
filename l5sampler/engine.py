"""L5 Sampler audio engine.

Pure numpy, no GTK. One mixer renders blocks for the sound card callback and
for offline WAV export, so what you export is exactly what you hear.

Timing is sample-accurate: the sequencer schedules hits inside render() in
sample units, never with UI timers.
"""
import collections
import math
import wave

import numpy as np

SR = 48000
MAX_VOICES = 48


# ---------------------------------------------------------------- sound prep
def render_sound(data, start, end, pitch):
    """Trimmed + pitched copy of a sound, with 3 ms edge fades (no clicks)."""
    a = int(max(0.0, start) * SR)
    b = max(a + 2, int(end * SR))
    seg = data[a:b]
    rate = 2.0 ** (pitch / 12.0)
    if abs(rate - 1.0) > 1e-6:
        n = max(2, int(len(seg) / rate))
        x = np.arange(n, dtype=np.float64) * rate
        seg = np.interp(x, np.arange(len(seg)), seg).astype(np.float32)
    else:
        seg = seg.astype(np.float32, copy=True)
    f = min(int(0.003 * SR), len(seg) // 4)
    if f > 0:
        ramp = np.linspace(0.0, 1.0, f, dtype=np.float32)
        seg[:f] *= ramp
        seg[-f:] *= ramp[::-1]
    return seg


def render_loop(data, start, end, steps_len, bpm):
    """Varispeed a trimmed loop to exactly steps_len 16ths at bpm (tape-style: pitch follows tempo)."""
    a = int(max(0.0, start) * SR)
    b = max(a + 2, int(end * SR))
    seg = data[a:b]
    n = max(2, int(round(steps_len * SR * 60.0 / bpm / 4.0)))
    x = np.linspace(0, len(seg) - 1, n)
    out = np.interp(x, np.arange(len(seg)), seg).astype(np.float32)
    f = min(int(0.002 * SR), n // 8)
    if f > 0:            # tiny edge fades so the wrap point never clicks
        ramp = np.linspace(0.0, 1.0, f, dtype=np.float32)
        out[:f] *= ramp
        out[-f:] *= ramp[::-1]
    return out


def loop_bars(seconds, bpm):
    return max(1, int(round(seconds * bpm / 240.0)))


def auto_trim(data):
    """Find start/end (seconds) of the audible part of a recording."""
    if len(data) == 0:
        return 0.0, 0.0
    ab = np.abs(data)
    pk = float(ab.max())
    th = max(0.015, pk * 0.08)
    idx = np.nonzero(ab >= th)[0]
    if len(idx) == 0:
        return 0.0, len(data) / SR
    a = max(0.0, idx[0] / SR - 0.01)
    b = min(len(data) / SR, idx[-1] / SR + 0.08)
    return a, b


def peaks(data, n):
    """n max-abs buckets for drawing a waveform."""
    if n <= 0 or len(data) == 0:
        return np.zeros(max(n, 0), np.float32)
    edges = np.linspace(0, len(data), n + 1).astype(int)
    out = np.zeros(n, np.float32)
    ab = np.abs(data)
    for i in range(n):
        a, b = edges[i], max(edges[i] + 1, edges[i + 1])
        out[i] = ab[a:b].max() if a < len(ab) else 0.0
    return out


# ---------------------------------------------------------------- wav io
def write_wav(path, mono, sr=SR, stereo=False):
    x = np.clip(mono, -1.0, 1.0)
    pcm = (x * 32767.0).astype('<i2')
    if stereo:
        pcm = np.repeat(pcm, 2)
    with wave.open(path, 'wb') as w:
        w.setnchannels(2 if stereo else 1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def read_wav(path):
    with wave.open(path, 'rb') as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if sw != 2:
        raise ValueError('only 16-bit wav supported')
    x = np.frombuffer(raw, dtype='<i2').astype(np.float32) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    if sr != SR:
        m = int(len(x) * SR / sr)
        x = np.interp(np.arange(m) * (sr / SR), np.arange(len(x)), x).astype(np.float32)
    return x


# ---------------------------------------------------------------- engine
class Voice(object):
    __slots__ = ('buf', 'pos', 'gain', 'loop', 'delay', 'tag')

    def __init__(self, buf, gain, delay=0, loop=False, tag=None):
        self.buf, self.gain, self.delay, self.loop, self.tag = buf, gain, delay, loop, tag
        self.pos = 0


class Pattern(object):
    """Immutable snapshot the UI hands to the audio thread (swap = atomic)."""
    __slots__ = ('bpm', 'swing', 'steps', 'rows', 'loops')

    def __init__(self, bpm=90, swing=0.0, steps=16, rows=(), loops=()):
        # rows:  tuple of (buf, gain, steps_tuple)          -> step-triggered hits
        # loops: tuple of (key, buf, gain, len_in_16ths)    -> play continuously, phase-locked to the grid
        self.bpm, self.swing, self.steps, self.rows, self.loops = bpm, swing, steps, tuple(rows), tuple(loops)

    def step_samples(self):
        return SR * 60.0 / self.bpm / 4.0

    def swing_delay(self):
        # 0..100 %. 100 % delays every 2nd 16th by half a step => 3:1 long-short.
        return (self.swing / 100.0) * 0.5 * self.step_samples()


class Engine(object):
    def __init__(self):
        self.t = 0                       # samples rendered so far
        self.voices = []
        self.cmds = collections.deque()  # UI -> audio thread (deque append/popleft are thread-safe)
        self.pattern = Pattern()
        self.seq_on = False
        self.step = 0
        self.next_grid = 0.0
        self.steps_total = 0             # 16ths scheduled since seq_start (loop phase reference)
        self._loops_applied = None
        self.step_log = collections.deque(maxlen=256)   # (sample, step) for the UI playhead
        self.hit_log = collections.deque(maxlen=2048)   # (sample, tag) for tests

    # ---- UI-thread API (all non-blocking)
    def play(self, buf, gain=1.0, tag=None, loop=False, choke=False):
        """choke=True: a new voice with this tag cuts the previous one (previews, loop pads)."""
        self.cmds.append(('play', buf, gain, tag, loop, choke))

    def stop_tag(self, tag):
        self.cmds.append(('stop', tag))

    def update_tag(self, tag, buf, gain):
        self.cmds.append(('update', tag, buf, gain))

    def seq_start(self):
        self.cmds.append(('seq_start',))

    def seq_stop(self):
        self.cmds.append(('seq_stop',))

    def tag_progress(self, tag):
        """(pos, length, loop) of the newest voice with tag, or None."""
        for v in reversed(list(self.voices)):
            if v.tag == tag:
                return v.pos, len(v.buf), v.loop
        return None

    # ---- audio thread
    def _apply(self, c):
        k = c[0]
        if k == 'play':
            _, buf, gain, tag, loop, choke = c
            if tag is not None and (choke or tag.startswith('preview')):
                self.voices = [v for v in self.voices if v.tag != tag]
            self.voices.append(Voice(buf, gain, 0, loop, tag))
            self.hit_log.append((self.t, tag))
            self._cap()
        elif k == 'stop':
            self.voices = [v for v in self.voices if v.tag != c[1]]
        elif k == 'update':
            _, tag, buf, gain = c
            for v in self.voices:
                if v.tag == tag:
                    v.buf, v.gain = buf, gain
                    if v.pos >= len(buf):
                        v.pos = v.pos % len(buf) if v.loop else len(buf)
        elif k == 'seq_start':
            self.seq_on, self.step, self.next_grid = True, 0, float(self.t)
            self.steps_total = 0
            self._loops_applied = None
            self.voices = [v for v in self.voices if not (v.tag == 'seq' or (v.tag or '').startswith('loop:'))]
            self.step_log.clear()
        elif k == 'seq_stop':
            self.seq_on = False
            self.voices = [v for v in self.voices if not (v.tag == 'seq' or (v.tag or '').startswith('loop:'))]

    def _cap(self):
        """Voice limit; never steals the backing loops."""
        if len(self.voices) > MAX_VOICES:
            loops = [v for v in self.voices if (v.tag or '').startswith('loop:')]
            rest = [v for v in self.voices if not (v.tag or '').startswith('loop:')]
            self.voices = loops + rest[-(MAX_VOICES - len(loops)):]

    def loop_phase(self, p):
        """Current grid position in 16ths (float) at sample self.t."""
        return self.steps_total - (self.next_grid - self.t) / p.step_samples()

    def _sync_loops(self, p):
        """(Re)align backing-loop voices to the grid after start / pattern swap (BPM change, loop added)."""
        sp = self.loop_phase(p)
        have = {v.tag: v for v in self.voices if (v.tag or '').startswith('loop:')}
        keep = [v for v in self.voices if not (v.tag or '').startswith('loop:')]
        for key, buf, gain, lsteps in p.loops:
            tag = 'loop:' + key
            L = len(buf)
            if L == 0:
                continue
            pos = int((sp % lsteps) / lsteps * L) % L
            v = have.get(tag)
            if v is None:
                v = Voice(buf, gain, 0, True, tag)
                v.pos = pos
            else:
                if v.buf is not buf:
                    v.buf, v.pos = buf, pos
                v.gain = gain
            keep.append(v)
        self.voices = keep

    def render(self, frames):
        while self.cmds:
            self._apply(self.cmds.popleft())
        out = np.zeros(frames, np.float32)
        end = self.t + frames
        if self.seq_on:
            p = self.pattern
            if self._loops_applied is not p:
                self._sync_loops(p)
                self._loops_applied = p
            sd = p.step_samples()
            n = p.steps
            while True:
                if self.step >= n:
                    self.step = 0
                ev = self.next_grid + (p.swing_delay() if self.step % 2 else 0.0)
                if ev >= end:
                    break
                off = max(0, int(round(ev - self.t)))
                for buf, gain, steps in p.rows:
                    if self.step < len(steps) and steps[self.step]:
                        self.voices.append(Voice(buf, gain, off, False, 'seq'))
                self.step_log.append((self.t + off, self.step))
                self.hit_log.append((self.t + off, 'step%d' % self.step))
                self.next_grid += sd
                self.steps_total += 1
                self.step = (self.step + 1) % n
            self._cap()
        keep = []
        for v in self.voices:
            d = v.delay
            if d >= frames:
                v.delay -= frames
                keep.append(v)
                continue
            L = len(v.buf)
            if L == 0:
                continue
            if v.loop:
                i = d
                while i < frames:
                    take = min(frames - i, L - v.pos)
                    out[i:i + take] += v.buf[v.pos:v.pos + take] * v.gain
                    v.pos += take
                    i += take
                    if v.pos >= L:
                        v.pos = 0
                v.delay = 0
                keep.append(v)
            else:
                take = min(frames - d, L - v.pos)
                if take > 0:
                    out[d:d + take] += v.buf[v.pos:v.pos + take] * v.gain
                    v.pos += take
                v.delay = 0
                if v.pos < L:
                    keep.append(v)
        self.voices = keep
        self.t = end
        # soft limiter: transparent at normal levels, no hard clipping when pads stack
        np.tanh(out, out=out)
        return out


def offline_render(pattern, loops=4):
    """Render `loops` passes of the pattern; cut to exact loop length (seamless)."""
    e = Engine()
    e.pattern = pattern
    e.seq_start()
    total = int(round(loops * pattern.steps * pattern.step_samples()))
    tail = SR  # let the last hits ring into the buffer, then cut
    chunks, done = [], 0
    while done < total + tail:
        chunks.append(e.render(4096))
        done += 4096
    y = np.concatenate(chunks)[:total]
    f = min(int(0.01 * SR), len(y))
    if f:
        y[-f:] *= np.linspace(1.0, 0.0, f, dtype=np.float32)
    return y


# ---------------------------------------------------------------- device io
class AudioIO(object):
    """Sound card output + mic recorder (sounddevice / PortAudio)."""

    def __init__(self, engine, device=None, blocksize=256, latency='low'):
        import sounddevice as sd
        self.sd = sd
        self.engine = engine
        self.xruns = 0
        self.callbacks = 0
        self.device = device
        self.out = sd.OutputStream(samplerate=SR, channels=2, dtype='float32', blocksize=blocksize,
                                   latency=latency, device=device, callback=self._cb)
        self.out.start()
        self.rec_stream = None
        self.rec_chunks = []
        self.rec_level = collections.deque(maxlen=400)

    def _cb(self, outdata, frames, time_info, status):
        if status:
            self.xruns += 1
        self.callbacks += 1
        y = self.engine.render(frames)
        outdata[:, 0] = y
        outdata[:, 1] = y

    @property
    def latency_s(self):
        try:
            return float(self.out.latency)
        except Exception:
            return 0.02

    # ---- mic
    def rec_start(self):
        self.rec_chunks = []
        self.rec_level.clear()

        def cb(indata, frames, t, status):
            x = indata[:, 0].copy()
            self.rec_chunks.append(x)
            self.rec_level.append(float(np.abs(x).max()) if len(x) else 0.0)

        self.rec_stream = self.sd.InputStream(samplerate=SR, channels=1, dtype='float32', blocksize=1024,
                                              device=self.device, callback=cb)
        self.rec_stream.start()

    def rec_stop(self):
        if self.rec_stream is None:
            return np.zeros(0, np.float32)
        try:
            self.rec_stream.stop()
            self.rec_stream.close()
        finally:
            self.rec_stream = None
        if not self.rec_chunks:
            return np.zeros(0, np.float32)
        x = np.concatenate(self.rec_chunks).astype(np.float32)
        return x[int(0.04 * SR):]   # skip the click the L5 codec makes as the mic opens

    def close(self):
        try:
            self.out.stop()
            self.out.close()
        except Exception:
            pass
