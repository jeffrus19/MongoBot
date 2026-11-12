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
| `src/plugins/mongo_comportamiento.py` | Capa de comportamiento: elige la cara según la conversación (escuchando → cúpula, pensando, hablando → emoción o globitos, enojo repetido → furioso, despertar), el sistema (saludo, sin conexión) y la inactividad (aburrido, ejercicio y videojuego alternados, guitarra solo fines de semana de 10 a 17, llamando, bostezo, dormir, temporada). Es lógica pura con reloj inyectable: se pasa casi tal cual a C++. |
| `src/mcp/tools/alarmas/register.py` | Herramientas `self.alarm.set_alarm`, `set_timer`, `set_reminder`, `list_alarms`, `cancel_alarm`, `stop_ringing`. |
| `src/mcp/tools/weather/service.py` | Clima real con Open-Meteo (sin clave). Por defecto San José, Costa Rica; muestra clima_sol, clima_nube o clima_lluvia 10 s según el código WMO. |
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
| Se calla si el usuario habla (mensaje `stt`) | Igual: al recibir `stt` del servidor que no sea uno de los avisos propios (empiezan con ALARMA, TEMPORIZADOR o RECORDATORIO), o al tocar la pantalla. |
| Alertas del servidor (`type=alert`) se muestran y se registran | Mostrarlas en la pantalla (el firmware ya trae `Alert`). |
| Sonido de la guitarra con `winsound` (`guitarra.wav` pedida, `guitarra_suave.wav` en inactividad) | `guitarra.ogg` (Opus 24 kHz) en la partición de assets, reproducido por el códec de audio; en inactividad, con la ganancia más baja. |

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
9. **Actividades de inactividad:** alterna ejercicio y videojuego. La guitarra solo
   entra sábados y domingos de 10:00 a 17:00 (hora de Costa Rica, por SNTP) y a
   volumen moderado (en la PC, `guitarra_suave.wav` al 40 %; en la placa, bajar la
   ganancia del códec mientras suene). Pedida por voz (show_face) toca siempre y a
   volumen normal. leyendo queda solo para show_face.

### Matriz de disparadores (69 animaciones)

- **Con disparador propio (44):** las 21 emociones del servidor, conversa_escucha,
  conversa_habla, pensando, furioso, despertar, saludo, sin_conexion, aburrido,
  mirando, llamando, guitarra (fin de semana), ejercicio, videojuego, bostezo, sleepy,
  navidad, anio_nuevo, musica, volumen, clima_sol/nube/lluvia, alarma,
  temporizador, recordatorio.
- **Solo en la placa:** conectando, configurar_wifi, actualizando,
  tacto_cosquillas, tacto_molesto, tacto_despertar.
- **Funciones futuras:** mensaje (Telegram), pomodoro_trabajo, pomodoro_descanso.
- **Personalidad, solo por show_face** (las elige la IA según la descripción de la
  herramienta): curioso, decepcionado, esceptico, eureka, excited, ignorando,
  ofendido, orgulloso, picaro, presumido, rodar_ojos, smug, terrified, leyendo.
- **Sobra:** escuchando (la reemplazó conversa_escucha). neutral es el reposo.

## Orden sugerido al portar

1. Caras minimalistas en LVGL (neutral, parpadeo y giro sobre la esfera primero).
2. Las 21 emociones del servidor.
3. `self.screen.show_face` con el candado.
4. Estados de conversación (cúpula escuchando, hablando con globitos, pensando).
5. Alarmas con NVS + SNTP y el "RING RING RING".
6. Capa de inactividad (aburrirse, ejercicio, videojuego, guitarra de fin de semana, dormir).
7. Tacto, temporada, clima y el resto.
