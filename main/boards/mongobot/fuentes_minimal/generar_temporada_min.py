"""MongoBot minimalista: animaciones de temporada.

Uso:  python generar_temporada_min.py [carpeta_salida]

- anio_nuevo.gif : mira hacia arriba mientras revientan fuegos artificiales de
  estrellas (amarillo, rosado y celeste); los ojos siguen cada estallido.
- navidad.gif    : cuernos de reno y nariz roja que brilla, cae nieve.
"""
import math
import os
import random
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mongo_minimal as mm                 # noqa: E402
from mongo_minimal import ARO              # noqa: E402
from generar_extras_min import cara, parpadeos, suave  # noqa: E402

FPS = 20
OJO = (240, 240, 240)
HX, HY, HR = 160, 172, 62


def estrella5(L, x, y, r, color, giro=0.0):
    if r <= 0.3:
        return
    pts = []
    for i in range(10):
        a = giro - math.pi / 2 + math.pi * i / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((x + rr * math.cos(a), y + rr * math.sin(a)))
    L.poligono(pts, color)


# ---------------------------------------------------------------- año nuevo

AMARILLO = (255, 222, 20)
ROSADO = (240, 30, 150)
CELESTE_F = (70, 215, 255)
# (momento del estallido, x, y, color, tamaño)
FUEGOS = [(0.5, 92, 66, AMARILLO, 1.5), (1.5, 238, 72, ROSADO, 1.15), (2.6, 160, 50, CELESTE_F, 1.35),
          (3.6, 250, 54, AMARILLO, 1.05), (4.2, 72, 58, ROSADO, 1.0)]
DUR_AN = 4.8
SUBIDA = 0.45
VIDA = 1.5


def fuego(L, t, t0, x, y, col, s, semilla):
    """Un cohete que sube y revienta en rayos curvos, estrellas y puntitos que caen."""
    dt = (t - t0) % DUR_AN
    # el ciclo empieza SUBIDA antes del estallido
    dt = (t - (t0 - SUBIDA)) % DUR_AN
    if dt < SUBIDA:                                        # sube el cohete
        u = suave(dt / SUBIDA)
        x0, y0 = x + 10, 240
        cx, cy = x0 + (x - x0) * u, y0 + (y - y0) * u
        g = tuple(int(v * 0.6) for v in col)
        L.linea([(cx, cy), (cx + 2, cy + 18)], 3, g)
        L.circulo(cx, cy, 3, col)
        return
    u = (dt - SUBIDA) / VIDA
    if u >= 1:
        return
    rnd = random.Random(semilla)
    caida = 26 * u * u
    brillo = 1 - u ** 3
    c = tuple(int(v * brillo) for v in col)
    # rayos curvos que salen del centro (como en tu dibujo)
    if u < 0.6:
        k = suave(u / 0.35)
        for i in range(7):
            a = math.radians(-160 + i * 23)
            r0, r1 = 10 * s * k, 38 * s * k
            pts = []
            for j in range(9):
                rr = r0 + (r1 - r0) * j / 8
                pts.append((x + rr * math.cos(a), y + rr * math.sin(a) + 0.012 * rr * rr + caida * 0.5))
            L.linea(pts, 3.2, c)
    # estrellas y puntitos que salen volando y caen
    for i in range(12):
        a = 2 * math.pi * i / 12 + rnd.uniform(-0.25, 0.25)
        v = rnd.uniform(34, 56) * s
        d = v * (1 - (1 - min(1, u * 1.6)) ** 2)
        px, py = x + d * math.cos(a), y + d * math.sin(a) + caida
        if i % 3 == 0:
            estrella5(L, px, py, (9 if i % 2 == 0 else 7) * s * (1 - 0.3 * u), c, giro=u * 2 * (1 if i % 2 else -1))
        else:
            L.circulo(px, py, 3.2 * s * (1 - 0.5 * u), c)
    if u < 0.25:                                            # destello del centro
        estrella5(L, x, y + caida * 0.3, 14 * s * (1 - u / 0.25), (255, 255, 255))


def a_anio_nuevo(L, t):
    # el estallido más reciente decide hacia dónde mira
    activo = None
    for t0, x, y, col, s in FUEGOS:
        dt = (t - t0) % DUR_AN
        if dt < VIDA:
            if activo is None or dt < activo[0]:
                activo = (dt, x, y, col)
    if activo:
        _, x, y, col = activo
        lx, ly = max(-0.3, min(0.3, (x - HX) / 260)), max(-0.35, min(-0.15, (y - HY) / 300))
    else:
        lx, ly = 0.0, -0.25
    b = abs(math.sin(2 * math.pi * t / 1.2)) * 0.5
    L.C = OJO
    c = cara(L, r=HR, cx=HX, cy=HY - 3 * b, lx=lx, ly=ly)
    flash = 0.0
    if activo and activo[0] < 0.25:
        flash = 1 - activo[0] / 0.25
    k = 1 + 0.12 * flash                                     # los ojos se abren con cada estallido
    for lado in (-1, 1):
        x_, y_ = c.ojo(lado)
        mm.ojo_rect(L, c, x_, y_, 15 * k, 24 * k * parpadeos(t, (2.2,)), OJO)
    L.cara = None
    for i, (t0, x, y, col, s) in enumerate(FUEGOS):
        fuego(L, t, t0, x, y, col, s, semilla=11 + i)


# ---------------------------------------------------------------- navidad

CAFE = (125, 82, 52)
ROJO = (235, 35, 40)


def cuerno(L, base, lado, meneo):
    """Cuerno de reno: un tronco curvo con tres puntas, en café."""
    bx, by = base
    g = math.radians(meneo * lado)

    def P(px, py):
        px *= lado
        return bx + px * math.cos(g) - py * math.sin(g), by + px * math.sin(g) + py * math.cos(g)

    tronco = mm.bezier([P(0, 0), P(4, -30), P(-6, -52), P(8, -78)], 16)
    L.linea(tronco, 10, CAFE)
    for (sx, sy), (ex, ey) in (((2, -22), (24, -34)), ((0, -44), (-18, -60)), ((1, -52), (24, -68))):
        L.linea(mm.bezier([P(sx, sy), P((sx + ex) / 2 + 2, (sy + ey) / 2 + 4), P(ex, ey)], 8), 9, CAFE)


def a_navidad(L, t):
    dur = 4.8
    b = math.sin(2 * math.pi * t / 2.4)
    L.C = OJO
    # nieve detrás
    rnd = random.Random(5)
    for i in range(40):
        x0 = rnd.uniform(0, 320)
        vel = rnd.uniform(18, 34)
        r = rnd.uniform(1.4, 3.2)
        fase = rnd.uniform(0, dur)
        y = ((t + fase) * vel) % 270 - 15
        x = x0 + 8 * math.sin((t + fase) * 1.3 + i)
        g = int(150 + 100 * (r - 1.4) / 1.8)
        L.circulo(x, y, r, (g, g, g))
    c = cara(L, r=HR, cx=HX, cy=HY - 2 * b, lx=0.12 * math.sin(2 * math.pi * t / dur), ly=-0.05)
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        mm.ojo_rect(L, c, x, y, 15, 24 * parpadeos(t, (1.6, 3.9)), OJO)
    # nariz roja que brilla
    nx, ny = c.mx, c.my - 2
    brillo = 0.5 + 0.5 * math.sin(2 * math.pi * t / 1.2)
    for k, a in ((2.2, 0.12), (1.6, 0.22)):
        col = tuple(int(255 * a * brillo + v * (1 - a * brillo) * 0) for v in ROJO)
        col = (int(ROJO[0] * a * brillo), int(ROJO[1] * a * brillo), int(ROJO[2] * a * brillo))
        pts = [(nx + 13 * k * math.cos(q), ny + 8 * k * math.sin(q)) for q in [2 * math.pi * i / 30 for i in range(30)]]
        L.poligono(pts, col)
    pts = [(nx + 13 * math.cos(q), ny + 8 * math.sin(q)) for q in [2 * math.pi * i / 30 for i in range(30)]]
    L.poligono(pts, ROJO)
    L.poligono([(nx - 5 + 3 * math.cos(q), ny - 3 + 2 * math.sin(q)) for q in [2 * math.pi * i / 12 for i in range(12)]],
               (255, 150, 150))
    L.cara = None
    # cuernos sobre el aro, se mecen con la cabeza
    meneo = 4 * math.sin(2 * math.pi * t / 1.2)
    for lado in (-1, 1):
        a = math.radians(-90 + lado * 38)
        base = (c.cx + c.rx * 0.96 * math.cos(a), c.cy + c.ry * 0.96 * math.sin(a))
        cuerno(L, base, lado, meneo)


ANIMS = [("anio_nuevo", a_anio_nuevo, DUR_AN), ("navidad", a_navidad, 4.8)]


def cuadro(fn, t):
    L = mm.Lienzo(OJO)
    L.solo = False          # conserva la cabeza redonda (ver CON_CUERPO en mongo_minimal)
    fn(L, t)
    return L.final()


def generar(salida):
    os.makedirs(salida, exist_ok=True)
    for nombre, fn, dur in ANIMS:
        fr = [cuadro(fn, i / FPS) for i in range(int(round(dur * FPS)))]
        pal = fr[int(0.7 * FPS)].quantize(colors=64, method=Image.Quantize.MEDIANCUT)
        q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in fr]
        ruta = os.path.join(salida, f"{nombre}.gif")
        q[0].save(ruta, save_all=True, append_images=q[1:], duration=int(1000 / FPS), loop=0, disposal=1, optimize=True)
        print(f"{nombre}.gif  {os.path.getsize(ruta) / 1024:.0f} KB")
        tmp = f"/tmp/temp_{nombre}"
        shutil.rmtree(tmp, ignore_errors=True)
        os.makedirs(tmp)
        for i, f in enumerate(fr):
            f.save(f"{tmp}/{i:04d}.png")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-stream_loop", "1",
                        "-i", f"{tmp}/%04d.png", "-vf", "scale=640:480:flags=lanczos,format=yuv420p",
                        "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
                        os.path.join(salida, f"{nombre}_preview.mp4")], check=True)


if __name__ == "__main__":
    generar(sys.argv[1] if len(sys.argv) > 1 else "temporada")
