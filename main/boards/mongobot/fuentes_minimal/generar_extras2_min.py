"""MongoBot minimalista: emociones de personalidad, transiciones, avisos y estados de la placa.

Uso:  python generar_extras2_min.py [carpeta_salida]

Emociones de personalidad: rodar_ojos, esceptico, ofendido, furioso, eureka,
picaro, ignorando, orgulloso, curioso, aburrido, decepcionado.
Transición: bostezo.  Avisos: recordatorio, mensaje.
Estados de la placa: configurar_wifi, actualizando, volumen.

Mismo estilo que el resto: aro siempre blanco, cara negra que gira sobre la
esfera, ojos del color de cada animación.
"""
import math
import os
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mongo_minimal as mm                 # noqa: E402
import generar_extras_min as gx            # noqa: E402
from mongo_minimal import ARO, CELESTE     # noqa: E402
from generar_extras_min import (cara, ojos, ojos_cerrados, ojos_felices, ondita, parpadeos,  # noqa: E402
                                rebote, suave, wifi)

FPS = 20
NEGRO = (0, 0, 0)


def pos_lado(c, lado):
    return c.ojo(lado)


# ---------------------------------------------------------------- emociones de personalidad

def a_rodar_ojos(L, t):
    """Pone los ojos en blanco: la mirada da la vuelta por arriba y vuelve, con un suspiro."""
    L.C = (200, 235, 90)
    if 0.3 <= t < 1.4:
        th = math.pi * (1 - suave((t - 0.3) / 1.1))      # de izquierda, por arriba, a derecha
        lx, ly = 0.55 * math.cos(th), -0.62 * math.sin(th)
    elif 1.4 <= t < 1.8:
        u = suave((t - 1.4) / 0.4)
        lx, ly = 0.55 * (1 - u), 0.0
    else:
        lx, ly = 0.0, 0.0
    suspiro = math.sin(math.pi * max(0, min(1, (t - 1.5) / 0.7)))
    c = cara(L, cy=124 + 4 * suspiro, sx=1 + 0.03 * suspiro, sy=1 - 0.03 * suspiro, lx=lx, ly=ly)
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        mm.parpado(L, c, x, y, cierre=0.4)
    mm.boca_plana(L, c, 8, dx=4, dy=4, inclina=-1.5)
    L.cara = None


def a_esceptico(L, t):
    """Un ojo normal con la ceja arriba y el otro entrecerrado en rayita: "mmm...". """
    L.C = (215, 205, 120)
    L.rot = math.radians(-5)
    c = cara(L, lx=0.22, ly=0.02)
    x, y = c.ojo(-1)
    sube = -6 * max(math.exp(-((t - 0.8) / 0.12) ** 2), math.exp(-((t - 1.15) / 0.12) ** 2))
    mm.ojo_rect(L, c, x, y, 18, 30 * parpadeos(t, (2.0,)))
    L.linea([(x - 11, y - 25 + sube), (x + 10, y - 29 + sube)], mm.TRAZO * 0.65)
    x, y = c.ojo(1)
    entrecierra = 1 + 0.15 * math.sin(2 * math.pi * t / 1.2)
    L.linea([(x - 11, y + 1), (x + 11, y - 3 * entrecierra)], mm.TRAZO * 0.75)
    L.linea([(x - 11, y - 12), (x + 11, y - 9)], mm.TRAZO * 0.6)
    mm.boca_plana(L, c, 7, dx=-3, dy=4, inclina=1.5)
    L.cara = None
    L.rot = 0
    for k in range(3):                                     # puntitos de "mmm"
        u = ((t / 1.2) - k * 0.18) % 1
        if u < 0.7:
            L.circulo(c.cx + c.rx + 12 + k * 10, c.cy - c.ry + 22, 3.2, L.C)


def a_ofendido(L, t):
    """"¿Perdón?": se echa para atrás de golpe, ojos grandes y quietos, cejas arriba."""
    L.C = (255, 120, 150)
    atras = suave((t - 0.25) / 0.15) * (1 - suave((t - 2.1) / 0.3))
    c = cara(L, r=80 * (1 - 0.1 * atras), cy=124 - 6 * atras)
    k = 1 + 0.18 * atras
    lento = parpadeos(t, (1.5,), dur=0.55)                 # parpadeo lento, indignado
    ojos(L, c, w=18 * k, h=30 * k, parp=lento)
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        L.linea([(x - 10, y - 24 - 6 * atras), (x + 10, y - 24 - 6 * atras)], mm.TRAZO * 0.6)
    L.cara = None
    if atras > 0.3:
        s = rebote((t - 0.3) / 0.3)
        mm.signo_pregunta(L, c.cx + c.rx + 14, c.cy - c.ry + 16, 0.9 * s, L.C)
        mm.signo_admiracion(L, c.cx + c.rx + 36, c.cy - c.ry + 18, 0.9 * s, L.C)


def a_furioso(L, t):
    """Más allá de angry: temblor fuerte, dientes apretados, vena y vapor por los dos lados."""
    L.C = (255, 40, 40)
    tiembla = 2.6 * math.sin(2 * math.pi * t / 0.06)
    resopla = abs(math.sin(2 * math.pi * t / 0.8))
    c = cara(L, cx=160 + tiembla, cy=126, sx=1.05 + 0.03 * resopla, sy=0.95 - 0.03 * resopla)
    ojos(L, c, w=18, h=16)
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        mm.ceja(L, x, y - 16, lado, 15, 15, mm.TRAZO * 0.85)
    # dientes apretados
    if mm.con_boca():
        x0, x1, y0, y1 = c.mx - 16, c.mx + 16, c.my - 2, c.my + 10
        L.d.rounded_rectangle((*L.T(x0, y0), *L.T(x1, y1)), radius=3 * mm.SS, fill=L.C)
        L.linea([(x0 + 2, (y0 + y1) / 2), (x1 - 2, (y0 + y1) / 2)], 1.6, NEGRO)
        for k in range(1, 4):
            xx = x0 + k * (x1 - x0) / 4
            L.linea([(xx, y0 + 1), (xx, y1 - 1)], 1.6, NEGRO)
    L.cara = None
    mm.vena(L, c.cx + c.rx - 4, c.cy - c.ry + 8, 1.2 + 0.25 * math.sin(2 * math.pi * t / 0.25))
    for lado in (-1, 1):                                   # vapor saliendo por los lados de arriba
        for k in range(3):
            u = ((t / 0.6) + k / 3) % 1
            x = c.cx + lado * (c.rx * 0.75 + 16 * u)
            y = c.cy - c.ry * 0.75 - 34 * u
            g = int(235 * (1 - u))
            L.circulo(x, y, 6 + 8 * u, (g, g, g))


def bombillo(L, x, y, k, prendido):
    if k <= 0.02:
        return
    col = (255, 230, 90) if prendido else (90, 90, 90)
    L.circulo(x, y, 15 * k, col)
    L.d.rounded_rectangle((*L.T(x - 7 * k, y + 11 * k), *L.T(x + 7 * k, y + 22 * k)), radius=2 * mm.SS, fill=ARO)
    L.linea([(x - 6 * k, y + 15 * k), (x + 6 * k, y + 15 * k)], 1.5, NEGRO)
    if prendido:
        for i in range(7):
            a = math.pi + math.pi * i / 6
            L.linea([(x + 21 * k * math.cos(a), y + 21 * k * math.sin(a)), (x + 30 * k * math.cos(a), y + 30 * k * math.sin(a))],
                    4, col)


def a_eureka(L, t):
    """Piensa mirando arriba y ¡zas!: se prende el bombillo, salta y abre los ojos.
    Al final el bombillo se apaga y vuelve a pensar, para cerrar el bucle."""
    L.C = (255, 230, 90)
    zas, vuelve = 0.7, 1.9
    if t < zas:
        c = cara(L, cy=138, lx=0.25, ly=-0.5)
        ojos(L, c, h=24)
        L.cara = None
        bombillo(L, 160, 30, 1.0, False)
        return
    u = t - zas
    salto = math.sin(math.pi * min(1, u / 0.35)) if u < 0.35 else 0
    f = suave((t - vuelve) / 0.5)                          # 0 -> 1 volviendo a pensar
    lx = 0.25 * f
    ly = -0.15 * (1 - suave(u / 0.5)) * (1 - f) - 0.5 * f
    c = cara(L, cy=138 - 12 * salto, sx=1 - 0.05 * salto, sy=1 + 0.07 * salto, lx=lx, ly=ly)
    k = 1.25 if u < 0.8 else 1.25 - 0.15 * suave((u - 0.8) / 0.3)
    k = k + (1.0 - k) * f
    alto = 30 * k + (24 - 30 * k) * f
    ojos(L, c, w=18 * k, h=alto)
    L.cara = None
    escala = 1.0 * (rebote(u / 0.25) if u < 0.25 else 1.0)
    bombillo(L, 160, 30 - 6 * salto, escala, f < 0.5)


def a_picaro(L, t):
    """Tramando algo: mira de reojo, un ojo más chiquito, sonrisa de lado y cejas que bailan."""
    L.C = (235, 110, 200)
    c = cara(L, lx=-0.4 + 0.05 * math.sin(2 * math.pi * t / 2.4), ly=0.05)
    baila = 4 * math.sin(2 * math.pi * t / 0.4) * (1 if 0.9 < t < 1.7 else 0)
    x, y = c.ojo(-1)
    mm.parpado(L, c, x, y, cierre=0.35)
    L.linea([(x - 10, y - 24 - baila), (x + 10, y - 22 - baila)], mm.TRAZO * 0.6)
    x, y = c.ojo(1)
    mm.parpado(L, c, x, y, cierre=0.65)
    L.linea([(x - 10, y - 18 + baila), (x + 10, y - 20 + baila)], mm.TRAZO * 0.6)
    mm.sonrisa_lado(L, c, -10)
    L.cara = None
    u = (t % 1.2) / 1.2
    mm.estrella4(L, c.cx - c.rx - 12, c.cy - 18, 9 * math.sin(math.pi * u), L.C)


def a_ignorando(L, t):
    """"No te hablo": voltea la cara casi hasta el borde y a ratos te mira de reojo."""
    L.C = (165, 175, 205)
    if 1.5 <= t < 2.1:
        u = (t - 1.5) / 0.6
        mirar = math.sin(math.pi * u)                    # se asoma y vuelve a voltear
    else:
        mirar = 0.0
    lx = 0.82 - 0.45 * mirar
    c = cara(L, lx=lx, ly=-0.25 + 0.15 * mirar)
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        if mirar > 0.4:
            mm.ojo_rect(L, c, x, y, 16, 22)
        else:
            L.linea(mm.bezier([(x - 9, y + 2), (x, y - 4), (x + 9, y + 2)]), mm.TRAZO * 0.75)
    L.cara = None
    if mirar < 0.2:                                         # "hmph"
        u = (t % 1.5) / 1.5
        for lado in (-1, 1):
            L.linea([(c.cx + c.rx + 6, c.cy - 4 + lado * 6), (c.cx + c.rx + 16 + 6 * u, c.cy - 4 + lado * 9)], 3,
                    tuple(int(v * (1 - u)) for v in L.C))


def a_orgulloso(L, t):
    """Satisfecho de sí mismo: cabeza arriba, ojos cerrados contentos, brillo detrás."""
    L.C = (255, 185, 70)
    hinchado = math.sin(math.pi * max(0, min(1, (t - 0.3) / 0.8)))
    c = cara(L, cy=128 - 4 * hinchado, sx=1 + 0.03 * hinchado, sy=1 + 0.03 * hinchado, ly=-0.35)
    ojos_felices(L, c)
    mm.sonrisa(L, c, 11, 6)
    L.cara = None
    for i in range(5):                                      # rayitos de orgullo arriba
        a = math.radians(-150 + 30 * i)
        k = 0.6 + 0.4 * math.sin(2 * math.pi * t / 1.2 + i)
        r0, r1 = c.rx + 10, c.rx + 10 + 16 * k
        L.linea([(c.cx + r0 * math.cos(a), c.cy + r0 * math.sin(a)), (c.cx + r1 * math.cos(a), c.cy + r1 * math.sin(a))], 4, L.C)
    u = (t % 2.4) / 2.4
    mm.estrella4(L, c.cx + c.rx + 22, c.cy + 10, 10 * math.sin(math.pi * u), (255, 255, 255))


def a_curioso(L, t):
    """Ladea la cabeza de un lado al otro con un vaivén suave; se le agranda el ojo del
    lado al que se inclina y le sale un signo de pregunta chiquito."""
    L.C = (90, 210, 230)
    vaiven = math.sin(2 * math.pi * t / 2.4)               # -1..1, cierra el bucle
    L.rot = math.radians(12 * vaiven)
    lado_t = 1 if vaiven >= 0 else -1
    c = cara(L, lx=0.25 * vaiven, ly=-0.1)
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        k = 1 + 0.22 * vaiven * lado
        mm.ojo_rect(L, c, x, y, 18 * k, 30 * k * parpadeos(t, (0.9,)))
    L.cara = None
    L.rot = 0
    s = max(0.0, (abs(vaiven) - 0.55) / 0.45)
    if s > 0.02:
        mm.signo_pregunta(L, c.cx + lado_t * (c.rx + 18), c.cy - c.ry + 14, 0.75 * rebote(s), L.C)


def a_aburrido(L, t):
    """Párpados caídos y un suspiro largo que le baja la cabeza."""
    L.C = (170, 170, 205)
    dur = 3.0
    suspiro = math.sin(math.pi * max(0, min(1, (t - 0.8) / 1.4)))
    c = cara(L, cy=126 + 8 * suspiro, sx=1 + 0.04 * suspiro, sy=1 - 0.05 * suspiro,
             lx=0.3 * math.sin(2 * math.pi * t / dur), ly=0.25)
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        mm.parpado(L, c, x, y, cierre=0.65)
    mm.boca_plana(L, c, 7, dy=6)
    L.cara = None
    if 1.0 < t < 2.4:                                       # el aire del suspiro
        u = (t - 1.0) / 1.4
        g = int(200 * (1 - u))
        for k in range(3):
            L.circulo(c.cx + c.rx * 0.5 + 20 * u + k * 8, c.cy + c.ry * 0.8 + 10 * u, 5 - k + 3 * u, (g, g, g))


def a_decepcionado(L, t):
    """"Meh": ojos planos que se hunden despacio, la cabeza baja un poquito."""
    L.C = (130, 150, 195)
    baja = suave(t / 1.0) * (1 - suave((t - 2.0) / 0.4))
    c = cara(L, cy=124 + 8 * baja, ly=0.2 * baja)
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        mm.ojo_rect(L, c, x, y + 5 * baja, 20, 10 - 2 * baja)
    mm.boca_plana(L, c, 9, dy=7 + 2 * baja, inclina=0)
    L.cara = None
    for k in range(3):                                      # "..." que se apagan
        u = max(0.0, min(1.0, (t - 0.6 - k * 0.25) / 0.3))
        g = int(180 * u * (1 - baja * 0.3))
        L.circulo(c.cx + c.rx + 14 + k * 10, c.cy + 24, 3.2, (g, g, g))


# ---------------------------------------------------------------- transición

def a_bostezo(L, t):
    """Aprieta los ojos, abre la boca grande estirando la cabeza, se le sale una lagrimita
    y termina con los ojos caídos."""
    L.C = (150, 150, 225)
    if t < 0.4:
        abre = 0.0
    elif t < 1.4:
        abre = suave((t - 0.4) / 0.7)
    else:
        abre = 1 - suave((t - 1.4) / 0.6)
    c = cara(L, cy=124 - 6 * abre, sx=1 - 0.05 * abre, sy=1 + 0.08 * abre, ly=-0.25 * abre)
    if abre > 0.25:
        for lado in (-1, 1):
            x, y = c.ojo(lado)
            L.linea([(x - 10, y - 2), (x + 10, y + 2 * lado * 0)], mm.TRAZO * 0.8)
        mm.boca_o(L, c, 6 + 9 * abre, dy=6 + 4 * abre)
    else:
        for lado in (-1, 1):
            x, y = c.ojo(lado)
            mm.parpado(L, c, x, y, cierre=0.55 if t > 1.8 else 0.2)
    L.cara = None
    if 1.3 < t < 2.4:                                       # lagrimita
        u = (t - 1.3) / 1.1
        x, y = c.ojo(1)
        mm.gota(L, x + 16, y + 4 + 14 * u, 4 * (1 - 0.4 * u))


# ---------------------------------------------------------------- avisos

def campana(L, x, y, ang, col):
    def P(px, py):
        return x + px * math.cos(ang) - py * math.sin(ang), y + px * math.sin(ang) + py * math.cos(ang)
    cuerpo = [P(-20, 24), P(-17, 4)] + [P(15 * math.cos(a), -6 + 15 * math.sin(a)) for a in
                                        [math.pi + math.pi * i / 16 for i in range(17)]] + [P(17, 4), P(20, 24)]
    L.poligono(cuerpo, col)
    L.circulo(*P(0, 30), 5, col)
    L.circulo(*P(0, -24), 3.5, col)


def a_recordatorio(L, t):
    L.C = (255, 190, 70)
    ang = math.radians(28 * math.sin(2 * math.pi * t / 0.5) * (1 if t < 1.6 else 0.25))
    c = cara(L, cx=140, cy=134, lx=0.4, ly=-0.4)
    ojos(L, c, w=18, h=32)
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        L.linea([(x - 9, y - 26), (x + 9, y - 27)], mm.TRAZO * 0.6)
    L.cara = None
    bx, by = 252, 52
    campana(L, bx, by, ang, L.C)
    if t < 1.6 and int(t * 8) % 2 == 0:                     # "ding"
        for lado in (-1, 1):
            for j in range(2):
                ondita(L, bx, by + 6, 30 + j * 9, (0 if lado > 0 else math.pi) - 0.4, (0 if lado > 0 else math.pi) + 0.4,
                       3, L.C)


def sobre(L, x, y, s, abierto=0.0):
    w, h = 40 * s, 28 * s
    L.d.rounded_rectangle((*L.T(x - w / 2, y - h / 2), *L.T(x + w / 2, y + h / 2)), radius=3 * mm.SS, fill=ARO)
    L.linea([(x - w / 2 + 3, y - h / 2 + 3), (x, y + 2 * s), (x + w / 2 - 3, y - h / 2 + 3)], 2.5 * s, NEGRO)
    if abierto > 0:
        L.poligono([(x - w / 2, y - h / 2), (x + w / 2, y - h / 2), (x, y - h / 2 - 16 * s * abierto)], ARO)


def a_mensaje(L, t):
    """Mensaje nuevo: un sobrecito llega volando con estela, rebota y le sale el aviso.
    Al final se achica y desaparece, y la mirada vuelve a donde entra el siguiente."""
    col = (90, 180, 240)
    L.C = col
    llega, se_va = 0.9, 1.9
    f = suave((t - se_va) / 0.5)                           # 0 -> 1 desapareciendo
    if t < llega:
        u = suave(t / llega)
        x = -30 + (244 + 30) * u
        y = 60 + 110 * (1 - (2 * u - 1) ** 2) * -0.6 + 110 * u
        s = 0.8 + 0.3 * u
    else:
        x, y, s = 244, 170, 1.1 * (1 - f)
        y -= 10 * abs(math.sin(math.pi * min(1, (t - llega) / 0.3))) * (1 if t - llega < 0.3 else 0)
    lx_obj = max(-0.6, min(0.6, (x - 140) / 180))
    ly_obj = max(-0.4, min(0.5, (y - 118) / 140))
    lx = lx_obj + (-0.6 - lx_obj) * f                      # vuelve a mirar por donde entra
    ly = ly_obj + (-0.41 - ly_obj) * f
    c = cara(L, cx=140, cy=118, lx=lx, ly=ly)
    k = 1.2 if t > llega + 0.2 else 1.0
    k = k + (1.0 - k) * f
    ojos(L, c, w=18 * k, h=30 * k)
    L.cara = None
    if t < llega:                                           # estela
        for i in range(5):
            uu = suave(max(0, t - 0.05 * (i + 1)) / llega)
            xx = -30 + 274 * uu
            yy = 60 + 110 * (1 - (2 * uu - 1) ** 2) * -0.6 + 110 * uu
            g = int(160 * (1 - i / 5))
            L.circulo(xx, yy, 4 - i * 0.6, (g, g, g))
    if s > 0.05:
        sobre(L, x, y, s)
    if t > llega + 0.15 and f < 0.95:                       # globito con el aviso
        k2 = rebote((t - llega - 0.15) / 0.3) if t - llega - 0.15 < 0.3 else 1.0
        k2 *= (1 - f)
        L.circulo(x + 22 * 1.1, y - 16 * 1.1, 9 * k2, col)
        if k2 > 0.3:
            L.linea([(x + 24.2, y - 17.6 - 5 * k2), (x + 24.2, y - 17.6 + 3 * k2)], 3 * k2, ARO)


# ---------------------------------------------------------------- estados de la placa

def a_configurar_wifi(L, t):
    """"Conectate a mí": MongoBot emite señal como punto de acceso y un celular se conecta."""
    col = (90, 220, 255)
    L.C = col
    c = cara(L, cx=130, cy=124, r=66, lx=0.2, ly=0.0)
    guino = 1.8 <= t < 2.4
    if guino:
        ojos(L, c, solo=-1)
        x, y = c.ojo(1)
        L.linea([(x - 9, y + 3), (x, y - 5), (x + 9, y + 3)], mm.TRAZO * 0.7)
    else:
        ojos(L, c, parp=parpadeos(t, (2.8,)))
    L.cara = None
    # ondas que salen de él (punto de acceso)
    for lado in (-1, 1):
        for j in range(3):
            u = ((t / 1.2) - j / 3) % 1
            r = c.rx + 8 + 30 * u
            g = tuple(int(v * (1 - u)) for v in col)
            ondita(L, c.cx, c.cy, r, (0 if lado > 0 else math.pi) - 0.45, (0 if lado > 0 else math.pi) + 0.45, 4, g)
    # celular que se va conectando
    px, py = 266, 150
    L.d.rounded_rectangle((*L.T(px - 18, py - 32), *L.T(px + 18, py + 32)), radius=6 * mm.SS, fill=ARO)
    L.d.rounded_rectangle((*L.T(px - 13, py - 25), *L.T(px + 13, py + 22)), radius=2 * mm.SS, fill=NEGRO)
    niveles = min(4, int((t / 0.5) % 6))
    wifi(L, px, py + 8, niveles, col, apagado=(50, 50, 50), escala=0.42)
    # flechita del celular hacia él
    u = (t % 1.2) / 1.2
    ax = px - 30 - 26 * u
    g = tuple(int(v * (1 - u)) for v in col)
    L.linea([(ax + 8, py - 4), (ax, py), (ax + 8, py + 4)], 3, g)


def engrane(L, x, y, r, giro, col):
    pts = []
    for i in range(32):
        a = giro + 2 * math.pi * i / 32
        rr = r if (i // 2) % 2 == 0 else r * 0.75
        pts.append((x + rr * math.cos(a), y + rr * math.sin(a)))
    L.poligono(pts, col)
    L.circulo(x, y, r * 0.35, NEGRO)


def a_actualizando(L, t):
    """Descargando firmware: cara concentrada, la barra de progreso llena el aro y un engrane gira."""
    col = (110, 170, 255)
    L.C = col
    dur = 4.0
    avance = suave(t / (dur - 0.4))
    c = cara(L, ly=0.15, lx=0.05 * math.sin(2 * math.pi * t / 2))
    for lado in (-1, 1):
        x, y = c.ojo(lado)
        mm.parpado(L, c, x, y, cierre=0.4)
    L.cara = None
    ri, re = c.rx * 0.74 + 1, c.rx - 1
    a0 = -math.pi / 2
    a1 = a0 + 2 * math.pi * avance
    if avance > 0.01:
        n = 80
        pts = [(c.cx + re * math.cos(a0 + (a1 - a0) * i / n), c.cy + re * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
        pts += [(c.cx + ri * math.cos(a1 - (a1 - a0) * i / n), c.cy + ri * math.sin(a1 - (a1 - a0) * i / n)) for i in range(n + 1)]
        L.poligono(pts, col)
    engrane(L, c.cx + c.rx + 20, c.cy - c.ry + 10, 14, 2 * math.pi * t / 2.0, col)
    # flechita de descarga que baja hacia la cabeza
    u = (t % 0.8) / 0.8
    ay = c.cy - c.ry - 30 + 14 * u
    g = tuple(int(v * (1 - u * 0.7)) for v in col)
    L.linea([(c.cx, ay - 14), (c.cx, ay)], 4, g)
    L.linea([(c.cx - 7, ay - 7), (c.cx, ay), (c.cx + 7, ay - 7)], 4, g)


def a_volumen(L, t):
    """Sube el volumen: las barritas crecen, salen ondas de sonido y los ojos se abren; luego baja."""
    col = (120, 235, 140)
    L.C = col
    dur = 2.4
    u = (t % dur) / dur
    nivel = 1 + 4 * (suave(u / 0.45) if u < 0.5 else 1 - suave((u - 0.55) / 0.45))
    c = cara(L, cx=130, cy=124, r=74, lx=0.25)
    k = 0.85 + 0.08 * nivel
    ojos(L, c, w=18 * k, h=30 * k)
    L.cara = None
    # barritas de volumen
    for i in range(5):
        h = 12 + i * 12
        x = 222 + i * 16
        y0 = 176
        lleno = nivel >= i + 1 - 0.05
        L.d.rounded_rectangle((*L.T(x - 5, y0 - h), *L.T(x + 5, y0)), radius=4 * mm.SS,
                              fill=col if lleno else (55, 55, 55))
    # ondas de sonido saliendo de él, más cuanto más volumen
    for j in range(int(nivel)):
        uu = ((t / 0.6) + j / 5) % 1
        r = c.rx + 6 + 22 * uu
        g = tuple(int(v * (1 - uu)) for v in col)
        ondita(L, c.cx, c.cy, r, math.pi - 0.5, math.pi + 0.5, 3.5, g)


ANIMS = [
    ("rodar_ojos", a_rodar_ojos, 2.4),
    ("esceptico", a_esceptico, 2.4),
    ("ofendido", a_ofendido, 2.4),
    ("furioso", a_furioso, 2.4),
    ("eureka", a_eureka, 2.4),
    ("picaro", a_picaro, 2.4),
    ("ignorando", a_ignorando, 3.0),
    ("orgulloso", a_orgulloso, 2.4),
    ("curioso", a_curioso, 2.4),
    ("aburrido", a_aburrido, 3.0),
    ("decepcionado", a_decepcionado, 2.4),
    ("bostezo", a_bostezo, 2.4),
    ("recordatorio", a_recordatorio, 2.4),
    ("mensaje", a_mensaje, 2.4),
    ("configurar_wifi", a_configurar_wifi, 3.6),
    ("actualizando", a_actualizando, 4.0),
    ("volumen", a_volumen, 2.4),
]


def cuadro(fn, t):
    mm.ACTUAL = fn.__name__[2:]          # a_furioso -> furioso (para SIN_BOCA)
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
        q[0].save(ruta, save_all=True, append_images=q[1:], duration=int(1000 / FPS), loop=0, disposal=1, optimize=True)
        total += os.path.getsize(ruta)
    print(f"{len(ANIMS)} GIF, {total / 1024:.0f} KB en total")
    tmp = "/tmp/extras2_grid"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    fnt = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    cols = 6
    filas = math.ceil(len(ANIMS) / cols)
    for i in range(int(7.2 * FPS)):
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
                    os.path.join(salida, "mongobot_extras2.mp4")], check=True)


if __name__ == "__main__":
    generar(sys.argv[1] if len(sys.argv) > 1 else "extras2")
