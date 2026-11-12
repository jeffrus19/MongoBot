"""Capa de comportamiento de MongoBot: decide qué cara mostrar en cada momento.

Recibe los cambios de estado (esperando / escuchando / hablando), los mensajes del
servidor (lo que dijiste, la emoción de la respuesta) y un "tic" por segundo, y
elige la animación:

Conversación
- Primera pregunta      -> escuchando (lo llamás desde el reposo)
- Conversación continua -> conversa_escucha (cúpula de cerca que asiente): desde el segundo
                           turno, o sea, cuando vuelve a escuchar justo después de hablar
                           (modo automático o tiempo real) o lo llamás de nuevo antes de
                           CONVERSA_VENTANA segundos. Pasado ese rato en reposo, la
                           conversación se da por terminada y la próxima vuelve a escuchando
- Ya hablaste (stt)     -> pensando, hasta que empieza a responder
- Hablando              -> la emoción que mandó el servidor; si es neutral, conversa_habla
                           (globitos), en la primera pregunta y en la conversación continua
- Enojo repetido        -> si llega "angry" 3 veces en 2 minutos, pasa a furioso
- Si estaba dormido     -> despertar un momento antes de escuchar

Sistema
- Al arrancar           -> saludo
- Sin conexión          -> sin_conexion, SOLO si de verdad no hay internet. py-xiaozhi
                           avisa "error de red" también cuando el servidor cierra la
                           sesión de mala manera; por eso cada aviso se confirma probando
                           la conexión (hay_internet). Mientras esté sin red, cada 15 s
                           vuelve a probar y, si volvió, regresa al reposo solo

Inactividad (sin que le hablés)
- 0 a 60 s              -> neutral (o la cara de temporada en diciembre)
- a los 60 s            -> aburrido, y luego alterna las actividades que tocan a esa hora
                           (HORARIOS), con ratos de "mirando" entre una y otra; cada tanto
                           toca el vidrio para llamarte (llamando) y te dice algo:
                             ejercicio             mar, mié y jue de 9:00 a 10:00; sáb y dom de 8:00 a 11:00
                             leyendo               todos los días de 8:00 a 20:00
                             guitarra              sábado y domingo de 10:00 a 17:00, sonido al 15 %
                             videojuego            lunes a viernes de 11:00 a 16:00, sonido al 15 %
                           De día nunca se duerme: en las horas sin actividad programada
                           (6:00-8:00 y 20:00-22:00) alterna leyendo y videojuego, este
                           sin sonido. Pedidas con show_face salen a cualquier hora y
                           suenan a volumen normal

Noche (de 22:00 a 6:00, todos los días)
- Al minuto sin hablarle -> bostezo, "buenas noches" y se duerme. Si lo despertás (por
                           su nombre) o suena una alarma o un recordatorio, se despierta,
                           y al minuto de terminar vuelve a dormirse. A las 6:00 se
                           levanta solo (despertar).

Las caras pedidas con la herramienta show_face (mongo_caras) siguen mandando: mientras
dura su candado, lo que elija esta capa queda pendiente.
"""

from __future__ import annotations

import asyncio
import random
import re
import socket
import time
from collections.abc import Callable
from datetime import date, datetime

from src.logging import get_logger

logger = get_logger()

# tiempos (segundos); las pruebas los acortan
ABURRIRSE = 60
DORMIR = 600               # (ya no se usa de día: solo duerme de noche)
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
CONVERSA_VENTANA = 30     # segundos en reposo tras una respuesta en que sigue la conversación
# "pon/coloca/programa una alarma a las 6:30": si la IA no la programa, la programa MongoBot
PEDIR_ALARMA = re.compile(
    r"\b(pon|ponme|poneme|pone|pon[eé]|coloca|colocame|coloc[aá]|programa|programame|program[aá]|"
    r"crea|cre[aá]|activa|activ[aá]|ajusta|ajust[aá])\b[\w ]{0,12}?\balarma", re.IGNORECASE)
HORA_ALARMA = re.compile(
    r"\b(?:a|para)\s+las?\s+(\d{1,2})(?:(?::|\.|\s+y\s+)(\d{2}|media|cuarto))?"
    r"\s*(a\.?\s?m\.?|p\.?\s?m\.?|de la ma[ñn]ana|de la tarde|de la noche|de la madrugada)?", re.IGNORECASE)


def hora_de_alarma(texto: str, ahora: datetime | None = None) -> tuple[int, int] | None:
    """'pon una alarma a las 6 y media de la tarde' -> (18, 30). Sin am/pm, la próxima."""
    if not PEDIR_ALARMA.search(texto or ""):
        return None
    m = HORA_ALARMA.search(texto)
    if not m:
        return None
    h = int(m.group(1))
    mi = {"media": 30, "cuarto": 15}.get((m.group(2) or "").lower(), None)
    mi = int(m.group(2)) if mi is None and m.group(2) else (mi or 0)
    sufijo = (m.group(3) or "").lower().replace(".", "").replace(" ", "")
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        return None
    if sufijo.startswith("p") or "tarde" in sufijo or "noche" in sufijo:
        h = h + 12 if h < 12 else h
    elif sufijo.startswith("a") or "mañana" in sufijo or "manana" in sufijo or "madrugada" in sufijo:
        h = 0 if h == 12 else h
    elif h < 12:
        ahora = ahora or datetime.now()             # sin am/pm: la próxima vez que llegue esa hora
        if (ahora.hour, ahora.minute) >= (h, mi) and (ahora.hour, ahora.minute) < (h + 12, mi):
            h += 12
    return h, mi


REVISAR_RED_CADA = 15      # segundos entre pruebas mientras está sin conexión
# "dame un pompi" (choque de puños/cinco): saludo con su palmada. Incluye cómo lo
# suele escribir el reconocimiento de voz.
POMPI = re.compile(r"\b(pomp[iy]e?s?|pombi(s)?)\b", re.IGNORECASE)
NOCHE = (22, 6)            # duerme de 22:00 a 6:00
DORMIR_NOCHE = 60          # de noche, segundos sin hablarle antes de dormirse
RELLENO = ["leyendo", "videojuego"]   # de día, cuando no toca ninguna actividad programada
ACTUALIZAR = re.compile(r"\bactualiz\w*", re.IGNORECASE)   # "actualizá...", "actualizar..."
ACTUALIZANDO_MIN = 6       # segundos mínimos de la animación actualizando

# actividad de inactividad -> lista de (días, hora de inicio, hora de fin); lunes = 0
TODOS = (0, 1, 2, 3, 4, 5, 6)
HORARIOS = {
    "ejercicio": [((1, 2, 3), 9, 10),        # martes, miércoles y jueves
                  ((5, 6), 8, 11)],          # sábado y domingo
    "leyendo": [(TODOS, 8, 20)],
    "guitarra": [((5, 6), 10, 17)],          # sábado y domingo
    "videojuego": [((0, 1, 2, 3, 4), 11, 16)],  # lunes a viernes
}
ACTIVIDADES = list(HORARIOS)
CON_SONIDO = ("guitarra", "videojuego")   # actividades con loop de audio (al 15 %)
GOLPES = ("llamando", "saludo")           # toca el vidrio: suena el golpe (no de noche)
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
        self._en_conversacion = False  # conversación continua (segundo turno en adelante)
        self._fin_respuesta = float("-inf")
        self._enojos: list[float] = []
        self._contacto = reloj()
        self._dormido = False
        self._dormido_noche = False    # se durmió por la hora: a las 6:00 se levanta solo
        self._sin_red = False
        self._alarma_pendiente = None
        self._por_revisar_red = False
        self._ultima_revision_red = float("-inf")
        self._fase = "reposo"          # reposo | aburrido | actividad | entre | llamando | bostezo | dormido
        self._fase_hasta = 0.0
        self._actividades_hechas = 0
        self._ultima_actividad: str | None = None
        self._hasta_saludo = 0.0
        self._sonando_mio = False      # el loop (guitarra/videojuego) lo encendió esta capa
        self._musica = False           # está sonando una canción del reproductor

    # ------------------------------------------------------------ utilidades

    def _mostrar(self, cara: str) -> None:
        cambio = cara != self.cara
        if cambio:
            self.cara = cara
            self._poner(cara)
            logger.debug(f"[Comportamiento] cara -> {cara}")
        if cara in GOLPES:
            if cambio and not self.es_de_noche():
                self._sonido_actividad(True, suave=False)
        elif cara not in CON_SONIDO:
            self._sonido_actividad(False)

    def _sonido_actividad(self, encender: bool, suave: bool = True) -> None:
        """Loop de la actividad actual (guitarra o videojuego) al 15 %. Solo apaga el
        sonido si lo encendió esta capa: lo pedido con show_face lleva su propio
        sonido y su propio tiempo."""
        if not encender and not self._sonando_mio:
            return
        try:
            from src.plugins import mongo_caras

            if mongo_caras.bloqueada():
                return
            mongo_caras._sonido(self.cara if encender else "", encender, suave=suave)
            self._sonando_mio = encender
        except Exception:                                        # noqa: BLE001
            pass

    def _fin_de_respuesta(self) -> None:
        """Terminó de contestar: se suelta la cara que solo acompañaba la respuesta (clima)
        y, si pediste una alarma que la IA no programó, se programa."""
        try:
            self._revisar_alarma_pendiente()
        except Exception as e:                                   # noqa: BLE001
            logger.error(f"[Comportamiento] alarma pendiente: {e}")
        try:
            from src.plugins import mongo_caras

            mongo_caras.fin_de_respuesta()
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
        """Actividades de inactividad que tocan ahora según HORARIOS."""
        acts = [a for a in ACTIVIDADES if self._en_horario(a)]
        if not acts and not self.es_de_noche():
            acts = list(RELLENO)              # de día siempre hace algo (nunca se duerme)
        return acts

    def _en_horario(self, actividad: str) -> bool:
        m = self._momento()
        return any(m.weekday() in dias and desde <= m.hour < hasta
                   for dias, desde, hasta in HORARIOS.get(actividad, []))

    def es_de_noche(self) -> bool:
        h = self._momento().hour
        return h >= NOCHE[0] or h < NOCHE[1]

    def _levantarse(self, ahora: float) -> None:
        """A las 6:00: se despierta solo."""
        self._dormido = self._dormido_noche = False
        self._contacto, self._fase = ahora, "reposo"
        from src.plugins import mongo_caras

        if not mongo_caras.bloqueada():
            mongo_caras.mostrar("despertar", DESPERTAR)
            self.cara = "despertar"
        self._texto("¡Buenos días! Ya amaneció, y yo igual de guapo.")
        logger.info("[Comportamiento] son las 6:00, se levanta")

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
        self._dormido_noche = False
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
        if anterior == "speaking" and estado != "speaking":
            self._fin_respuesta = self._reloj()
            self._fin_de_respuesta()
        if estado == "listening":
            if anterior == "speaking" or (anterior == "idle"
                                          and self._reloj() - self._fin_respuesta <= CONVERSA_VENTANA):
                self._en_conversacion = True
            elif anterior == "idle":
                self._en_conversacion = False
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
            self._mostrar(self.cara_escucha())
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
        if POMPI.search(texto or ""):
            from src.plugins import mongo_caras

            mongo_caras.mostrar("saludo", SALUDO)     # choca los cinco con su palmada
            self.cara = "saludo"
            logger.info("[Comportamiento] pompi: saludo")
            return
        if ACTUALIZAR.search(texto or ""):
            from src.plugins import mongo_caras

            # acompaña la respuesta, pero al menos ACTUALIZANDO_MIN segundos
            mongo_caras.mostrar("actualizando", 60, hasta_respuesta=True, minimo=ACTUALIZANDO_MIN)
            self.cara = "actualizando"
            logger.info("[Comportamiento] le pidieron actualizar: actualizando")
            return
        if self.estado != "speaking":
            self._mostrar("pensando")
        self._clima_si_pregunta(texto)
        self._alarma_si_pide(texto)

    def _alarma_si_pide(self, texto: str) -> None:
        """Recuerda el pedido de alarma; al terminar la respuesta se revisa si la IA la programó."""
        hora = hora_de_alarma(texto, self._momento())
        if hora is None:
            return
        from src.plugins import mongo_alarmas

        mongo_alarmas._asegurar()
        ultimo = max([it["id"] for it in mongo_alarmas._items], default=0)
        self._alarma_pendiente = (hora, ultimo)
        logger.info(f"[Comportamiento] pidió alarma a las {hora[0]:02d}:{hora[1]:02d}")

    def _revisar_alarma_pendiente(self) -> None:
        pend, self._alarma_pendiente = self._alarma_pendiente, None
        if not pend:
            return
        (h, m), ultimo = pend
        from src.plugins import mongo_alarmas

        if any(it["id"] > ultimo for it in mongo_alarmas._items):
            return                                    # la IA ya la programó
        it = mongo_alarmas.programar("alarma", mongo_alarmas.proxima(h, m, []), hora=(h, m))
        logger.info(f"[Comportamiento] la IA no programó la alarma: la programo yo ({mongo_alarmas.describir(it)})")
        self._texto(f"Alarma programada para las {h:02d}:{m:02d}")

    def _clima_si_pregunta(self, texto: str) -> None:
        """Pregunta del clima: pone la animación del clima real, la use o no la IA."""
        try:
            from src.mcp.tools.weather import service

            if not service.PREGUNTA_CLIMA.search(texto or ""):
                return
            asyncio.get_running_loop().create_task(service.mostrar_clima_de(texto))
        except RuntimeError:
            pass                                  # sin loop (pruebas sin asyncio)
        except Exception as e:                                   # noqa: BLE001
            logger.debug(f"[Comportamiento] clima automático: {e}")

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
            self._fin_de_respuesta()
            self._emocion_turno = None
            self._en_conversacion = True
            self._fin_respuesta = self._reloj()
            self._mostrar("conversa_escucha")

    def cara_escucha(self) -> str:
        """escuchando en la primera pregunta; conversa_escucha en la conversación continua."""
        return "conversa_escucha" if self._en_conversacion else "escuchando"

    def al_musica(self, estado: str) -> None:
        """Estado del reproductor: playing / paused / stopped / completed / error."""
        sonando = (estado or "").lower() == "playing"
        self._musica = sonando
        if sonando:
            self._contactar()
        if self.estado == "idle":
            self._mostrar("musica" if sonando else self._cara_reposo())

    def error_de_red(self) -> None:
        """py-xiaozhi avisó un error de red: se confirma en verificar_red antes de
        mostrar sin_conexion (puede ser solo el servidor cerrando la sesión)."""
        self._por_revisar_red = True

    async def verificar_red(self) -> bool:
        """Prueba la conexión y actualiza la cara. Devuelve True si hay internet."""
        self._por_revisar_red = False
        self._ultima_revision_red = self._reloj()
        ok = await asyncio.to_thread(hay_internet)
        if not ok:
            if not self._sin_red:
                logger.warning("[Comportamiento] sin internet: muestro sin_conexion")
            self.sin_conexion()
        elif self._sin_red:
            self.volvio_red()
        else:
            logger.info("[Comportamiento] aviso de error de red, pero hay internet: lo ignoro")
        return ok

    def sin_conexion(self) -> None:
        """Sin internet confirmado."""
        self._sin_red = True
        if self.estado == "idle":
            self._mostrar("sin_conexion")

    def volvio_red(self) -> None:
        logger.info("[Comportamiento] volvió la conexión")
        self._sin_red = False
        self._contacto = self._reloj()
        if self.estado == "idle":
            self._mostrar("musica" if self._musica else self._cara_reposo())

    def toca_revisar_red(self) -> bool:
        return self._por_revisar_red or (
            self._sin_red and self._reloj() - self._ultima_revision_red >= REVISAR_RED_CADA)

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
        if self.cara in CON_SONIDO and self._fase == "actividad" and not self._sonando_mio and self._en_horario(self.cara):
            self._sonido_actividad(True)      # una cara pedida tapó la actividad; vuelve el sonido
        if self._musica:                      # escuchando música no se aburre
            self._contacto = ahora
            if self.cara != "musica":
                self._mostrar("musica")
            return
        quieto = ahora - self._contacto
        noche = self.es_de_noche()
        if self._dormido:
            if self._dormido_noche and not noche:
                self._levantarse(ahora)
            return
        if noche and quieto >= DORMIR_NOCHE and self._fase != "bostezo":
            self._fase, self._fase_hasta = "bostezo", ahora + BOSTEZO
            self._mostrar("bostezo")
            self._texto("Buenas noches... a dormir, que la belleza no se mantiene sola."
                        if noche else "Bueno... me voy a echar una siestita.")
            return
        if self._fase == "bostezo":
            if ahora >= self._fase_hasta:
                self._fase, self._dormido = "dormido", True
                self._dormido_noche = noche
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
            disponibles = self._actividades()
            if not disponibles:                    # de noche: solo mira alrededor
                self._fase, self._fase_hasta = "entre", ahora + ENTRE_ACTIVIDADES
                self._mostrar("mirando")
                return
            opciones = [a for a in disponibles if a != self._ultima_actividad] or disponibles
            act = self._azar.choice(opciones)
            self._ultima_actividad = act
            self._fase, self._fase_hasta = "actividad", ahora + ACTIVIDAD
            self._actividades_hechas += 1
            self._mostrar(act)
            if act in CON_SONIDO and self._en_horario(act):   # el videojuego de relleno va mudo
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


def hay_internet(timeout: float = 3.0) -> bool:
    """¿Hay salida a internet? Abre una conexión TCP corta a servidores públicos."""
    for host, puerto in (("1.1.1.1", 443), ("8.8.8.8", 53), ("api.tenclass.net", 443)):
        try:
            with socket.create_connection((host, puerto), timeout=timeout):
                return True
        except OSError:
            continue
    return False


async def correr() -> None:
    """Tic una vez por segundo. Lo arranca el plugin de UI."""
    while True:
        try:
            if _instancia is not None:
                _instancia.tic()
                if _instancia.toca_revisar_red():
                    await _instancia.verificar_red()
        except asyncio.CancelledError:
            raise
        except Exception as e:                                   # noqa: BLE001
            logger.error(f"[Comportamiento] error en el tic: {e}", exc_info=True)
        await asyncio.sleep(1.0)
