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
- a los 60 s            -> aburrido, y luego alterna ejercicio, videojuego y leyendo, con ratos de
                           "mirando" entre una y otra; cada tanto toca el vidrio para
                           llamarte (llamando) y te dice algo. La guitarra solo entra en la
                           rotación sábados y domingos de 10:00 a 17:00, y solo en ese
                           horario suenan la guitarra y el videojuego (8 bits), al 30 %.
                           Pedidas con show_face suenan siempre, a volumen normal
- a los 10 min          -> bostezo y se duerme (sleepy) hasta que le hablés

Las caras pedidas con la herramienta show_face (mongo_caras) siguen mandando: mientras
dura su candado, lo que elija esta capa queda pendiente.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Callable
from datetime import date, datetime

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

ACTIVIDADES = ["ejercicio", "videojuego", "leyendo"]
GUITARRA_DIAS = (5, 6)          # sábado y domingo (lunes = 0)
GUITARRA_HORAS = (10, 17)       # de 10:00 a 17:00
CON_SONIDO = ("guitarra", "videojuego")   # actividades con loop de audio (solo en ese horario)
FRASES_LLAMAR = [
    "Diay, ¿me vas a dejar aquí solito?",
    "Mae, aquí sigo, guapísimo como siempre, por si te interesa.",
    "¿Sabías que el pulpo tiene tres corazones? Yo uno, pero bien bonito.",
    "Toc toc... ¿hay alguien ahí afuera?",
    "Ya me aburrí de jugar solo. Hablame, ¿no?",
]


class Comportamiento:
    def __init__(self, poner_cara: Callable[[str], None], poner_texto: Callable[[str], None] | None = None,
                 reloj: Callable[[], float] = time.monotonic, hoy: Callable[[], date] = date.today,
                 azar: random.Random | None = None, momento: Callable[[], datetime] | None = None):
        self._poner = poner_cara
        self._texto = poner_texto or (lambda _t: None)
        self._reloj = reloj
        self._hoy = hoy
        self._momento = momento or datetime.now
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
        self._sonando_mio = False      # el loop (guitarra/videojuego) lo encendió esta capa
        self._musica = False           # está sonando una canción del reproductor

    # ------------------------------------------------------------ utilidades

    def _mostrar(self, cara: str) -> None:
        if cara != self.cara:
            self.cara = cara
            self._poner(cara)
            logger.debug(f"[Comportamiento] cara -> {cara}")
        if cara not in CON_SONIDO:
            self._sonido_actividad(False)

    def _sonido_actividad(self, encender: bool) -> None:
        """Loop de la actividad actual (guitarra o videojuego) al 30 %. Solo apaga el
        sonido si lo encendió esta capa: lo pedido con show_face lleva su propio
        sonido y su propio tiempo."""
        if not encender and not self._sonando_mio:
            return
        try:
            from src.plugins import mongo_caras

            if mongo_caras.bloqueada():
                return
            mongo_caras._sonido(self.cara if encender else "", encender, suave=True)
            self._sonando_mio = encender
        except Exception:                                        # noqa: BLE001
            pass

    def _soltar_cara_pedida(self) -> None:
        """Suelta la cara de show_face, salvo una alarma sonando (se apaga al contestarle)."""
        from src.plugins import mongo_alarmas, mongo_caras

        if mongo_caras.bloqueada() and mongo_alarmas._sonando is None:
            mongo_caras.soltar()

    def _existe(self, cara: str) -> bool:
        try:
            from src.plugins import mongo_caras

            disponibles = mongo_caras.caras_disponibles()
            return not disponibles or cara in disponibles
        except Exception:                                        # noqa: BLE001
            return True

    def _actividades(self) -> list[str]:
        """Actividades de inactividad; la guitarra solo fines de semana de día."""
        acts = list(ACTIVIDADES)
        if self._en_horario():
            acts.append("guitarra")
        return acts

    def _en_horario(self) -> bool:
        """Sábado o domingo de 10:00 a 17:00: puede tocar guitarra y sonar el videojuego."""
        m = self._momento()
        return m.weekday() in GUITARRA_DIAS and GUITARRA_HORAS[0] <= m.hour < GUITARRA_HORAS[1]

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
        self._sonido_actividad(False)
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
            if anterior == "idle":
                # lo llamás desde el reposo: se suelta una cara pedida (p. ej. guitarra 40 s).
                # Si viene de hablar (modo automático) la cara sigue hasta que le hablés.
                self._soltar_cara_pedida()
            from src.plugins import mongo_caras

            if estaba_dormido and not mongo_caras.bloqueada():
                # una alarma que suena mientras duerme no se tapa con el despertar
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
            self._mostrar("sin_conexion" if self._sin_red else ("musica" if self._musica else self._cara_reposo()))

    def al_texto_usuario(self, texto: str) -> None:
        """El servidor transcribió lo que dijiste (stt): piensa mientras responde."""
        from src.plugins import mongo_alarmas

        if mongo_alarmas.es_aviso_propio(texto):
            return
        self._contactar()
        self._soltar_cara_pedida()
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
        if e not in ("", "neutral", "furioso") and not self._existe(e):
            logger.warning(f"[Comportamiento] emoción sin animación: {e}")
            e = ""
        self._emocion_turno = None if e in ("", "neutral") else e
        self._contactar()
        self._mostrar(self._emocion_turno or "conversa_habla")

    def al_tts(self, estado: str) -> None:
        """Inicio/fin de la voz. En tiempo real nunca pasa a 'hablando': al terminar
        de hablar vuelve a la cara de escucha."""
        if (estado or "").lower() == "stop" and self.estado == "listening":
            self._emocion_turno = None
            self._mostrar("conversa_escucha")

    def al_musica(self, estado: str) -> None:
        """Estado del reproductor: playing / paused / stopped / completed / error."""
        sonando = (estado or "").lower() == "playing"
        self._musica = sonando
        if sonando:
            self._contactar()
        if self.estado == "idle":
            self._mostrar("musica" if sonando else self._cara_reposo())

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
        if self.cara in CON_SONIDO and self._fase == "actividad" and not self._sonando_mio and self._en_horario():
            self._sonido_actividad(True)      # una cara pedida tapó la actividad; vuelve el sonido
        if self._musica:                      # escuchando música no se aburre
            self._contacto = ahora
            if self.cara != "musica":
                self._mostrar("musica")
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
            opciones = [a for a in self._actividades() if a != self._ultima_actividad]
            act = self._azar.choice(opciones)
            self._ultima_actividad = act
            self._fase, self._fase_hasta = "actividad", ahora + ACTIVIDAD
            self._actividades_hechas += 1
            self._mostrar(act)
            if act in CON_SONIDO and self._en_horario():
                self._sonido_actividad(True)
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
