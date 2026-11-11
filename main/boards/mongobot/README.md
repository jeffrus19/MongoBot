# MongoBot

Asistente de voz sobre la **Freenove ESP32-S3 Display 2.8"** (FNK0104A): pantalla
ILI9341 320x240 táctil, códec ES8311 con micrófono y parlante.

El hardware y los pines son los mismos del board `freenove-esp32s3-display-2.8-lcd`.
Lo que cambia:

- Caras propias: 21 GIF animados en `emojis/`, uno por emoción (`happy.gif`,
  `sad.gif`, ...). Se empaquetan en la partición de assets al compilar.
- Tema oscuro, para que la interfaz combine con el fondo negro de las caras.
- Palabras de activación propias con MultiNet: "mongo bot" y "monguito"
  (definidas en `config.json`).

## Compilar

Desde la terminal de ESP-IDF, en la raíz del proyecto:

```
python scripts/build.py mongobot --language es-ES
```

## Cambiar las caras

Reemplaza los GIF de `emojis/` manteniendo los nombres. Tamaño recomendado:
320x240, fondo negro.

## Cambiar las palabras de activación

Edita `custom_wake_word` en `config.json`. Varias palabras se separan con `;`.
`threshold` va de 1 a 99: más bajo es más sensible (y se equivoca más).
