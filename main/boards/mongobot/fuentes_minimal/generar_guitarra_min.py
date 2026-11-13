"""MongoBot minimalista tocando guitarra (animación de inactividad).

Uso:  python generar_guitarra_min.py [carpeta_salida]

- guitarra.gif         : 320x240, bucle de 6,4 s
- guitarra.ogg / .wav  : el mismo arpegio de guitarra clásica (La m, Fa, Do, Sol)
- guitarra_preview.mp4 : animación y sonido juntos

MongoBot mira hacia arriba a la izquierda con la guitarra al frente. Las cuerdas
del brazo vibran con cada nota del arpegio, la cabeza cabecea al ritmo, la
guitarra se mece y a la mitad cierra los ojos disfrutando mientras salen notas.
"""
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mongo_minimal as mm          # noqa: E402
import audio_guitarra as g1         # noqa: E402  (sonido y tiempos de las notas)

FPS = g1.FPS
DUR = g1.DUR                         # 6,4 s
N = int(round(DUR * FPS))
COLOR = mm.COLORES["musica"]         # color de los ojos y las notas
ARO, NEGRO = mm.ARO, (0, 0, 0)
BORDE = 7.0

# guitarra: centro del cuerpo y dirección del brazo (hacia arriba a la derecha)
G_CX, G_CY = 184, 180
ANG = math.radians(-66)              # ángulo del brazo respecto a la horizontal


def ojos_abiertos(t):
    """1 abiertos mirando arriba; 0 cerrados disfrutando (de 2,6 a 4,4 s)."""
    if 2.6 <= t < 2.8:
        return 1 - mm.ease((t - 2.6) / 0.2)
    if 2.8 <= t < 4.4:
        return 0.0
    if 4.4 <= t < 4.65:
        return mm.ease((t - 4.4) / 0.25)
    return 1.0


def cuadro(t):
    L = mm.Lienzo(COLOR)
    L.solo = False          # conserva la cabeza redonda (ver CON_CUERPO en mongo_minimal)
    negra = (t / (2 * g1.CORCHEA)) % 1                 # pulso de negra
    cabeceo = 3.0 * math.sin(negra * math.pi) ** 2
    ab = ojos_abiertos(t)

    # ---- cabeza, mirando arriba a la izquierda (menos cuando cierra los ojos)
    lx, ly = -0.45 * ab - 0.15, -0.45 * ab + 0.15 * (1 - ab)
    c = mm.Cara(1.0, 1.0 + 0.015 * math.sin(negra * math.pi), dx=-16, dy=-8 + cabeceo, lx=lx, ly=ly)
    mm.cabeza(L, c)
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        if ab > 0.15:
            k = mm.parpadeo(t, 1.3) * mm.parpadeo(t, 5.6)
            mm.ojo_rect(L, c, x, y, 18, 30 * ab * k)
        else:
            mm.ojo_feliz(L, x, y + 2, w=11, alto=6)
    if ab < 0.5:
        mm.sonrisa(L, c, 10, 5)
    L.cara = None                                      # la guitarra no va sobre la esfera

    # ---- guitarra (se mece al ritmo)
    meneo = math.radians(3.0 * math.sin(2 * math.pi * t / (4 * g1.CORCHEA)))
    a = ANG + meneo
    ux, uy = math.cos(a), math.sin(a)                  # a lo largo del brazo
    vx, vy = -uy, ux                                   # perpendicular

    def P(s, w):
        """Punto a 's' px por el brazo y 'w' px hacia el costado desde el cuerpo."""
        return G_CX + s * ux + w * vx, G_CY + s * uy + w * vy

    def circulo(s, w, r, col):
        x, y = P(s, w)
        L.circulo(x, y, r, col)

    def rect(s0, s1, ancho, col):
        pts = [P(s0, -ancho / 2), P(s1, -ancho / 2), P(s1, ancho / 2), P(s0, ancho / 2)]
        L.poligono(pts, col)

    # silueta blanca (el borde) y luego relleno negro
    for col, extra in ((ARO, BORDE), (NEGRO, 0)):
        rect(30, 128, 20 + 2 * extra, col)            # brazo
        rect(122, 150 + extra, 26 + 2 * extra, col)           # clavijero
        circulo(-8, 0, 36 + extra, col)               # cuerpo de abajo
        circulo(32, 0, 27 + extra, col)               # cuerpo de arriba
        # cintura para que no se vea como dos círculos separados
        rect(-8, 32, 40 + 2 * extra, col)
    # puntas redondeadas del clavijero
    # boca de la guitarra y puente
    x, y = P(24, 0)
    L.anillo(x, y, 11, 11, 5.5, ARO)
    L.linea([P(-22, -14), P(-22, 14)], 6, ARO)
    # cuerdas: del puente al clavijero; vibran con cada nota del arpegio
    pasos = 40
    for i, w0 in enumerate((-4.5, 0.0, 4.5)):
        amp = max(g1.amplitud_cuerda(t, 2 * i + 1), g1.amplitud_cuerda(t, 2 * i + 2)) * 2.0
        fase = math.cos(2 * math.pi * (9.3 + i * 2.1) * t)
        s0, s1 = -22, 124
        pts = []
        for k in range(pasos + 1):
            u = k / pasos
            s = s0 + (s1 - s0) * u
            # sobre la boca la cuerda pasa por encima del agujero
            pts.append(P(s, w0 + amp * fase * math.sin(math.pi * u)))
        if amp > 0.2:
            for sg in (-1, 1):
                L.linea([P(s0 + (s1 - s0) * k / pasos, w0 + sg * amp * math.sin(math.pi * k / pasos))
                         for k in range(pasos + 1)], 1.0, (110, 110, 110))
        L.linea(pts, 1.5, ARO)

    # ---- notas que flotan mientras disfruta
    for k in range(3):
        u = ((t - 2.7) / 1.8 - k * 0.3)
        if 0 <= u < 1:
            x = 262 + 18 * math.sin(u * 5 + k) + k * 10
            y = 120 - 70 * u
            r = 5.5 * math.sin(math.pi * min(1, u * 1.5)) + 0.5
            col = tuple(int(v * (1 - u * 0.6)) for v in COLOR)
            L.circulo(x, y + 12, r, col)
            L.linea([(x + r * 0.8, y + 11), (x + r * 0.8, y - 6), (x + r * 0.8 + 7, y - 2)], 3.5, col)
    return L.final()


def generar(salida):
    os.makedirs(salida, exist_ok=True)
    imgs = [cuadro(i / FPS) for i in range(N)]
    pal = imgs[0].quantize(colors=32, method=Image.Quantize.MEDIANCUT)
    # que la paleta tenga el color de las notas y de los ojos felices
    q = [im.quantize(palette=imgs[60].quantize(colors=32, method=Image.Quantize.MEDIANCUT),
                     dither=Image.Dither.NONE) for im in imgs]
    gif = os.path.join(salida, "guitarra.gif")
    q[0].save(gif, save_all=True, append_images=q[1:], duration=int(1000 / FPS), loop=0, disposal=1,
              optimize=True)
    print(f"guitarra.gif  {os.path.getsize(gif) / 1024:6.1f} KB  ({N} cuadros, {DUR:.1f} s)")

    wav = os.path.join(salida, "guitarra.wav")
    g1.guardar_wav(wav, g1.generar_audio(44100), 44100)
    ogg = os.path.join(salida, "guitarra.ogg")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-ar", "24000", "-ac", "1",
                    "-c:a", "libopus", "-b:a", "32k", ogg], check=True)

    tmp = "/tmp/gmin"
    os.makedirs(tmp, exist_ok=True)
    for i, im in enumerate(imgs):
        im.save(f"{tmp}/{i:04d}.png")
    mp4 = os.path.join(salida, "guitarra_preview.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-stream_loop", "2",
                    "-i", f"{tmp}/%04d.png", "-stream_loop", "2", "-i", wav,
                    "-vf", "scale=640:480:flags=lanczos,format=yuv420p", "-c:v", "libx264", "-preset",
                    "veryfast", "-crf", "18", "-c:a", "aac", "-b:a", "160k", "-shortest", mp4], check=True)
    print(f"guitarra_preview.mp4  {os.path.getsize(mp4) / 1024:6.1f} KB")


if __name__ == "__main__":
    generar(sys.argv[1] if len(sys.argv) > 1 else "guitarra_min")
