"""Prueba de la capa de comportamiento de MongoBot, sin servidor ni audio.

Uso (desde la carpeta de py-xiaozhi):
    python scripts/probar_comportamiento.py

Simula conversaciones completas (escuchar, pensar, hablar, emociones, enojo repetido,
caras pedidas, alarma, sin conexión, despertar) contra el UiPresenter real, y una línea
de tiempo de 12 minutos de inactividad con reloj acelerado. Muestra qué cara queda en
cada paso.
"""
import os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio, sys, random
sys.path.insert(0, '.')
from datetime import date, datetime
from src.constants.constants import DeviceState as S
from src.plugins.ui_presenter import UiPresenter
from src.plugins import mongo_caras, mongo_alarmas, mongo_comportamiento as mc

# Las pruebas no dependen de la hora en que se corran: por defecto, jueves 12:00.
from datetime import datetime as _dt
_init_real = mc.Comportamiento.__init__
def _init_fijo(self, *a, momento=None, **k):
    _init_real(self, *a, momento=momento or (lambda: _dt(2026, 11, 12, 12, 0)), **k)
mc.Comportamiento.__init__ = _init_fijo


class Pantalla:
    def __init__(self): self.cara=None; self.texto=""
    def set_emotion(self, e): self.cara=e
    def set_chat_text(self, t): self.texto=t
    def set_status(self, *a): pass

async def escenario(titulo, pasos):
    print(f"\n=== {titulo}")
    pan=Pantalla(); pres=UiPresenter(pan)
    for desc, acc in pasos:
        if isinstance(acc,(int,float)): await asyncio.sleep(acc)
        elif isinstance(acc,dict): pres.show_protocol_message(acc)
        elif callable(acc):
            r=acc(pres)
            if asyncio.iscoroutine(r): await r
        else: pres.show_device_state(acc)
        print(f"   {desc:<50} -> {pan.cara}")
    return pres

async def conversaciones():
    await escenario("1. Pregunta normal", [
        ("Ctrl+J: escuchando", S.LISTENING),
        ("soltás, llega lo que dijiste (stt)", {"type":"stt","text":"¿por qué el cielo es azul?"}),
        ("empieza a responder (hablando)", S.SPEAKING),
        ("llega la emoción: thinking", {"type":"llm","emotion":"thinking"}),
        ("termina: en espera", S.IDLE)])
    await escenario("2. Respuesta neutral, la emoción llega antes de hablar", [
        ("escuchando", S.LISTENING),
        ("stt", {"type":"stt","text":"hola Mongo"}),
        ("llm: neutral", {"type":"llm","emotion":"neutral"}),
        ("hablando", S.SPEAKING),
        ("en espera", S.IDLE)])
    await escenario("3. Lo molestás 3 veces seguidas", [
        ("escuchando", S.LISTENING), ("stt", {"type":"stt","text":"sos feo"}), ("hablando", S.SPEAKING),
        ("llm: angry (1)", {"type":"llm","emotion":"angry"}), ("en espera", S.IDLE),
        ("escuchando", S.LISTENING), ("llm: angry (2)", {"type":"llm","emotion":"angry"}), ("en espera", S.IDLE),
        ("escuchando", S.LISTENING), ("llm: angry (3)", {"type":"llm","emotion":"angry"}), ("en espera", S.IDLE)])
    await escenario("4. Le pedís una cara (show_face furioso 1 s)", [
        ("escuchando", S.LISTENING), ("stt", {"type":"stt","text":"poné cara de furioso"}),
        ("la IA llama show_face(furioso, 1 s)", lambda p: mongo_caras.mostrar("furioso", 1)),
        ("hablando", S.SPEAKING), ("llm: angry", {"type":"llm","emotion":"angry"}),
        ("se acaba el candado (1,2 s)", 1.2), ("en espera", S.IDLE)])
    await escenario("5. Suena una alarma, la apagás hablándole", [
        ("se dispara: cara de alarma", lambda p: mongo_caras.mostrar("alarma", 30)),
        ("escuchando (abre el micrófono)", S.LISTENING),
        ("eco del aviso: no cuenta como tuyo", {"type":"stt","text":"ALARMA: gimnasio"}),
        ("grita RING RING RING", S.SPEAKING),
        ("simular que estaba sonando", lambda p: setattr(mongo_alarmas, "_sonando", {"item":{}, "veces":1, "ultimo":0})),
        ("le decís 'ya me levanté' (stt)", {"type":"stt","text":"ya me levanté"}),
        ("responde", S.SPEAKING), ("en espera", S.IDLE)])
    await escenario("6. Se cae el internet y vuelve", [
        ("en espera", S.IDLE),
        ("error de red", lambda p: p.show_network_error()),
        ("vuelve: le hablás", S.LISTENING), ("en espera", S.IDLE)])
    p = await escenario("7. Estaba dormido y le hablás", [
        ("dormirlo a la fuerza", lambda p: setattr(mc.actual(), "_dormido", True)),
        ("Ctrl+J", S.LISTENING),
        ("pasa el despertar (1,5 s)", 1.5)])
    await escenario("8. Pide guitarra con show_face mientras hay inactividad", [
        ("la IA pone guitarra 1 s", lambda p: mongo_caras.mostrar("guitarra", 1)),
        ("tic de inactividad (no debe taparla)", lambda p: mc.actual().tic()),
        ("se acaba (1,2 s)", 1.2)])

async def mas_casos():
    mongo_alarmas._sonando = None
    await escenario("12. Toca guitarra (40 s) y a los 0,5 s le hablás", [
        ("la IA pone guitarra 40 s", lambda p: mongo_caras.mostrar("guitarra", 40)),
        ("pasa medio segundo", 0.5),
        ("Ctrl+J: escuchando (debe soltar la guitarra)", S.LISTENING),
        ("stt", {"type":"stt","text":"ya, suficiente"}),
        ("hablando", S.SPEAKING), ("en espera", S.IDLE)])
    await escenario("13. Suena la alarma: py-xiaozhi abre el micrófono (no debe soltarla)", [
        ("se dispara", lambda p: mongo_caras.mostrar("alarma", 30)),
        ("marcar que está sonando", lambda p: setattr(mongo_alarmas, "_sonando", {"item":{}, "veces":1, "ultimo":0})),
        ("escuchando", S.LISTENING),
        ("hablando (RING RING RING)", S.SPEAKING),
        ("le decís 'ok ya' (stt)", {"type":"stt","text":"ok ya"}),
        ("en espera", S.IDLE)])
    mongo_alarmas._sonando = None


def linea_de_tiempo(hoy=date(2026,11,11), segundos=720):
    reloj=[0.0]
    caras=[]; textos=[]
    c = mc.Comportamiento(lambda e: caras.append((reloj[0], e)), lambda t: textos.append((reloj[0], t)),
                          reloj=lambda: reloj[0], hoy=lambda: hoy, azar=random.Random(3),
                          momento=lambda: datetime.combine(hoy, datetime.min.time()).replace(hour=12))
    c.inicio()
    for s in range(segundos):
        reloj[0]=float(s); c.tic()
    return caras, textos

def mostrar_linea(titulo, caras, textos):
    print(f"\n=== {titulo}")
    todo = sorted([(t,'cara',x) for t,x in caras]+[(t,'dice',x) for t,x in textos])
    for t,tipo,x in todo:
        m,s=divmod(int(t),60)
        print(f"   {m:>2}:{s:02d}  {'cara ->' if tipo=='cara' else 'dice: '} {x}")

asyncio.run(conversaciones())
asyncio.run(mas_casos())
caras,textos = linea_de_tiempo()
mostrar_linea("9. Inactividad: 12 minutos sin hablarle (11 de noviembre)", caras, textos)
caras,_ = linea_de_tiempo(date(2026,12,20), 30)
mostrar_linea("10. Reposo el 20 de diciembre", caras, [])
caras,_ = linea_de_tiempo(date(2026,12,31), 30)
mostrar_linea("11. Reposo el 31 de diciembre", caras, [])
