"""MongoBot minimalista: líneas de color sobre negro, una animación por emoción.

Uso:  python mongo_minimal.py [carpeta_salida]

La cara va pintada sobre una esfera que gira (como el bot de Grok): al mirar
a un lado, los rasgos se achatan, se inclinan y el ojo cercano se ve mayor.

Genera:
- <emocion>.gif           : 320x240, bucle de 2,4 s, una por emoción
- mongo_minimal_todas.mp4 : las 24 emociones (y 2 estados extra) en una cuadrícula

El aro de la cabeza siempre es blanco; cada emoción pinta de su color lo que
va adentro de la cara (ojos, boca, cejas) y los signos de alrededor. El sonrojo va en rosa y las lágrimas en
celeste, sea cual sea el color de la emoción. Todo se dibuja con líneas,
píldoras, arcos y figuras simples, así que se puede programar igual en la
placa con LVGL, sin GIF.
"""
import math
import os
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

W, H, SS = 320, 240, 4
FPS = 20
DUR = 2.4
N = int(DUR * FPS)
TRAZO = 9.0
CX, CY, RX, RY = 160, 124, 62, 58

ARO = (245, 245, 245)     # el aro de la cabeza siempre es blanco
ROSA = (255, 120, 160)
CELESTE = (120, 200, 255)

COLORES = {
    "neutral": (235, 235, 235),
    "happy": (255, 214, 80),
    "laughing": (255, 165, 50),
    "funny": (170, 240, 80),
    "sad": (110, 150, 255),
    "crying": (90, 125, 255),
    "angry": (255, 65, 55),
    "loving": (255, 95, 165),
    "embarrassed": (255, 140, 120),
    "surprised": (80, 225, 255),
    "shocked": (255, 245, 110),
    "thinking": (170, 140, 255),
    "winking": (110, 240, 190),
    "cool": (60, 225, 215),
    "relaxed": (140, 230, 150),
    "delicious": (255, 145, 85),
    "kissy": (255, 125, 200),
    "confident": (255, 195, 50),
    "sleepy": (145, 145, 225),
    "silly": (235, 95, 255),
    "confused": (225, 175, 90),
    "excited": (255, 105, 75),
    "smug": (200, 235, 90),
    "terrified": (185, 215, 200),
    "escuchando": (235, 235, 235),
    "musica": (255, 200, 120),
    "mirando": (235, 235, 235),
    "conversa_escucha": (0, 0, 0),
    "conversa_habla": (0, 0, 0),
}


def ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def pulso(t, periodo, fase=0.0):
    return 0.5 - 0.5 * math.cos(2 * math.pi * (t / periodo + fase))


def parpadeo(t, t0=1.7):
    u = (t - t0) / 0.18
    return 1 - 0.92 * math.sin(math.pi * u) if 0 <= u < 1 else 1.0


# ---------------------------------------------------------------- lienzo
# Animaciones sin boca: la expresión va solo en los ojos (y cejas, rubor, etc.)
SIN_BOCA = {
    "happy", "laughing", "funny", "sad", "crying", "angry", "loving", "embarrassed", "surprised",
    "shocked", "thinking", "winking", "cool", "relaxed", "delicious", "kissy", "confident", "sleepy",
    "silly", "excited", "smug", "furioso", "rodar_ojos", "esceptico", "picaro", "orgulloso", "aburrido",
    "decepcionado", "presumido", "musica", "pomodoro_descanso",
}
ACTUAL = ""        # animación que se está dibujando (la ponen los generadores)


def con_boca():
    return ACTUAL not in SIN_BOCA


# Tamaño estándar de la cabeza: radio 80 (el de las animaciones extra). Las emociones
# de este archivo se dibujan con radio 62 y se agrandan con un zoom al centro de la
# cabeza; las que necesitan espacio para interactuar (la cúpula de conversación) no.
R_ESTANDAR = 80
SIN_ZOOM = {"conversa_escucha", "conversa_habla"}


# Pantalla vertical de la placa (Freenove 2.8", 240x320). Las animaciones se siguen
# dibujando con las coordenadas de siempre (320x240, cabeza en CX, CY) sobre un lienzo
# de 320x320: se bajan VERT_Y px y al final se recorta la franja central de 240 de ancho.
# Cada animación puede correr el recorte (VERT_DX) o bajar más (VERT_DY) si lo necesita.
VERTICAL = True
PW, PH = 240, 320
VERT_Y = 40
# En vertical el ancho es 240: toda la escena (cabeza y adornos) se achica un poco, igual
# para todas, para que los adornos de los lados no toquen el borde. La cúpula no.
VERT_ESCALA = 0.85
VERT_SIN_ESCALA = {"conversa_escucha", "conversa_habla"}
VERT_ESCALA_POR = {"escuchando": 0.8}      # las ondas de los dos lados necesitan un poco más
VERT_DY: dict[str, float] = {}
VERT_DX: dict[str, float] = {}
try:                                   # lo calcula encuadre_vertical.py
    import json as _json

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "encuadre_vertical.json"),
              encoding="utf-8") as _f:
        for _n, _e in _json.load(_f).items():
            VERT_DX[_n], VERT_DY[_n] = _e["dx"], _e["dy"]
except (OSError, ValueError):
    pass


class Lienzo:
    def __init__(self, color):
        self.oy = (VERT_Y + VERT_DY.get(ACTUAL, 0)) if VERTICAL else 0
        self.ox = VERT_DX.get(ACTUAL, 0) if VERTICAL else 0
        self.escala = 1.0 if (not VERTICAL or ACTUAL in VERT_SIN_ESCALA) else VERT_ESCALA_POR.get(ACTUAL, VERT_ESCALA)
        self.img = Image.new("RGB", (W * SS, (H + 2 * VERT_Y if VERTICAL else H) * SS), (0, 0, 0))
        self.d = ImageDraw.Draw(self.img)
        self.C = color
        self.rot = 0.0
        self.piv = (CX, CY)
        self.cara = None   # cuando hay una Cara, lo de adentro se pinta sobre la esfera
        self.zoom = 1.0    # agranda todo alrededor de zoom_c al terminar (final)
        self.zoom_c = (CX, CY)

    def T(self, x, y):
        c = self.cara
        if c is not None:
            # (x, y) está dibujado como si la cara mirara de frente; se lleva a la
            # esfera, se gira (yaw, pitch) y se proyecta con un poco de perspectiva
            dx, dy = (x - c.cx0) / c.rx, (y - c.cy0) / c.ry
            r2 = dx * dx + dy * dy
            if r2 < 1:
                z = math.sqrt(1 - r2)
                cy_, sy_ = math.cos(c.yaw), math.sin(c.yaw)
                cp, sp = math.cos(c.pitch), math.sin(c.pitch)
                x1 = dx * cy_ + z * sy_
                z1 = -dx * sy_ + z * cy_
                y2 = dy * cp + z1 * sp
                z2 = -dy * sp + z1 * cp
                k = 0.88 + 0.12 * max(z2, 0)
                x, y = c.cx + c.rx * x1 * k, c.cy + c.ry * y2 * k
            else:
                x, y = x - c.cx0 + c.cx, y - c.cy0 + c.cy
        if self.rot:
            px, py = self.piv
            c, s = math.cos(self.rot), math.sin(self.rot)
            x, y = px + (x - px) * c - (y - py) * s, py + (x - px) * s + (y - py) * c
        return x * SS, (y + self.oy) * SS

    def linea(self, pts, ancho=TRAZO, color=None):
        color = color or self.C
        q = [self.T(x, y) for x, y in pts]
        if len(q) > 1:
            self.d.line(q, fill=color, width=max(1, int(ancho * SS)), joint="curve")
        r = ancho * SS / 2
        for x, y in (q[0], q[-1]):
            self.d.ellipse((x - r, y - r, x + r, y + r), fill=color)

    def poligono(self, pts, color=None):
        self.d.polygon([self.T(x, y) for x, y in pts], fill=color or self.C)

    def circulo(self, cx, cy, r, color=None):
        x, y = self.T(cx, cy)
        self.d.ellipse((x - r * SS, y - r * SS, x + r * SS, y + r * SS), fill=color or self.C)

    def anillo(self, cx, cy, rx, ry, ancho=TRAZO * 0.8, color=None):
        pts = [(cx + rx * math.cos(a), cy + ry * math.sin(a)) for a in [2 * math.pi * i / 48 for i in range(49)]]
        self.linea(pts, ancho, color)

    def pildora(self, cx, cy, w, h, color=None):
        w, h = max(w, 2), max(h, 2)
        if h >= w:
            self.linea([(cx, cy - (h - w) / 2), (cx, cy + (h - w) / 2)], w, color)
        else:
            self.linea([(cx - (w - h) / 2, cy), (cx + (w - h) / 2, cy)], h, color)

    def final(self):
        img = self.img
        cw, ch = img.size
        if self.zoom != 1.0:
            # agranda alrededor de zoom_c dejando ese punto quieto (no lo lleva al centro)
            w, h = cw / self.zoom, ch / self.zoom
            zx, zy = self.zoom_c[0] * SS, (self.zoom_c[1] + self.oy) * SS
            x0, y0 = zx - zx / self.zoom, zy - zy / self.zoom
            img = img.crop((int(x0), int(y0), int(x0 + w), int(y0 + h))).resize((cw, ch))
        if not VERTICAL:
            return img.resize((W, H), Image.LANCZOS)
        if self.escala != 1.0:
            # achica alrededor del centro de la cabeza (CX, CY + oy), que queda quieto
            zx, zy = CX * SS, (CY + self.oy) * SS
            x0, y0 = zx - zx / self.escala, zy - zy / self.escala
            img = img.crop((int(x0), int(y0), int(x0 + cw / self.escala), int(y0 + ch / self.escala))).resize((cw, ch))
        x0 = (CX + self.ox - PW / 2) * SS
        img = img.crop((int(x0), 0, int(x0 + PW * SS), ch))
        return img.resize((PW, PH), Image.LANCZOS)


def bezier(P, n=20):
    pts = []
    for i in range(n + 1):
        u = i / n
        if len(P) == 3:
            x = (1 - u) ** 2 * P[0][0] + 2 * (1 - u) * u * P[1][0] + u * u * P[2][0]
            y = (1 - u) ** 2 * P[0][1] + 2 * (1 - u) * u * P[1][1] + u * u * P[2][1]
        else:
            x = (1 - u) ** 3 * P[0][0] + 3 * (1 - u) ** 2 * u * P[1][0] + 3 * (1 - u) * u * u * P[2][0] + u ** 3 * P[3][0]
            y = (1 - u) ** 3 * P[0][1] + 3 * (1 - u) ** 2 * u * P[1][1] + 3 * (1 - u) * u * u * P[2][1] + u ** 3 * P[3][1]
        pts.append((x, y))
    return pts


# ---------------------------------------------------------------- piezas
class Cara:
    """Cabeza redonda: un aro blanco grueso con la cara negra adentro.

    (lx, ly) es hacia dónde mira, de -1 a 1. La cara está pintada sobre una
    esfera que gira: al mirar a un lado, el círculo negro y los ojos se corren,
    se achatan y se inclinan siguiendo la curva, y el ojo cercano se ve más
    grande que el lejano. Las coordenadas de los rasgos se escriben como si
    mirara de frente; el lienzo se encarga de girarlas.
    """

    def __init__(self, sx=1.0, sy=1.0, dx=0.0, dy=0.0, lx=0.0, ly=0.0):
        self.cx, self.cy = CX + dx, CY + dy          # dónde está la cabeza
        self.cx0, self.cy0 = self.cx, self.cy        # centro de la cara "de frente"
        self.rx, self.ry = RX * sx, RY * sy
        self.lx, self.ly = lx, ly
        self.yaw = math.radians(38 * lx)
        self.pitch = math.radians(32 * ly)
        self.irx, self.iry = self.rx * 0.74, self.ry * 0.74
        self.fx, self.fy = self.cx, self.cy
        self.sep = self.rx * 0.29
        self.ey = self.fy - self.ry * 0.13
        self.my = self.fy + self.ry * 0.30
        self.mx = self.fx

    def ojo(self, lado):
        return self.fx + lado * self.sep, self.ey


def cabeza(L, c):
    # el aro: la silueta de la esfera, siempre un círculo
    px, py = L.T(c.cx, c.cy)
    L.d.ellipse((px - c.rx * SS, py - c.ry * SS, px + c.rx * SS, py + c.ry * SS), fill=ARO)
    # la cara negra va pintada sobre la esfera y gira con ella
    L.cara = c
    pts = [(c.cx + c.irx * math.cos(a), c.cy + c.iry * math.sin(a)) for a in [2 * math.pi * i / 72 for i in range(72)]]
    L.poligono(pts, (0, 0, 0))


def ojo_rect(L, c, x, y, w, h, color=None):
    """Ojo de rectángulo redondeado; se angosta y se inclina un poco al mirar de lado."""
    h = max(3.0, h)
    rad = min(max(4.5, w * 0.24), w / 2, h / 2)
    giro = 0
    pts = []
    esquinas = [(w / 2 - rad, -h / 2 + rad, -90), (w / 2 - rad, h / 2 - rad, 0),
                (-w / 2 + rad, h / 2 - rad, 90), (-w / 2 + rad, -h / 2 + rad, 180)]
    for ex, ey, a0 in esquinas:
        for k in range(7):
            a = math.radians(a0 + 15 * k)
            px, py = ex + rad * math.cos(a), ey + rad * math.sin(a)
            pts.append((x + px * math.cos(giro) - py * math.sin(giro), y + px * math.sin(giro) + py * math.cos(giro)))
    L.poligono(pts, color)


def respirar(t, amp=0.012):
    r = math.sin(2 * math.pi * t / DUR)
    return 1 - amp * r, 1 + amp * r


def ojos_pildora(L, c, t, h=30, w=18, mx=0, my=0, blink=True, solo=None):
    k = parpadeo(t) if blink else 1.0
    for lado in (-1, 1):
        if solo and lado != solo:
            continue
        x, y = c.ojo(lado)
        ojo_rect(L, c, x + mx, y + my, w, h * k)


def ojo_feliz(L, x, y, w=12, alto=7, ancho=TRAZO * 0.8):
    L.linea([(x - w, y + 4), (x, y - alto), (x + w, y + 4)], ancho)


def ojo_triste_cerrado(L, x, y, w=15):
    L.linea(bezier([(x - w, y - 2), (x, y + 8), (x + w, y - 2)]), TRAZO * 0.8)


def ojo_mayor(L, x, y, lado, w=10):
    """> <  (apretados de risa)."""
    L.linea([(x + lado * w, y - 8), (x - lado * w * 0.7, y), (x + lado * w, y + 8)], TRAZO * 0.75)


def sonrisa(L, c, w=14, alto=9, dx=0, ancho=TRAZO * 0.75):
    if not con_boca():
        return
    L.linea(bezier([(c.mx - w + dx, c.my), (c.mx + dx, c.my + alto * 2), (c.mx + w + dx, c.my)]), ancho)


def boca_abierta(L, c, w=16, alto=18, dy=0):
    """Boca abierta en forma de D, rellena con un color más oscuro."""
    if not con_boca():
        return
    x0, x1, y = c.mx - w, c.mx + w, c.my - 4 + dy
    pts = [(x0, y)] + bezier([(x0, y), (c.mx, y + alto * 1.6), (x1, y)])[1:] + [(x0, y)]
    oscuro = tuple(int(v * 0.35) for v in L.C)
    L.poligono(pts, oscuro)
    L.linea(pts, TRAZO * 0.7)


def boca_o(L, c, r=9, dy=0):
    if not con_boca():
        return
    L.anillo(c.mx, c.my + dy, r * 0.85, r, TRAZO * 0.7)


def boca_ondulada(L, c, w=16, amp=3, dy=0, fase=0.0):
    if not con_boca():
        return
    pts = [(c.mx - w + 2 * w * i / 16, c.my + dy + amp * math.sin(i / 16 * 4 * math.pi + fase)) for i in range(17)]
    L.linea(pts, TRAZO * 0.65)


def boca_plana(L, c, w=12, dx=0, dy=0, inclina=0):
    if not con_boca():
        return
    L.linea([(c.mx - w + dx, c.my + dy - inclina), (c.mx + w + dx, c.my + dy + inclina)], TRAZO * 0.7)


def sonrisa_lado(L, c, dx=6):
    if not con_boca():
        return
    L.linea(bezier([(c.mx - 6 + dx, c.my + 2), (c.mx + 8 + dx, c.my + 6), (c.mx + 18 + dx, c.my - 4)]), TRAZO * 0.7)


def lengua(L, c, dx=0, largo=14, dy=0):
    if not con_boca():
        return
    x, y = c.mx + dx, c.my + 4 + dy
    pts = [(x - 7, y)] + [(x + 7 * math.cos(a), y + largo - 7 + 7 * math.sin(a)) for a in
                          [math.pi * (1 - i / 12) for i in range(13)]][::-1] + [(x + 7, y)]
    L.poligono(pts, ROSA)


def ceja(L, x, y, lado, inclina, largo=16, ancho=TRAZO * 0.7):
    """inclina > 0: el extremo de adentro baja (enojo); < 0: sube (tristeza)."""
    x_in, x_out = x - lado * largo * 0.8, x + lado * largo
    L.linea([(x_out, y), (x_in, y + inclina)], ancho)


def rubor(L, c, intensidad=1.0, dy=0):
    if intensidad <= 0.02:
        return
    col = tuple(int(v * min(1, intensidad)) for v in ROSA)
    for lado in (-1, 1):
        x0, y0 = c.mx + lado * (c.sep + 9), c.ey + 21 + dy
        for k in range(3):
            xx = x0 + (k - 1) * 6
            L.linea([(xx - 2.2, y0 + 3.5), (xx + 2.2, y0 - 3.5)], 3, col)


def gota(L, x, y, r, color=CELESTE):
    L.circulo(x, y, r, color)
    L.poligono([(x - r * 0.8, y - r * 0.55), (x + r * 0.8, y - r * 0.55), (x, y - r * 2.2)], color)


def corazon(L, x, y, s, color=None):
    pts = []
    for i in range(41):
        a = 2 * math.pi * i / 40
        hx = 16 * math.sin(a) ** 3
        hy = -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a))
        pts.append((x + hx * s / 16, y + hy * s / 16))
    L.poligono(pts, color)


def estrella4(L, x, y, r, color=None, giro=0.0):
    pts = []
    for i in range(8):
        a = giro + math.pi / 4 * i - math.pi / 2
        rr = r if i % 2 == 0 else r * 0.3
        pts.append((x + rr * math.cos(a), y + rr * math.sin(a)))
    L.poligono(pts, color)


def espiral(L, x, y, r, giro):
    pts = [(x + r * (u / 2.6) * math.cos(giro + u * 2 * math.pi), y + r * (u / 2.6) * math.sin(giro + u * 2 * math.pi))
           for u in [2.6 * i / 60 for i in range(61)]]
    L.linea(pts, 4.5)


def signo_pregunta(L, x, y, s=1.0, color=None):
    pts = bezier([(x - 7 * s, y - 8 * s), (x - 6 * s, y - 20 * s), (x + 12 * s, y - 18 * s), (x + 8 * s, y - 6 * s)])
    pts += bezier([(x + 8 * s, y - 6 * s), (x + 5 * s, y), (x, y - 1 * s), (x, y + 6 * s)])[1:]
    L.linea(pts, 4.5 * s, color)
    L.circulo(x, y + 14 * s, 2.8 * s, color)


def signo_admiracion(L, x, y, s=1.0, color=None):
    L.linea([(x, y - 14 * s), (x, y + 4 * s)], 5 * s, color)
    L.circulo(x, y + 13 * s, 3 * s, color)


def zeta(L, x, y, s, color=None):
    L.linea([(x - 6 * s, y - 6 * s), (x + 6 * s, y - 6 * s), (x - 6 * s, y + 6 * s), (x + 6 * s, y + 6 * s)], 3.5 * s,
            color)


def vena(L, x, y, k):
    for ang in (0, 90, 180, 270):
        a = math.radians(ang + 45)
        co, si = math.cos(a), math.sin(a)
        L.linea([(x + 5 * k * co, y + 5 * k * si), (x + 13 * k * co + 4 * k * si, y + 13 * k * si - 4 * k * co)],
                4.5 * k)


def gota_sudor(L, c, lado=1, dy=0):
    gota(L, c.cx + lado * (c.rx - 6), c.cy - c.ry + 22 + dy, 5, CELESTE)


def lentes(L, c, dy=0):
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        y += 2 + dy
        m = c.sep - 3
        L.d.rounded_rectangle((*L.T(x - m, y - 12), *L.T(x + m, y + 12)), radius=8 * SS, fill=L.C)
        L.linea([(x - 7, y + 6), (x + 2, y - 6)], 4, (0, 0, 0))


def parpado(L, c, x, y, w=18, h=28, cierre=0.5, mx=0, my=0):
    """Ojo con el párpado de arriba caído (mirada confiada o de lado):
    la parte de arriba del ojo queda cortada en recto."""
    alto = h * (1 - cierre * 0.55)
    ojo_rect(L, c, x + mx, y + my + (h - alto) / 2, w, alto)
    yp = y + my - h / 2 + (h - alto) - 1
    L.linea([(x + mx - w * 0.55, yp), (x + mx + w * 0.55, yp)], TRAZO * 0.6)


# ---------------------------------------------------------------- emociones

def e_neutral(L, t):
    sx, sy = respirar(t)
    mira = 0.7 * (ease((t - 0.4) / 0.3) - ease((t - 1.1) / 0.3)) - 0.7 * (ease((t - 1.1) / 0.3) - ease((t - 1.6) / 0.3))
    c = Cara(sx, sy, lx=mira)
    cabeza(L, c)
    ojos_pildora(L, c, t)


def e_happy(L, t):
    b = abs(math.sin(2 * math.pi * t / 0.8))
    c = Cara(1 + 0.025 - 0.04 * b, 1 - 0.03 + 0.05 * b, dy=-7 * b)
    cabeza(L, c)
    for lado in (-1, 1):
        ojo_feliz(L, *c.ojo(lado))
    sonrisa(L, c)
    rubor(L, c, 0.7)


def e_laughing(L, t):
    sacude = 2.5 * math.sin(2 * math.pi * t / 0.24)
    b = abs(math.sin(2 * math.pi * t / 0.48))
    c = Cara(1.03, 0.97 + 0.03 * b, dx=sacude * 0.4, dy=-3 * b)
    cabeza(L, c)
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        ojo_mayor(L, x, y, lado)
        # lagrimitas de risa que saltan hacia afuera
        g = abs(math.sin(2 * math.pi * t / 0.48))
        gota(L, x + lado * (17 + 4 * g), y + 4 - 4 * g, 4)
    boca_abierta(L, c, 13, 11)


def e_funny(L, t):
    sx, sy = respirar(t, 0.02)
    L.rot = math.radians(6 * math.sin(2 * math.pi * t / 1.2))
    c = Cara(sx, sy)
    cabeza(L, c)
    ojos_pildora(L, c, t, solo=-1, blink=False)
    ojo_feliz(L, *c.ojo(1), w=11, alto=6)
    sonrisa(L, c, 14, 6)
    lengua(L, c, dx=5, largo=12 + 3 * pulso(t, 0.6), dy=6)


def e_sad(L, t):
    sx, sy = respirar(t, 0.008)
    c = Cara(sx * 1.01, sy * 0.98, dy=4, ly=0.45)
    cabeza(L, c)
    ojos_pildora(L, c, t, h=22)
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        ceja(L, x, y - 22, lado, -9)
    if con_boca():
        L.linea(bezier([(c.mx - 12, c.my + 8), (c.mx, c.my - 2), (c.mx + 12, c.my + 8)]), TRAZO * 0.7)
    # una lágrima que se forma y cae por la mejilla
    u = (t / DUR) % 1
    x, y = c.ojo(1)
    if u < 0.5:
        gota(L, x + 2, y + 16, 4.5 * ease(u / 0.5))
    else:
        v = (u - 0.5) / 0.5
        gota(L, x + 2, y + 16 + 60 * v * v, 4.5)


def e_crying(L, t):
    sacude = 1.5 * math.sin(2 * math.pi * t / 0.3)
    c = Cara(1.0, 0.98, dx=sacude, dy=3, ly=0.2)
    cabeza(L, c)
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        ojo_triste_cerrado(L, x, y, w=11)
        ceja(L, x, y - 20, lado, -8)
        # chorro de lágrimas que corre y gotea
        x0, y0 = x + lado * 2, y + 10
        largo = 34 + 4 * math.sin(2 * math.pi * t / 0.6 + lado)
        L.linea([(x0, y0), (x0 + lado * 3, y0 + largo)], 7, CELESTE)
        for k in range(2):
            u = ((t / 0.8) + k * 0.5 + (0.25 if lado > 0 else 0)) % 1
            gota(L, x0 + lado * 3, y0 + largo + 6 + 40 * u * u, 4)
    boca_ondulada(L, c, 15, 3, dy=4, fase=t * 12)


def e_angry(L, t):
    tiembla = 1.5 * math.sin(2 * math.pi * t / 0.09)
    c = Cara(1.05, 0.95, dx=tiembla)
    cabeza(L, c)
    ojos_pildora(L, c, t, h=18, my=3)
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        ceja(L, x, y - 22, lado, 13)
    boca_plana(L, c, 13, dy=4)
    k = 1 + 0.15 * math.sin(2 * math.pi * t / 0.3)
    vena(L, c.cx + c.rx - 6, c.cy - c.ry + 8, k)


def e_loving(L, t):
    sx, sy = respirar(t, 0.015)
    c = Cara(sx, sy)
    cabeza(L, c)
    beat = t % 0.8 / 0.8
    k = 1 + 0.18 * (math.exp(-((beat - 0.1) / 0.06) ** 2) + 0.6 * math.exp(-((beat - 0.3) / 0.06) ** 2))
    for lado in (-1, 1):
        corazon(L, *c.ojo(lado), 15 * k, ROSA)
    sonrisa(L, c, 10, 6)
    rubor(L, c, 1.0)


def e_embarrassed(L, t):
    sx, sy = respirar(t, 0.01)
    c = Cara(sx, sy, dy=2, lx=-0.65 + 0.1 * math.sin(2 * math.pi * t / 1.2), ly=0.45)
    cabeza(L, c)
    ojos_pildora(L, c, t, h=24)
    boca_ondulada(L, c, 10, 2, dy=4, fase=t * 4)
    rubor(L, c, 1.0)
    gota_sudor(L, c, 1, dy=4 * pulso(t, 1.2))


def e_surprised(L, t):
    # sube de golpe, se acomoda y al final vuelve abajo para cerrar el bucle
    sube = ease(t / 0.25) - 0.3 * ease((t - 0.25) / 0.3) - 0.7 * ease((t - 1.9) / 0.5)
    c = Cara(0.96, 1.06, dy=-6 * sube)
    cabeza(L, c)
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        L.anillo(x, y, 12, 14)
        L.circulo(x, y, 4.5)
        ceja(L, x, y - 26, lado, -3, 12)
    boca_o(L, c, 8, dy=4)
    signo_admiracion(L, c.cx - c.rx - 18, c.cy - c.ry + 10, 1.0 + 0.15 * pulso(t, 0.6))


def e_shocked(L, t):
    salto = math.exp(-((t % 1.2) / 0.12) ** 2)
    tiembla = 1.2 * math.sin(2 * math.pi * t / 0.1)
    c = Cara(0.94 + 0.04 * (1 - salto), 1.08, dx=tiembla, dy=-10 * salto)
    cabeza(L, c)
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        L.anillo(x, y, 16, 18)
        L.circulo(x, y, 3.5)
    boca_abierta(L, c, 10, 13, dy=2)
    for k, dx in enumerate((-7, 7)):
        signo_admiracion(L, c.cx + c.rx + 20 + dx, c.cy - c.ry + 6, 0.9)


def e_thinking(L, t):
    sx, sy = respirar(t, 0.01)
    c = Cara(sx, sy, lx=0.6, ly=-0.6)
    cabeza(L, c)
    ojos_pildora(L, c, t, h=26)
    x, y = c.ojo(1)
    ceja(L, x, y - 24, 1, -5, 12)
    boca_plana(L, c, 7, dx=-4, dy=-2, inclina=-2)
    # puntitos de pensamiento y el signo
    for k in range(3):
        u = ((t / 1.2) - k * 0.15) % 1
        a = 1.0 if u < 0.7 else 0
        L.circulo(c.cx + c.rx + 6 + k * 9, c.cy - c.ry + 16 - k * 9, (2.5 + k) * a)
    signo_pregunta(L, c.cx + c.rx + 40, c.cy - c.ry - 10 + 3 * math.sin(2 * math.pi * t / 1.2), 1.0)


def e_winking(L, t):
    sx, sy = respirar(t, 0.015)
    c = Cara(sx, sy)
    cabeza(L, c)
    ojos_pildora(L, c, t, solo=-1, blink=False)
    ojo_feliz(L, *c.ojo(1), w=11, alto=6)
    sonrisa(L, c, 13, 7, dx=3)
    rubor(L, c, 0.6)
    u = (t % 1.2) / 1.2
    br = math.exp(-((u - 0.3) / 0.15) ** 2)
    estrella4(L, c.cx + c.rx + 22, c.cy - c.ry + 12, 6 + 8 * br, giro=0.6 * br)


def e_cool(L, t):
    sx, sy = respirar(t, 0.01)
    c = Cara(sx, sy)
    cabeza(L, c)
    cejas = -6 * max(math.exp(-((t - 0.5) / 0.12) ** 2), math.exp(-((t - 0.85) / 0.12) ** 2))
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        L.linea([(x - 12, y - 24 + cejas), (x + 12, y - 26 + cejas)], TRAZO * 0.6)
    lentes(L, c)
    sonrisa_lado(L, c)


def e_relaxed(L, t):
    resp = math.sin(2 * math.pi * t / DUR)
    c = Cara(1 - 0.02 * resp, 1 + 0.025 * resp, dy=-2 * resp)
    cabeza(L, c)
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        L.linea(bezier([(x - 10, y), (x, y + 7), (x + 10, y)]), TRAZO * 0.8)
    sonrisa(L, c, 11, 5)
    rubor(L, c, 0.45)


def e_delicious(L, t):
    sx, sy = respirar(t, 0.015)
    c = Cara(sx, sy)
    cabeza(L, c)
    for lado in (-1, 1):
        ojo_feliz(L, *c.ojo(lado), w=11, alto=6)
    sonrisa(L, c, 14, 6)
    # la lengua se relame de lado a lado
    lengua(L, c, dx=10 * math.sin(2 * math.pi * t / 1.2), largo=12, dy=3)
    rubor(L, c, 0.6)
    u = (t % 1.2) / 1.2
    br = math.sin(math.pi * u)
    estrella4(L, c.cx - c.rx - 18, c.cy + 10, 4 + 6 * br)


def e_kissy(L, t):
    sx, sy = respirar(t, 0.01)
    c = Cara(sx, sy)
    cabeza(L, c)
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        L.linea(bezier([(x - 10, y), (x, y + 7), (x + 10, y)]), TRAZO * 0.8)
    # boca de beso "3"
    bx, by = c.mx + 2, c.my + 2
    if con_boca():
        L.linea(bezier([(bx - 4, by - 9), (bx + 9, by - 9), (bx + 6, by), (bx - 1, by)]) +
                bezier([(bx - 1, by), (bx + 6, by), (bx + 9, by + 9), (bx - 4, by + 9)])[1:], TRAZO * 0.6)
    rubor(L, c, 0.8)
    # un corazón sale volando
    u = (t / DUR) % 1
    corazon(L, c.mx + 26 + 40 * u, c.my - 6 - 50 * u + 6 * math.sin(u * 8), 9 * (1 - u * 0.4), ROSA)


def e_confident(L, t):
    sx, sy = respirar(t, 0.01)
    c = Cara(sx, sy, lx=0.35)
    cabeza(L, c)
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        parpado(L, c, x, y, cierre=0.45)
    sonrisa_lado(L, c, 4)
    u = (t % 1.2) / 1.2
    estrella4(L, c.cx + c.rx + 22, c.cy + 18, 4 + 7 * math.sin(math.pi * u))


def e_sleepy(L, t):
    cabe = math.sin(2 * math.pi * t / DUR)
    c = Cara(1.01, 0.99, dy=3 + 3 * cabe, ly=0.3 + 0.1 * cabe)
    cabeza(L, c)
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        L.linea(bezier([(x - 10, y + 2), (x, y + 8), (x + 10, y + 2)]), TRAZO * 0.75)
    boca_o(L, c, 5 + 2 * pulso(t, DUR), dy=6)
    for k in range(3):
        u = ((t / DUR) + k / 3) % 1
        s = 0.5 + 0.7 * u
        col = tuple(int(v * (1 - u) ** 0.7) for v in L.C)
        zeta(L, c.cx + c.rx + 10 + 30 * u, c.cy - c.ry + 10 - 40 * u, s * 1.4, col)


def e_silly(L, t):
    L.rot = math.radians(10 * math.sin(2 * math.pi * t / 0.8))
    b = abs(math.sin(2 * math.pi * t / 0.8))
    c = Cara(1.0, 1.0, dy=-4 * b)
    cabeza(L, c)
    for lado in (-1, 1):
        ojo_mayor(L, *c.ojo(lado), lado)
    sonrisa(L, c, 12, 5)
    lengua(L, c, dx=4 * math.sin(2 * math.pi * t / 0.4), largo=16, dy=6)


def e_confused(L, t):
    sx, sy = respirar(t, 0.01)
    L.rot = math.radians(7 * math.sin(2 * math.pi * t / DUR))
    c = Cara(sx, sy)
    cabeza(L, c)
    giro = 2 * math.pi * t / 1.2
    for lado in (-1, 1):
        espiral(L, *c.ojo(lado), 15, giro * lado)
    boca_ondulada(L, c, 12, 3, dy=6, fase=0)
    L.rot = 0
    signo_pregunta(L, c.cx + c.rx + 26, c.cy - c.ry + 2 + 3 * math.sin(2 * math.pi * t / 0.8), 1.1)


def e_excited(L, t):
    b = abs(math.sin(2 * math.pi * t / 0.6))
    c = Cara(1.03 - 0.05 * b, 0.97 + 0.06 * b, dy=-9 * b)
    cabeza(L, c)
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        estrella4(L, x, y, 14 + 3 * pulso(t, 0.3), giro=0.3 * math.sin(2 * math.pi * t / 0.6))
    boca_abierta(L, c, 13, 10)
    rubor(L, c, 0.8)
    for k, (dx, dy) in enumerate(((-c.rx - 22, -c.ry + 20), (c.rx + 22, -c.ry + 6), (c.rx + 14, c.ry - 10))):
        u = ((t / 0.9) + k / 3) % 1
        estrella4(L, c.cx + dx, c.cy + dy, 9 * math.sin(math.pi * u))


def e_smug(L, t):
    sx, sy = respirar(t, 0.01)
    c = Cara(sx, sy, lx=0.65, ly=0.1)
    cabeza(L, c)
    x, y = c.ojo(-1)
    parpado(L, c, x, y, cierre=0.6)
    x, y = c.ojo(1)
    parpado(L, c, x, y, cierre=0.6)
    # una ceja que sube y baja
    sube = -7 * max(math.exp(-((t - 0.6) / 0.15) ** 2), math.exp(-((t - 1.0) / 0.15) ** 2))
    L.linea([(x - 10, y - 22 + sube), (x + 10, y - 25 + sube)], TRAZO * 0.6)
    sonrisa_lado(L, c, 8)


def e_terrified(L, t):
    tiembla = 2.0 * math.sin(2 * math.pi * t / 0.07)
    c = Cara(0.97, 1.03, dx=tiembla, lx=0.15 * math.sin(2 * math.pi * t / 0.6))
    cabeza(L, c)
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        L.anillo(x, y, 15, 17)
        L.circulo(x + 1.2 * math.sin(2 * math.pi * t / 0.11), y, 3)
        ceja(L, x, y - 26, lado, -8, 13)
    boca_ondulada(L, c, 16, 4, dy=6, fase=t * 20)
    for lado, ddy in ((-1, 0), (1, 10)):
        u = ((t / 1.2) + (0.5 if lado > 0 else 0)) % 1
        gota(L, c.cx + lado * (c.rx + 10), c.cy - c.ry + 26 + ddy + 30 * u * u, 5)


def e_escuchando(L, t):
    sx, sy = respirar(t, 0.015)
    c = Cara(sx * 0.97, sy * 1.04, ly=-0.55)
    cabeza(L, c)
    ojos_pildora(L, c, t)
    for lado in (-1, 1):
        for i in range(3):
            fase = (t * 1.6 - i * 0.33) % 1
            r = 14 + 26 * fase
            col = tuple(int(v * (1 - fase)) for v in L.C)
            pts = [(c.cx + lado * (c.rx + 6 + r * math.cos(a)), c.cy + r * math.sin(a)) for a in
                   [-0.6 + 1.2 * j / 10 for j in range(11)]]
            L.linea(pts, 5, col)


def e_musica(L, t):
    L.rot = math.radians(6 * math.sin(2 * math.pi * t / 1.2))
    b = abs(math.sin(2 * math.pi * t / 1.2))
    c = Cara(1.02 - 0.03 * b, 0.98 + 0.04 * b, dy=-5 * b)
    cabeza(L, c)
    arco = [(c.cx + (c.rx + 12) * math.cos(a), c.cy - 6 - (c.ry + 14) * math.sin(a)) for a in
            [math.pi * i / 30 for i in range(31)]]
    L.linea(arco, TRAZO * 0.9, ARO)
    for lado in (-1, 1):
        L.pildora(c.cx + lado * (c.rx + 6), c.cy + 4, 20, 40, ARO)
    for lado in (-1, 1):
        ojo_feliz(L, *c.ojo(lado), w=11, alto=6)
    sonrisa(L, c, 10, 5)
    L.rot = 0
    u = (t / 1.2) % 1
    nx, ny = c.cx + c.rx + 34 + 4 * math.sin(2 * math.pi * u), c.cy - c.ry - 4 - 10 * u
    L.circulo(nx, ny + 16, 7)
    L.linea([(nx + 6, ny + 15), (nx + 6, ny - 12), (nx + 16, ny - 6)], 5)


def e_mirando(L, t):
    """Curioseando: recorre la esfera con la mirada (arriba a la izquierda,
    arriba a la derecha, abajo) y se queda viendo de reojo con sospecha."""
    puntos = [(0.0, 0.0, 0.0), (0.35, -0.75, -0.65), (0.8, 0.75, -0.6), (1.25, 0.6, 0.6),
              (1.7, -0.2, 0.15), (2.4, 0.0, 0.0)]
    lx = ly = 0.0
    for (t0, x0, y0), (t1, x1, y1) in zip(puntos, puntos[1:]):
        if t0 <= t < t1:
            u = ease(min(1, (t - t0) / min(0.28, t1 - t0)))
            lx, ly = x0 + (x1 - x0) * u, y0 + (y1 - y0) * u
    b = abs(math.sin(2 * math.pi * t / 1.2)) * 0.6
    c = Cara(1 + 0.02 * b, 1 - 0.02 * b, dy=-2 * b, lx=lx, ly=ly)
    cabeza(L, c)
    sospecha = ease((t - 1.7) / 0.2) * (1 - ease((t - 2.2) / 0.15))
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        if sospecha > 0.5:
            # ojos entrecerrados en rayita inclinada: "mmm..."
            L.linea([(x - 9, y - 2 * lado), (x + 9, y + 2 * lado)], TRAZO * 0.75)
        else:
            ojo_rect(L, c, x, y, 18, 30 * parpadeo(t, 1.25))


# ---------------------------------------------------------------- conversación
# Cuando hay una conversación, MongoBot se arrima a la pantalla: la cabeza crece
# hasta verse como una cúpula blanca cortada abajo, con ojos negros grandes que
# se mueven sobre la esfera. Así parece que te está poniendo atención.
CUPULA = dict(cx=160, cy=124, r=90, corte=176)
ZOOM_CUPULA_VERTICAL = 1.12          # en la pantalla vertical la cúpula se acerca un poco más
OJO_CERCA = (240, 240, 240)          # de cerca los ojos son blancos


def cupula(L, t, lx=0.0, ly=0.0, k=1.0, ojo_col=OJO_CERCA, blink=True, voz=0.0, sonrisa=0.0, parp=None):
    """Cara de cerca: cúpula con el aro blanco y la cara negra adentro, cortada abajo,
    solo con ojos. La cara negra y los ojos van sobre la esfera y giran con (lx, ly).
    k: 0 = cabeza normal, 1 = cúpula (transición).
    voz: 0..1, los ojos se achatan apenas con cada sílaba.
    sonrisa: 0..1, a los ojos se les curva la parte de abajo (ojos sonrientes)."""
    e = ease(k)
    cx = CX + (CUPULA["cx"] - CX) * e
    cy = CY + (CUPULA["cy"] - CY) * e
    r = RX + (CUPULA["r"] - RX) * e
    c = Cara(r / RX, r / RY, dx=cx - CX, dy=cy - CY, lx=lx * e, ly=ly * e)
    c.irx = c.iry = r * (0.74 + 0.06 * e)     # de cerca el aro se ve un poco más fino
    cabeza(L, c)
    if parp is None:
        parp = parpadeo(t % DUR) if blink else 1.0
    sep = RX * 0.29 + (27 - RX * 0.29) * e
    ey = cy - (RY * 0.13 + (8 - RY * 0.13) * e)
    w = (18 + (24 - 18) * e) * (1 + 0.06 * voz)
    h = (30 + (40 - 30) * e) * parp * (1 - 0.14 * voz)
    col = tuple(int(a + (b - a) * e) for a, b in zip(ojo_col, OJO_CERCA))
    for lado in (-1, 1):
        ex = cx + lado * sep
        ojo_rect(L, c, ex, ey - 2.5 * voz, w, max(4, h), col)
        if sonrisa > 0.02:
            # un arco negro muerde la parte de abajo del ojo: ojos sonrientes
            yb = ey - 2.5 * voz + h / 2 + h * 0.12
            pts = [(ex + w * 0.75 * math.cos(a), yb + h * 0.55 * sonrisa * math.sin(a)) for a in
                   [2 * math.pi * i / 36 for i in range(36)]]
            L.poligono(pts, (0, 0, 0))
    L.cara = None
    # el corte de abajo: la cúpula se asoma desde el borde
    corte = 240 + (CUPULA["corte"] - 240) * e
    if corte < 240:
        L.d.rectangle((*L.T(0, corte), *L.T(W, H)), fill=(0, 0, 0))
    return c


def acercamiento(L, k, t, ojo_col, blink=True):
    cupula(L, t, k=k, ojo_col=ojo_col, blink=blink)


CONV_DUR = 6.0      # los estados de conversación duran más: movimientos lentos


def nivel_voz(t):
    """Volumen de voz simulado (sílabas), repetible cada CONV_DUR segundos."""
    f = 1 / CONV_DUR
    s = 0.5 + 0.5 * math.sin(2 * math.pi * 20 * f * t) * math.sin(2 * math.pi * 5 * f * t + 1.0)
    s *= 0.55 + 0.45 * math.sin(2 * math.pi * 41 * f * t) ** 2
    return max(0.0, min(1.0, s * 1.4))


def voz_suave(t):
    """La voz promediada en un cuarto de segundo: los ojos la siguen sin temblar."""
    return sum(nivel_voz(t - 0.25 * i / 7) for i in range(8)) / 8


def _suave(u):
    """Curva más suave que ease: arranca y frena despacio, como un movimiento real."""
    u = max(0.0, min(1.0, u))
    return u * u * u * (u * (u * 6 - 15) + 10)


def _mirada(puntos, t):
    """Mirada entre puntos (momento en que llega, lx, ly, cuánto tarda en llegar)."""
    for (_, x0, y0, _), (t1, x1, y1, d) in zip(puntos, puntos[1:]):
        if t < t1:
            if d > 0 and t >= t1 - d:
                u = _suave((t - (t1 - d)) / d)
                return x0 + (x1 - x0) * u, y0 + (y1 - y0) * u
            return x0, y0
    return puntos[-1][1], puntos[-1][2]


def _deriva(t, amp=0.035):
    """Microvaivén de la mirada: nunca está del todo quieta (periódico cada CONV_DUR)."""
    f = 2 * math.pi / CONV_DUR
    return (amp * (math.sin(f * t + 0.3) + 0.5 * math.sin(3 * f * t + 1.1)),
            amp * (math.sin(2 * f * t + 2.0) + 0.4 * math.sin(5 * f * t)))


def _parpadeos(t, momentos, dur=0.22):
    k = 1.0
    for tb in momentos:
        u = (t - tb) / dur
        if 0 <= u < 1:
            k = min(k, 1 - 0.92 * math.sin(math.pi * u))
    return k


def e_conversa_escucha(L, t):
    """De cerca, escuchando: levanta la mirada despacio hacia arriba a la derecha,
    como buscándote, se queda viéndote y asiente con calma dos veces."""
    arriba, centro = (0.45, -0.52), (0.05, 0.12)
    # (momento en que llega, lx, ly, cuánto tarda en llegar)
    puntos = [(0.0, *centro, 0.0), (0.9, *arriba, 0.9), (2.3, *arriba, 0.0),
              (2.9, 0.35, -0.05, 0.6), (3.6, *arriba, 0.7), (4.2, 0.35, -0.05, 0.6),
              (4.9, *arriba, 0.7), (5.4, *arriba, 0.0), (6.0, *centro, 0.6)]
    lx, ly = _mirada(puntos, t)
    dx, dy = _deriva(t)
    cupula(L, t, lx + dx, ly + dy, parp=_parpadeos(t, (1.7, 5.1)))


# globitos: (aparece, desaparece, dx, dy, punta hacia) relativos al centro de la cúpula
GLOBOS = [(0.2, 2.0, 62, -98, "abajo"), (2.2, 4.0, 122, -40, "izquierda"), (4.2, 5.8, -66, -98, "abajo_der")]
# En la pantalla vertical sobra espacio arriba y falta a los lados: los globitos salen encima
GLOBOS_VERTICAL = [(0.2, 2.0, 58, -132, "abajo"), (2.2, 4.0, 0, -172, "abajo"), (4.2, 5.8, -58, -132, "abajo_der")]


def globo(L, x, y, k, puntos, punta):
    """Globo de diálogo blanco con tres puntitos negros. k: 0..1 (con rebote al aparecer)."""
    if k <= 0.02:
        return
    rx, ry = 34 * k, 19 * k
    L.d.ellipse((*L.T(x - rx, y - ry), *L.T(x + rx, y + ry)), fill=ARO)
    # la colita apunta hacia la cabeza
    if punta == "abajo":            # colita abajo a la izquierda
        L.poligono([(x - 14 * k, y + ry * 0.7), (x - 4 * k, y + ry * 0.8), (x - 18 * k, y + ry + 9 * k)], ARO)
    elif punta == "abajo_der":      # colita abajo a la derecha
        L.poligono([(x + 14 * k, y + ry * 0.7), (x + 4 * k, y + ry * 0.8), (x + 18 * k, y + ry + 9 * k)], ARO)
    else:                           # colita hacia la izquierda, un poco abajo
        L.poligono([(x - rx * 0.8, y + 2 * k), (x - rx * 0.6, y + 10 * k), (x - rx - 9 * k, y + 12 * k)], ARO)
    for n in range(3):
        a = max(0.0, min(1.0, puntos - n))
        if a > 0:
            s_ = 3.2 * k * a
            px = x + (n - 1) * 11 * k
            L.d.rectangle((*L.T(px - s_, y - s_), *L.T(px + s_, y + s_)), fill=(0, 0, 0))


def e_conversa_habla(L, t):
    """De cerca, hablando, solo con ojos: la misma cúpula de escuchar. Le van saliendo
    globitos de diálogo alrededor y los ojos los miran despacio; siguen la voz con
    suavidad y a ratos sonríen."""
    v = voz_suave(t)
    puntos_mirada = [(0.0, 0.1, -0.1, 0.0), (0.7, 0.35, -0.4, 0.7), (2.2, 0.35, -0.4, 0.0),
                     (2.9, 0.5, -0.1, 0.7), (4.2, 0.5, -0.1, 0.0), (4.9, -0.35, -0.4, 0.7),
                     (5.6, -0.35, -0.4, 0.0), (6.0, 0.1, -0.1, 0.4)]
    if VERTICAL:   # el segundo globito sale arriba al centro: mira hacia arriba
        puntos_mirada = [(tt, 0.0, -0.6, d) if 2.2 <= tt < 4.2 else (tt, lx_, ly_, d)
                         for tt, lx_, ly_, d in puntos_mirada]
    lx, ly = _mirada(puntos_mirada, t)
    dx, dy = _deriva(t, 0.025)
    sonrisa = _suave((t - 2.4) / 0.5) * (1 - _suave((t - 3.7) / 0.5))
    cupula(L, t, lx + dx, ly + dy - 0.03 * v, voz=v * (1 - 0.6 * sonrisa), sonrisa=sonrisa,
           parp=_parpadeos(t, (1.3, 4.7)))
    cx, cy = CUPULA["cx"], CUPULA["cy"]
    for t0, t1, gx, gy, punta in (GLOBOS_VERTICAL if VERTICAL else GLOBOS):
        if t0 <= t < t1:
            u = t - t0
            k = rebote(u / 0.3) if u < 0.3 else 1.0
            if t > t1 - 0.25:
                k = 1 - _suave((t - (t1 - 0.25)) / 0.25)
            puntos = min(3.0, max(0.0, (u - 0.25) / 0.22))
            globo(L, cx + gx, cy + gy + 2 * math.sin(2 * math.pi * u / 1.2), k, puntos, punta)


def rebote(u):
    """Aparece creciendo con un pequeño sobrepaso."""
    u = max(0.0, min(1.0, u))
    return 1 + 2.7 * (u - 1) ** 3 + 1.7 * (u - 1) ** 2


def demo_conversacion(salida):
    """Video: cabeza normal -> se acerca -> escucha -> habla -> se aleja."""
    dur = 16.0
    tmp = "/tmp/mm_conv"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    for i in range(int(dur * FPS)):
        t = i / FPS
        L = Lienzo(COLORES["neutral"])
        if t < 1.2:
            e_neutral(L, t % DUR)
        elif t < 2.0:
            acercamiento(L, (t - 1.2) / 0.8, t, COLORES["neutral"], blink=False)
        elif t < 8.0:
            e_conversa_escucha(L, t - 2.0)
        elif t < 8.4:
            # de la cúpula a la esfera de hablar: fundido corto
            L2 = Lienzo(COLORES["neutral"])
            e_conversa_escucha(L, 0.0)
            e_conversa_habla(L2, 0.0)
            Image.blend(L.final(), L2.final(), ease((t - 8.0) / 0.4)).save(f"{tmp}/{i:04d}.png")
            continue
        elif t < 14.0:
            e_conversa_habla(L, t - 8.4)
        elif t < 14.4:
            L2 = Lienzo(COLORES["neutral"])
            e_conversa_habla(L, 5.6)
            acercamiento(L2, 1.0, t, COLORES["neutral"], blink=False)
            Image.blend(L.final(), L2.final(), ease((t - 14.0) / 0.4)).save(f"{tmp}/{i:04d}.png")
            continue
        elif t < 14.8:
            acercamiento(L, 1 - (t - 14.4) / 0.4, t, COLORES["neutral"], blink=False)
        else:
            e_neutral(L, (t - 14.8) % DUR)
        L.final().save(f"{tmp}/{i:04d}.png")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", f"{tmp}/%04d.png",
                    "-vf", "scale=640:480:flags=lanczos,format=yuv420p", "-c:v", "libx264", "-crf", "18",
                    "-preset", "veryfast", salida], check=True)


EMOCIONES = ["neutral", "happy", "laughing", "funny", "sad", "crying", "angry", "loving",
             "embarrassed", "surprised", "shocked", "thinking", "winking", "cool", "relaxed",
             "delicious", "kissy", "confident", "sleepy", "silly", "confused", "excited",
             "smug", "terrified", "escuchando", "musica", "mirando", "conversa_escucha", "conversa_habla"]


DURACION = {"conversa_escucha": CONV_DUR, "conversa_habla": CONV_DUR}


def n_cuadros(nombre):
    return int(round(DURACION.get(nombre, DUR) * FPS))


def cuadro(nombre, t):
    global ACTUAL
    ACTUAL = nombre
    L = Lienzo(COLORES[nombre])
    if nombre not in SIN_ZOOM:
        L.zoom = R_ESTANDAR / RX
    elif VERTICAL:
        L.zoom = ZOOM_CUPULA_VERTICAL      # en vertical la cúpula se acerca más

    globals()["e_" + nombre](L, t)
    return L.final()


def guardar_gif(cuadros, ruta):
    pal = cuadros[0].quantize(colors=32, method=Image.Quantize.MEDIANCUT)
    q = [c.quantize(palette=pal, dither=Image.Dither.NONE) for c in cuadros]
    q[0].save(ruta, save_all=True, append_images=q[1:], duration=int(1000 / FPS), loop=0,
              disposal=1, optimize=True)


def generar(salida):
    os.makedirs(salida, exist_ok=True)
    anims = {}
    total = 0
    for n in EMOCIONES:
        anims[n] = [cuadro(n, i / FPS) for i in range(n_cuadros(n))]
        ruta = os.path.join(salida, f"{n}.gif")
        guardar_gif(anims[n], ruta)
        total += os.path.getsize(ruta)
    print(f"{len(EMOCIONES)} GIF, {total / 1024:.0f} KB en total")

    # cuadrícula con todas, tres vueltas
    tmp = "/tmp/mm_grid"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    try:
        fnt = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
    except OSError:
        fnt = None
    cols = 6
    filas = math.ceil(len(EMOCIONES) / cols)
    for i in range(int(CONV_DUR * FPS) * 2):
        hoja = Image.new("RGB", (320 * cols, 270 * filas), (14, 14, 14))
        d = ImageDraw.Draw(hoja)
        for k, n in enumerate(EMOCIONES):
            x, y = (k % cols) * 320, (k // cols) * 270
            hoja.paste(anims[n][i % len(anims[n])], (x, y))
            d.text((x + 160, y + 255), n, fill=COLORES[n] if sum(COLORES[n]) > 60 else ARO, font=fnt, anchor="mm")
        hoja.save(f"{tmp}/{i:04d}.png")
    mp4 = os.path.join(salida, "mongo_minimal_todas.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", f"{tmp}/%04d.png",
                    "-vf", "scale=1920:-2,format=yuv420p", "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
                    mp4], check=True)
    demo_conversacion(os.path.join(salida, "mongo_conversacion.mp4"))


if __name__ == "__main__":
    generar(sys.argv[1] if len(sys.argv) > 1 else "minimal")
