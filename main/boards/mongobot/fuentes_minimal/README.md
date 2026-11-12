# MongoBot minimalista

Estilo nuevo de la cara: un aro blanco grueso con la cara negra adentro. Lo que
va dentro de la cara (ojos, boca, cejas) y los signos de alrededor cambian de
color según la emoción. La cara está pintada sobre una esfera que gira, así que
al mirar a un lado los rasgos se achatan, se inclinan y el ojo cercano se ve
más grande.

Todo se dibuja con figuras simples (círculos, líneas, rectángulos redondeados),
así que en la placa la idea es dibujarlo en vivo con LVGL, sin GIF. Estos
scripts generan GIF y videos para revisar las animaciones y para probarlas en
py-xiaozhi.

## Scripts

| Script | Qué genera |
|---|---|
| `mongo_minimal.py` | Las 24 emociones, los estados escuchando, música y mirando, y el modo conversación (se acerca, escucha y habla). Un GIF por estado y dos videos de muestra. |
| `generar_guitarra_min.py` | Tocando guitarra: GIF, audio OGG para la placa y WAV para la PC. |
| `generar_ejercicio_min.py` | Haciendo flexiones. |
| `generar_videojuego_min.py` | Jugando videojuegos con un monstruito de 8 bits propio. |
| `generar_extras_min.py` | Estados del sistema y funciones: pensando, despertar, conectando, sin conexión, saludo, alarma, temporizador, clima (sol, nube, lluvia), pomodoro (trabajo y descanso), presumido, llamando la atención, reacción al tacto (cosquillas, molesto, despertar) y leyendo. |
| `generar_extras2_min.py` | Emociones de personalidad (rodar los ojos, escéptico, ofendido, furioso, eureka, pícaro, ignorando, orgulloso, curioso, aburrido, decepcionado), bostezo, avisos (recordatorio y mensaje) y estados de la placa (configurar WiFi, actualizando y volumen). |
| `audio_guitarra.py` | Módulo con el sonido de la guitarra y los tiempos de cada nota. |

Uso (desde esta carpeta):

```
python mongo_minimal.py salida
python generar_guitarra_min.py salida
python generar_ejercicio_min.py salida
python generar_videojuego_min.py salida
python generar_extras_min.py salida
python generar_extras2_min.py salida
```

Necesitan Pillow, numpy, scipy y ffmpeg en el PATH.

Las animaciones de inactividad ya generadas están en `../inactividad/`.
