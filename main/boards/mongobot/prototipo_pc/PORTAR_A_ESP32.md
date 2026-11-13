# Pasar el prototipo de PC a la ESP32

Todo lo de MongoBot se prueba primero en py-xiaozhi (PC) y después se pasa al
firmware. Esta carpeta guarda una copia del prototipo para tenerlo a mano al
portarlo. La idea es que en la placa funcione igual y con **los mismos nombres
de herramientas MCP**, así el texto de personalidad en xiaozhi.me no cambia.

## Qué hay en el prototipo

| Archivo (en py-xiaozhi) | Qué hace |
|---|---|
| `src/plugins/mongo_caras.py` | Puente herramienta → pantalla, con "candado" para que la cara pedida no la tape otra. |
| `src/mcp/tools/cara/register.py` | Herramientas `self.screen.show_face` y `self.screen.list_faces`. |
| `src/plugins/mongo_alarmas.py` | Alarmas, temporizadores y recordatorios: guarda, revisa cada segundo y, al cumplirse, hace que MongoBot grite "¡RING RING RING!" con su voz. |
| `src/plugins/mongo_comportamiento.py` | Capa de comportamiento: elige la cara según la conversación (escuchando → cúpula, pensando, hablando → emoción o globitos, enojo repetido → furioso, despertar), el sistema (saludo, sin conexión) y la inactividad (aburrido, ejercicio, leyendo, guitarra y videojuego según su horario, llamando, bostezo, dormir, temporada). Es lógica pura con reloj inyectable: se pasa casi tal cual a C++. |
| `src/mcp/tools/alarmas/register.py` | Herramientas `self.alarm.set_alarm`, `set_timer`, `set_reminder`, `list_alarms`, `cancel_alarm`, `stop_ringing`. |
| `src/mcp/tools/weather/service.py` | Clima real con Open-Meteo (sin clave). Por defecto San José, Costa Rica; muestra clima_sol, clima_nube o clima_lluvia 10 s según el código WMO. |
| `src/mcp/tools/trafico/` | Herramienta `self.traffic.check(destination, origin)`: ruta en carro y tiempo estimado **sin tráfico en vivo**, con OpenStreetMap y sin claves (Nominatim para ubicar el lugar, prefiriendo Costa Rica; OSRM para la ruta). Origen por defecto: Sabanilla. Devuelve la mejor ruta (vía, minutos, km) y las alternativas; la IA aclara que en hora pico puede tardar más. Máximo una consulta por segundo y User-Agent propio, como piden esos servicios. En la placa: las mismas dos llamadas HTTPS con `esp_http_client`. |
| Cambios en `ui_presenter.py`, `ui.py`, `mcp_server.py`, `volume/register.py`, `weather/register.py` | Conectan lo anterior (marcados con el comentario `# MongoBot`). |

## Equivalencias en el firmware (XiaoZhi, C++)

| En la PC | En la ESP32 |
|---|---|
| GIF en `assets/emojis` | Caras dibujadas en vivo con LVGL (círculos, líneas, rectángulos redondeados), a partir de `fuentes_minimal/`. La proyección sobre la esfera es la misma fórmula de `Lienzo.T` en `mongo_minimal.py`. |
| `McpTool(...)` en Python | `McpServer::GetInstance().AddTool(...)` en el código del board (`mongobot.cc`), con los mismos nombres y parámetros. |
| `mongo_caras.mostrar` + candado | Una clase en el board que cambia la animación de LVGL y bloquea `SetEmotion` mientras dure. |
| Archivo `mongo_alarmas.json` | NVS (la clase `Settings` del firmware). |
| Hora de la PC | Hora por SNTP al conectarse al WiFi (zona horaria de Costa Rica, UTC-6, sin horario de verano). |
| `mongo_comportamiento.Comportamiento` (al_estado, al_texto_usuario, al_emocion, sin_conexion, tic) | Una clase igual en el board: `al_estado` desde `Application::SetDeviceState`, `al_texto_usuario` al recibir `stt`, `al_emocion` donde el firmware llama `SetEmotion` desde el mensaje `llm`, y `tic` desde un timer de 1 s. Los tiempos (60 s aburrirse, 10 min dormir, etc.) igual. |
| Revisión cada segundo (`asyncio`) | Un `esp_timer` o tarea de FreeRTOS que revisa una vez por segundo. |
| Aviso al servidor con `UI_SEND_TEXT` para que grite "RING RING RING" | En py-xiaozhi ese texto viaja como mensaje de palabra de activación (`listen` / `detect` con texto), igual que en el firmware (`SendWakeWordDetected`). **Probado:** el servidor solo acepta textos cortos; uno largo responde con `type=alert`. Por eso el aviso va corto (`ALARMA: gimnasio`, máx. 60 caracteres) y la instrucción de gritar está en la descripción de las herramientas `self.alarm.*`. En la placa: mismo mensaje y mismos avisos cortos. |
| Se calla solo cuando el usuario pide que pare (`stt` con una orden de parar) | Igual, o al tocar la pantalla. |
| Alertas del servidor (`type=alert`) se muestran y se registran | Mostrarlas en la pantalla (el firmware ya trae `Alert`). |
| Sonido de guitarra y videojuego con `winsound` (`<nombre>.wav` pedido, `<nombre>_suave.wav` en inactividad) | `guitarra.ogg` y `videojuego.ogg` (Opus 24 kHz) en la partición de assets, reproducido por el códec de audio; en inactividad, con la ganancia más baja. |

## Reglas que salieron de las pruebas (noviembre 2026)

Las cuatro pruebas de `prototipo_pc` (`probar_animaciones`, `probar_comportamiento`,
`probar_disparadores`, `probar_casos_limite`) pasan sin fallas. En la placa hay que
respetar estas reglas, porque cada una corrigió un error real:

1. **Cuándo se suelta una cara pedida (show_face).** Solo cuando lo llamás desde el
   reposo (idle → escuchando) o cuando llega un `stt` tuyo. Si viene de hablar y
   sigue escuchando solo (modo automático), la cara se queda: si no, "tocá guitarra"
   duraba lo que dura la respuesta.
2. **La alarma no se suelta nunca por eso.** Solo se apaga cuando le contestás
   (`stt` que no sea un aviso propio) o al tocar la pantalla.
3. **Alarma mientras duerme.** No poner "despertar" si hay una cara con candado;
   antes el despertar tapaba la alarma.
4. **Emoción desconocida** (el servidor manda algo sin animación): usar
   conversa_habla, no neutral.
5. **Modo tiempo real** (no pasa por "hablando"): al llegar `tts stop` estando en
   escucha, volver a conversa_escucha. Antes se quedaba con la emoción.
6. **Guitarra de inactividad tapada** por otra cara (volumen, por ejemplo): cuando
   se suelta, el tic vuelve a encender el sonido.
7. **show_face tolerante:** mayúsculas, espacios y nombres en español
   ("feliz", "enojado", "año nuevo") se traducen al nombre exacto; los segundos se
   recortan a 2-120 en vez de rechazar la llamada.
8. **Animaciones de una sola vez:** despertar y tacto_despertar no se repiten.
9. **Horarios de las actividades de inactividad** (hora de Costa Rica, por SNTP):
   - ejercicio: martes, miércoles y jueves de 9:00 a 10:00; sábado y domingo de 8:00 a 11:00;
   - leyendo: todos los días de 8:00 a 20:00;
   - guitarra: sábado y domingo de 10:00 a 17:00, sonido al 15 %;
   - videojuego: lunes a viernes de 11:00 a 16:00, sonido 8 bits al 10 %.
   Nunca repite la misma actividad dos veces seguidas si hay otra disponible. Fuera
   de horario (de noche) no hace actividades: solo mira alrededor hasta dormirse.
   Pedidas por voz (show_face) salen a cualquier hora y suenan a volumen normal.
   En la PC son `guitarra_suave.wav` (15 %) y `videojuego_suave.wav` (10 %); en la placa,
   bajar la ganancia del códec mientras suenen. El loop del videojuego es propio:
   `inactividad/videojuego.ogg`, fuente en `fuentes_minimal/audio_videojuego.py`.

10. **Pregunta suelta y conversación continua.** Lo llamás desde el reposo:
   escuchando. Desde el segundo turno (vuelve a escuchar justo después de hablar, en
   modo automático o tiempo real, o lo llamás de nuevo antes de 30 s): conversa_escucha,
   la cúpula de cerca. Al responder sin emoción: conversa_habla (globitos) en los dos
   casos. Pasados 30 s en reposo, la conversación termina y la próxima vuelve a
   escuchando. Despertarlo cuenta como pregunta nueva.
11. **Noche: duerme de 22:00 a 6:00, todos los días.** Al minuto sin hablarle bosteza,
   dice buenas noches y se duerme (sin actividades ni llamarte). Se despierta si lo
   llamás por su nombre o si suena una alarma o un recordatorio; al minuto de terminar
   vuelve a dormirse. A las 6:00 se levanta solo (despertar y "buenos días"). De día
   sigue la siesta a los 10 min sin interacción.

12. **sin_conexion solo si de verdad no hay conexión.** py-xiaozhi avisa "error de
   red" también cuando el servidor cierra la sesión de mala manera, y la cara salía
   sin motivo. Ahora cada aviso se confirma abriendo una conexión corta a internet;
   si responde, se ignora. Mientras esté sin red, prueba cada 15 s y, si volvió,
   regresa al reposo solo. En la placa: mostrarla solo cuando el WiFi esté caído
   (`WifiStation::IsConnected()` falso) o no haya salida a internet, no por un cierre
   del websocket.

13. **Golpes en el vidrio:** cuando MongoBot toca la pantalla suena un golpe propio
   (`fuentes_minimal/audio_golpes.py`): llamando, tres toquecitos de nudillo
   sincronizados con la animación (3,0 s, se repite con ella), y saludo, la palmada del
   choque de cinco (una vez, a 1,0 s). No suenan de noche. En la placa:
   `inactividad/llamando.ogg` y `inactividad/saludo.ogg`.

14. **"Pompi":** si lo que dijiste (stt) trae "pompi" (o como lo escribe el
   reconocimiento: pompy, pompis, pombi), sale saludo con la palmada por 3 s, aunque
   sea de noche, y la respuesta se muestra al terminar. Regex `POMPI` en
   mongo_comportamiento.

15. **Clima con su animación:** las herramientas se llaman `self.weather.get_current` y
   `self.weather.get_forecast`. Antes se llamaban `get_weather`, igual que la del
   servidor de XiaoZhi, y el servidor respondía con una alerta "Duplicate tool names"
   y usaba la suya (sin animación). La cara del clima (sol, nube o lluvia según el
   código WMO) acompaña toda la respuesta y se suelta cuando termina de hablar
   (`mostrar(..., hasta_respuesta=True)`).

16. **De día no se duerme.** Solo duerme de noche (22:00 a 6:00). En las horas del
   día sin actividad programada (6:00-8:00 y 20:00-22:00) alterna leyendo y videojuego
   (este sin sonido). Ya no existe la siesta de los 10 minutos.
17. **"Actualizá...":** si lo que dijiste trae "actualiz..." (actualizá, actualizar,
   actualizame), sale actualizando mientras contesta, con un mínimo de 6 s
   (`mostrar(..., hasta_respuesta=True, minimo=6)` y `fin_de_respuesta()`).

18. **Pantalla vertical (240x320).** La placa se usa parada. Las animaciones se
   dibujan con las mismas coordenadas de antes (320x240, cabeza en 160,124) sobre un
   lienzo de 320x320, y al final se recorta la franja de 240 de ancho. Cada animación
   tiene su encuadre en `fuentes_minimal/encuadre_vertical.json` (dx: corrimiento del
   recorte, ±40 como máximo para no cortar la cabeza; dy: subir o bajar la escena), que
   calcula `encuadre_vertical.py`: la cabeza queda siempre a la misma altura (centro en
   y=150 de 320) salvo las que necesitan otro lugar (cúpula de conversación, juego sin
   conexión, temporada, ejercicio, videojuego).
   En vertical toda la escena se achica al 85 % (80 % en escuchando) para que los
   adornos de los lados queden a 8 px o más del borde; el encuadre lo verifica.
   En vertical la cúpula de conversación se acerca un poco (zoom 1,12) y sale desde el
   borde de abajo, y los globitos salen encima de la cabeza en vez de a los lados.
   En LVGL: pantalla en orientación vertical (rotación del ILI9341/ST7789) y cada
   animación desplazada según ese JSON. `generar_todo.py` regenera las 69 de una vez.

19. **Clima siempre con animación.** Si lo que dijiste es una pregunta del clima
   (clima, llover, lluvia, temperatura, pronóstico, nublado, "qué tiempo hace"...),
   MongoBot busca él mismo el clima real y pone sol, nube o lluvia, aunque la IA
   conteste sin usar la herramienta. Toma la ciudad de "en <ciudad>" (si no existe, San
   José) y "mañana" usa el pronóstico del día siguiente. Regex `PREGUNTA_CLIMA` en
   weather/service.py. Qué cara: soleado -> clima_sol, nublado o neblina -> clima_nube,
   lloviendo o con 50 % o más de probabilidad de lluvia en las próximas 3 horas (o en
   el día, si es pronóstico) -> clima_lluvia.

20. **"Pon / coloca / programa una alarma a las ...":** si lo que dijiste pide una alarma
   con hora y la IA termina de contestar sin haberla programado, la programa MongoBot
   (`hora_de_alarma`: entiende 6:30, 7 pm, "6 y media de la tarde", "5 de la mañana";
   sin am/pm toma la próxima vez que llegue esa hora). Si la IA sí la programó, no se
   duplica; si no dijiste la hora, la IA pregunta.

21. **Videojuego, máximo 3 veces al día** por su cuenta (cuenta las veces que lo elige
   la inactividad; se reinicia cada día). Pedido por voz, sin límite. Cuando se acaba,
   el relleno de día queda solo con leyendo. En la placa: guardar el contador con la
   fecha en NVS para que no se reinicie si se reinicia la placa.

22. **La alarma suena hasta que le digás que pare.** Grita cada 30 s sin límite. Solo se
   apaga con una orden de parar ("para", "detené", "apagala", "ya", "basta", "callate",
   "ya me levanté"...; regex `PARAR` en mongo_alarmas) o la herramienta stop_ringing.
   Hablarle de otra cosa no la apaga. En la placa también al tocar la pantalla.
23. **Nunca pregunta qué o cuál alarma.** set_alarm se llama de una con la hora (la
   etiqueta es opcional); cancel_alarm sin decir cuál cancela la próxima, y con una hora
   ("6:30") cancela las de esa hora.

24. **Cómo suena la alarma.** Timbre de despertador mecánico en bucle (alarma.wav /
   `inactividad/alarma.ogg`, fuente `audio_alarma.py`) desde que se cumple hasta que le
   decís que pare, y cada 30 s MongoBot grita con su voz exactamente
   "RING RING RIIIIING ¡ALARMA!" ("¡SE ACABÓ EL TIEMPO!" en el temporizador,
   "¡RECORDATORIO! nota" en el recordatorio). Ese texto es lo que se le manda al
   servidor; la regla de repetirlo tal cual va en la descripción de las herramientas y
   en el rol del agente (porque en el primer turno las herramientas pueden no estar
   cargadas todavía).

25. **La cara del clima coincide con lo que dice.** Mientras está puesta una cara de
   clima, cada frase que dice MongoBot (mensajes `tts` con texto) se revisa: si habla de
   lluvia (y no "no va a llover") pasa a clima_lluvia, si dice nublado a clima_nube, si
   dice soleado o despejado a clima_sol (`cara_de_frase_clima`). Así nunca dice
   "soleado" con el paraguas, aunque la IA conteste de memoria.

26. **Rutas: OpenStreetMap siempre.** La descripción de self.traffic.check dice que es la
   forma predeterminada (y única) de contestar rutas, distancias y tiempos de viaje. Si
   preguntás una ruta ("ruta a Escazú", "¿cómo llego a...?", "¿cuánto duro a...?") y la
   IA contesta sin usarla, al terminar MongoBot le manda "usa OpenStreetMap: <tu
   pregunta>" una sola vez (regex `PEDIR_RUTA`).

27. **Solo ojos.** La mayoría de las caras van sin el aro blanco ni el disco negro: solo
   los ojos (y cejas, rubor, lágrimas), unas 2 veces más grandes, para aprovechar la
   pantalla. Conservan la cabeza redonda las que tienen cuerpo o lo necesitan
   (`CON_CUERPO` en mongo_minimal.py: saludo, sin_conexion, ejercicio, leyendo, guitarra,
   videojuego, clima_*, conectando, musica, conversa_habla, llamando, configurar_wifi,
   mensaje, pomodoro_*, navidad, anio_nuevo). Las que tienen adornos alrededor usan un
   tamaño y un corrimiento propios (`OJOS_AJUSTE`) para que nada toque el borde y el
   conjunto quede centrado. En LVGL: no dibujar el aro y escalar los rasgos con el mismo
   factor.

28. **Reposo de la mañana.** De 8:00 a 11:00, todos los días, la cara de reposo es
   pomodoro_trabajo en vez de neutral (`TRABAJO` en mongo_comportamiento.py). Navidad y
   año nuevo siguen teniendo prioridad.

### Matriz de disparadores (69 animaciones)

- **Con disparador propio (46):** escuchando, las 21 emociones del servidor, conversa_escucha,
  conversa_habla, pensando, furioso, despertar, saludo, sin_conexion, aburrido,
  mirando, llamando, ejercicio, leyendo, guitarra, videojuego (cada una en su horario), bostezo, sleepy,
  navidad, anio_nuevo, musica, volumen, clima_sol/nube/lluvia, alarma,
  temporizador, recordatorio.
- **Solo en la placa:** conectando, configurar_wifi, actualizando,
  tacto_cosquillas, tacto_molesto, tacto_despertar.
- **Funciones futuras:** mensaje (Telegram), pomodoro_descanso.
- **Personalidad, solo por show_face** (las elige la IA según la descripción de la
  herramienta): curioso, decepcionado, esceptico, eureka, excited, ignorando,
  ofendido, orgulloso, picaro, presumido, rodar_ojos, smug, terrified.
- neutral es el reposo (de 8:00 a 11:00, pomodoro_trabajo).

## Orden sugerido al portar

1. Caras minimalistas en LVGL (neutral, parpadeo y giro sobre la esfera primero).
2. Las 21 emociones del servidor.
3. `self.screen.show_face` con el candado.
4. Estados de conversación (cúpula escuchando, hablando con globitos, pensando).
5. Alarmas con NVS + SNTP y el "RING RING RING".
6. Capa de inactividad (aburrirse, ejercicio, videojuego, leer, guitarra de fin de semana, dormir).
7. Tacto, temporada, clima y el resto.
