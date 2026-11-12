"""Matriz de disparadores: prueba, para cada una de las animaciones de MongoBot,
todos los caminos que la activan en py-xiaozhi (sin servidor ni audio).

Uso (desde la carpeta de py-xiaozhi):
    python scripts/probar_disparadores.py
"""
import asyncio, json, os, re, sys
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, '.')
from datetime import date, datetime
import random
from src.constants.constants import DeviceState as S
from src.plugins.ui_presenter import UiPresenter
from src.plugins import mongo_caras, mongo_alarmas, mongo_comportamiento as mc

# Las pruebas no dependen de la hora en que se corran: por defecto, jueves 12:00.
from datetime import datetime as _dt
_init_real = mc.Comportamiento.__init__
def _init_fijo(self, *a, momento=None, **k):
    _init_real(self, *a, momento=momento or (lambda: _dt(2026, 11, 12, 12, 0)), **k)
mc.Comportamiento.__init__ = _init_fijo


SERVIDOR = ["neutral","happy","laughing","funny","sad","angry","crying","loving","embarrassed","surprised","shocked",
            "thinking","winking","cool","relaxed","delicious","kissy","confident","sleepy","silly","confused"]
SOLO_PLACA = {"conectando": "conectando al WiFi (placa)", "configurar_wifi": "modo punto de acceso (placa)",
              "actualizando": "actualización de firmware (placa)", "tacto_cosquillas": "tocar la pantalla (placa)",
              "tacto_molesto": "tocar mucho la pantalla (placa)", "tacto_despertar": "tocarlo dormido (placa)",
              "mensaje": "mensaje de Telegram (función futura)", "pomodoro_trabajo": "pomodoro (función futura)",
              "pomodoro_descanso": "pomodoro (función futura)"}

class Pantalla:
    def __init__(self): self.cara=None
    def set_emotion(self, e): self.cara=e
    def set_chat_text(self, t): pass
    def set_status(self, *a): pass
    def set_music_line(self, t): pass

resultados = {}   # animación -> [(camino, ok, detalle)]
def anotar(anim, camino, ok, detalle=""):
    resultados.setdefault(anim, []).append((camino, ok, detalle))

def nuevo():
    mongo_caras.soltar(); mongo_alarmas._sonando = None
    pan = Pantalla(); pres = UiPresenter(pan); return pan, pres

async def main():
    todas = sorted(p[:-4] for p in os.listdir('assets/emojis') if p.endswith('.gif'))

    # 1) emociones que manda el servidor, durante la respuesta
    for e in SERVIDOR:
        pan, pres = nuevo()
        pres.show_device_state(S.LISTENING); pres.show_protocol_message({"type":"stt","text":"pregunta"})
        pres.show_device_state(S.SPEAKING); pres.show_protocol_message({"type":"llm","emotion":e})
        esperado = "conversa_habla" if e == "neutral" else e
        anotar(e if e != "neutral" else "conversa_habla", f"servidor manda '{e}'", pan.cara == esperado, pan.cara)
        if e != "neutral":
            pres.show_device_state(S.IDLE)
            anotar(e, "al terminar vuelve a reposo", pan.cara == "neutral", pan.cara)

    # 2) herramienta show_face: todas las animaciones
    from src.mcp.tools.cara import register_cara_tools
    tools = {}; register_cara_tools(lambda t: tools.__setitem__(t.name, t))
    for a in todas:
        pan, pres = nuevo()
        t = tools["self.screen.show_face"]
        r = json.loads(await t.callback(t.properties.parse_arguments({"face": a, "seconds": 2})))
        anotar(a, "show_face", r.get("ok") and pan.cara == a, pan.cara)
    mongo_caras.soltar()

    # 3) capa de comportamiento
    pan, pres = nuevo()
    pres.show_device_state(S.LISTENING); anotar("escuchando", "primera pregunta", pan.cara == "escuchando", pan.cara)
    pres.show_protocol_message({"type":"stt","text":"hola"}); anotar("pensando", "llega lo que dijiste (stt)", pan.cara == "pensando", pan.cara)
    pres.show_device_state(S.SPEAKING); anotar("conversa_habla", "estado hablando sin emoción", pan.cara == "conversa_habla", pan.cara)
    pres.show_device_state(S.LISTENING); anotar("conversa_escucha", "conversación continua", pan.cara == "conversa_escucha", pan.cara)
    pres.show_device_state(S.SPEAKING)
    for i in range(3):
        pres.show_device_state(S.LISTENING); pres.show_device_state(S.SPEAKING); pres.show_protocol_message({"type":"llm","emotion":"angry"})
    anotar("furioso", "tres 'angry' seguidos", pan.cara == "furioso", pan.cara)
    pres.show_device_state(S.IDLE); pres.show_network_error()
    mc.hay_internet = lambda: False; await mc.actual().verificar_red()
    anotar("sin_conexion", "error de red en espera", pan.cara == "sin_conexion", pan.cara)
    mc.actual()._dormido = True; mc.actual()._sin_red = False; mc.actual()._fin_respuesta = float("-inf")
    pres.show_device_state(S.LISTENING); anotar("despertar", "le hablás dormido", pan.cara == "despertar", pan.cara)
    await asyncio.sleep(1.6); anotar("escuchando", "después de despertar", pan.cara == "escuchando", pan.cara)
    pres.show_device_state(S.IDLE)
    from src.mcp.tools.music.events import MusicStateData
    pres.show_music_state(MusicStateData(state="playing", song="Canción", position=0, duration=180))
    anotar("musica", "suena una canción", pan.cara == "musica", pan.cara)

    # inactividad con reloj acelerado
    vistas = {}
    reloj=[0.0]
    jueves = lambda: datetime(2026, 11, 12, 12, 0)       # jueves 12:00: ejercicio, leyendo y videojuego
    c = mc.Comportamiento(lambda e: vistas.setdefault(e, reloj[0]), reloj=lambda: reloj[0], hoy=lambda: date(2026,11,12),
                          azar=random.Random(1), momento=jueves)
    c.inicio()
    for s in range(720): reloj[0]=float(s); c.tic()
    for a, desc in [("saludo","al arrancar"),("aburrido","1 min sin hablarle"),("mirando","entre actividades"),
                    ("llamando","cada 3 actividades"),("bostezo","a los 10 min"),("sleepy","después del bostezo"),
                    ("leyendo","inactividad 8:00-20:00")]:
        anotar(a, desc, a in vistas, f"min {vistas[a]/60:.1f}" if a in vistas else "no salió")
    # horarios: qué actividades salen en cada momento (en ~10 min de inactividad)
    E, L, G, V = "ejercicio", "leyendo", "guitarra", "videojuego"
    for cuando, esperado in ((datetime(2026,11,12,12,0), {L,V}),     # jueves mediodía
                             (datetime(2026,11,12,9,30), {E,L}),     # jueves, hora de ejercicio
                             (datetime(2026,11,12,10,30), {L}),      # jueves antes del videojuego
                             (datetime(2026,11,12,16,0), {L}),       # jueves después del videojuego
                             (datetime(2026,11,16,9,30), {L}),       # lunes: no hay ejercicio
                             (datetime(2026,11,20,9,30), {L}),       # viernes: no hay ejercicio
                             (datetime(2026,11,14,9,0), {E,L}),      # sábado temprano
                             (datetime(2026,11,14,11,0), {L,G}),     # sábado: termina el ejercicio
                             (datetime(2026,11,15,10,30), {E,L,G}),  # domingo: ejercicio y guitarra
                             (datetime(2026,11,15,17,0), {L}),       # domingo ya sin guitarra
                             (datetime(2026,11,16,7,59), set()),     # lunes muy temprano
                             (datetime(2026,11,16,20,0), set())):    # lunes de noche
        vistas3=set(); r3=[0.0]
        c3 = mc.Comportamiento(vistas3.add, reloj=lambda: r3[0], hoy=lambda: cuando.date(), azar=random.Random(2), momento=lambda c=cuando: c)
        c3.inicio()
        for s in range(590): r3[0]=float(s); c3.tic()
        salieron = vistas3 & {E,L,G,V}
        ok = salieron == esperado and (esperado or "mirando" in vistas3)
        for a in (esperado or {"mirando"}):
            anotar(a, f"{cuando:%a %H:%M}", ok, ",".join(sorted(salieron)) or "nada")
    for d, a in [(date(2026,12,20),"navidad"),(date(2026,12,31),"anio_nuevo")]:
        vistas2=[]; r2=[0.0]
        c2 = mc.Comportamiento(vistas2.append, reloj=lambda: r2[0], hoy=lambda d=d: d); c2.inicio()
        for s in range(10): r2[0]=float(s); c2.tic()
        anotar(a, f"reposo el {d.day}/{d.month}", a in vistas2, ",".join(vistas2))

    # 4) alarmas
    for tipo in ("alarma","temporizador","recordatorio"):
        pan, pres = nuevo()
        from src.mcp.tools.alarmas import register_alarma_tools
        t2={}; register_alarma_tools(lambda t: t2.__setitem__(t.name,t))
        nombre={"alarma":"self.alarm.set_alarm","temporizador":"self.alarm.set_timer","recordatorio":"self.alarm.set_reminder"}[tipo]
        args={"alarma":{"time":"23:59"},"temporizador":{"minutes":5},"recordatorio":{"text":"x","in_minutes":5}}[tipo]
        tool=t2[nombre]; await tool.callback(tool.properties.parse_arguments(args))
        anotar(tipo, "al programarla", pan.cara == tipo, pan.cara)
        mongo_caras.soltar()
        enviados=[]
        async def env(x): enviados.append(x)
        mongo_alarmas.conectar_envio(env)
        await mongo_alarmas._gritar({"tipo":tipo,"texto":"x"}, 1)
        anotar("alarma" if tipo!="recordatorio" else "recordatorio", f"cuando suena ({tipo})", pan.cara in ("alarma","recordatorio"), f"{pan.cara}; aviso: {enviados[-1]}")
    mongo_alarmas.cancelar("all"); mongo_caras.soltar()

    # 5) volumen y clima (herramientas)
    pan, pres = nuevo()
    from src.mcp.tools.volume import register_volume_tools
    class Ctl:
        def set_volume(self, v): pass
        def get_volume(self): return 50
    tv={}; register_volume_tools(lambda t: tv.__setitem__(t.name,t), Ctl())
    tool=tv["self.audio_speaker.set_volume"]; await tool.callback(tool.properties.parse_arguments({"volume":70}))
    anotar("volumen", "le cambiás el volumen", pan.cara == "volumen", pan.cara)
    mongo_caras.soltar()
    from src.mcp.tools.weather import service as w
    from src.mcp.tools.weather.register import register_weather_tools
    tw={}; register_weather_tools(lambda t: tw.__setitem__(t.name,t))
    for codigo, cara in ((0,"clima_sol"),(3,"clima_nube"),(63,"clima_lluvia")):
        w._get_json = lambda url, params, timeout=8.0, c=codigo: ({"results":[{"name":"San José","country":"Costa Rica","country_code":"CR","latitude":9.9,"longitude":-84.1}]} if "geocoding" in url else {"current":{"weather_code":c,"temperature_2m":24}})
        pan, pres = nuevo()
        tool=tw["get_weather"]; await tool.callback(tool.properties.parse_arguments({}))
        anotar(cara, f"pregunta del clima (código {codigo})", pan.cara == cara, pan.cara)
    mongo_caras.soltar()

    # informe
    print(f"{'ANIMACIÓN':<20} {'CAMINOS':>7}  RESULTADO")
    fallos = 0; sin_disparador = []
    for a in todas:
        caminos = resultados.get(a, [])
        propios = [x for x in caminos if x[0] != "show_face"]
        mal = [x for x in caminos if not x[1]]
        fallos += len(mal)
        estado = "FALLA" if mal else ("ok" if propios else "solo show_face")
        if not propios: sin_disparador.append(a)
        detalle = "; ".join(f"{c}" for c, ok, d in propios) or SOLO_PLACA.get(a, "solo se puede pedir con show_face")
        print(f"{a:<20} {len(caminos):>7}  {estado:<15} {detalle}")
        for c, ok, d in mal:
            print(f"{'':<30}FALLA en '{c}': quedó {d}")
    print(f"\n{len(todas)} animaciones, {sum(len(v) for v in resultados.values())} pruebas, {fallos} fallas")
    print(f"Sin disparador propio en la PC ({len(sin_disparador)}): {', '.join(sin_disparador)}")

asyncio.run(main())
