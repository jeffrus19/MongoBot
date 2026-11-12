"""MongoBot minimalista: animaciones de estados del sistema, funciones y personalidad.

Uso:  python generar_extras_min.py [carpeta_salida]

Genera un GIF por animación y un video con todas en cuadrícula:

  pensando, despertar, conectando, sin_conexion, saludo, alarma, temporizador,
  clima_sol, clima_nube, clima_lluvia, pomodoro_trabajo, pomodoro_descanso,
  presumido, llamando, tacto_cosquillas, tacto_molesto, tacto_despertar, leyendo

Usa las piezas de mongo_minimal.py: el aro siempre blanco, la cara negra que gira
sobre la esfera y los ojos del color de cada animación.
"""
import math
import os
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mongo_minimal as mm          # noqa: E402
from mongo_minimal import ARO, CELESTE, ROSA, ease  # noqa: E402

FPS = 20
NEGRO = (0, 0, 0)
GRIS = (150, 150, 150)
AMARILLO = (255, 205, 60)


def suave(u):
    u = max(0.0, min(1.0, u))
    return u * u * u * (u * (u * 6 - 15) + 10)


def rebote(u):
    u = max(0.0, min(1.0, u))
    return 1 + 2.7 * (u - 1) ** 3 + 1.7 * (u - 1) ** 2


def parpadeos(t, momentos, dur=0.2):
    k = 1.0
    for tb in momentos:
        u = (t - tb) / dur
        if 0 <= u < 1:
            k = min(k, 1 - 0.92 * math.sin(math.pi * u))
    return k


def cara(L, r=80, cx=160, cy=124, lx=0.0, ly=0.0, sx=1.0, sy=1.0):
    c = mm.Cara(sx * r / mm.RX, sy * r / mm.RY, dx=cx - mm.CX, dy=cy - mm.CY, lx=lx, ly=ly)
    mm.cabeza(L, c)
    return c


def ojos(L, c, w=18, h=30, parp=1.0, color=None, solo=None):
    k = c.rx / 80
    for lado in (-1, 1):
        if solo and lado != solo:
            continue
        x, y = c.ojo(lado)
        mm.ojo_rect(L, c, x, y, w * k, max(3, h * k * parp), color)


def ojos_cerrados(L, c, curva=7, color=None):
    k = c.rx / 80
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        L.linea(mm.bezier([(x - 10 * k, y), (x, y + curva * k), (x + 10 * k, y)]), mm.TRAZO * 0.8 * k, color)


def ojos_felices(L, c, color=None):
    k = c.rx / 80
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        L.linea([(x - 11 * k, y + 4 * k), (x, y - 6 * k), (x + 11 * k, y + 4 * k)], mm.TRAZO * 0.8 * k, color)


def ondita(L, x, y, r, a0, a1, ancho, color):
    pts = [(x + r * math.cos(a), y + r * math.sin(a)) for a in [a0 + (a1 - a0) * i / 16 for i in range(17)]]
    L.linea(pts, ancho, color)


def toque(L, x, y, u):
    """Onda de un dedo tocando la pantalla (u: 0..1)."""
    if 0 <= u < 1:
        col = tuple(int(255 * (1 - u)) for _ in range(3))
        L.anillo(x, y, 6 + 26 * u, 6 + 26 * u, 3.5, col)
        if u < 0.3:
            L.circulo(x, y, 6 * (1 - u / 0.3), (200, 200, 200))


# ---------------------------------------------------------------- 1. pensando

def a_pensando(L, t):
    col = (170, 140, 255)
    L.C = col
    dur = 2.4
    c = cara(L, lx=0.35 + 0.05 * math.sin(2 * math.pi * t / dur), ly=-0.45)
    ojos(L, c, h=24, parp=parpadeos(t, (1.6,)))
    x, y = c.ojo(1)
    L.linea([(x - 9, y - 22), (x + 10, y - 26)], mm.TRAZO * 0.6)          # una ceja arriba
    L.cara = None
    # tres puntitos que dan vueltas alrededor del aro
    for k in range(3):
        a = 2 * math.pi * (t / 1.2) - k * 0.5 - math.pi / 2
        L.circulo(c.cx + (c.rx + 13) * math.cos(a), c.cy + (c.ry + 13) * math.sin(a), 5.5 - 1.3 * k, col)


# ---------------------------------------------------------------- 2. despertar

def despertar(L, t, col=(235, 235, 235)):
    L.C = col
    if t < 0.75:                                           # durmiendo
        resp = math.sin(2 * math.pi * t / 1.5)
        c = cara(L, cy=130 + 2 * resp, sy=1 - 0.015 * resp, ly=0.3)
        ojos_cerrados(L, c)
        L.cara = None
        mm.zeta(L, c.cx + c.rx + 12, c.cy - c.ry + 8 - 6 * t, 1.1, (120, 120, 160))
        return
    u = t - 0.75
    salto = math.sin(math.pi * min(1, u / 0.35)) if u < 0.35 else 0
    estira = 1 + 0.08 * salto
    asentar = suave((u - 0.35) / 0.4)
    c = cara(L, cy=130 - 16 * salto - 6 * asentar, sx=1 / estira, sy=estira,
             lx=0.0 if u < 0.9 else 0.2 * math.sin(2 * math.pi * (u - 0.9) / 1.2) * (1 - suave((u - 1.4) / 0.3)))
    grande = 1.25 - 0.25 * asentar
    ojos(L, c, w=18 * grande, h=30 * grande, parp=parpadeos(t, (1.9, 2.15)))
    L.cara = None
    if u < 1.0:
        k = rebote(u / 0.25)
        mm.signo_admiracion(L, c.cx + c.rx + 18, c.cy - c.ry + 10, 1.2 * k, AMARILLO)


def a_despertar(L, t):
    despertar(L, t)


# ---------------------------------------------------------------- 3. conectando / sin conexión

def wifi(L, x, y, niveles, color, apagado=(60, 60, 60), escala=1.0):
    L.circulo(x, y, 4.5 * escala, color if niveles > 0 else apagado)
    for i, r in enumerate((13, 23, 33)):
        col = color if niveles > i + 1 - 1e-6 else apagado
        ondita(L, x, y, r * escala, -math.pi * 0.75, -math.pi * 0.25, 5 * escala, col)


def a_conectando(L, t):
    col = (90, 220, 255)
    L.C = col
    c = cara(L, r=66, cy=150, lx=0.3 * math.sin(2 * math.pi * t / 2.0), ly=-0.4)   # mismo largo que el bucle
    ojos(L, c, parp=parpadeos(t, (1.2,)))
    L.cara = None
    niveles = int((t / 0.4) % 5)                            # 0, 1, 2, 3, 4(=todo) y vuelve
    wifi(L, 160, 62, min(niveles, 4), col)


CACTUS = ["..X..", "..X.X", "X.XXX", "XXX..", "..X..", "..X.."]


def pixeles(L, filas, x, y, p, color):
    for j, f in enumerate(filas):
        for i, ch in enumerate(f):
            if ch == "X":
                L.d.rectangle((*L.T(x + i * p, y + j * p), *L.T(x + (i + 1) * p - 0.5, y + (j + 1) * p - 0.5)),
                              fill=color)


def a_sin_conexion(L, t):
    """Inspirada en el juego sin internet: corre por el suelo y salta cactus pixelados."""
    dur, v = 3.2, 150.0
    L.C = GRIS
    suelo = 196
    # suelo con piedritas que pasan
    L.linea([(0, suelo), (320, suelo)], 2.5, GRIS)
    for k in range(8):
        x = (k * 47 - v * t) % 340 - 10
        L.linea([(x, suelo + 8 + (k % 3) * 4), (x + 4 + k % 3 * 2, suelo + 8 + (k % 3) * 4)], 2, (90, 90, 90))
    # nubecitas pixeladas
    for k, (y0, vel) in enumerate(((40, 25), (70, 15))):
        x = 340 - ((t * vel + k * 160) % 380)
        L.d.rounded_rectangle((*L.T(x, y0), *L.T(x + 34, y0 + 10)), radius=5 * mm.SS, fill=(70, 70, 70))
    # cactus
    llegadas = []
    for off in (0.0, 1.6):
        tt = (t + off) % dur
        x = 340 - v * tt
        pixeles(L, CACTUS, x - 15, suelo - 36, 6, GRIS)
        llegadas.append((340 - 84) / v - off)
    # salto cuando un cactus pasa por debajo
    alto = 0.0
    for tl in llegadas:
        dt = ((t - tl + dur / 2) % dur) - dur / 2
        if abs(dt) < 0.38:
            alto = max(alto, 52 * (1 - (dt / 0.38) ** 2))
    corre = abs(math.sin(2 * math.pi * t / 0.3)) * (0 if alto > 1 else 1)
    r = 30
    c = cara(L, r=r, cx=84, cy=suelo - r - 2 - alto - 2 * corre, lx=0.5, ly=-0.1 if alto else 0.05)
    if alto > 1:
        ojos_felices(L, c, GRIS)
    else:
        ojos(L, c, parp=parpadeos(t, (2.4,)), color=GRIS)
    L.cara = None
    # wifi tachado arriba a la derecha
    wifi(L, 270, 58, 4, (110, 110, 110), escala=0.8)
    L.linea([(250, 30), (292, 62)], 4.5, (220, 80, 80))


# ---------------------------------------------------------------- 4. saludo (choca esos cinco)

def a_saludo(L, t):
    col = (255, 214, 80)
    L.C = col
    sube = suave(t / 0.6) * (1 - suave((t - 2.6) / 0.4))
    sacude = 0.0
    if 1.0 <= t < 1.25:
        sacude = 3 * math.sin(2 * math.pi * (t - 1.0) / 0.06) * (1 - (t - 1.0) / 0.25)
    cy = 124 + 160 * (1 - sube)
    guino = 1.6 <= t < 2.3
    c = cara(L, cx=150 + sacude, cy=cy + sacude * 0.5, lx=0.15 if t < 1.6 else 0.0)
    if 0.6 <= t < 1.6 or guino:
        if guino:
            ojos(L, c, solo=-1)
            x, y = c.ojo(1)
            L.linea([(x - 11, y + 4), (x, y - 6), (x + 11, y + 4)], mm.TRAZO * 0.8)
        else:
            ojos_felices(L, c)
        mm.rubor(L, c, 0.8)
    else:
        ojos(L, c, parp=parpadeos(t, (2.45,)))
    L.cara = None
    # la mano viene hacia la pantalla, choca y se va
    if 0.55 <= t < 1.7:
        if t < 1.0:
            u = suave((t - 0.55) / 0.45)
        elif t < 1.25:
            u = 1.0
        else:
            u = 1 - suave((t - 1.25) / 0.45)
        r = 22 + 24 * u
        hx, hy = 250 - 6 * u + sacude, 205 - 50 * u
        L.circulo(hx, hy, r, ARO)
        L.circulo(hx, hy, r - 7 - 3 * u, NEGRO)
        if 1.0 <= t < 1.35:
            k = (t - 1.0) / 0.35
            for i in range(10):
                a = 2 * math.pi * i / 10
                r0, r1 = r + 8 + 16 * k, r + 20 + 26 * k
                L.linea([(hx + r0 * math.cos(a), hy + r0 * math.sin(a)), (hx + r1 * math.cos(a), hy + r1 * math.sin(a))],
                        5 * (1 - k) + 1, col)
    if guino:
        u = (t - 1.6) / 0.7
        mm.estrella4(L, c.cx + c.rx + 18, c.cy - c.ry + 16, 12 * math.sin(math.pi * u), col)


# ---------------------------------------------------------------- 5. alarma / temporizador

def a_alarma(L, t):
    col = (255, 120, 60)
    L.C = col
    vib = math.sin(2 * math.pi * t * 18)
    L.rot = math.radians(5 * vib)
    L.piv = (160, 130)
    c = cara(L, r=72, cy=130 + 1.5 * abs(vib))
    k = c.rx / 80
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        L.anillo(x, y, 11 * k + 1, 13 * k + 1, mm.TRAZO * 0.7)
        L.circulo(x + 1.5 * vib, y, 4)
    L.cara = None
    # campanas, martillito y patitas del despertador
    for lado in (-1, 1):
        bx, by = c.cx + lado * c.rx * 0.62, c.cy - c.ry * 0.86
        pts = [(bx + 20 * math.cos(a), by + 20 * math.sin(a)) for a in
               [math.pi + lado * 0.35 + math.pi * i / 20 for i in range(21)]]
        L.poligono(pts, col)
        L.linea([(c.cx + lado * c.rx * 0.55, c.cy + c.ry * 0.86), (c.cx + lado * c.rx * 0.78, c.cy + c.ry * 1.12)],
                mm.TRAZO * 0.9, ARO)
    mx = c.cx + 9 * vib
    L.linea([(c.cx, c.cy - c.ry - 2), (mx, c.cy - c.ry - 18)], 4, ARO)
    L.circulo(mx, c.cy - c.ry - 20, 4.5, ARO)
    L.rot = 0
    # rayitas de vibración
    if int(t * 12) % 2 == 0:
        for lado in (-1, 1):
            for j in range(3):
                r = c.rx + 14 + j * 9
                ondita(L, c.cx, c.cy, r, (0 if lado > 0 else math.pi) - 0.35, (0 if lado > 0 else math.pi) + 0.35,
                       3.5, col)


def a_temporizador(L, t):
    col = (60, 225, 215)
    L.C = col
    dur = 4.0
    resta = 1 - t / dur
    a_punta = -math.pi / 2 + 2 * math.pi * (1 - resta)
    c = cara(L, lx=0.35 * math.cos(a_punta), ly=0.35 * math.sin(a_punta))
    ojos(L, c, h=26, parp=parpadeos(t, (2.2,)))
    L.cara = None
    # el tiempo que queda va pintado sobre el aro blanco
    ri, re = c.rx * 0.74 + 1, c.rx - 1
    n = 80
    a0 = a_punta
    a1 = -math.pi / 2 + 2 * math.pi
    pts = [(c.cx + re * math.cos(a0 + (a1 - a0) * i / n), c.cy + re * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
    pts += [(c.cx + ri * math.cos(a1 - (a1 - a0) * i / n), c.cy + ri * math.sin(a1 - (a1 - a0) * i / n)) for i in range(n + 1)]
    if resta > 0.005:
        L.poligono(pts, col)
    # la puntita late con cada segundo
    late = 1 + 0.5 * math.exp(-((t % 1.0) / 0.12) ** 2)
    rm = (ri + re) / 2
    L.circulo(c.cx + rm * math.cos(a_punta), c.cy + rm * math.sin(a_punta), 6 * late, ARO)


# ---------------------------------------------------------------- 6. clima

def a_clima_sol(L, t):
    col = (255, 214, 80)
    L.C = col
    b = abs(math.sin(2 * math.pi * t / 1.2))
    c = cara(L, cx=146, cy=132 - 3 * b, lx=0.25, ly=-0.3)
    ojos_felices(L, c)
    mm.rubor(L, c, 0.6)
    L.cara = None
    sx, sy = 254, 52
    L.circulo(sx, sy, 18 + 1.5 * math.sin(2 * math.pi * t / 1.2), col)
    for i in range(8):
        a = 2 * math.pi * i / 8 + 2 * math.pi * t / 4.8
        L.linea([(sx + 27 * math.cos(a), sy + 27 * math.sin(a)), (sx + 37 * math.cos(a), sy + 37 * math.sin(a))], 5, col)


def nube(L, x, y, s, color):
    for dx, dy, r in ((-18, 4, 14), (0, -6, 19), (19, 2, 15), (0, 8, 14)):
        L.circulo(x + dx * s, y + dy * s, r * s, color)


def a_clima_nube(L, t):
    col = (175, 190, 215)
    L.C = col
    dur = 3.2
    nx = 160 + 60 * math.sin(2 * math.pi * t / dur)
    c = cara(L, cy=138, lx=(nx - 160) / 200, ly=-0.5)
    ojos(L, c, h=24, parp=parpadeos(t, (1.9,)))
    L.cara = None
    nube(L, nx, 46, 1.3, (200, 205, 215))
    nube(L, 320 - (t * 25 % 380) + 20, 22, 0.7, (110, 115, 125))


def a_clima_lluvia(L, t):
    col = CELESTE
    L.C = col
    c = cara(L, cx=150, cy=140, lx=0.3, ly=-0.45)
    ojos(L, c, h=26, parp=parpadeos(t, (1.5,)))
    L.cara = None
    # lluvia (se corta donde está el paraguas)
    for k in range(26):
        x0 = (k * 37) % 330
        y = ((t * 260 + k * 53) % 300) - 40
        x = x0 - 0.25 * y
        ux, uy = 205, 54
        if math.hypot(x - ux, y - uy) < 64 and y < uy + 30:
            continue
        L.linea([(x, y), (x - 4, y + 13)], 3, (120, 180, 230))
    # paraguas inclinado sobre la cabeza
    g = math.radians(-22 + 3 * math.sin(2 * math.pi * t / 2.4))
    ux, uy, R = 205, 60, 60

    def P(x, y):
        return ux + x * math.cos(g) - y * math.sin(g), uy + x * math.sin(g) + y * math.cos(g)

    cupula = [P(R * math.cos(a), R * 0.82 * math.sin(a)) for a in [math.pi + math.pi * i / 30 for i in range(31)]]
    L.poligono(cupula + [P(R, 0), P(-R, 0)], ARO)
    for i in range(3):                                          # borde ondulado abajo
        cx_ = -R + R / 3 + i * 2 * R / 3
        L.poligono([P(cx_ + (R / 3) * math.cos(a), 6 * math.sin(a)) for a in [math.pi * j / 12 for j in range(13)]], NEGRO)
    L.linea([P(0, -R * 0.82), P(0, -R * 0.82 - 8)], 5, ARO)
    mango = [P(0, 0), P(0, 72)] + [P(-9 + 9 * math.cos(a), 72 + 9 * math.sin(a)) for a in [math.pi * i / 10 for i in range(11)]]
    L.linea(mango, 5.5, ARO)
    # salpicaduras en el paraguas
    for k in range(3):
        u = ((t * 2.5) + k / 3) % 1
        px, py = P(-40 + k * 38, -R * 0.6 + k * 4 - (6 if k == 1 else 0))
        if u < 0.35:
            L.circulo(px - 6 * u * 3, py - 8 * u * 3, 2.2, (150, 200, 240))
            L.circulo(px + 6 * u * 3, py - 7 * u * 3, 2.2, (150, 200, 240))


# ---------------------------------------------------------------- 7. pomodoro

def tomate(L, x, y, r, resta, col_arco):
    L.circulo(x, y, r, (240, 75, 65))
    L.poligono([(x - 8, y - r + 2), (x, y - r - 7), (x + 8, y - r + 2), (x, y - r + 6)], (100, 210, 90))
    if resta > 0.01:
        n = 50
        a0 = -math.pi / 2
        pts = [(x + (r + 8) * math.cos(a0 + 2 * math.pi * resta * i / n), y + (r + 8) * math.sin(a0 + 2 * math.pi * resta * i / n))
               for i in range(n + 1)]
        L.linea(pts, 4, col_arco)


def a_pomodoro_trabajo(L, t):
    col = (255, 110, 90)
    L.C = col
    dur = 3.0
    c = cara(L, cx=140, cy=128, lx=-0.15 + 0.1 * math.sin(2 * math.pi * t / dur), ly=0.3)
    k = 1.0
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        mm.parpado(L, c, x, y, cierre=0.4)
    L.cara = None
    tomate(L, 264, 150, 22, 1 - t / dur * 0.25 - 0.1, ARO)
    # gotita de esfuerzo
    u = (t / dur) % 1
    mm.gota(L, c.cx + c.rx * 0.7, c.cy - c.ry * 0.6 + 20 * u, 5 * (1 - u * 0.3))


def a_pomodoro_descanso(L, t):
    col = (140, 230, 150)
    L.C = col
    resp = math.sin(2 * math.pi * t / 3.0)
    c = cara(L, cx=140, cy=126 - 2 * resp, sy=1 + 0.015 * resp, ly=-0.15)
    ojos_cerrados(L, c)
    mm.sonrisa(L, c, 10, 5)
    mm.rubor(L, c, 0.5)
    L.cara = None
    # taza de café con vapor
    x, y = 262, 172
    L.d.rounded_rectangle((*L.T(x - 20, y - 18), *L.T(x + 20, y + 20)), radius=6 * mm.SS, fill=ARO)
    L.anillo(x + 24, y, 8, 10, 5, ARO)
    L.d.rectangle((*L.T(x - 15, y - 13), *L.T(x + 15, y - 9)), fill=(120, 80, 60))
    for k in range(3):
        u = ((t / 1.5) + k / 3) % 1
        pts = [(x - 10 + k * 10 + 4 * math.sin(v * 6 + t * 3), y - 24 - v * 40 * u - 4) for v in [i / 10 for i in range(11)]]
        gris = int(200 * (1 - u))
        L.linea(pts, 3, (gris, gris, gris))
    mm.zeta(L, c.cx + c.rx + 4, c.cy - c.ry + 6 - 4 * resp, 0.8, (110, 160, 120))


# ---------------------------------------------------------------- 8. presumido

def a_presumido(L, t):
    col = AMARILLO
    L.C = col
    L.rot = math.radians(-6 + 2 * math.sin(2 * math.pi * t / 2.4))
    c = cara(L, lx=-0.25, ly=-0.35)
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        mm.parpado(L, c, x, y, cierre=0.5)
    mm.sonrisa_lado(L, c, 2)
    L.cara = None
    L.rot = 0
    # estrellas que titilan alrededor
    for k, (x, y, s) in enumerate(((262, 50, 13), (52, 80, 9), (270, 160, 8), (70, 190, 11), (236, 22, 6))):
        u = ((t / 1.2) + k * 0.23) % 1
        mm.estrella4(L, x, y, s * math.sin(math.pi * u), col, giro=0.4 * u)
    # destello que pasa por el aro
    u = (t % 2.4) / 2.4
    if u < 0.3:
        a = math.radians(200 + 90 * u / 0.3)
        mm.estrella4(L, c.cx + c.rx * 0.88 * math.cos(a), c.cy + c.ry * 0.88 * math.sin(a), 15 * math.sin(math.pi * u / 0.3),
                     (255, 255, 255))


# ---------------------------------------------------------------- 9. llamando la atención (toca el vidrio)

def a_llamando(L, t):
    col = (235, 235, 235)
    L.C = col
    toques = (0.35, 0.65, 0.95)
    sacude = 0.0
    for tt in toques:
        if 0 <= t - tt < 0.12:
            sacude = 2.5 * math.sin(2 * math.pi * (t - tt) / 0.06)
    pregunta = suave((t - 1.6) / 0.3) * (1 - suave((t - 2.7) / 0.3))
    c = cara(L, r=92, cx=150 + sacude, cy=132 + sacude * 0.4, lx=0.22 * pregunta, ly=0.05)
    ojos(L, c, parp=parpadeos(t, (2.2,)))
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        L.linea([(x - 10, y - 26 - 4 * pregunta), (x + 10, y - 27 - 4 * pregunta)], mm.TRAZO * 0.6)
    L.cara = None
    # la mano toca el vidrio desde adentro
    hx, hy = 236 + sacude, 180
    golpe = 0.0
    for tt in toques:
        d = t - tt
        if -0.12 <= d < 0.15:
            golpe = max(golpe, math.exp(-(d / 0.05) ** 2))
    r = 26 + 14 * golpe
    L.circulo(hx, hy, r, ARO)
    L.circulo(hx, hy, r - 7, NEGRO)
    for tt in toques:
        d = t - tt
        if 0 <= d < 0.5:
            u = d / 0.5
            L.anillo(hx, hy, r + 6 + 30 * u, r + 6 + 30 * u, 3, tuple(int(220 * (1 - u)) for _ in range(3)))
    if pregunta > 0.05:
        mm.signo_pregunta(L, c.cx + c.rx + 18, c.cy - c.ry + 20, 1.1 * pregunta, col)


# ---------------------------------------------------------------- 10. reacción al tacto

def a_tacto_cosquillas(L, t):
    col = (255, 150, 120)
    L.C = col
    L.rot = math.radians(9 * math.sin(2 * math.pi * t / 0.3))
    b = abs(math.sin(2 * math.pi * t / 0.3))
    c = cara(L, cy=126 - 3 * b)
    for lado in (-1, 1):
        mm.ojo_mayor(L, *c.ojo(lado), lado)
    mm.boca_abierta(L, c, 12, 9)
    mm.rubor(L, c, 1.0)
    L.cara = None
    L.rot = 0
    for k in range(4):
        u = ((t / 0.6) + k / 4) % 1
        a = math.radians(-150 + k * 40)
        r = c.rx + 10 + 14 * u
        L.linea([(c.cx + r * math.cos(a), c.cy + r * math.sin(a)), (c.cx + (r + 8) * math.cos(a), c.cy + (r + 8) * math.sin(a))],
                4 * (1 - u) + 0.5, col)
    toque(L, 196, 150, (t % 0.6) / 0.45)


def a_tacto_molesto(L, t):
    col = (255, 65, 55)
    L.C = col
    tiembla = 1.5 * math.sin(2 * math.pi * t / 0.08)
    c = cara(L, cx=160 + tiembla, sx=1.04, sy=0.96)
    ojos(L, c, h=18)
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        mm.ceja(L, x, y - 20, lado, 13)
    L.cara = None
    mm.vena(L, c.cx + c.rx - 6, c.cy - c.ry + 8, 1 + 0.15 * math.sin(2 * math.pi * t / 0.3))
    # vapor saliendo de la cabeza
    for k in range(3):
        u = ((t / 0.9) + k / 3) % 1
        x = c.cx - 30 + k * 30 + 6 * math.sin(u * 8)
        gris = int(230 * (1 - u))
        L.circulo(x, c.cy - c.ry - 6 - 40 * u, 6 + 6 * u, (gris, gris, gris))
    toque(L, 200, 160, (t % 0.8) / 0.4)


def a_tacto_despertar(L, t):
    if t < 0.75:
        despertar(L, t)
        toque(L, 186, 150, (t - 0.45) / 0.4)
    else:
        despertar(L, t)


# ---------------------------------------------------------------- 11. leyendo

TAPA = (165, 25, 32)        # libro todo rojo: tapas un poco más oscuras
HOJA = (210, 42, 48)        # páginas
HOJA_PASA = (232, 72, 76)


def libro(L, x, y, hoja_u):
    """Libro abierto todo rojo; hoja_u (0..1) pasa una página."""
    for lado in (-1, 1):
        tapa = [(x, y), (x + lado * 59, y - 10), (x + lado * 59, y + 50), (x, y + 59)]
        L.poligono(tapa, TAPA)
        hoja = [(x, y + 4), (x + lado * 53, y - 5), (x + lado * 53, y + 45), (x, y + 54)]
        L.poligono(hoja, HOJA)
    L.linea([(x, y + 4), (x, y + 54)], 2.0, (130, 18, 24))     # lomo
    if 0 < hoja_u < 1:
        k = math.cos(math.pi * hoja_u)                          # 1 derecha -> -1 izquierda
        alto = 8 * (1 - abs(k))
        pts = [(x, y + 4), (x + 53 * k, y - 5 - alto), (x + 53 * k, y + 45 - alto), (x, y + 54)]
        L.poligono(pts, HOJA_PASA)
        L.linea(pts[1:3], 1.6, (150, 25, 30))


def a_leyendo(L, t):
    col = (150, 190, 255)
    L.C = col
    dur = 4.8
    # los ojos recorren los renglones: van de izquierda a derecha y saltan de vuelta
    renglon = (t % 1.2) / 1.2
    lx = -0.05 + 0.5 * suave(renglon / 0.9) if renglon < 0.9 else 0.45 - 0.5 * suave((renglon - 0.9) / 0.1)
    c = cara(L, cx=128, cy=112, lx=lx, ly=0.4 + 0.05 * int(t / 1.2 % 4))
    ojos(L, c, w=14, h=20, parp=parpadeos(t, (3.3,)))
    # lentes redondos
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        pts = [(x + 17 * math.cos(a), y + 17 * math.sin(a)) for a in [2 * math.pi * i / 40 for i in range(41)]]
        L.linea(pts, 3.5, ARO)
    x1, y1 = c.ojo(-1)
    x2, y2 = c.ojo(1)
    L.linea([(x1 + 17, y1 - 3), (x2 - 17, y2 - 3)], 3.5, ARO)
    L.cara = None
    pasa = ((t % 2.4) - 2.0) / 0.4
    libro(L, 208, 168, pasa)


UNA_VEZ = {"despertar", "tacto_despertar"}      # cuentan una historia: se reproducen una vez

ANIMS = [
    ("pensando", a_pensando, 2.4),
    ("despertar", a_despertar, 2.4),
    ("conectando", a_conectando, 2.0),
    ("sin_conexion", a_sin_conexion, 3.2),
    ("saludo", a_saludo, 3.0),
    ("alarma", a_alarma, 2.4),
    ("temporizador", a_temporizador, 4.0),
    ("clima_sol", a_clima_sol, 4.8),
    ("clima_nube", a_clima_nube, 3.2),
    ("clima_lluvia", a_clima_lluvia, 2.4),
    ("pomodoro_trabajo", a_pomodoro_trabajo, 3.0),
    ("pomodoro_descanso", a_pomodoro_descanso, 3.0),
    ("presumido", a_presumido, 2.4),
    ("llamando", a_llamando, 3.0),
    ("tacto_cosquillas", a_tacto_cosquillas, 2.4),
    ("tacto_molesto", a_tacto_molesto, 2.4),
    ("tacto_despertar", a_tacto_despertar, 2.4),
    ("leyendo", a_leyendo, 4.8),
]


def cuadro(fn, t):
    L = mm.Lienzo((235, 235, 235))
    fn(L, t)
    return L.final()


def generar(salida):
    os.makedirs(salida, exist_ok=True)
    anims = {}
    total = 0
    for nombre, fn, dur in ANIMS:
        fr = [cuadro(fn, i / FPS) for i in range(int(round(dur * FPS)))]
        anims[nombre] = fr
        pal = fr[len(fr) // 2].quantize(colors=48, method=Image.Quantize.MEDIANCUT)
        q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in fr]
        ruta = os.path.join(salida, f"{nombre}.gif")
        repetir = {} if nombre in UNA_VEZ else {"loop": 0}      # las de una sola vez se quedan en la última imagen
        q[0].save(ruta, save_all=True, append_images=q[1:], duration=int(1000 / FPS), disposal=1, optimize=True,
                  **repetir)
        total += os.path.getsize(ruta)
    print(f"{len(ANIMS)} GIF, {total / 1024:.0f} KB en total")

    tmp = "/tmp/extras_grid"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    fnt = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    cols = 6
    filas = math.ceil(len(ANIMS) / cols)
    for i in range(int(9.6 * FPS)):
        hoja = Image.new("RGB", (320 * cols, 272 * filas), (14, 14, 14))
        d = ImageDraw.Draw(hoja)
        for k, (nombre, _, _) in enumerate(ANIMS):
            x, y = (k % cols) * 320, (k // cols) * 272
            fr = anims[nombre]
            hoja.paste(fr[i % len(fr)], (x, y))
            d.text((x + 160, y + 256), nombre, fill=(225, 225, 225), font=fnt, anchor="mm")
        hoja.save(f"{tmp}/{i:04d}.png")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", f"{tmp}/%04d.png",
                    "-vf", "scale=1920:-2,format=yuv420p", "-c:v", "libx264", "-crf", "21", "-preset", "veryfast",
                    os.path.join(salida, "mongobot_extras.mp4")], check=True)


if __name__ == "__main__":
    generar(sys.argv[1] if len(sys.argv) > 1 else "extras")
