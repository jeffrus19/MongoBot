"""Sonido de guitarra clásica para la animación de tocar guitarra.

Arpegio tranquilo La menor - Fa maj7 - Do - Sol en un bucle de 6,4 s, con
síntesis de cuerda punteada (Karplus-Strong) y tono de nylon. También da los
tiempos de cada nota para que las cuerdas dibujadas vibren a la par.
"""
import math

import numpy as np

FPS = 20
CORCHEA = 0.2                    # s por nota (75 negras por minuto)
NOTAS_POR_ACORDE = 8
ACORDES = 4
DUR = CORCHEA * NOTAS_POR_ACORDE * ACORDES   # 6,4 s
N = int(round(DUR * FPS))

# Afinación estándar (MIDI) de la cuerda 1 a la 6
AFINACION = [64, 59, 55, 50, 45, 40]

# Acordes: (cuerda: traste) con cuerdas numeradas 1..6
ACORDES_DEF = [
    ("Am", {5: 0, 4: 2, 3: 2, 2: 1, 1: 0}, 5),
    ("Fmaj7", {4: 3, 3: 2, 2: 1, 1: 0}, 4),
    ("C", {5: 3, 4: 2, 3: 0, 2: 1, 1: 0}, 5),
    ("G", {6: 3, 5: 2, 4: 0, 3: 0, 2: 0, 1: 3}, 6),
]
# Patrón tranquilo de 8 corcheas: bajo, 3, 2, 3, 1, 3, 2, 3
PATRON = ["bajo", 3, 2, 3, 1, 3, 2, 3]


def notas():
    """Lista de (tiempo, cuerda 1..6, nota MIDI, fuerza)."""
    res = []
    for i, (_, forma, bajo) in enumerate(ACORDES_DEF):
        for j, p in enumerate(PATRON):
            cuerda = bajo if p == "bajo" else p
            if cuerda not in forma:
                cuerda = min(forma, key=lambda c: abs(c - cuerda))
            midi = AFINACION[cuerda - 1] + forma[cuerda]
            t = (i * NOTAS_POR_ACORDE + j) * CORCHEA
            fuerza = 0.95 if p == "bajo" else (0.7 if j % 2 else 0.6)
            res.append((t, cuerda, midi, fuerza))
    return res


NOTAS = notas()

# ---------------------------------------------------------------- sonido


def cuerda_punteada(freq, dur, sr, fuerza, rng):
    """Karplus-Strong con filtro suave: suena a cuerda de nylon."""
    n = int(dur * sr)
    p = int(round(sr / freq))
    buf = rng.uniform(-1, 1, p)
    # ataque más blando: la uña no, la yema del dedo
    for _ in range(3):
        buf = 0.5 * (buf + np.roll(buf, 1))
    out = np.empty(n)
    perdida = 0.996 if freq < 150 else 0.994
    idx = 0
    for k in range(n):
        v = buf[idx]
        out[k] = v
        nxt = buf[(idx + 1) % p]
        buf[idx] = perdida * 0.5 * (v + nxt)
        idx = (idx + 1) % p
    env = np.minimum(1, np.arange(n) / (0.004 * sr))
    return out * env * fuerza


def generar_audio(sr):
    rng = np.random.default_rng(7)
    total = int(DUR * sr)
    mezcla = np.zeros(total)
    largo = 2.4                       # cola de cada nota, pasa al siguiente bucle
    for t, cuerda, midi, fuerza in NOTAS:
        f = 440 * 2 ** ((midi - 69) / 12)
        s = cuerda_punteada(f, largo, sr, fuerza, rng)
        i0 = int(t * sr)
        # las colas dan la vuelta al bucle: así se repite sin cortes
        idx = (np.arange(len(s)) + i0) % total
        np.add.at(mezcla, idx, s)
    # cuerpo de la guitarra: un poco de graves y menos brillo
    from scipy.signal import butter, sosfilt
    sos = butter(2, 3500, "low", fs=sr, output="sos")
    mezcla = sosfilt(sos, np.concatenate([mezcla, mezcla]))[total:]
    # reverberación corta de habitación
    rev = np.zeros_like(mezcla)
    for d, g in ((0.031, 0.22), (0.047, 0.17), (0.071, 0.12), (0.113, 0.08)):
        rev += g * np.roll(mezcla, int(d * sr))
    mezcla = mezcla + rev
    mezcla = mezcla / np.max(np.abs(mezcla)) * 0.6
    return mezcla.astype(np.float32)


def guardar_wav(ruta, audio, sr):
    import wave
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def amplitud_cuerda(t, cuerda):
    """Amplitud de vibración de una cuerda en el instante t (con vuelta de bucle)."""
    a = 0.0
    for tn, c, _, fuerza in NOTAS:
        if c != cuerda:
            continue
        dt = (t - tn) % DUR
        a += fuerza * math.exp(-dt / 0.35)
    return min(1.0, a)
