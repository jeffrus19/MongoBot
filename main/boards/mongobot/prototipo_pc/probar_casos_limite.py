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
    ver("lo llamás", pan.cara, "conversa_escucha")

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
    m("playing"); pres.show_device_state(S.LISTENING); ver("le hablás con música", pan.cara, "conversa_escucha")
    pres.show_device_state(S.IDLE); ver("termina la charla, sigue la música", pan.cara, "musica")
    m("completed"); ver("terminó la canción", pan.cara, "neutral")

    print("11. Se cae la red mientras habla")
    pan, pres = nuevo()
    pres.show_device_state(S.LISTENING); pres.show_device_state(S.SPEAKING)
    pres.show_network_error(); ver("mientras habla no cambia", pan.cara, "conversa_habla")
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
    print(f"\n{ok_total} bien, {fallas} fallas")

asyncio.run(main())
