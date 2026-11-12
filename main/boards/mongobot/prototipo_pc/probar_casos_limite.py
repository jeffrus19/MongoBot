"""Prueba 3: casos raros de MongoBot (sin servidor ni audio).

Uso (desde la carpeta de py-xiaozhi):
    python scripts/probar_casos_limite.py
"""
import asyncio, json, os, sys
from datetime import datetime
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, '.')
from src.constants.constants import DeviceState as S
from src.plugins.ui_presenter import UiPresenter
from src.plugins import mongo_caras, mongo_alarmas, mongo_comportamiento as mc

# Las pruebas no dependen de la hora en que se corran: por defecto, jueves 12:00.
from datetime import datetime as _dt
_init_real = mc.Comportamiento.__init__
def _init_fijo(self, *a, momento=None, **k):
    _init_real(self, *a, momento=momento or (lambda: _dt(2026, 11, 12, 12, 0)), **k)
mc.Comportamiento.__init__ = _init_fijo

from src.mcp.tools.cara import register_cara_tools
from src.mcp.tools.music.events import MusicStateData

class Pantalla:
    def __init__(self): self.cara=None; self.historial=[]
    def set_emotion(self, e): self.cara=e; self.historial.append(e)
    def set_chat_text(self, t): pass
    def set_status(self, *a): pass
    def set_music_line(self, t): pass

sonidos = []
mongo_caras._sonido = lambda nombre, encender, suave=False: sonidos.append((nombre, encender) if not encender else (nombre, encender, suave))

ok_total = fallas = 0
def ver(desc, real, esperado):
    global ok_total, fallas
    bien = real == esperado
    ok_total += bien; fallas += not bien
    print(f"  {'ok   ' if bien else 'FALLA'} {desc}: {real}" + ("" if bien else f"  (esperaba {esperado})"))

def nuevo():
    mongo_caras.soltar(); mongo_alarmas._sonando = None; sonidos.clear()
    pan = Pantalla(); pres = UiPresenter(pan); pres.show_device_state(S.IDLE); return pan, pres

tools = {}; register_cara_tools(lambda t: tools.__setitem__(t.name, t))
async def cara(nombre, seg=8):
    t = tools["self.screen.show_face"]
    try:
        args = t.properties.parse_arguments({"face": nombre, "seconds": seg})
    except Exception as e:
        return {"ok": False, "error": f"argumentos: {e}"}
    return json.loads(await t.callback(args))

async def main():
    print("1. Modo automático: pide guitarra, termina de hablar y sigue escuchando")
    pan, pres = nuevo()
    pres.show_device_state(S.LISTENING); pres.show_protocol_message({"type":"stt","text":"tocá guitarra"})
    await cara("guitarra", 20); pres.show_device_state(S.SPEAKING)
    pres.show_protocol_message({"type":"llm","emotion":"happy"})
    ver("mientras habla", pan.cara, "guitarra")
    pres.show_device_state(S.LISTENING)
    ver("vuelve a escuchar solo (sigue la guitarra)", pan.cara, "guitarra")
    pres.show_protocol_message({"type":"stt","text":"ya, pará"})
    ver("le volvés a hablar", pan.cara, "pensando")

    print("2. Conversación nueva desde reposo con una cara pedida")
    pan, pres = nuevo()
    await cara("presumido", 20); pres.show_device_state(S.LISTENING)
    ver("lo llamás", pan.cara, "escuchando")

    print("3. Alarma mientras duerme")
    pan, pres = nuevo()
    mc.actual()._dormido = True
    enviados = []
    async def env(x): enviados.append(x)
    mongo_alarmas.conectar_envio(env)
    it = {"tipo":"alarma","texto":"gimnasio"}
    mongo_alarmas._sonando = {"item": it, "veces": 1, "ultimo": 0}
    await mongo_alarmas._gritar(it, 1)
    ver("suena", pan.cara, "alarma")
    pres.show_device_state(S.LISTENING); pres.show_protocol_message({"type":"stt","text":enviados[-1]})
    ver("el aviso entra como si le hablaran", pan.cara, "alarma")
    pres.show_device_state(S.SPEAKING); pres.show_protocol_message({"type":"llm","emotion":"shocked"})
    ver("grita RING", pan.cara, "alarma")
    pres.show_device_state(S.LISTENING); pres.show_protocol_message({"type":"stt","text":"ya desperté"})
    ver("le contestás: se calla", (mongo_alarmas._sonando, pan.cara), (None, "pensando"))

    print("4. Emociones raras del servidor")
    for emo, esperado in (("HAPPY","happy"), (" sad ","sad"), ("fear","conversa_habla"), ("","conversa_habla")):
        pan, pres = nuevo()
        pres.show_device_state(S.LISTENING); pres.show_device_state(S.SPEAKING)
        pres.show_protocol_message({"type":"llm","emotion":emo})
        ver(f"emoción {emo!r}", pan.cara, esperado)

    print("5. Emoción antes de que empiece a hablar")
    pan, pres = nuevo()
    pres.show_device_state(S.LISTENING); pres.show_protocol_message({"type":"stt","text":"hola"})
    pres.show_protocol_message({"type":"llm","emotion":"winking"}); pres.show_device_state(S.SPEAKING)
    ver("al hablar mantiene la emoción", pan.cara, "winking")

    print("6. Modo tiempo real (no pasa por 'hablando')")
    pan, pres = nuevo()
    pres.show_device_state(S.LISTENING); pres.show_protocol_message({"type":"stt","text":"contame algo"})
    pres.show_protocol_message({"type":"tts","state":"start"}); pres.show_protocol_message({"type":"llm","emotion":"laughing"})
    ver("responde", pan.cara, "laughing")
    pres.show_protocol_message({"type":"tts","state":"stop"})
    ver("terminó de hablar: te escucha", pan.cara, "conversa_escucha")

    print("7. Nombres de caras")
    pan, pres = nuevo()
    for nombre, esperado in (("HAPPY","happy"), ("  Guitarra ","guitarra"), ("feliz","happy"), ("enojado","angry"),
                             ("dormido","sleepy"), ("año nuevo","anio_nuevo"), ("xyz", None)):
        r = await cara(nombre, 2)
        ver(f"show_face({nombre!r})", r.get("face") if r.get("ok") else None, esperado)
    r = await cara("cool", 500); ver("segundos=500", r.get("ok") and r.get("seconds"), 120)
    r = await cara("cool", 0); ver("segundos=0", r.get("ok") and r.get("seconds"), 2)
    mongo_caras.soltar()

    print("8. Dos caras seguidas")
    pan, pres = nuevo()
    await cara("furioso", 2); await asyncio.sleep(0.3); await cara("happy", 3)
    await asyncio.sleep(2.2); ver("a los 2,5 s sigue la segunda", pan.cara, "happy")
    await asyncio.sleep(1.2); ver("al terminar la segunda", pan.cara, "neutral")

    print("9. Guitarra de inactividad con una cara encima")
    pan, pres = nuevo(); c = mc.actual()
    c._momento = lambda: datetime(2026, 11, 14, 11, 0)      # sábado 11:00
    c._contacto -= 100; c._dormido = False; c._fase = "actividad"; c._ultima_actividad = "guitarra"
    c._fase_hasta = c._reloj() + 30
    await cara("volumen", 2); c._mostrar("guitarra")
    ver("con el volumen encima: sin sonido", c._sonando_mio, False)
    await asyncio.sleep(2.2); c.tic()
    ver("vuelve la guitarra", pan.cara, "guitarra")
    ver("y vuelve el sonido", c._sonando_mio, True)
    pres.show_device_state(S.LISTENING)
    ver("le hablás: se apaga", (c._sonando_mio, sonidos[-1]), (False, ("", False)))

    print("10. Música")
    pan, pres = nuevo()
    m = lambda st: pres.show_music_state(MusicStateData(state=st, song="x", position=0, duration=100))
    m("playing"); ver("suena", pan.cara, "musica")
    m("paused"); ver("pausa", pan.cara, "neutral")
    m("playing"); pres.show_device_state(S.LISTENING); ver("le hablás con música", pan.cara, "escuchando")
    pres.show_device_state(S.IDLE); ver("termina la charla, sigue la música", pan.cara, "musica")
    m("completed"); ver("terminó la canción", pan.cara, "neutral")

    print("11. Se cae la red mientras habla")
    pan, pres = nuevo()
    pres.show_device_state(S.LISTENING); pres.show_device_state(S.SPEAKING)
    mc.hay_internet = lambda: False
    pres.show_network_error(); await mc.actual().verificar_red(); ver("mientras habla no cambia", pan.cara, "conversa_habla")
    pres.show_device_state(S.IDLE); ver("queda en reposo", pan.cara, "sin_conexion")
    for _ in range(70): mc.actual().tic()
    ver("sin red no se aburre", pan.cara, "sin_conexion")
    pres.show_device_state(S.LISTENING); ver("vuelve a conversar", pan.cara, "conversa_escucha")

    print("12. Cara pedida en reposo mientras pasa el tiempo")
    pan, pres = nuevo(); c = mc.actual()
    await cara("presumido", 2); c._contacto -= 61; c.tic()
    ver("se aburre debajo pero no se ve", pan.cara, "presumido")
    await asyncio.sleep(2.2); ver("al soltar muestra lo de abajo", pan.cara, "aburrido")

    print("13. Sonido del videojuego (8 bits)")
    for cuando, esperado in ((datetime(2026,11,12,12,0), ("videojuego", True, True)),):
        pan, pres = nuevo(); c = mc.actual(); c._momento = lambda c2=cuando: c2
        c._contacto -= 100; c._fase = "entre"; c._fase_hasta = 0; c._actividades_hechas = 1
        c._ultima_actividad = "ejercicio"; c._azar.choice = lambda ops: "videojuego"
        c.tic()
        encendidos = [s for s in sonidos if s[1]]
        ver(f"{cuando:%a %H:%M} jugando", (pan.cara, encendidos[-1] if encendidos else None), ("videojuego", esperado))
    c._fase_hasta = 0; c.tic()
    ver("al terminar el juego se apaga", (pan.cara, c._sonando_mio), ("mirando", False))
    pan, pres = nuevo(); sonidos.clear()
    real = mongo_caras._sonido
    await cara("videojuego", 2)
    ver("pedido por voz (volumen normal)", [s for s in sonidos if s[1]][-1], ("videojuego", True, False))
    mongo_caras.soltar()

    print("14. Noche (22:00 a 6:00)")
    hora = [datetime(2026,11,12,21,59)]
    pan, pres = nuevo(); c = mc.actual(); c._momento = lambda: hora[0]
    def quieto(seg): c._contacto = c._reloj() - seg
    def dormirse():
        quieto(61); c.tic(); c._fase_hasta = 0; c.tic()
    quieto(61); c.tic(); ver("21:59 un minuto solo: se aburre", pan.cara, "aburrido")
    hora[0] = datetime(2026,11,12,22,0); pres.show_device_state(S.LISTENING); pres.show_device_state(S.IDLE)
    quieto(30); c.tic(); ver("22:00, 30 s solo: sigue despierto", pan.cara, "neutral")
    quieto(61); c.tic(); ver("22:00, un minuto solo: bosteza", pan.cara, "bostezo")
    c._fase_hasta = 0; c.tic(); ver("y se duerme", (pan.cara, c._dormido_noche), ("sleepy", True))
    for _ in range(5): c.tic()
    ver("de noche no hace actividades", pan.cara, "sleepy")
    pres.show_device_state(S.LISTENING); ver("lo despertás por su nombre", pan.cara, "despertar")
    mongo_caras.soltar(); ver("te escucha", pan.cara, "escuchando")
    pres.show_protocol_message({"type":"stt","text":"qué hora es"}); pres.show_device_state(S.SPEAKING); pres.show_device_state(S.IDLE)
    dormirse(); ver("termina la charla y al minuto vuelve a dormir", pan.cara, "sleepy")
    enviados.clear(); it = {"tipo":"recordatorio","texto":"pastilla"}
    mongo_alarmas._sonando = {"item": it, "veces": 1, "ultimo": 0}
    await mongo_alarmas._gritar(it, 1); ver("suena un recordatorio dormido", pan.cara, "recordatorio")
    pres.show_device_state(S.LISTENING); pres.show_protocol_message({"type":"stt","text":enviados[-1]})
    pres.show_device_state(S.SPEAKING); ver("lo grita despierto", pan.cara, "recordatorio")
    pres.show_device_state(S.LISTENING); pres.show_protocol_message({"type":"stt","text":"ya, apagala"})
    pres.show_device_state(S.SPEAKING); pres.show_device_state(S.IDLE)
    dormirse(); ver("después del recordatorio vuelve a dormir", pan.cara, "sleepy")
    hora[0] = datetime(2026,11,13,5,59); c.tic(); ver("5:59 sigue dormido", pan.cara, "sleepy")
    hora[0] = datetime(2026,11,13,6,0); c.tic(); ver("6:00 se levanta solo", (pan.cara, c._dormido), ("despertar", False))
    mongo_caras.soltar(); c.tic(); ver("y queda en reposo", pan.cara, "neutral")
    quieto(61); c.tic(); ver("6:01, un minuto solo: ya no se duerme, se aburre", pan.cara, "aburrido")
    mongo_caras.soltar()

    print("15. Pregunta suelta y conversación continua")
    pan, pres = nuevo(); c = mc.actual()
    pres.show_device_state(S.LISTENING); ver("primera pregunta", pan.cara, "escuchando")
    pres.show_protocol_message({"type":"stt","text":"hola"}); ver("piensa", pan.cara, "pensando")
    pres.show_device_state(S.SPEAKING); ver("responde sin emoción", pan.cara, "conversa_habla")
    pres.show_device_state(S.LISTENING); ver("modo automático: sigue la conversación", pan.cara, "conversa_escucha")
    pres.show_protocol_message({"type":"stt","text":"y vos?"}); pres.show_device_state(S.SPEAKING)
    pres.show_protocol_message({"type":"llm","emotion":"happy"}); ver("responde feliz", pan.cara, "happy")
    pres.show_device_state(S.IDLE); ver("termina", pan.cara, "neutral")
    pres.show_device_state(S.LISTENING); ver("lo llamás a los pocos segundos", pan.cara, "conversa_escucha")
    pres.show_device_state(S.SPEAKING); pres.show_device_state(S.IDLE)
    c._fin_respuesta -= 31
    pres.show_device_state(S.LISTENING); ver("más de 30 s después: pregunta nueva", pan.cara, "escuchando")
    pres.show_device_state(S.IDLE); c._fin_respuesta = float("-inf"); c._dormido = True
    pres.show_device_state(S.LISTENING); mongo_caras.soltar(); ver("despertarlo es una pregunta nueva", pan.cara, "escuchando")
    mongo_caras.soltar()
    print("16. Aviso de error de red: solo sin_conexion si de verdad no hay internet")
    pan, pres = nuevo(); c = mc.actual()
    mc.hay_internet = lambda: True
    pres.show_network_error(); ver("aviso recibido, todavía sin probar", (pan.cara, c.toca_revisar_red()), ("neutral", True))
    await c.verificar_red(); ver("hay internet: no cambia", (pan.cara, c._sin_red), ("neutral", False))
    mc.hay_internet = lambda: False
    pres.show_network_error(); await c.verificar_red(); ver("sin internet: sin_conexion", pan.cara, "sin_conexion")
    ver("recién probado: no vuelve a probar enseguida", c.toca_revisar_red(), False)
    c._ultima_revision_red -= 16; ver("a los 15 s toca probar otra vez", c.toca_revisar_red(), True)
    await c.verificar_red(); ver("sigue sin internet", pan.cara, "sin_conexion")
    mc.hay_internet = lambda: True; c._ultima_revision_red -= 16
    await c.verificar_red(); ver("volvió el internet: reposo solo", (pan.cara, c._sin_red), ("neutral", False))
    c.tic(); ver("ya no revisa", c.toca_revisar_red(), False)
    print("17. Golpes en el vidrio (saludo y llamando)")
    pan, pres = nuevo(); c = mc.actual(); sonidos.clear()
    c.inicio(); ver("al arrancar: palmada del saludo", (pan.cara, sonidos[-1]), ("saludo", ("saludo", True, False)))
    c._mostrar("neutral"); ver("termina el saludo: se apaga", sonidos[-1], ("", False))
    c._mostrar("llamando"); ver("toca el vidrio: toquecitos", sonidos[-1], ("llamando", True, False))
    n = len(sonidos); c._mostrar("llamando"); ver("no reinicia el sonido si sigue igual", len(sonidos), n)
    c._mostrar("videojuego"); c._mostrar("mirando"); ver("después se apaga", (sonidos[-1], c._sonando_mio), (("", False), False))
    c._momento = lambda: datetime(2026, 11, 12, 23, 0); c.cara = None; sonidos.clear()
    c._mostrar("saludo"); ver("de noche no golpea", sonidos, [])
    print("18. Pompi")
    for frase, esperado in (("dame un pompi", "saludo"), ("Pompi, mae", "saludo"), ("pompis!", "saludo"),
                            ("pompy", "saludo"), ("compré un pompón", "pensando"), ("hola", "pensando")):
        pan, pres = nuevo(); sonidos.clear()
        pres.show_device_state(S.LISTENING); pres.show_protocol_message({"type": "stt", "text": frase})
        ver(f"dice {frase!r}", pan.cara, esperado)
    pan, pres = nuevo(); sonidos.clear()
    pres.show_device_state(S.LISTENING); pres.show_protocol_message({"type": "stt", "text": "pompi"})
    ver("suena la palmada", [s for s in sonidos if s[1]][-1][:2], ("saludo", True))
    pres.show_device_state(S.SPEAKING); pres.show_protocol_message({"type": "llm", "emotion": "happy"})
    ver("mientras contesta sigue el saludo", pan.cara, "saludo")
    mongo_caras.soltar(); ver("al terminar el saludo muestra la respuesta", pan.cara, "happy")
    print("19. Clima: la cara acompaña toda la respuesta")
    from src.mcp.tools.weather import service as w
    from src.mcp.tools.weather.register import register_weather_tools
    tw = {}; register_weather_tools(lambda t: tw.__setitem__(t.name, t))
    for nombre_tool, codigo, cara_esperada in (("self.weather.get_current", 61, "clima_lluvia"),
                                               ("self.weather.get_forecast", 1, "clima_sol")):
        w._get_json = lambda url, params, timeout=8.0, c=codigo: (
            {"results": [{"name": "San José", "country": "Costa Rica", "country_code": "CR", "latitude": 9.9, "longitude": -84.1}]}
            if "geocoding" in url else {"current": {"weather_code": c, "temperature_2m": 22},
                                        "daily": {"time": ["2026-11-12"], "weather_code": [c], "temperature_2m_max": [26],
                                                  "temperature_2m_min": [17], "precipitation_probability_max": [40]}})
        pan, pres = nuevo()
        pres.show_device_state(S.LISTENING); pres.show_protocol_message({"type": "stt", "text": "cómo está el clima"})
        t = tw[nombre_tool]; await t.callback(t.properties.parse_arguments({}))
        pres.show_device_state(S.SPEAKING); pres.show_protocol_message({"type": "llm", "emotion": "happy"})
        ver(f"{nombre_tool}: mientras contesta", pan.cara, cara_esperada)
        await asyncio.sleep(0.2); ver("sigue mientras habla", pan.cara, cara_esperada)
        pres.show_device_state(S.IDLE); ver("al terminar de contestar se suelta", (pan.cara, mongo_caras.bloqueada()), ("neutral", False))
    pan, pres = nuevo()
    pres.show_device_state(S.LISTENING); await tw["self.weather.get_current"].callback({"city": "San José"})
    pres.show_protocol_message({"type": "tts", "state": "start"}); pres.show_protocol_message({"type": "tts", "state": "stop"})
    ver("tiempo real: al terminar la voz vuelve a escuchar", pan.cara, "conversa_escucha")
    pan, pres = nuevo(); pres.show_device_state(S.LISTENING); await cara("guitarra", 20); pres.show_device_state(S.SPEAKING)
    pres.show_device_state(S.LISTENING); ver("una cara normal (guitarra) no se suelta al terminar", pan.cara, "guitarra")
    mongo_caras.soltar()
    print("20. De día no se duerme")
    pan, pres = nuevo(); c = mc.actual(); c._momento = lambda: datetime(2026, 11, 12, 20, 30)
    c._contacto -= 3600; c.tic(); c._fase_hasta = 0; c.tic()
    ver("20:30, una hora solo: no bosteza, hace algo", (pan.cara in ("leyendo", "videojuego"), c._dormido), (True, False))
    ver("el videojuego de relleno va mudo", c._sonando_mio, False)
    print("21. Le pedís actualizar algo")
    pan, pres = nuevo()
    pres.show_device_state(S.LISTENING); pres.show_protocol_message({"type": "stt", "text": "actualizá la lista de compras"})
    ver("muestra actualizando", pan.cara, "actualizando")
    pres.show_device_state(S.SPEAKING); pres.show_protocol_message({"type": "llm", "emotion": "happy"})
    ver("sigue mientras contesta", pan.cara, "actualizando")
    pres.show_device_state(S.IDLE); ver("respuesta corta: se queda el mínimo", pan.cara, "actualizando")
    mongo_caras._minimo_hasta = 0; mongo_caras.fin_de_respuesta(); ver("cumplido el mínimo se suelta", pan.cara, "neutral")
    pan, pres = nuevo()
    pres.show_device_state(S.LISTENING); pres.show_protocol_message({"type": "stt", "text": "actualizar el clima"})
    mongo_caras._minimo_hasta = 0
    pres.show_device_state(S.SPEAKING); pres.show_device_state(S.IDLE)
    ver("respuesta larga: se suelta al terminar", pan.cara, "neutral")
    pan, pres = nuevo(); pres.show_device_state(S.LISTENING); pres.show_protocol_message({"type": "stt", "text": "qué hay de actualidad"})
    ver("'actualidad' no es actualizar", pan.cara, "pensando")
    mongo_caras.soltar()
    print("22. Pregunta del clima sin que la IA use la herramienta")
    from src.mcp.tools.weather import service as w
    pedidos = []
    def falso(ciudad, dias=0):
        pedidos.append((ciudad, dias))
        if ciudad == "Xyzzy":
            raise RuntimeError("no existe")
        return {"lugar": {"nombre": ciudad, "pais": "CR"},
                "datos": {"current": {"weather_code": 63}, "daily": {"weather_code": [0, 1]}}}
    w._clima = falso
    for frase, cara_esp, ciudad_esp in (("¿cómo está el clima?", "clima_lluvia", w.CIUDAD_POR_DEFECTO),
                                        ("¿va a llover en Heredia mañana?", "clima_sol", "Heredia"),
                                        ("¿llueve en Xyzzy?", "clima_lluvia", w.CIUDAD_POR_DEFECTO)):
        pan, pres = nuevo()
        pres.show_device_state(S.LISTENING); pres.show_protocol_message({"type": "stt", "text": frase})
        await asyncio.sleep(0.05)
        pres.show_device_state(S.SPEAKING); pres.show_protocol_message({"type": "llm", "emotion": "happy"})
        ver(f"{frase!r}: animación", (pan.cara, pedidos[-1][0]), (cara_esp, ciudad_esp))
        pres.show_device_state(S.IDLE); ver("al terminar se suelta", pan.cara, "neutral")
    pan, pres = nuevo(); pres.show_device_state(S.LISTENING); pres.show_protocol_message({"type": "stt", "text": "cuánto tiempo falta"})
    await asyncio.sleep(0.05); ver("'cuánto tiempo falta' no es clima", pan.cara, "pensando")
    mongo_caras.soltar()
    print("23. Pedir una alarma por voz")
    from src.mcp.tools.alarmas import register_alarma_tools
    ta = {}; register_alarma_tools(lambda t: ta.__setitem__(t.name, t))
    mongo_alarmas.cancelar("all")
    pan, pres = nuevo()
    pres.show_device_state(S.LISTENING); pres.show_protocol_message({"type": "stt", "text": "pon una alarma a las 6:30 de la mañana"})
    pres.show_device_state(S.SPEAKING); ver("mientras contesta todavía no hay alarma", len(mongo_alarmas.listar()), 0)
    pres.show_device_state(S.IDLE)
    al = mongo_alarmas.listar()
    ver("la IA no la programó: la programa MongoBot", [(a["tipo"], a["hora"]) for a in al], [("alarma", [6, 30])])
    mongo_alarmas.cancelar("all")
    pan, pres = nuevo()
    pres.show_device_state(S.LISTENING); pres.show_protocol_message({"type": "stt", "text": "coloca una alarma a las 7 pm"})
    t = ta["self.alarm.set_alarm"]; await t.callback(t.properties.parse_arguments({"time": "19:00"}))
    pres.show_device_state(S.SPEAKING); pres.show_device_state(S.IDLE)
    ver("la IA sí la programó: no se duplica", len(mongo_alarmas.listar()), 1)
    mongo_alarmas.cancelar("all")
    pan, pres = nuevo()
    pres.show_device_state(S.LISTENING); pres.show_protocol_message({"type": "stt", "text": "pon una alarma"})
    pres.show_device_state(S.SPEAKING); pres.show_device_state(S.IDLE)
    ver("sin hora no programa nada (la IA pregunta)", len(mongo_alarmas.listar()), 0)
    mongo_caras.soltar()
    print("24. Videojuego solo 3 veces al día")
    vistas = []; r = [0.0]; dia = [datetime(2026, 11, 12, 12, 0)]
    c = mc.Comportamiento(vistas.append, reloj=lambda: r[0], hoy=lambda: dia[0].date(), momento=lambda: dia[0])
    c.inicio()
    for s in range(3 * 3600):
        r[0] = float(s); c.tic()
    juegos = sum(1 for v in vistas if v == "videojuego")
    ver("3 horas solo un jueves al mediodía: veces que jugó", juegos, 3)
    ver("después sigue leyendo", vistas.count("leyendo") > 3, True)
    dia[0] = datetime(2026, 11, 13, 12, 0); n0 = len(vistas)
    for s in range(3 * 3600, 4 * 3600):
        r[0] = float(s); c.tic()
    ver("al día siguiente vuelve a jugar", "videojuego" in vistas[n0:], True)
    pan, pres = nuevo()
    for _ in range(5):
        r_ = await cara("videojuego", 2)
    ver("pedido por voz no tiene límite", r_.get("ok"), True)
    mongo_caras.soltar()
    print("25. La alarma suena hasta que le digás que pare")
    mongo_alarmas.cancelar("all"); enviados.clear()
    pan, pres = nuevo()
    it = {"tipo": "alarma", "texto": ""}
    mongo_alarmas._sonando = {"item": it, "veces": 1, "ultimo": 0}
    for _ in range(6):                                    # 6 vueltas de 30 s: sigue gritando
        mongo_alarmas._sonando["ultimo"] = 0
        await mongo_alarmas._revisar()
    ver("después de 7 gritos sigue sonando", (mongo_alarmas._sonando is not None, mongo_alarmas._sonando["veces"]), (True, 7))
    pres.show_device_state(S.LISTENING); pres.show_protocol_message({"type": "stt", "text": "qué hora es"})
    ver("le hablás de otra cosa: no se apaga", mongo_alarmas._sonando is not None, True)
    for frase in ("detené la alarma", "ya", "basta mae", "apagala", "para"):
        mongo_alarmas._sonando = {"item": it, "veces": 1, "ultimo": 0}
        mongo_alarmas.usuario_hablo(frase)
        ver(f"'{frase}' la apaga", mongo_alarmas._sonando, None)
    print("26. Cancelar sin decir cuál")
    from datetime import datetime as _d, timedelta as _td
    mongo_alarmas.cancelar("all")
    a1 = mongo_alarmas.programar("alarma", _d.now() + _td(hours=2), hora=(1, 1))
    a2 = mongo_alarmas.programar("alarma", _d.now() + _td(hours=1), hora=(2, 2))
    ver("'cancelá la alarma' quita la próxima", [x["id"] for x in mongo_alarmas.cancelar("")], [a2["id"]])
    a3 = mongo_alarmas.programar("alarma", _d(2030, 1, 1, 6, 30), hora=(6, 30))
    ver("'quitá la de las 6:30' quita esa", [x["id"] for x in mongo_alarmas.cancelar("6:30")], [a3["id"]])
    mongo_alarmas.cancelar("all"); mongo_alarmas._sonando = None
    print("27. La cara del clima coincide con lo que dice")
    pan, pres = nuevo()
    pres.show_device_state(S.LISTENING); pres.show_protocol_message({"type": "stt", "text": "dime el clima"})
    await asyncio.sleep(0.05); ver("busca el clima real (lluvia)", pan.cara, "clima_lluvia")
    pres.show_device_state(S.SPEAKING)
    pres.show_protocol_message({"type": "tts", "state": "sentence_start", "text": "Sigue igualito: soleado en San José."})
    ver("dice 'soleado': pasa a sol", pan.cara, "clima_sol")
    pres.show_protocol_message({"type": "tts", "state": "sentence_start", "text": "Pero en un rato va a llover, llevá sombrilla."})
    ver("dice que va a llover: lluvia", pan.cara, "clima_lluvia")
    pres.show_device_state(S.IDLE); ver("al terminar se suelta", pan.cara, "neutral")
    pan, pres = nuevo()
    pres.show_device_state(S.LISTENING); pres.show_protocol_message({"type": "stt", "text": "hola"})
    pres.show_device_state(S.SPEAKING); pres.show_protocol_message({"type": "llm", "emotion": "happy"})
    pres.show_protocol_message({"type": "tts", "state": "sentence_start", "text": "Qué día más soleado."})
    ver("sin cara de clima puesta no cambia nada", pan.cara, "happy")
    mongo_caras.soltar()
    print("28. Preguntas de ruta: si la IA no usa OpenStreetMap, se lo pide otra vez")
    from src.mcp.tools.trafico import service as tr
    enviados.clear(); mongo_alarmas.conectar_envio(env)
    pan, pres = nuevo()
    pres.show_device_state(S.LISTENING); pres.show_protocol_message({"type": "stt", "text": "ruta a escazú"})
    pres.show_device_state(S.SPEAKING); pres.show_device_state(S.IDLE); await asyncio.sleep(0.05)
    ver("la IA no buscó: se lo pide", enviados[-1:], ["usa OpenStreetMap: ruta a escazú"])
    enviados.clear(); pan, pres = nuevo()
    pres.show_device_state(S.LISTENING); pres.show_protocol_message({"type": "stt", "text": "cómo llego a Cartago"})
    tr.consultas += 1                                   # la IA sí llamó a la herramienta
    pres.show_device_state(S.SPEAKING); pres.show_device_state(S.IDLE); await asyncio.sleep(0.05)
    ver("la IA sí buscó: no repite", enviados, [])
    pan, pres = nuevo()
    pres.show_device_state(S.LISTENING); pres.show_protocol_message({"type": "stt", "text": "usa OpenStreetMap: ruta a escazú"})
    pres.show_device_state(S.SPEAKING); pres.show_device_state(S.IDLE); await asyncio.sleep(0.05)
    ver("el pedido repetido no se vuelve a repetir", enviados, [])
    for t, esp in (("cuánto duro a Heredia", True), ("qué tan lejos queda Limón", True), ("cómo está el tráfico", True),
                   ("hola mae", False), ("pon música", False)):
        ver(f"{t!r} es pregunta de ruta", bool(mc.PEDIR_RUTA.search(t)), esp)
    print(f"\n{ok_total} bien, {fallas} fallas")

asyncio.run(main())
