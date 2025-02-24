#!/usr/bin/env python3
import RPi.GPIO as GPIO
import time

# Imposta il numero del pin GPIO (in modalità BCM)
LED_PIN = 17

GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)

try:
    while True:
        # Accendi il LED
        GPIO.output(LED_PIN, GPIO.HIGH)
        print("LED acceso")
        time.sleep(1)  # rimane acceso per 1 secondo

        # Spegni il LED
        GPIO.output(LED_PIN, GPIO.LOW)
        print("LED spento")
        time.sleep(1)  # rimane spento per 1 secondo

except KeyboardInterrupt:
    print("Terminazione del programma.")

finally:
    GPIO.cleanup()
