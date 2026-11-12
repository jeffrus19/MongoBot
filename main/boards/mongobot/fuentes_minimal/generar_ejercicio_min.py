"""MongoBot minimalista haciendo flexiones (animación de inactividad).

Uso:  python generar_ejercicio_min.py [carpeta_salida]

- ejercicio.gif         : 320x240, bucle de 4,8 s (cuatro flexiones)
- ejercicio_preview.mp4 : la animación para revisarla

Las manos (dos circulitos) quedan fijas en el piso. La cabeza baja hasta
quedar entre ellas, se achata y aprieta los ojos con el esfuerzo; luego empuja
y sube. La gota de sudor crece con cada flexión, en la última tiembla del
esfuerzo y la gota se resbala; arriba vuelve a formarse otra.
"""
import math
import os
import subprocess
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mongo_minimal as mm          # noqa: E402

FPS = 20
REP = 1.2                           # segundos por flexión
REPS = 4
DUR = REP * REPS
N = int(round(DUR * FPS))
COLOR = (120, 235, 120)             # verde deportivo para los ojos
R = 72                               # radio de la cabeza
ARRIBA_Y, ABAJO_Y = 98, 124          # centro de la cabeza arriba / abajo
MANOS = [(160 - 52, 180), (160 + 52, 180)]
MANO_R = 22


def profundidad(t):
    """0 arriba, 1 abajo, dentro de una flexión."""
    u = (t % REP) / REP
    if u < 0.38:
        return mm.ease(u / 0.38)            # baja
    if u < 0.52:
        return 1.0                           # aguanta abajo
    if u < 0.85:
        return 1 - mm.ease((u - 0.52) / 0.33)  # empuja y sube
    return 0.0


def cuadro(t):
    L = mm.Lienzo(COLOR)
    rep = int(t // REP)
    p = profundidad(t)
    u = (t % REP) / REP
    ultima = rep == REPS - 1
    # en la última cuesta más: tiembla abajo
    tiembla = 1.6 * math.sin(2 * math.pi * t / 0.07) if ultima and 0.3 < u < 0.65 else 0.0
    # rebote al llegar arriba
    rebote = -2.5 * math.sin(math.pi * min(1, max(0, (u - 0.85) / 0.15))) if u > 0.85 else 0.0

    cy = ARRIBA_Y + (ABAJO_Y - ARRIBA_Y) * p + rebote
    sx, sy = 1 + 0.06 * p, 1 - 0.06 * p
    c = mm.Cara(sx * R / mm.RX, sy * R / mm.RY, dx=tiembla, dy=cy - mm.CY, ly=0.25 * p)
    mm.cabeza(L, c)
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        if p > 0.55:
            mm.ojo_mayor(L, x, y, lado, w=9)          # > <  apretando
        else:
            mm.ojo_rect(L, c, x, y, 15, 26 * mm.parpadeo(t, 3.0))
    L.cara = None

    # manos fijas en el piso; se aplastan un poquito cuando la cabeza baja
    for mx, my in MANOS:
        aplasta = 1 - 0.08 * p
        r = MANO_R
        L.d.ellipse((*L.T(mx - r * (2 - aplasta), my - r * aplasta + (1 - aplasta) * r),
                     *L.T(mx + r * (2 - aplasta), my + r * aplasta + (1 - aplasta) * r)), fill=mm.ARO)
        ri = r - 7
        L.d.ellipse((*L.T(mx - ri * (2 - aplasta), my - ri * aplasta + (1 - aplasta) * r),
                     *L.T(mx + ri * (2 - aplasta), my + ri * aplasta + (1 - aplasta) * r)), fill=(0, 0, 0))

    # gota de sudor arriba a la derecha: crece con cada flexión y en la última se resbala
    gx, gy = c.cx + c.rx * 0.62, c.cy - c.ry * 0.80
    if not ultima:
        tam = 9 + 2.0 * rep + 1.0 * p
        mm.gota(L, gx, gy, tam)
        L.circulo(gx - tam * 0.35, gy - tam * 0.1, tam * 0.28, (230, 248, 255))
    else:
        v = mm.ease(u / 0.8)
        # se resbala por el borde de la cabeza y cae
        a = math.radians(-52 + 70 * v)
        x = c.cx + (c.rx + 4) * math.cos(a)
        y = c.cy + (c.ry + 4) * math.sin(a) + 40 * max(0, v - 0.7) ** 2 * 10
        if y < 238:
            mm.gota(L, x, y, 15 * (1 - 0.3 * v))
        # arriba vuelve a formarse una chiquita
        if u > 0.6:
            k = mm.ease((u - 0.6) / 0.4)
            mm.gota(L, gx, gy, 9 * k)

    # rayitas de esfuerzo al empujar
    if 0.52 < u < 0.8:
        k = math.sin(math.pi * (u - 0.52) / 0.28)
        col = tuple(int(v * k) for v in COLOR)
        for lado in (-1, 1):
            x0 = c.cx + lado * (c.rx + 12)
            for j, dy in enumerate((-14, 0, 14)):
                L.linea([(x0, c.cy + dy), (x0 + lado * 9, c.cy + dy - 3 * (j - 1))], 3.5, col)
    return L.final()


def generar(salida):
    os.makedirs(salida, exist_ok=True)
    imgs = [cuadro(i / FPS) for i in range(N)]
    pal = imgs[int(0.6 * REP * FPS)].quantize(colors=32, method=Image.Quantize.MEDIANCUT)
    q = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in imgs]
    gif = os.path.join(salida, "ejercicio.gif")
    q[0].save(gif, save_all=True, append_images=q[1:], duration=int(1000 / FPS), loop=0, disposal=1,
              optimize=True)
    print(f"ejercicio.gif  {os.path.getsize(gif) / 1024:6.1f} KB  ({N} cuadros, {DUR:.1f} s)")
    tmp = "/tmp/emin"
    os.makedirs(tmp, exist_ok=True)
    for i, im in enumerate(imgs):
        im.save(f"{tmp}/{i:04d}.png")
    mp4 = os.path.join(salida, "ejercicio_preview.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-stream_loop", "2",
                    "-i", f"{tmp}/%04d.png", "-vf", "scale=640:480:flags=lanczos,format=yuv420p",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", mp4], check=True)


if __name__ == "__main__":
    generar(sys.argv[1] if len(sys.argv) > 1 else "ejercicio_min")
