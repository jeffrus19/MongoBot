"""Caras de MongoBot (versión 2, estilo anime a color).

Uso:  python generar_caras2.py hoja.png [carpeta_salida] [carpeta_sueltas]

En carpeta_sueltas (por defecto "sueltas") puede ir una cara dibujada aparte,
con el nombre de la emoción (crying.png), y reemplaza a la de la hoja.

Recorta las 24 caras de la hoja (6 columnas x 4 filas), las lleva a 320x240
y genera un GIF animado por cara:
- parpadeo en las caras con ojos abiertos (en winking y funny solo el ojo abierto)
- espirales girando en confused, corazones latiendo en loving
- las zetas flotando en sleepy
- en crying las lágrimas corren y en la punta se forman gotas que caen
- en sad las gotitas bajo los ojos se estiran, caen y se vuelven a formar
- los corazones de happy, delicious y kissy laten
- las lagrimitas de laughing saltan con la risa, la estrella de winking
  titila y las cejas de cool suben y bajan
- un vaivén suave de 1 px en las demás
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
import cv2

W, H = 320, 240
FPS = 10
DUR = 3.0
N = int(DUR * FPS)

FILAS = [(30, 200), (300, 457), (533, 710), (774, 959)]
COLS = [(27, 237), (297, 508), (555, 769), (796, 1020), (1052, 1264), (1311, 1515)]
NOMBRES = ["angry", "confident", "confused", "cool", "crying", "delicious",
           "embarrassed", "funny", "happy", "kissy", "laughing", "loving",
           "neutral", "relaxed", "sad", "shocked", "silly", "sleepy",
           "surprised", "thinking", "winking", "excited", "smug", "terrified"]
VENTANA = (248, 186)   # recorte fijo en la hoja: misma escala para todas

# cajas de los ojos (en 320x240) para el parpadeo
OJOS = {
    "angry": [(49, 89, 130, 143), (199, 88, 285, 142)],
    "confident": [(26, 109, 114, 147), (182, 80, 264, 126)],
    "delicious": [(32, 100, 120, 147), (188, 97, 273, 135)],
    "embarrassed": [(53, 64, 127, 136), (200, 63, 273, 131)],
    "funny": [(43, 84, 120, 161)],
    "neutral": [(33, 106, 126, 155), (201, 100, 295, 151)],
    "relaxed": [(30, 109, 108, 151), (195, 101, 270, 136)],
    "shocked": [(44, 86, 118, 164), (190, 85, 263, 159)],
    "surprised": [(59, 63, 131, 137), (187, 61, 269, 144)],
    "thinking": [(30, 101, 113, 139), (182, 85, 262, 124)],
    "winking": [(45, 99, 117, 169)],
    "excited": [(40, 63, 121, 151), (191, 60, 275, 145)],
    "smug": [(38, 112, 127, 147), (195, 86, 279, 128)],
    "terrified": [(63, 70, 139, 158), (190, 67, 264, 153)],
}
GIRA = {"confused": [(68, 121, 47), (218, 113, 47)]}          # centro x, y, radio
# corazones que laten: caja y si se recorta por lo claro (ojos) o por lo rosado
LATE = {"loving": [((52, 57, 122, 121), "claro"), ((184, 56, 252, 117), "claro")],
        "happy": [((30, 156, 62, 192), "rosa")],
        "delicious": [((234, 147, 271, 182), "rosa")],
        "kissy": [((228, 132, 269, 176), "rosa")]}
# gotas que cuelgan bajo los ojos, se estiran, se sueltan y se vuelven a formar
# piezas que se mueven solas: caja, cómo se recortan y qué movimiento hacen
MUEVE = {
    "laughing": [((34, 103, 68, 129), "azul", "risa_izq"), ((246, 102, 280, 128), "azul", "risa_der")],
    "winking": [((260, 60, 300, 101), "blanco", "destello")],
    "cool": [((72, 57, 130, 75), "blanco", "ceja_izq"), ((170, 50, 227, 68), "blanco", "ceja_der")],
}
GOTEA = {"sad": [(36, 165, 60, 201), (236, 164, 264, 210)]}
FLOTA = {"sleepy": (222, 0, 305, 60)}
# lágrimas: zonas de los chorros y las puntas de donde caen las gotas
LLORA = {"crying": dict(chorros=[(40, 125, 121, 218), (203, 120, 282, 218)],
                        puntas=[(48, 215), (269, 216)])}


def recortar(hoja):
    caras = {}
    k = 0
    for y0, y1 in FILAS:
        for x0, x1 in COLS:
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            cw, ch = VENTANA
            box = (int(cx - cw / 2), int(cy - ch / 2), int(cx + cw / 2), int(cy + ch / 2))
            caras[NOMBRES[k]] = hoja.crop(box).resize((W, H), Image.LANCZOS)
            k += 1
    return caras


def cara_suelta(ruta):
    """Una cara dibujada aparte (con su nombre abajo, como en la hoja).
    Se encuadra con la misma escala que las de la hoja."""
    src = Image.open(ruta).convert("RGBA")
    fondo = Image.new("RGBA", src.size, (0, 0, 0, 255))
    fondo.alpha_composite(src)
    img = fondo.convert("RGB")
    lum = np.array(img).max(axis=2) > 60
    filas = np.nonzero(lum.sum(axis=1))[0]
    # la cara es el primer bloque de filas; el texto viene después de un hueco
    cortes = np.nonzero(np.diff(filas) > 15)[0]
    y1 = filas[cortes[0]] if len(cortes) else filas[-1]
    y0 = filas[0]
    cols = np.nonzero(lum[y0:y1 + 1].sum(axis=0))[0]
    x0, x1 = cols[0], cols[-1]
    cw = (x1 - x0) * 248 / 212          # misma proporción cara/ventana que en la hoja
    ch = cw * 0.75
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    box = (int(round(cx - cw / 2)), int(round(cy - ch / 2)),
           int(round(cx + cw / 2)), int(round(cy + ch / 2)))
    return img.crop(box).resize((W, H), Image.LANCZOS)


def ease(u):
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, u)))


def cierre(t, t0=1.6):
    """0 abierto, 1 cerrado. Un parpadeo rápido a t0."""
    dt = t - t0
    if 0 <= dt < 0.1:
        return ease(dt / 0.1)
    if 0.1 <= dt < 0.2:
        return 1.0
    if 0.2 <= dt < 0.35:
        return 1 - ease((dt - 0.2) / 0.15)
    return 0.0


def mascaras_ojos(img, cajas):
    a = np.array(img).astype(int)
    m = a.min(axis=2) > 170
    m = ndimage.binary_closing(m, iterations=2)
    m = ndimage.binary_fill_holes(m)
    lab, _ = ndimage.label(m)
    res = []
    for x0, y0, x1, y1 in cajas:
        sel = np.zeros_like(m)
        for i, c in enumerate(ndimage.center_of_mass(m, lab, range(1, lab.max() + 1))):
            cy, cx = c
            if x0 <= cx <= x1 and y0 <= cy <= y1:
                sel |= lab == i + 1
        sel = ndimage.binary_fill_holes(ndimage.binary_dilation(sel, iterations=3))
        ys, xs = np.nonzero(sel)
        res.append((sel, (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)))
    return res


def fondo_sin_ojos(img, ojos):
    """La cara sin los ojos: el hueco se rellena con lo que hay alrededor
    (rubor, sombras), para que al cerrar los ojos no quede un agujero negro."""
    m = np.zeros((H, W), np.uint8)
    for sel, _ in ojos:
        m[sel] = 255
    return Image.fromarray(cv2.inpaint(np.array(img), m, 5, cv2.INPAINT_TELEA))


def parpadear(img, plato, ojos, c):
    if c <= 0:
        return img
    out = plato.copy()
    d = ImageDraw.Draw(out)
    s = max(0.04, 1 - c)
    for sel, (x0, y0, x1, y1) in ojos:
        h = y1 - y0
        yc = y0 + 0.55 * h
        if c < 0.8:
            region = img.crop((x0, y0, x1, y1))
            msk = Image.fromarray((sel[y0:y1, x0:x1] * 255).astype(np.uint8))
            nh = max(1, int(round(h * s)))
            out.paste(region.resize((x1 - x0, nh), Image.LANCZOS),
                      (x0, int(round(yc - nh * 0.55))),
                      msk.resize((x1 - x0, nh), Image.LANCZOS))
        else:
            # ojo cerrado: una línea de pestañas con una curvita, como en sleepy
            pts = [(x0 + 4 + (x1 - x0 - 8) * u, yc + 5 * math.sin(math.pi * u))
                   for u in np.linspace(0, 1, 20)]
            d.line(pts, fill=(255, 255, 255), width=4, joint="curve")
    return out


def mascara_lagrimas(img, cajas):
    a = np.array(img).astype(int)
    r, b = a[..., 0], a[..., 2]
    azul = (b > 150) & (b - r > 40)
    m = np.zeros_like(azul)
    for x0, y0, x1, y1 in cajas:
        m[y0:y1, x0:x1] = azul[y0:y1, x0:x1]
    return m


def gota(d, x, y, r, estiramiento=1.0):
    """Gota celeste con brillo, como las del dibujo."""
    if r < 0.6:
        return
    ry = r * estiramiento
    d.ellipse((x - r, y - ry, x + r, y + ry), fill=(160, 219, 252))
    d.polygon([(x - r * 0.75, y - ry * 0.55), (x + r * 0.75, y - ry * 0.55), (x, y - ry * 2.0)],
              fill=(160, 219, 252))
    d.ellipse((x - r * 0.55, y - ry * 0.45, x - r * 0.05, y + ry * 0.05), fill=(235, 250, 255))


def llorar(img, cfg, mascara, t):
    # 1. el chorro corre: bandas de luz que bajan por las lágrimas
    a = np.array(img).astype(float)
    yy, xx = np.mgrid[0:H, 0:W]
    fase = (yy - 40 * t) / 20 + 0.015 * xx
    luz = np.clip(np.cos(2 * np.pi * fase), 0, 1) ** 6 * 0.55
    luz = luz * mascara
    claro = np.array([228, 246, 255], float)
    a = a * (1 - luz[..., None]) + claro * luz[..., None]
    out = Image.fromarray(a.astype(np.uint8))
    # 2. en la punta de cada chorro se forma una gota que crece y cae
    d = ImageDraw.Draw(out)
    for k, (x, y) in enumerate(cfg["puntas"]):
        u = ((t + k * DUR / 2) % DUR) / (DUR / 2)   # dos gotas por lado en cada bucle
        u = u % 1.0
        if u < 0.75:                                # se va llenando
            r = 5.0 * base_ease(u / 0.75)
            gota(d, x, y + r * 0.6, r, 1.1)
        else:                                       # se suelta y cae
            v = (u - 0.75) / 0.25
            gota(d, x, y + 4 + 30 * v * v, 5.0, 1.3)
    return out


def base_ease(u):
    return ease(u)


def girar(img, discos, t):
    out = img.copy()
    ang = -360 * t / DUR
    for cx, cy, r in discos:
        box = (cx - r, cy - r, cx + r, cy + r)
        reg = img.crop(box).rotate(ang, resample=Image.BICUBIC)
        m = Image.new("L", (2 * r, 2 * r), 0)
        ImageDraw.Draw(m).ellipse((0, 0, 2 * r - 1, 2 * r - 1), fill=255)
        out.paste(reg, box[:2], m)
    return out


def latir(f, img, cajas, t):
    """Late como corazón: dos golpecitos por segundo (pum-pum... pausa)."""
    out = f.copy()
    beat = t % 1.0
    esc = 1 + 0.12 * (math.exp(-((beat - 0.1) / 0.07) ** 2) + 0.6 * math.exp(-((beat - 0.3) / 0.07) ** 2))
    for (x0, y0, x1, y1), tipo in cajas:
        reg = img.crop((x0, y0, x1, y1))
        w, h = x1 - x0, y1 - y0
        nw, nh = int(round(w * esc)), int(round(h * esc))
        reg2 = reg.resize((nw, nh), Image.LANCZOS)
        a2 = np.array(reg2).astype(int)
        if tipo == "rosa":
            r, g, b = a2[..., 0], a2[..., 1], a2[..., 2]
            sel = (r > 120) & (r - g > 40)
            sel = ndimage.binary_dilation(ndimage.binary_fill_holes(sel), iterations=1)
        else:
            sel = a2.max(axis=2) > 40
        m = Image.fromarray((sel * 255).astype(np.uint8))
        out.paste(reg2, (int(round(x0 + w / 2 - nw / 2)), int(round(y0 + h / 2 - nh / 2))), m)
    return out


def gotear(f, img, cajas, t):
    """La gota que cuelga se va estirando, se suelta y cae; enseguida se
    empieza a formar otra. Un lado va medio bucle atrasado del otro."""
    out = f.copy()
    d = ImageDraw.Draw(out)
    for k, (x0, y0, x1, y1) in enumerate(cajas):
        u = ((t / DUR) + k * 0.5) % 1.0
        reg = img.crop((x0, y0, x1, y1))
        w, h = x1 - x0, y1 - y0
        d.rectangle((x0, y0, x1 - 1, y1 - 1), fill=(0, 0, 0))
        if u < 0.7:                                  # se estira despacio
            e = 1 + 0.25 * ease(u / 0.7)
            out.paste(reg.resize((w, int(h * e)), Image.LANCZOS), (x0, y0))
        else:
            v = (u - 0.7) / 0.3
            caida = 120 * min(1.0, v / 0.45) ** 2     # la gota suelta cae rápido
            out.paste(reg, (x0, int(y0 + h * 0.25 + caida)))
            e = 0.15 + 0.85 * ease(v)                 # y arriba se forma la nueva
            nueva = reg.resize((w, max(1, int(h * e))), Image.LANCZOS)
            out.paste(nueva, (x0, y0))
    return out


def cejas_cool(t, lado):
    """Sube y baja las cejas dos veces rápido (las dos), y más tarde solo la
    derecha se queda arriba un rato, con cara de "¿ah, sí?"."""
    dy = 0.0
    for t0 in (0.5, 0.8):                      # dos subidas rápidas
        u = (t - t0) / 0.28
        if 0 <= u < 1:
            dy = -8 * math.sin(math.pi * u)
    if lado == "der":
        u = t - 1.8
        if 0 <= u < 0.15:
            dy = -9 * ease(u / 0.15)
        elif 0.15 <= u < 0.85:
            dy = -9
        elif 0.85 <= u < 1.05:
            dy = -9 * (1 - ease((u - 0.85) / 0.2))
    return dy


def movimiento(tipo, t):
    """(dx, dy, escala, giro) de cada pieza en el instante t."""
    if tipo.startswith("risa"):
        # las lagrimitas saltan hacia afuera al ritmo de la carcajada
        sale = -1 if tipo.endswith("izq") else 1
        golpe = abs(math.sin(2 * math.pi * 2.5 * t))
        return sale * 3 * golpe, -3 * golpe, 1 + 0.08 * golpe, 0
    if tipo == "destello":
        # la estrella titila: crece, gira un poco y vuelve
        u = (t % 1.5) / 1.5
        brillo = math.exp(-((u - 0.25) / 0.12) ** 2)
        return 0, 0, 0.85 + 0.4 * brillo, 25 * brillo
    if tipo.startswith("ceja"):
        return 0, cejas_cool(t, tipo.split("_")[1]), 1, 0
    return 0, 0, 1, 0


def mover(f, img, piezas, t):
    out = f.copy()
    arr = np.array(out)
    for (x0, y0, x1, y1), recorte, tipo in piezas:
        reg = img.crop((x0, y0, x1, y1))
        a = np.array(reg).astype(int)
        if recorte == "azul":
            sel = (a[..., 2] > 150) & (a[..., 2] - a[..., 0] > 30)
            sel = ndimage.binary_dilation(sel, iterations=2)
        else:
            sel = a.max(axis=2) > 50
        # se borra la pieza de su lugar
        sub = arr[y0:y1, x0:x1]
        sub[sel] = 0
        arr[y0:y1, x0:x1] = sub
        out = Image.fromarray(arr)
        dx, dy, esc, giro = movimiento(tipo, t)
        rgba = reg.convert("RGBA")
        rgba.putalpha(Image.fromarray((sel * 255).astype(np.uint8)))
        w, h = rgba.size
        if esc != 1 or giro:
            rgba = rgba.resize((max(1, int(w * esc)), max(1, int(h * esc))), Image.LANCZOS)
            rgba = rgba.rotate(giro, resample=Image.BICUBIC, expand=True)
        nw, nh = rgba.size
        px = int(round(x0 + w / 2 - nw / 2 + dx))
        py = int(round(y0 + h / 2 - nh / 2 + dy))
        out.paste(rgba, (px, py), rgba)
        arr = np.array(out)
    return out


def flotar(img, caja, t):
    out = img.copy()
    x0, y0, x1, y1 = caja
    reg = img.crop(caja)
    dy = int(round(-3 * math.sin(2 * math.pi * t / DUR)))
    dx = int(round(2 * math.sin(4 * math.pi * t / DUR)))
    ImageDraw.Draw(out).rectangle(caja, fill=(0, 0, 0))
    out.paste(reg, (x0 + dx, y0 + dy))
    return out


def vaiven(img, t):
    dy = 1 if math.sin(2 * math.pi * t / DUR) > 0 else 0
    if dy == 0:
        return img
    out = Image.new("RGB", (W, H), (0, 0, 0))
    out.paste(img, (0, -dy))
    return out


def animar(nombre, img):
    ojos = mascaras_ojos(img, OJOS[nombre]) if nombre in OJOS else None
    plato = fondo_sin_ojos(img, ojos) if ojos else None
    lagrimas = mascara_lagrimas(img, LLORA[nombre]["chorros"]) if nombre in LLORA else None
    cuadros = []
    for i in range(N):
        t = i / FPS
        f = img
        if ojos:
            f = parpadear(img, plato, ojos, cierre(t))
        if nombre in LLORA:
            f = llorar(f, LLORA[nombre], lagrimas, t)
        if nombre in GIRA:
            f = girar(f, GIRA[nombre], t)
        if nombre in LATE:
            f = latir(f, img, LATE[nombre], t)
        if nombre in GOTEA:
            f = gotear(f, img, GOTEA[nombre], t)
        if nombre in FLOTA:
            f = flotar(f, FLOTA[nombre], t)
        if nombre in MUEVE:
            f = mover(f, img, MUEVE[nombre], t)
        quieta = not (ojos or any(nombre in d for d in (LLORA, GIRA, LATE, GOTEA, FLOTA, MUEVE)))
        if quieta:
            f = vaiven(img, t)
        cuadros.append(f)
    return cuadros


def guardar_gif(cuadros, ruta):
    pal = cuadros[0].quantize(colors=64, method=Image.Quantize.MEDIANCUT)
    q = [c.quantize(palette=pal, dither=Image.Dither.NONE) for c in cuadros]
    q[0].save(ruta, save_all=True, append_images=q[1:], duration=int(1000 / FPS), loop=0,
              disposal=1, optimize=True)


def generar(hoja_ruta, salida, sueltas=None):
    """sueltas: carpeta con caras dibujadas aparte (crying.png, ...) que
    reemplazan a las de la hoja."""
    os.makedirs(salida, exist_ok=True)
    caras = recortar(Image.open(hoja_ruta).convert("RGB"))
    if sueltas and os.path.isdir(sueltas):
        for f in os.listdir(sueltas):
            n = os.path.splitext(f)[0]
            if n in caras:
                caras[n] = cara_suelta(os.path.join(sueltas, f))
                print(f"{n}: usando {f}")
    total = 0
    for n in NOMBRES:
        ruta = os.path.join(salida, f"{n}.gif")
        guardar_gif(animar(n, caras[n]), ruta)
        total += os.path.getsize(ruta)
    print(f"{len(NOMBRES)} GIF, {total / 1024:.0f} KB en total")


if __name__ == "__main__":
    generar(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "caras2",
            sys.argv[3] if len(sys.argv) > 3 else "sueltas")
