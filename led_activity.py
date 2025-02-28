import RPi.GPIO as GPIO
import time
import threading
import signal
import sys
import inotify.adapters

# Configurazione
LED_PIN = 17
WATCHED_FILE = "/home/pi/sismografo.db"

# Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)

# Stato iniziale: LED acceso fisso (indica che il sistema è vivo)
GPIO.output(LED_PIN, GPIO.HIGH)

# Flag per la gestione del lampeggio
blinking = False
stop_thread = False

def blink_led():
    """Thread che gestisce il lampeggio del LED."""
    global blinking, stop_thread
    while not stop_thread:
        if blinking:
            for _ in range(5):  # Lampeggia 5 volte
                GPIO.output(LED_PIN, GPIO.LOW)
                time.sleep(0.2)
                GPIO.output(LED_PIN, GPIO.HIGH)
                time.sleep(0.2)
            blinking = False
        else:
            GPIO.output(LED_PIN, GPIO.HIGH)
            time.sleep(0.5)

def signal_activity():
    """Attiva il lampeggio."""
    global blinking
    blinking = True

def file_watcher():
    """Monitora il file sismografo.db e segnala ogni modifica."""
    notifier = inotify.adapters.Inotify()
    notifier.add_watch(WATCHED_FILE)

    for event in notifier.event_gen(yield_nones=False):
        (_, type_names, path, filename) = event
        if 'MODIFY' in type_names:
            signal_activity()

def clean_exit(signum, frame):
    """Pulisce e termina il programma."""
    global stop_thread
    stop_thread = True
    GPIO.output(LED_PIN, GPIO.LOW)
    GPIO.cleanup()
    sys.exit(0)

# Collegamento segnali di sistema (CTRL+C o arresto systemd)
signal.signal(signal.SIGINT, clean_exit)
signal.signal(signal.SIGTERM, clean_exit)

# Avvia thread per il lampeggio
led_thread = threading.Thread(target=blink_led)
led_thread.daemon = True
led_thread.start()

# Avvia il watcher sul file (bloccante)
try:
    file_watcher()
except KeyboardInterrupt:
    clean_exit(None, None)

