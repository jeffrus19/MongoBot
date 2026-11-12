# MongoBot

Asistente de voz sobre la **Freenove ESP32-S3 Display 2.8"** (FNK0104A): pantalla
ILI9341 320x240 táctil, códec ES8311 con micrófono y parlante.

El hardware y los pines son los mismos del board `freenove-esp32s3-display-2.8-lcd`.
Lo que cambia:

- Caras propias estilo anime a color: 21 GIF animados en `emojis/`, uno por
  emoción (`happy.gif`, `sad.gif`, ...). Se empaquetan en la partición de assets
  al compilar. En `emojis_extra/` hay tres más (excited, smug, terrified) que el
  servidor no manda, pensadas para los comportamientos por inactividad.
- Animaciones de inactividad en `inactividad/`: tocar guitarra (con sonido),
  hacer ejercicio y jugar videojuegos, en el estilo minimalista.
- Estilo minimalista en `fuentes_minimal/`: la cara nueva (aro blanco, cara
  negra que gira sobre una esfera, colores por emoción) con las 24 emociones y
  el modo conversación. Pensado para dibujarse en vivo con LVGL; por ahora las
  caras del firmware siguen siendo los GIF de `emojis/`.
- Tema oscuro, para que la interfaz combine con el fondo negro de las caras.
- Palabras de activación propias con MultiNet: "mongo bot" y "monguito"
  (definidas en `config.json`).

## Compilar

Desde la terminal de ESP-IDF, en la raíz del proyecto:

```
python scripts/build.py mongobot --language es-ES
```

## Cambiar las caras

Las caras salen de `fuentes_caras/caras_hoja.png` (6 columnas x 4 filas, con el
nombre de cada emoción debajo). Para regenerarlas:

```
cd main/boards/mongobot/fuentes_caras
python generar_caras2.py caras_hoja.png salida sueltas
```

Después se copian a `emojis/` las 21 estándar y a `emojis_extra/` las otras tres.
Una cara dibujada aparte se pone en `sueltas/` con el nombre de la emoción
(`crying.png`) y reemplaza a la de la hoja. Necesita Pillow, numpy, scipy y
opencv-python.

También se puede reemplazar un GIF a mano, manteniendo el nombre: 320x240,
fondo negro.

## Cambiar las palabras de activación

Edita `custom_wake_word` en `config.json`. Varias palabras se separan con `;`.
`threshold` va de 1 a 99: más bajo es más sensible (y se equivoca más).
