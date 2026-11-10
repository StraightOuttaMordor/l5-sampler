"""Headless engine tests (no GTK, no sound card)."""
import os
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from l5sampler import engine as E  # noqa: E402
from l5sampler.kit import starter_kit  # noqa: E402

R = []


def ok(name, cond, info=''):
    R.append(bool(cond))
    print(('PASS ' if cond else 'FAIL ') + name + (('  — ' + str(info)) if info else ''))


kit = dict(starter_kit())
ok('kit: 4 sounds, non-silent', len(kit) == 4 and all(np.abs(v).max() > 0.2 for v in kit.values()),
   {k: round(float(np.abs(v).max()), 2) for k, v in kit.items()})
ok('kit: no clipping', all(np.abs(v).max() <= 1.0 for v in kit.values()))

# render_sound trims and pitches
k = kit['Kick']
b = E.render_sound(k, 0.1, 0.3, 0)
ok('trim length', abs(len(b) - 0.2 * E.SR) <= 1, len(b))
b12 = E.render_sound(k, 0.0, 0.4, 12)
ok('pitch +12 halves length', abs(len(b12) - 0.2 * E.SR) <= 2, len(b12))
ok('edges faded (no click)', abs(b[0]) < 1e-3 and abs(b[-1]) < 1e-3, (b[0], b[-1]))

# auto trim
x = np.zeros(E.SR * 2, np.float32)
x[E.SR // 2:E.SR // 2 + 4800] = 0.5 * np.sin(np.arange(4800) / 5.0)
a, z = E.auto_trim(x)
ok('auto_trim finds the hit', 0.48 < a < 0.5 and 0.6 < z < 0.7, (round(a, 3), round(z, 3)))

# sequencer timing: straight
click = np.ones(10, np.float32) * 0.5
steps = tuple([1] * 16)
e = E.Engine()
e.pattern = E.Pattern(120, 0, 16, [(click, 1.0, steps)])
e.seq_start()
for _ in range(800):
    e.render(256)
ts = [t for t, tag in e.hit_log if tag and tag.startswith('step')]
d = np.diff(ts)
sd = E.SR * 60 / 120 / 4
ok('straight 16ths exact @120', len(d) > 20 and np.all(np.abs(d - sd) <= 1), (sd, sorted(set(d.tolist()))[:4]))

# swing 100 => odd steps delayed by half a step
e = E.Engine()
e.pattern = E.Pattern(120, 100, 16, [(click, 1.0, steps)])
e.seq_start()
for _ in range(200):
    e.render(256)
ts = [t for t, tag in e.hit_log if tag and tag.startswith('step')]
d = np.diff(ts)[:8]
ok('swing 100% -> 3:1 long-short', np.all(np.abs(d[0::2] - 1.5 * sd) <= 1) and np.all(np.abs(d[1::2] - 0.5 * sd) <= 1),
   d.tolist())

# audio actually lands where scheduled (sample-accurate, independent of block size)
for bs in (64, 256, 1000):
    e = E.Engine()
    e.pattern = E.Pattern(120, 0, 16, [(click, 1.0, tuple([1] + [0] * 15))])
    e.seq_start()
    y = np.concatenate([e.render(bs) for _ in range(int(E.SR * 4.2 / bs))])
    on = np.nonzero(np.abs(y) > 0.1)[0]
    starts = on[np.insert(np.diff(on) > 1, 0, True)]
    ok('bar starts every 2.000 s (block %d)' % bs, len(starts) >= 2 and np.all(np.diff(starts) == E.SR * 2), starts.tolist())

# 3/4
e = E.Engine()
e.pattern = E.Pattern(120, 0, 12, [(click, 1.0, tuple([1] + [0] * 11))])
e.seq_start()
y = np.concatenate([e.render(256) for _ in range(int(E.SR * 3.2 / 256))])
on = np.nonzero(np.abs(y) > 0.1)[0]
starts = on[np.insert(np.diff(on) > 1, 0, True)]
ok('3/4: bar = 12 steps = 1.5 s', np.all(np.diff(starts) == int(E.SR * 1.5)), starts.tolist())

# stop kills sequencer voices
e.seq_stop()
y = e.render(4096)
ok('seq_stop silences', np.abs(y).max() == 0)

# one-shot + loop + update + stop
e = E.Engine()
e.play(click, 1.0, tag='one')
y = e.render(256)
ok('one-shot plays immediately (offset 0)', abs(y[0]) > 0.1 and np.abs(y[10:]).max() == 0)
tone = np.sin(np.arange(1000) / 7.0).astype(np.float32) * 0.5
e.play(tone, 1.0, tag='preview', loop=True)
y = np.concatenate([e.render(256) for _ in range(40)])
ok('loop keeps going past buffer end', np.abs(y[-256:]).max() > 0.3)
e.update_tag('preview', tone[:500], 0.5)
e.render(256)
e.stop_tag('preview')
ok('stop_tag silences loop', np.abs(e.render(256)).max() == 0)

# limiter: 30 stacked full-scale hits never exceed 1
e = E.Engine()
for _ in range(30):
    e.play(np.ones(500, np.float32), 1.0)
ok('soft limiter caps stacked pads', np.abs(e.render(512)).max() <= 1.0)

# offline export = exact loop length
p = E.Pattern(90, 30, 16, [(E.render_sound(kit['Kick'], 0, 0.5, 0), 1.0, tuple([1, 0, 0, 0] * 4)),
                           (E.render_sound(kit['Hat'], 0, 0.12, 0), 0.8, tuple([1, 0] * 8))])
y = E.offline_render(p, loops=4)
ok('export length = 4 loops exactly', len(y) == int(round(4 * 16 * p.step_samples())), (len(y), 4 * 16 * p.step_samples()))
ok('export non-silent, unclipped', 0.01 < float(np.sqrt(np.mean(y * y))) and np.abs(y).max() <= 1.0)
fn = os.path.join(tempfile.mkdtemp(), 't.wav')
E.write_wav(fn, y, stereo=True)
y2 = E.read_wav(fn)
ok('wav roundtrip', len(y2) == len(y) and np.abs(y2 - y).max() < 1e-3)

print('\n%d/%d passed' % (sum(R), len(R)))
sys.exit(0 if all(R) else 1)
