"""Starter kit: synth Kick / Snare / Hat / Clap rendered once with numpy."""
import numpy as np

from .engine import SR


def _env(n, peak, decay_s):
    t = np.arange(n) / SR
    att = int(0.002 * SR)
    e = peak * np.exp(-t / (decay_s / 6.9))     # ~-60 dB at decay_s
    if att:
        e[:att] *= np.linspace(0, 1, att)
    return e.astype(np.float32)


def _onepole_hp(x, fc):
    a = np.exp(-2 * np.pi * fc / SR)
    y = np.empty_like(x)
    lp = 0.0
    for i in range(len(x)):          # runs once at first launch only
        lp = (1 - a) * x[i] + a * lp
        y[i] = x[i] - lp
    return y


def _bandpass(x, fc, q=1.2):
    # RBJ biquad
    w = 2 * np.pi * fc / SR
    al = np.sin(w) / (2 * q)
    b0, b1, b2 = al, 0.0, -al
    a0, a1, a2 = 1 + al, -2 * np.cos(w), 1 - al
    b0, b1, b2, a1, a2 = b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0
    y = np.zeros_like(x)
    x1 = x2 = y1 = y2 = 0.0
    for i in range(len(x)):
        xi = x[i]
        yi = b0 * xi + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, xi, y1, yi
        y[i] = yi
    return y


def kick():
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    f = 45 + (150 - 45) * np.exp(-t / 0.045)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(ph) * _env(n, 0.95, 0.45)).astype(np.float32)


def snare(rng):
    n = int(0.3 * SR)
    t = np.arange(n) / SR
    nz = _onepole_hp(rng.uniform(-1, 1, n).astype(np.float32), 1200) * _env(n, 0.8, 0.18)
    body = (2 / np.pi) * np.arcsin(np.sin(2 * np.pi * 185 * t)) * _env(n, 0.55, 0.09)
    return (nz + body).astype(np.float32)


def hat(rng):
    n = int(0.12 * SR)
    x = _onepole_hp(_onepole_hp(rng.uniform(-1, 1, n).astype(np.float32), 7000), 7000)
    x = x / (np.abs(x).max() + 1e-9)
    return (x * _env(n, 0.7, 0.05)).astype(np.float32)


def clap(rng):
    n = int(0.35 * SR)
    out = np.zeros(n, np.float32)
    for k, (d, dec) in enumerate([(0.0, 0.012), (0.012, 0.012), (0.024, 0.18)]):
        o = int(d * SR)
        m = n - o
        out[o:] += rng.uniform(-1, 1, m).astype(np.float32) * _env(m, 0.9, dec)
    return (_bandpass(out, 1400) * 2.2).astype(np.float32)


def starter_kit(seed=7):
    rng = np.random.RandomState(seed)
    return [('Kick', kick()), ('Snare', snare(rng)), ('Hat', hat(rng)), ('Clap', clap(rng))]
