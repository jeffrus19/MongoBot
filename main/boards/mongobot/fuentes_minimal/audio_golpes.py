"""Sonidos de golpe para las animaciones en que MongoBot toca la pantalla.

- llamando.wav: tres toquecitos en el vidrio (0,35 / 0,65 / 0,95 s), dura lo mismo que la
  animación (3,0 s) para repetirse junto con ella.
- saludo.wav: la palmada del "choque los cinco" contra la pantalla (a los 1,0 s); suena una vez.
44,1 kHz, mono, 16 bits.
"""
import wave

import numpy as np

SR = 44100
rng = np.random.default_rng(7)


def toque(fuerza=1.0):
    """Nudillo contra un vidrio grueso: golpe grave corto + clic + un poco de 'tin'."""
    t = np.arange(int(0.18 * SR)) / SR
    grave = np.sin(2 * np.pi * (170 - 60 * t / 0.18) * t) * np.exp(-t / 0.028)
    clic = rng.uniform(-1, 1, t.size) * np.exp(-t / 0.0025)
    clic = np.convolve(clic, np.ones(4) / 4, mode="same")
    vidrio = (np.sin(2 * np.pi * 2350 * t) + 0.5 * np.sin(2 * np.pi * 3720 * t)) * np.exp(-t / 0.035)
    return fuerza * (0.75 * grave + 0.35 * clic + 0.10 * vidrio)


def palmada():
    """Mano abierta contra la pantalla: ráfaga de ruido filtrado + golpe grave."""
    t = np.arange(int(0.25 * SR)) / SR
    ruido = rng.uniform(-1, 1, t.size)
    ruido = np.convolve(ruido, np.ones(3) / 3, mode="same") * np.exp(-t / 0.018)
    grave = np.sin(2 * np.pi * (130 - 40 * t / 0.25) * t) * np.exp(-t / 0.05)
    vidrio = np.sin(2 * np.pi * 1900 * t) * np.exp(-t / 0.06)
    return 0.7 * ruido + 0.8 * grave + 0.08 * vidrio


def pista(dur, eventos, pico=0.55):
    buf = np.zeros(int(dur * SR))
    for t0, sonido in eventos:
        a = int(t0 * SR)
        b = min(buf.size, a + sonido.size)
        buf[a:b] += sonido[: b - a]
    return buf / np.abs(buf).max() * pico


def guardar(nombre, buf):
    datos = (buf * 32767).astype("<i2").tobytes()
    with wave.open(nombre, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(datos)
    print(f"{nombre}: {buf.size / SR:.2f} s")


if __name__ == "__main__":
    guardar("llamando.wav", pista(3.0, [(0.35, toque(1.0)), (0.65, toque(0.9)), (0.95, toque(1.0))]))
    guardar("saludo.wav", pista(3.0, [(1.0, palmada())], pico=0.6))
