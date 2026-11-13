"""MongoBot minimalista jugando videojuegos (animación de inactividad).

Uso:  python generar_videojuego_min.py [carpeta_salida]

- videojuego.gif         : 320x240, bucle de 4,8 s
- videojuego_preview.mp4 : la animación para revisarla

MongoBot sostiene el control con las dos manos. Un monstruito de 8 bits (diseño
propio) baja a pasos por la derecha moviendo las patitas, y los ojos lo siguen.
Cuando se acerca, MongoBot frunce el ceño y juega más rápido (el control vibra);
al final lo derriba: el monstruito revienta en pixeles, MongoBot celebra y
aparece otro arriba.
"""
import math
import os
import random
import subprocess
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mongo_minimal as mm          # noqa: E402

FPS = 20
DUR = 4.8
N = int(round(DUR * FPS))
COLOR = (110, 200, 255)             # celeste "gamer" para los ojos
ROJO = (235, 40, 45)
CONTROL = (78, 64, 64)
CONTROL_LUZ = (112, 94, 92)
R = 72
HX, HY = 146, 96                    # centro de la cabeza
MANOS = [(146 - 60, 184), (146 + 60, 184)]
MANO_R = 22
PIX = 5                             # tamaño de cada pixel del monstruito

# monstruito propio de 8 bits: dos cuadros (las patitas se alternan)
SPRITE_A = [
    "..X.....X..",
    "...XXXXX...",
    ".XXXXXXXXX.",
    ".XX..X..XX.",
    ".XXXXXXXXX.",
    ".XXX...XXX.",
    ".XXXXXXXXX.",
    ".X.X.X.X.X.",
]
SPRITE_B = SPRITE_A[:-1] + ["X.X.X.X.X.X"]
SPRITE_B[0] = ".X.......X."

# recorrido del monstruito: baja a saltos por la derecha
PASOS = [(0.0, 262, 34), (0.6, 262, 34), (0.7, 254, 64), (1.3, 254, 64), (1.4, 262, 94),
         (2.0, 262, 94), (2.1, 252, 124), (2.7, 252, 124), (2.8, 258, 150), (3.0, 258, 150)]
GOLPE = 3.0                         # cuando lo derriba
NUEVO = 3.9                         # cuando aparece el siguiente


def catmull(puntos, pasos=8, cerrado=True):
    """Curva suave que pasa por todos los puntos."""
    n = len(puntos)
    out = []
    rango = range(n) if cerrado else range(n - 1)
    for i in rango:
        p0, p1 = puntos[(i - 1) % n], puntos[i]
        p2, p3 = puntos[(i + 1) % n], puntos[(i + 2) % n]
        if not cerrado:
            p0 = puntos[max(i - 1, 0)]
            p3 = puntos[min(i + 2, n - 1)]
        for k in range(pasos):
            u = k / pasos
            u2, u3 = u * u, u * u * u
            out.append(tuple(0.5 * ((2 * p1[d]) + (-p0[d] + p2[d]) * u + (2 * p0[d] - 5 * p1[d] + 4 * p2[d] - p3[d]) * u2
                                    + (-p0[d] + 3 * p1[d] - 3 * p2[d] + p3[d]) * u3) for d in (0, 1)))
    if not cerrado:
        out.append(puntos[-1])
    return out


# contorno del control (mitad derecha, de arriba al centro de abajo); se refleja
_MITAD = [(0, -22), (30, -21), (54, -16), (64, -2), (66, 16), (60, 36), (46, 44), (34, 38), (26, 24), (14, 17), (0, 16)]


def control_silueta(cx, cy, giro=0.0, solo_arriba=False):
    izq = [(-x, y) for x, y in reversed(_MITAD[1:-1])]
    contorno = _MITAD + izq
    if solo_arriba:
        base = [(-50, -17), (-30, -21), (0, -22), (30, -21), (50, -17)]
        pts = catmull(base, 6, cerrado=False)
    else:
        pts = catmull(contorno, 8)
    co, si = math.cos(giro), math.sin(giro)
    return [(cx + x * co - y * si, cy + x * si + y * co) for x, y in pts]


def pos_monstruo(t):
    if t >= NUEVO:
        return 262, 34
    for (t0, x0, y0), (t1, x1, y1) in zip(PASOS, PASOS[1:]):
        if t0 <= t < t1:
            u = mm.ease((t - t0) / (t1 - t0)) if t1 - t0 < 0.2 else 0.0
            return x0 + (x1 - x0) * u, y0 + (y1 - y0) * u
    return PASOS[-1][1], PASOS[-1][2]


def dibujar_sprite(L, filas, x, y, color, escala=1.0):
    p = PIX * escala
    w = len(filas[0]) * p
    for j, fila in enumerate(filas):
        for i, ch in enumerate(fila):
            if ch == "X":
                x0, y0 = x - w / 2 + i * p, y + j * p
                L.d.rectangle((*L.T(x0, y0), *L.T(x0 + p, y0 + p)), fill=color)


def explosion(L, x, y, u):
    """Los pixeles del monstruito salen volando y se apagan."""
    rnd = random.Random(7)
    for j, fila in enumerate(SPRITE_A):
        for i, ch in enumerate(fila):
            if ch != "X":
                continue
            px, py = x - 27.5 + i * PIX, y + j * PIX
            ang = math.atan2(py - (y + 20), px - x) + rnd.uniform(-0.4, 0.4)
            vel = rnd.uniform(40, 90)
            qx, qy = px + math.cos(ang) * vel * u, py + math.sin(ang) * vel * u + 60 * u * u
            col = ROJO if u < 0.6 else (255, 140, 60)
            s = PIX * (1 - 0.7 * u)
            L.d.rectangle((*L.T(qx, qy), *L.T(qx + s, qy + s)), fill=col)


def cuadro(t):
    L = mm.Lienzo(COLOR)
    L.solo = False          # conserva la cabeza redonda (ver CON_CUERPO en mongo_minimal)
    mx_, my_ = pos_monstruo(t)
    concentrado = mm.ease((t - 1.3) / 0.3) * (1 - mm.ease((t - GOLPE) / 0.1))
    celebra = mm.ease((t - GOLPE) / 0.1) * (1 - mm.ease((t - 3.85) / 0.2))

    # la mirada sigue al monstruito (y vuelve al centro cuando celebra)
    dx, dy = mx_ - HX, (my_ + 20) - HY
    lx = max(-0.45, min(0.45, dx / 220)) * (1 - celebra)
    ly = max(-0.45, min(0.45, dy / 160)) * (1 - celebra)
    salto = -6 * abs(math.sin(2 * math.pi * (t - GOLPE) / 0.45)) * celebra
    c = mm.Cara(R / mm.RX, R / mm.RY, dx=HX - mm.CX, dy=HY - mm.CY + salto, lx=lx, ly=ly)
    mm.cabeza(L, c)
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        if celebra > 0.5:
            mm.ojo_feliz(L, x, y, w=11, alto=6)
            continue
        mm.ojo_rect(L, c, x, y, 16, 27 * mm.parpadeo(t, 0.9))
        if concentrado > 0.02:
            # ceño: se corta la esquina de arriba del lado de adentro
            k = concentrado
            L.poligono([(x - lado * 12, y - 16), (x + lado * 12, y - 16),
                        (x + lado * 12, y - 16 + 3), (x - lado * 12, y - 16 + 3 + 14 * k)], (0, 0, 0))
    if celebra > 0.5:
        mm.sonrisa(L, c, 10, 6)
    L.cara = None

    # control
    golpe_rapido = 0.18 if concentrado > 0.5 else 0.32
    vib = 1.0 * math.sin(2 * math.pi * t / golpe_rapido) * (0.4 + 0.6 * concentrado)
    cxc, cyc = HX, 186 + salto * 0.5 + vib * 0.5
    # control sin botones: una silueta lisa con dos agarraderas
    inclina = math.radians(2.5 * math.sin(2 * math.pi * t / (golpe_rapido * 2)) * (0.3 + 0.7 * concentrado))
    pts = control_silueta(cxc, cyc, inclina)
    L.poligono(pts, CONTROL)
    # brillo suave en el borde de arriba
    arriba = [p for p in control_silueta(cxc, cyc + 3, inclina, solo_arriba=True)]
    L.linea(arriba, 3, CONTROL_LUZ)

    # manos: presionan el control por turnos
    for k, (hx, hy) in enumerate(MANOS):
        fase = (t / golpe_rapido + k * 0.5) % 1
        baja = 2.5 * math.sin(math.pi * fase) ** 2
        y0 = hy + salto * 0.5 + baja
        L.circulo(hx, y0, MANO_R, mm.ARO)
        L.circulo(hx, y0, MANO_R - 7, (0, 0, 0))

    # monstruito
    if t < GOLPE:
        cuadro_sprite = SPRITE_A if int(t / 0.25) % 2 == 0 else SPRITE_B
        dibujar_sprite(L, cuadro_sprite, mx_, my_, ROJO)
    elif t < GOLPE + 0.6:
        explosion(L, mx_, my_, (t - GOLPE) / 0.6)
    elif t >= NUEVO:
        # el nuevo aparece parpadeando
        if int((t - NUEVO) / 0.1) % 2 == 0 or t > NUEVO + 0.5:
            cuadro_sprite = SPRITE_A if int(t / 0.25) % 2 == 0 else SPRITE_B
            dibujar_sprite(L, cuadro_sprite, mx_, my_, ROJO)
    return L.final()


def generar(salida):
    os.makedirs(salida, exist_ok=True)
    imgs = [cuadro(i / FPS) for i in range(N)]
    pal = imgs[30].quantize(colors=32, method=Image.Quantize.MEDIANCUT)
    q = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in imgs]
    gif = os.path.join(salida, "videojuego.gif")
    q[0].save(gif, save_all=True, append_images=q[1:], duration=int(1000 / FPS), loop=0, disposal=1,
              optimize=True)
    print(f"videojuego.gif  {os.path.getsize(gif) / 1024:6.1f} KB  ({N} cuadros, {DUR:.1f} s)")
    tmp = "/tmp/vmin"
    os.makedirs(tmp, exist_ok=True)
    for i, im in enumerate(imgs):
        im.save(f"{tmp}/{i:04d}.png")
    mp4 = os.path.join(salida, "videojuego_preview.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-stream_loop", "2",
                    "-i", f"{tmp}/%04d.png", "-vf", "scale=640:480:flags=lanczos,format=yuv420p",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", mp4], check=True)


if __name__ == "__main__":
    generar(sys.argv[1] if len(sys.argv) > 1 else "videojuego_min")
