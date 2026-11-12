"""Capa de comportamiento de MongoBot: decide qué cara mostrar en cada momento.

Recibe los cambios de estado (esperando / escuchando / hablando), los mensajes del
servidor (lo que dijiste, la emoción de la respuesta) y un "tic" por segundo, y
elige la animación:

Conversación
- Escuchando            -> conversa_escucha (cúpula que asiente)
- Ya hablaste (stt)     -> pensando, hasta que empieza a responder
- Hablando              -> la emoción que mandó el servidor; si es neutral, conversa_habla
- Enojo repetido        -> si llega "angry" 3 veces en 2 minutos, pasa a furioso
- Si estaba dormido     -> despertar un momento antes de escuchar

Sistema
- Al arrancar           -> saludo
- Sin conexión          -> sin_conexion, hasta que vuelva a conversar

Inactividad (sin que le hablés)
- 0 a 60 s              -> neutral (o la cara de temporada en diciembre)
- a los 60 s            -> aburrido, y luego una actividad al azar (guitarra con sonido,
                           ejercicio, videojuego o leyendo), con ratos de "mirando" entre una
                           y otra; cada tanto toca el vidrio para llamarte (llamando) y te
                           dice algo
- a los 10 min          -> bostezo y se duerme (sleepy) hasta que le hablés

Las caras pedidas con la herramienta show_face (mongo_caras) siguen mandando: mientras
dura su candado, lo que elija esta capa queda pendiente.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Callable
from datetime import date

from src.logging import get_logger

logger = get_logger()

# tiempos (segundos); las pruebas los acortan
ABURRIRSE = 60
DORMIR = 600
ACTIVIDAD = 40
ENTRE_ACTIVIDADES = 8
ABURRIDO = 6
LLAMAR_CADA = 3            # cada cuántas actividades llama la atención
LLAMANDO = 6
BOSTEZO = 3
SALUDO = 3
DESPERTAR = 1.4
ENOJO_VENTANA = 120
ENOJO_VECES = 3

ACTIVIDADES = ["guitarra", "ejercicio", "videojuego", "leyendo"]
FRASES_LLAMAR = [
    "Diay, ¿me vas a dejar aquí solito?",
    "Mae, aquí sigo, guapísimo como siempre, por si te interesa.",
    "¿Sabías que el pulpo tiene tres corazones? Yo uno, pero bien bonito.",
    "Toc toc... ¿hay alguien ahí afuera?",
    "Ya me aburrí de tocar guitarra solo. Hablame, ¿no?",
]


class Comportamiento:
    def __init__(self, poner_cara: Callable[[str], None], poner_texto: Callable[[str], None] | None = None,
                 reloj: Callable[[], float] = time.monotonic, hoy: Callable[[], date] = date.today,
                 azar: random.Random | None = None):
        self._poner = poner_cara
        self._texto = poner_texto or (lambda _t: None)
        self._reloj = reloj
        self._hoy = hoy
        self._azar = azar or random.Random()
        self.estado = "idle"
        self.cara = None
        self._emocion_turno: str | None = None
        self._enojos: list[float] = []
        self._contacto = reloj()
        self._dormido = False
        self._sin_red = False
        self._fase = "reposo"          # reposo | aburrido | actividad | entre | llamando | bostezo | dormido
        self._fase_hasta = 0.0
        self._actividades_hechas = 0
        self._ultima_actividad: str | None = None
        self._hasta_saludo = 0.0
        self._sonando_mio = False      # la guitarra la encendió esta capa (no show_face)

    # ------------------------------------------------------------ utilidades

    def _mostrar(self, cara: str) -> None:
        if cara != self.cara:
            self.cara = cara
            self._poner(cara)
            logger.debug(f"[Comportamiento] cara -> {cara}")
        if cara != "guitarra":
            self._sonido_guitarra(False)

    def _sonido_guitarra(self, encender: bool) -> None:
        """Solo apaga el sonido si lo encendió esta capa: la guitarra pedida con
        show_face lleva su propio sonido y su propio tiempo."""
        if not encender and not self._sonando_mio:
            return
        try:
            from src.plugins import mongo_caras

            if mongo_caras.bloqueada():
                return
            mongo_caras._sonido("guitarra" if encender else "", encender)
            self._sonando_mio = encender
        except Exception:                                        # noqa: BLE001
            pass

    def _cara_reposo(self) -> str:
        hoy = self._hoy()
        if hoy.month == 12 and 15 <= hoy.day <= 25:
            return "navidad"
        if (hoy.month == 12 and hoy.day == 31) or (hoy.month == 1 and hoy.day == 1):
            return "anio_nuevo"
        return "neutral"

    def _contactar(self) -> bool:
        """Hubo interacción: reinicia la inactividad. Devuelve True si estaba dormido."""
        estaba_dormido = self._dormido
        self._contacto = self._reloj()
        self._dormido = False
        self._fase = "reposo"
        self._actividades_hechas = 0
        self._sonido_guitarra(False)
        return estaba_dormido

    # ------------------------------------------------------------ entradas

    def inicio(self) -> None:
        """Al arrancar py-xiaozhi."""
        self._hasta_saludo = self._reloj() + SALUDO
        self._contacto = self._reloj()
        self._mostrar("saludo")

    def al_estado(self, estado: str) -> None:
        """estado: 'idle', 'listening', 'speaking' (o los DeviceState equivalentes)."""
        estado = str(getattr(estado, "value", estado)).lower()
        anterior, self.estado = self.estado, estado
        if estado == "listening":
            self._sin_red = False
            estaba_dormido = self._contactar()
            if anterior != "listening":
                self._emocion_turno = None
                # empezás a hablarle: se suelta una cara pedida (p. ej. guitarra 40 s),
                # salvo una alarma sonando, que se apaga cuando le contestás
                from src.plugins import mongo_alarmas, mongo_caras

                if mongo_caras.bloqueada() and mongo_alarmas._sonando is None:
                    mongo_caras.soltar()
            if estaba_dormido:
                from src.plugins import mongo_caras

                mongo_caras.mostrar("despertar", DESPERTAR)
                self.cara = "despertar"
            self._mostrar("conversa_escucha")
        elif estado == "speaking":
            self._sin_red = False
            self._contactar()
            self._mostrar(self._emocion_turno or "conversa_habla")
        elif estado == "idle":
            self._contactar()
            self._emocion_turno = None
            self._mostrar("sin_conexion" if self._sin_red else self._cara_reposo())

    def al_texto_usuario(self, texto: str) -> None:
        """El servidor transcribió lo que dijiste (stt): piensa mientras responde."""
        from src.plugins import mongo_alarmas

        if mongo_alarmas.es_aviso_propio(texto):
            return
        self._contactar()
        if self.estado != "speaking":
            self._mostrar("pensando")

    def al_emocion(self, emocion: str) -> None:
        """Emoción de la respuesta (mensaje llm)."""
        e = (emocion or "").strip().lower()
        ahora = self._reloj()
        if e == "angry":
            self._enojos = [t for t in self._enojos if ahora - t < ENOJO_VENTANA] + [ahora]
            if len(self._enojos) >= ENOJO_VECES:
                e = "furioso"
        self._emocion_turno = None if e in ("", "neutral") else e
        self._contactar()
        self._mostrar(self._emocion_turno or "conversa_habla")

    def sin_conexion(self) -> None:
        self._sin_red = True
        if self.estado == "idle":
            self._mostrar("sin_conexion")

    # ------------------------------------------------------------ inactividad

    def tic(self) -> None:
        """Se llama una vez por segundo."""
        ahora = self._reloj()
        if self._hasta_saludo and ahora >= self._hasta_saludo:
            self._hasta_saludo = 0.0
            if self.estado == "idle" and self.cara == "saludo":
                self._mostrar(self._cara_reposo())
        if self.estado != "idle" or self._sin_red or self._hasta_saludo:
            return
        quieto = ahora - self._contacto
        if self._dormido:
            return
        if quieto >= DORMIR and self._fase != "bostezo":
            self._fase, self._fase_hasta = "bostezo", ahora + BOSTEZO
            self._mostrar("bostezo")
            self._texto("Bueno... me voy a echar una siestita.")
            return
        if self._fase == "bostezo":
            if ahora >= self._fase_hasta:
                self._fase, self._dormido = "dormido", True
                self._mostrar("sleepy")
            return
        if quieto < ABURRIRSE:
            if self._fase != "reposo":
                self._fase = "reposo"
            if self.cara not in (self._cara_reposo(),):
                self._mostrar(self._cara_reposo())
            return
        if self._fase == "reposo":
            self._fase, self._fase_hasta = "aburrido", ahora + ABURRIDO
            self._mostrar("aburrido")
            return
        if ahora < self._fase_hasta:
            return
        # se acabó la fase actual: siguiente
        if self._fase in ("aburrido", "entre", "llamando"):
            if self._fase != "llamando" and self._actividades_hechas and self._actividades_hechas % LLAMAR_CADA == 0:
                self._fase, self._fase_hasta = "llamando", ahora + LLAMANDO
                self._mostrar("llamando")
                self._texto(self._azar.choice(FRASES_LLAMAR))
                self._actividades_hechas += 1      # para no llamar dos veces seguidas
                return
            opciones = [a for a in ACTIVIDADES if a != self._ultima_actividad]
            act = self._azar.choice(opciones)
            self._ultima_actividad = act
            self._fase, self._fase_hasta = "actividad", ahora + ACTIVIDAD
            self._actividades_hechas += 1
            self._mostrar(act)
            if act == "guitarra":
                self._sonido_guitarra(True)
            return
        if self._fase == "actividad":
            self._fase, self._fase_hasta = "entre", ahora + ENTRE_ACTIVIDADES
            self._mostrar("mirando")


_instancia: Comportamiento | None = None


def crear(poner_cara: Callable[[str], None], poner_texto: Callable[[str], None] | None = None) -> Comportamiento:
    global _instancia
    _instancia = Comportamiento(poner_cara, poner_texto)
    return _instancia


def actual() -> Comportamiento | None:
    return _instancia


async def correr() -> None:
    """Tic una vez por segundo. Lo arranca el plugin de UI."""
    while True:
        try:
            if _instancia is not None:
                _instancia.tic()
        except asyncio.CancelledError:
            raise
        except Exception as e:                                   # noqa: BLE001
            logger.error(f"[Comportamiento] error en el tic: {e}", exc_info=True)
        await asyncio.sleep(1.0)
