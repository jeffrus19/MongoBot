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
| `src/plugins/mongo_comportamiento.py` | Capa de comportamiento: elige la cara según la conversación (escuchando → cúpula, pensando, hablando → emoción o globitos, enojo repetido → furioso, despertar), el sistema (saludo, sin conexión) y la inactividad (aburrido, guitarra/ejercicio/videojuego/leyendo, llamando, bostezo, dormir, temporada). Es lógica pura con reloj inyectable: se pasa casi tal cual a C++. |
| `src/mcp/tools/alarmas/register.py` | Herramientas `self.alarm.set_alarm`, `set_timer`, `set_reminder`, `list_alarms`, `cancel_alarm`, `stop_ringing`. |
| Cambios en `ui_presenter.py`, `ui.py`, `mcp_server.py` | Conectan lo anterior (marcados con el comentario `# MongoBot`). |

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
| Sonido de la guitarra con `winsound` | `guitarra.ogg` (Opus 24 kHz) en la partición de assets, reproducido por el códec de audio. |

## Orden sugerido al portar

1. Caras minimalistas en LVGL (neutral, parpadeo y giro sobre la esfera primero).
2. Las 21 emociones del servidor.
3. `self.screen.show_face` con el candado.
4. Estados de conversación (cúpula escuchando, hablando con globitos, pensando).
5. Alarmas con NVS + SNTP y el "RING RING RING".
6. Capa de inactividad (aburrirse, guitarra, ejercicio, videojuego, leer, dormir).
7. Tacto, temporada, clima y el resto.
