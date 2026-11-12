"""Prueba de consola de las animaciones de MongoBot.

Uso (desde la carpeta de py-xiaozhi):
    python scripts/probar_animaciones.py

Revisa, para cada animación del visor (assets/emojis/ver_animaciones.html):
- que la interfaz la encuentre igual que EmotionService (nombre + .gif en assets/emojis)
- que el GIF sea válido: tamaño 320x240, cantidad de cuadros y duración del bucle
Al final muestra un resumen y si falta algo. No necesita librerías extra.
"""
import re
import struct
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EMOJIS = RAIZ / "assets" / "emojis"
VISOR = EMOJIS / "ver_animaciones.html"
EXTENSIONES = (".gif", ".png", ".jpg", ".jpeg", ".webp")   # las mismas que EmotionService


def buscar(nombre):
    """Igual que EmotionService._find_emotion_file."""
    for ext in EXTENSIONES:
        p = EMOJIS / f"{nombre}{ext}"
        if p.exists():
            return p
    return None


def leer_gif(ruta):
    """Devuelve (ancho, alto, cuadros, duración en ms) leyendo el GIF a mano."""
    datos = ruta.read_bytes()
    if datos[:6] not in (b"GIF87a", b"GIF89a"):
        raise ValueError("no es un GIF")
    ancho, alto, banderas = struct.unpack("<HHB", datos[6:11])
    i = 13
    if banderas & 0x80:
        i += 3 * (2 ** ((banderas & 7) + 1))
    cuadros, duracion = 0, 0
    while i < len(datos):
        b = datos[i]
        if b == 0x3B:                                  # fin
            break
        if b == 0x21:                                  # extensión
            etiqueta = datos[i + 1]
            i += 2
            if etiqueta == 0xF9:                       # control gráfico: trae el retraso
                duracion += struct.unpack("<H", datos[i + 2:i + 4])[0] * 10
            while datos[i]:
                i += datos[i] + 1
            i += 1
        elif b == 0x2C:                                # imagen
            cuadros += 1
            banderas_img = datos[i + 9]
            i += 10
            if banderas_img & 0x80:
                i += 3 * (2 ** ((banderas_img & 7) + 1))
            i += 1                                     # tamaño mínimo LZW
            while datos[i]:
                i += datos[i] + 1
            i += 1
        else:
            raise ValueError(f"bloque desconocido 0x{b:02x} en {i}")
    return ancho, alto, cuadros, duracion


def main():
    if not VISOR.exists():
        print(f"No encuentro el visor: {VISOR}")
        return 1
    html = VISOR.read_text(encoding="utf-8")
    grupos = re.findall(r"<h2>(.*?) <span>\d+</span></h2>(.*?)</div>", html, re.S)
    total, malos, peso = 0, [], 0
    print(f"Carpeta: {EMOJIS}\n")
    for titulo, cuerpo in grupos:
        nombres = re.findall(r'src="([^"]+)\.gif"', cuerpo)
        print(f"== {titulo} ({len(nombres)})")
        for n in nombres:
            total += 1
            ruta = buscar(n)
            if ruta is None:
                print(f"   FALTA  {n}")
                malos.append(n)
                continue
            try:
                w, h, cuadros, ms = leer_gif(ruta)
            except Exception as e:                      # noqa: BLE001
                print(f"   MALO   {n}: {e}")
                malos.append(n)
                continue
            kb = ruta.stat().st_size / 1024
            peso += kb
            ok = (w, h) == (320, 240) and cuadros > 1
            marca = "ok   " if ok else "REVISAR"
            if not ok:
                malos.append(n)
            print(f"   {marca}  {n:<20} {w}x{h}  {cuadros:>3} cuadros  {ms / 1000:>4.1f} s  {kb:>6.1f} KB")
        print()
    print("-" * 64)
    print(f"Animaciones: {total}   Peso total: {peso / 1024:.2f} MB")
    if malos:
        print(f"Con problemas ({len(malos)}): {', '.join(malos)}")
        return 1
    print("Todo bien: la interfaz encuentra todas y los GIF son válidos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
