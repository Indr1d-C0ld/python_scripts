#!/usr/bin/env python3
import RPi.GPIO as GPIO
import time
import os

LED_PIN = 17  # GPIO17 (pin fisico 11)
MODE_FILE = "/tmp/led_mode.txt"  # File usato per impostare il "modo" del LED

GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)

def blink_pattern(pattern, repeat=1):
    """
    Esegue un pattern definito dalla lista 'pattern'.
    Ogni elemento della lista rappresenta un intervallo in secondi.
    Se il valore è positivo, il LED viene acceso per quel tempo,
    se negativo, il LED viene spento per quel tempo.
    """
    for _ in range(repeat):
        for interval in pattern:
            if interval > 0:
                GPIO.output(LED_PIN, GPIO.HIGH)
            else:
                GPIO.output(LED_PIN, GPIO.LOW)
            time.sleep(abs(interval))
    GPIO.output(LED_PIN, GPIO.LOW)

def get_mode():
    """
    Legge il file MODE_FILE per determinare il pattern da usare.
    Se il file non esiste, torna "normal".
    """
    if os.path.exists(MODE_FILE):
        try:
            with open(MODE_FILE, "r") as f:
                mode = f.read().strip()
            return mode
        except Exception as e:
            return "normal"
    else:
        return "normal"

try:
    while True:
        mode = get_mode()

        if mode == "normal":
            # Pattern normale: LED acceso per 1s, spento per 1s.
            blink_pattern([1, -1])
        elif mode == "warning":
            # Pattern di avviso: lampeggio rapido (3 blink brevi).
            blink_pattern([0.2, -0.2, 0.2, -0.2, 0.2, -0.2], repeat=2)
        elif mode == "error":
            # Pattern di errore: LED acceso a lungo, poi breve pausa.
            blink_pattern([1, -0.3], repeat=3)
        else:
            # Default: stesso del normale.
            blink_pattern([1, -1])
        
        # Una breve pausa tra i cicli, puoi regolare questo valore
        time.sleep(0.5)
        
except KeyboardInterrupt:
    print("Terminazione del servizio LED.")

finally:
    GPIO.cleanup()
