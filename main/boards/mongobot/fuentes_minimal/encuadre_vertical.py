"""Calcula, para cada animación, cómo encuadrarla en la pantalla vertical (240x320).

Mira en qué parte del lienzo horizontal de siempre (320x240) hay dibujo a lo largo del
bucle y elige:
- VERT_DX: cuánto correr el recorte de 240 de ancho para que entren los adornos de los
  lados (máximo ±40 px, así la cabeza siempre queda completa);
- VERT_DY: cuánto subir o bajar la escena: lo que arranca desde el borde de abajo (la
  cúpula de conversación, la mano del saludo) queda pegado abajo; lo demás, centrado.
Guarda el resultado en encuadre_vertical.json, que lee mongo_minimal.
Uso: python encuadre_vertical.py
"""
import json
import os
import statistics
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import mongo_minimal as mm  # noqa: E402


def animaciones():
    import generar_ejercicio_min as ge
    import generar_extras2_min as ex2
    import generar_extras_min as ex
    import generar_guitarra_min as gg
    import generar_temporada_min as tp
    import generar_videojuego_min as gv
    for n in mm.EMOCIONES:
        yield n, (lambda t, n=n: mm.cuadro(n, t)), mm.DURACION.get(n, mm.DUR)
    for mod in (ex, ex2, tp):
        for n, fn, d in mod.ANIMS:
            yield n, (lambda t, fn=fn, mod=mod: mod.cuadro(fn, t)), d
    for n, mod in (("guitarra", gg), ("ejercicio", ge), ("videojuego", gv)):
        yield n, mod.cuadro, mod.DUR


# Ajustes a mano después de mirar el resultado (se aplican encima del cálculo)
AJUSTES = {
    "conversa_escucha": {"dy": 98},      # el corte de la cúpula queda en el borde de abajo (zoom 1,12)
    "conversa_habla": {"dy": 98, "dx": 0},
    "sin_conexion": {"dy": 40},          # el jueguito, más abajo
    "mensaje": {"dx": 25},               # el sobre está a la derecha
    "configurar_wifi": {"dx": 20},       # el celular está a la derecha
}


def caja(im):
    a = np.asarray(im.convert("L"))
    ys, xs = np.nonzero(a > 24)
    if not len(xs):
        return None
    return xs.min(), xs.max(), ys.min(), ys.max()


def calcular(fn, dur, muestras=16):
    mm.VERTICAL = False
    cajas = [c for c in (caja(fn(dur * i / muestras)) for i in range(muestras)) if c]
    mm.VERTICAL = True
    izq = min(c[0] for c in cajas)
    der = max(c[1] for c in cajas)
    arriba = statistics.median(c[2] for c in cajas)
    abajo = statistics.median(c[3] for c in cajas)
    # horizontal: que entre todo lo que se pueda, sin cortar la cabeza
    centro = mm.CX
    if der - izq <= mm.PW:
        centro = min(max(centro, der - mm.PW / 2 + 2), izq + mm.PW / 2 - 2)
    else:
        centro = (izq + der) / 2
    dx = max(-40, min(40, round(centro - mm.CX)))
    # vertical: pegado abajo si sale desde el borde, si no centrado
    extra = 2 * mm.VERT_Y                       # 80 px más de alto que el lienzo original
    if abajo >= mm.H - 4:
        oy = extra
    elif arriba <= 3:
        oy = 0
    else:
        oy = max(0, min(extra, round(mm.PH / 2 - (arriba + abajo) / 2)))
    return dx, oy - mm.VERT_Y


if __name__ == "__main__":
    res = {}
    for n, fn, dur in animaciones():
        dx, dy = calcular(fn, dur)
        res[n] = {"dx": dx, "dy": dy, **AJUSTES.get(n, {})}
        dx, dy = res[n]["dx"], res[n]["dy"]
        print(f"{n:<20} dx={dx:+4d}  dy={dy:+4d}")
    with open(os.path.join(AQUI, "encuadre_vertical.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, ensure_ascii=False)
