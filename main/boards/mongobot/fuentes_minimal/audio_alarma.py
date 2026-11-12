"""Timbre de despertador mecánico para las alarmas de MongoBot (alarma.wav).

Martillo golpeando dos campanas a ~22 golpes por segundo durante 2 s y 0,8 s de
silencio; dura 2,8 s y se repite en bucle mientras la alarma suena.
44,1 kHz, mono, 16 bits.
"""
import wave

import numpy as np

SR = 44100
rng = np.random.default_rng(3)


def campana(dur=0.25):
    t = np.arange(int(dur * SR)) / SR
    parciales = [(2140, 1.0, 0.09), (2710, 0.6, 0.07), (3390, 0.45, 0.05), (5180, 0.2, 0.03)]
    s = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t / d) for f, a, d in parciales)
    clic = rng.uniform(-1, 1, t.size) * np.exp(-t / 0.002) * 0.4
    return s + clic


def timbre(ring=2.0, pausa=0.8, golpes_por_s=22):
    buf = np.zeros(int((ring + pausa) * SR) + SR)
    paso = 1 / golpes_por_s
    k = 0
    while k * paso < ring:
        a = int(k * paso * SR)
        g = campana() * (0.85 if k % 2 else 1.0) * (1 + 0.04 * rng.standard_normal())
        b = min(buf.size, a + g.size)
        buf[a:b] += g[: b - a]
        k += 1
    buf = buf[: int((ring + pausa) * SR)]
    return buf / np.abs(buf).max() * 0.6


if __name__ == "__main__":
    b = timbre()
    with wave.open("alarma.wav", "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((b * 32767).astype("<i2").tobytes())
    print(f"alarma.wav {b.size / SR:.1f} s")
