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
| Revisión cada segundo (`asyncio`) | Un `esp_timer` o tarea de FreeRTOS que revisa una vez por segundo. |
| Aviso al servidor con `UI_SEND_TEXT` para que grite "RING RING RING" | Mandar el aviso por el protocolo del firmware para que el servidor responda hablando. **Hay que verificar con la placa** cuál mensaje usar (por ejemplo, el de palabra de activación con un texto propio); si no se puede, de respaldo suena un pitido local. |
| Se calla si el usuario habla (mensaje `stt`) | Igual: al recibir `stt` del servidor, o al tocar la pantalla. |
| Sonido de la guitarra con `winsound` | `guitarra.ogg` (Opus 24 kHz) en la partición de assets, reproducido por el códec de audio. |

## Orden sugerido al portar

1. Caras minimalistas en LVGL (neutral, parpadeo y giro sobre la esfera primero).
2. Las 21 emociones del servidor.
3. `self.screen.show_face` con el candado.
4. Estados de conversación (cúpula escuchando, hablando con globitos, pensando).
5. Alarmas con NVS + SNTP y el "RING RING RING".
6. Capa de inactividad (aburrirse, guitarra, ejercicio, videojuego, leer, dormir).
7. Tacto, temporada, clima y el resto.
