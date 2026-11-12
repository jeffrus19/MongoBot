"""Loop chiptune original para la animación de videojuego (8 bits).
Melodía propia: onda cuadrada (melodía), triangular (bajo), ruido (percusión) y
un "blip" de puntos cada tanto. Genera videojuego.wav (44,1 kHz, mono, 16 bits)."""
import array, math, random, wave

SR = 44100
BPM = 150
CORCHEA = 60 / BPM / 2
random.seed(8)

def nota(n):                      # número MIDI -> Hz
    return 440 * 2 ** ((n - 69) / 12)

def cuadrada(f, t, ciclo=0.5):
    return 1.0 if (f * t) % 1 < ciclo else -1.0

def triangular(f, t):
    x = (f * t) % 1
    return 4 * x - 1 if x < 0.5 else 3 - 4 * x

# melodía (MIDI, corcheas); 0 = silencio. 4 compases x 8 corcheas, se repite 2 veces
MEL = [72,0,76,79, 76,74,72,0,  74,0,77,81, 79,77,74,0,
       76,79,84,79, 76,72,74,76, 77,76,74,71, 72,0,0,0]
BAJO = [48,48,55,55, 53,53,55,55, 48,48,55,55, 53,55,48,48]   # negras
largo = int(SR * CORCHEA * len(MEL) * 2)
buf = [0.0] * largo

def poner(inicio, dur, fn, vol):
    a, b = int(inicio * SR), min(largo, int((inicio + dur) * SR))
    for i in range(a, b):
        t = (i - a) / SR
        env = min(1.0, t / 0.005) * max(0.0, 1 - t / dur) ** 0.6
        buf[i] += fn(t) * vol * env

for vuelta in range(2):
    base = vuelta * CORCHEA * len(MEL)
    for k, n in enumerate(MEL):
        if n:
            f = nota(n); ciclo = 0.25 if vuelta else 0.5
            poner(base + k * CORCHEA, CORCHEA * 0.9, lambda t, f=f, c=ciclo: cuadrada(f, t, c), 0.22)
    for k, n in enumerate(BAJO):
        f = nota(n)
        poner(base + k * 2 * CORCHEA, 2 * CORCHEA * 0.95, lambda t, f=f: triangular(f, t), 0.35)
    for k in range(len(MEL)):                       # percusión de ruido
        if k % 4 == 0:
            poner(base + k * CORCHEA, 0.06, lambda t: random.uniform(-1, 1), 0.18)
        elif k % 2 == 0:
            poner(base + k * CORCHEA, 0.025, lambda t: random.uniform(-1, 1), 0.08)
    # blip de "punto ganado": dos notas rápidas hacia arriba
    for pos in (11, 27):
        t0 = base + pos * CORCHEA
        poner(t0, 0.06, lambda t: cuadrada(nota(88), t, 0.5), 0.12)
        poner(t0 + 0.06, 0.12, lambda t: cuadrada(nota(95), t, 0.5), 0.12)

pico = max(abs(x) for x in buf)
datos = array.array('h', (int(x / pico * 0.85 * 32767) for x in buf))
with wave.open("videojuego.wav", "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(datos.tobytes())
print(f"videojuego.wav: {largo / SR:.1f} s")
