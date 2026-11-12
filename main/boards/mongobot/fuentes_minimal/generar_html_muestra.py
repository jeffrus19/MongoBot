"""Genera un HTML de muestra con todas las animaciones de MongoBot (GIF incrustados).

Uso:  python generar_html_muestra.py <carpeta con los GIF> <archivo de salida.html>
"""
import base64
import html
import os
import sys

GRUPOS = [
    ("Emociones del servidor", "Las manda el servidor de XiaoZhi con cada respuesta.",
     "neutral happy laughing funny sad crying angry loving embarrassed surprised shocked thinking winking cool "
     "relaxed delicious kissy confident sleepy silly confused excited smug terrified"),
    ("Personalidad", "Las elige la IA con show_face (sarcasmo, presumir, enojo...).",
     "furioso rodar_ojos esceptico ofendido eureka picaro ignorando orgulloso curioso aburrido decepcionado "
     "presumido bostezo"),
    ("Conversación", "escuchando en la primera pregunta; conversa_escucha y conversa_habla en la conversación continua.",
     "escuchando conversa_escucha conversa_habla pensando despertar mirando llamando"),
    ("Inactividad", "Ejercicio mar-jue 9-10 y sáb-dom 8-11 · leyendo todos los días 8-20 · guitarra sáb-dom 10-17 · "
     "videojuego L-V 11-16 (sonido al 15 %). Pedidas por voz salen a cualquier hora.",
     "ejercicio leyendo guitarra videojuego musica"),
    ("Sistema y placa", "Arranque, conexión, volumen y pantalla táctil.",
     "saludo sin_conexion conectando configurar_wifi actualizando volumen tacto_cosquillas tacto_molesto "
     "tacto_despertar"),
    ("Funciones", "Alarmas, clima, mensajes y pomodoro.",
     "alarma temporizador recordatorio clima_sol clima_nube clima_lluvia mensaje pomodoro_trabajo pomodoro_descanso"),
    ("Temporada", "Navidad del 15 al 25 de diciembre; año nuevo el 31 y el 1.", "navidad anio_nuevo"),
]

ESTILO = """
:root{color-scheme:dark}
body{margin:0;background:#0d0d0f;color:#e8e8ea;font:15px/1.4 system-ui,-apple-system,"Segoe UI",sans-serif}
header{padding:28px 32px 8px} h1{margin:0;font-size:26px} header p{margin:6px 0 0;color:#9a9aa2}
input{margin-top:14px;width:260px;padding:8px 12px;border-radius:8px;border:1px solid #333;background:#18181b;color:inherit;font:inherit}
section{padding:10px 32px 18px} h2{font-size:18px;margin:18px 0 2px} h2 span{color:#777;font-weight:400;font-size:14px}
section>p{margin:0 0 12px;color:#9a9aa2;font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:14px}
figure{margin:0;background:#151518;border:1px solid #232327;border-radius:12px;padding:10px;text-align:center}
figure img{width:100%;aspect-ratio:4/3;object-fit:contain;border-radius:8px;background:#000}
figcaption{margin-top:6px;font-family:ui-monospace,Consolas,monospace;font-size:13px;user-select:all}
.oculto{display:none}
"""

FILTRO = """
document.getElementById('f').addEventListener('input',e=>{const q=e.target.value.trim().toLowerCase();
document.querySelectorAll('figure').forEach(f=>f.classList.toggle('oculto',!!q&&!f.textContent.includes(q)));
document.querySelectorAll('section').forEach(s=>s.classList.toggle('oculto',!s.querySelector('figure:not(.oculto)')));});
"""


def main(carpeta, salida):
    todas = {f[:-4] for f in os.listdir(carpeta) if f.endswith(".gif")}
    grupos = list(GRUPOS)
    usadas = [n for _, _, lista in grupos for n in lista.split()]
    faltan = [n for n in usadas if n not in todas]
    if faltan:
        sys.exit(f"faltan GIF: {faltan}")
    otras = sorted(todas - set(usadas))
    if otras:
        grupos.append(("Otras", "", " ".join(otras)))
    partes = []
    for titulo, desc, lista in grupos:
        nombres = lista.split()
        tarjetas = "".join(
            f'<figure><img src="data:image/gif;base64,'
            f'{base64.b64encode(open(os.path.join(carpeta, n + ".gif"), "rb").read()).decode()}" alt="{n}">'
            f"<figcaption>{n}</figcaption></figure>" for n in nombres)
        partes.append(f"<section><h2>{html.escape(titulo)} <span>{len(nombres)}</span></h2>"
                      f'<p>{html.escape(desc)}</p><div class="grid">{tarjetas}</div></section>')
    doc = (f'<!DOCTYPE html>\n<html lang="es"><head><meta charset="utf-8">'
           f'<meta name="viewport" content="width=device-width,initial-scale=1">'
           f"<title>MongoBot · {len(todas)} animaciones</title><style>{ESTILO}</style></head><body>"
           f"<header><h1>MongoBot · {len(todas)} animaciones</h1>"
           f"<p>Estilo minimalista. Tocá un nombre para seleccionarlo; es el que se usa con show_face.</p>"
           f'<input id="f" placeholder="Buscar por nombre…" autocomplete="off"></header>'
           f'{"".join(partes)}<script>{FILTRO}</script></body></html>')
    with open(salida, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"{len(todas)} animaciones -> {salida} ({os.path.getsize(salida) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
