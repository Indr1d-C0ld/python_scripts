import time
from pynput.mouse import Controller
from pynput.keyboard import Controller as KeyboardController

# Configurazione
INTERVALLO = 60  # Intervallo in secondi tra ogni azione
UTILIZZA_MOUSE = True  # True per muovere il mouse, False per premere un tasto innocuo
TASTO_INNOCUO = "shift"  # Tasto innocuo da premere se UTILIZZA_MOUSE è False

# Inizializza il controller del mouse e della tastiera
mouse = Controller()
keyboard = KeyboardController()

def muovi_mouse():
    """Muove il mouse impercettibilmente."""
    posizione_attuale = mouse.position
    # Muove il mouse di 1 pixel a destra e poi torna alla posizione originale
    mouse.move(1, 0)
    time.sleep(0.1)
    mouse.position = posizione_attuale

def premi_tasto():
    """Premi un tasto innocuo."""
    keyboard.press(TASTO_INNOCUO)
    keyboard.release(TASTO_INNOCUO)

if __name__ == "__main__":
    print(f"Script attivo: azione ogni {INTERVALLO} secondi.")
    print(f"{'Muovo il mouse' if UTILIZZA_MOUSE else f'Premo il tasto {TASTO_INNOCUO}'} per evitare lo standby.")

    try:
        while True:
            if UTILIZZA_MOUSE:
                muovi_mouse()
            else:
                premi_tasto()
            time.sleep(INTERVALLO)
    except KeyboardInterrupt:
        print("\nScript terminato.")
