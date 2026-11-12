"""Genera las 69 animaciones de MongoBot en una sola carpeta, con los mismos ajustes
de cada generador (colores de la paleta, bucle o una sola vez).

Uso: python generar_todo.py <carpeta de salida>
Con mongo_minimal.VERTICAL = True salen en 240x320 (pantalla vertical de la placa).
"""
import os
import sys

from PIL import Image

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import generar_ejercicio_min as ge  # noqa: E402
import generar_extras2_min as ex2  # noqa: E402
import generar_extras_min as ex  # noqa: E402
import generar_guitarra_min as gg  # noqa: E402
import generar_temporada_min as tp  # noqa: E402
import generar_videojuego_min as gv  # noqa: E402
import mongo_minimal as mm  # noqa: E402


def guardar(fr, ruta, colores, i_pal, una_vez=False, fps=20):
    pal = fr[min(i_pal, len(fr) - 1)].quantize(colors=colores, method=Image.Quantize.MEDIANCUT)
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in fr]
    extra = {} if una_vez else {"loop": 0}
    q[0].save(ruta, save_all=True, append_images=q[1:], duration=int(1000 / fps), disposal=1, optimize=True, **extra)


def generar(salida):
    os.makedirs(salida, exist_ok=True)
    hechas = []
    for n in mm.EMOCIONES:
        fr = [mm.cuadro(n, i / mm.FPS) for i in range(mm.n_cuadros(n))]
        guardar(fr, os.path.join(salida, f"{n}.gif"), 32, 0)
        hechas.append(n)
    for mod, colores in ((ex, 48), (ex2, 48)):
        for n, fn, dur in mod.ANIMS:
            fr = [mod.cuadro(fn, i / mod.FPS) for i in range(int(round(dur * mod.FPS)))]
            guardar(fr, os.path.join(salida, f"{n}.gif"), colores, len(fr) // 2, n in getattr(mod, "UNA_VEZ", set()))
            hechas.append(n)
    for n, fn, dur in tp.ANIMS:
        fr = [tp.cuadro(fn, i / tp.FPS) for i in range(int(round(dur * tp.FPS)))]
        guardar(fr, os.path.join(salida, f"{n}.gif"), 64, int(0.7 * tp.FPS))
        hechas.append(n)
    for n, mod, i_pal in (("guitarra", gg, 60), ("ejercicio", ge, int(0.6 * ge.REP * ge.FPS)), ("videojuego", gv, 30)):
        fr = [mod.cuadro(i / mod.FPS) for i in range(mod.N)]
        guardar(fr, os.path.join(salida, f"{n}.gif"), 32, i_pal)
        hechas.append(n)
    print(f"{len(hechas)} animaciones en {salida}")


if __name__ == "__main__":
    generar(sys.argv[1] if len(sys.argv) > 1 else "vertical")
