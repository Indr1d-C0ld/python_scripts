import RPi.GPIO as GPIO
import time

# Configurazione del GPIO
DHT_PIN = 4  # Pin GPIO (in modalità BCM)

GPIO.setmode(GPIO.BCM)
GPIO.setup(DHT_PIN, GPIO.IN)

def read_dht22(pin):
    data = []
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)
    time.sleep(0.02)
    GPIO.output(pin, GPIO.HIGH)
    GPIO.setup(pin, GPIO.IN)

    # Raccogli il segnale
    for i in range(500):
        data.append(GPIO.input(pin))

    # Decodifica i dati
    humidity_bits = data[0:8]
    temperature_bits = data[16:24]

    humidity = int("".join(map(str, humidity_bits)), 2)
    temperature = int("".join(map(str, temperature_bits)), 2)

    return humidity, temperature

try:
    humidity, temperature = read_dht22(DHT_PIN)
    print(f"Umidità: {humidity}% | Temperatura: {temperature}°C")
except Exception as e:
    print(f"Errore: {e}")
finally:
    GPIO.cleanup()

