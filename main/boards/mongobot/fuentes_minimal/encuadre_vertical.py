"""Calcula, para cada animación, cómo encuadrarla en la pantalla vertical (240x320).

Mira en qué parte del lienzo horizontal de siempre (320x240) hay dibujo a lo largo del
bucle y elige:
- VERT_DX: cuánto correr el recorte de 240 de ancho para que entren los adornos de los
  lados (máximo ±40 px, así la cabeza siempre queda completa);
- VERT_DY: cuánto subir o bajar la escena para que la cabeza quede SIEMPRE a la misma
  altura (CABEZA_Y en la pantalla), salvo que eso deje afuera algún adorno; lo que
  necesita otro lugar va en AJUSTES (la cúpula de conversación sale desde abajo).
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


CABEZA_Y = 150          # altura del centro de la cabeza en la pantalla vertical (de 320)


def centro_cabeza(im):
    """Altura del centro del aro blanco: la mancha más grande de color ARO, medida por su
    borde de arriba y de abajo (así no la mueve hacia dónde mira la cara de adentro)."""
    from scipy import ndimage

    a = np.asarray(im.convert("RGB")).astype(int)
    m = (np.abs(a - np.array(mm.ARO)).max(axis=2) <= 12)
    etiquetas, n = ndimage.label(m)
    if not n:
        return None
    tam = ndimage.sum(m, etiquetas, range(1, n + 1))
    ys = np.nonzero(etiquetas == (int(np.argmax(tam)) + 1))[0]
    return (ys.min() + ys.max()) / 2


def caja(im):
    a = np.asarray(im.convert("L"))
    ys, xs = np.nonzero(a > 24)
    if not len(xs):
        return None
    return xs.min(), xs.max(), ys.min(), ys.max()


def calcular(fn, dur, muestras=16):
    mm.VERTICAL = False
    imgs = [fn(dur * i / muestras) for i in range(muestras)]
    mm.VERTICAL = True
    cajas = [c for c in (caja(im) for im in imgs) if c]
    centros = [c for c in (centro_cabeza(im) for im in imgs) if c is not None]
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
    # vertical: la cabeza siempre a la misma altura (CABEZA_Y)
    extra = 2 * mm.VERT_Y                       # 80 px más de alto que el lienzo original
    cy = statistics.median(centros) if centros else mm.CY
    oy = CABEZA_Y - cy
    oy = max(-arriba, min(mm.PH - 1 - abajo, oy))   # sin dejar afuera lo que se ve casi siempre
    oy = max(0, min(extra + 60, round(oy)))
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
