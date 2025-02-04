#!/usr/bin/env python3
"""
network_monitor.py

Script per monitorare in tempo reale una lista di host (IP) mediante ping,
mostrandone lo stato (online/offline) in un’interfaccia testuale con curses.
Evidenzia il cambiamento di stato (avvenuto nell'ultimo minuto) con un colore diverso.

La configurazione (lista di host, nome, intervallo di controllo) viene salvata in un file JSON.
"""

import curses
import subprocess
import time
import json
import os

CONFIG_FILE = "hosts_config.json"

# Funzione per eseguire il ping di un host
def ping_host(ip):
    try:
        # -c 1: un pacchetto; -W 1: timeout di 1 secondo (dipende dalla distribuzione)
        output = subprocess.run(["ping", "-c", "1", "-W", "1", ip],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        return output.returncode == 0
    except Exception:
        return False

# Funzione per caricare la configurazione oppure richiederla in modo interattivo
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    else:
        print("Configurazione non trovata. Inserisci i dati per i monitor da avviare.")
        hosts = []
        while True:
            ip = input("Inserisci indirizzo IP (oppure lascia vuoto per terminare): ").strip()
            if not ip:
                break
            nome = input("Inserisci un nome per questo host: ").strip()
            intervallo = input("Intervallo di controllo (in secondi, default 60): ").strip()
            try:
                intervallo = int(intervallo) if intervallo else 60
            except ValueError:
                intervallo = 60
            # Inizializziamo la struttura per l’host
            hosts.append({
                "ip": ip,
                "nome": nome if nome else ip,
                "interval": intervallo,
                "last_state": None,         # True=online, False=offline, None=mai controllato
                "last_change": 0,           # timestamp dell'ultimo cambio stato
                "next_check": time.time()   # prossimo controllo
            })
        # Salva la configurazione per i prossimi avvii
        with open(CONFIG_FILE, "w") as f:
            json.dump(hosts, f, indent=4)
        return hosts

# Funzione per aggiornare lo stato degli host se il tempo di controllo è scaduto
def update_hosts(hosts):
    now = time.time()
    for host in hosts:
        if now >= host["next_check"]:
            stato = ping_host(host["ip"])
            # Se lo stato è diverso da quello registrato, aggiorna l’istante di cambio
            if host["last_state"] is None or stato != host["last_state"]:
                host["last_change"] = now
            host["last_state"] = stato
            host["next_check"] = now + host["interval"]

# Funzione che gestisce l’interfaccia curses
def curses_loop(stdscr, hosts):
    # Inizializza i colori: ad esempio, verde per online, rosso per offline, giallo se cambiato recentemente.
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)  # online
    curses.init_pair(2, curses.COLOR_RED, -1)    # offline
    curses.init_pair(3, curses.COLOR_YELLOW, -1) # cambio recente
    curses.init_pair(4, curses.COLOR_CYAN, -1)   # intestazione

    stdscr.nodelay(True)  # modalità non bloccante per la lettura dell’input
    stdscr.timeout(1000)  # aggiornamento ogni secondo

    while True:
        stdscr.erase()
        height, width = stdscr.getmaxyx()
        header = "Network Monitor - aggiorna ogni secondo. Premere 'q' per uscire."
        stdscr.attron(curses.color_pair(4))
        stdscr.addstr(0, 0, header)
        stdscr.attroff(curses.color_pair(4))
        stdscr.addstr(1, 0, "-" * (len(header)+2))
        
        # Aggiorna gli host
        update_hosts(hosts)

        # Mostra la lista degli host
        row = 3
        now = time.time()
        for host in hosts:
            stato = host["last_state"]
            # Imposta il testo di stato
            if stato is None:
                stato_str = "N/D"
            else:
                stato_str = "ONLINE" if stato else "OFFLINE"

            # Scegli il colore: se il cambio è avvenuto negli ultimi 60 secondi, usa il colore “cambio recente”
            if now - host["last_change"] < 60:
                color = curses.color_pair(3) | curses.A_BOLD | curses.A_BLINK
            else:
                color = curses.color_pair(1) if stato else curses.color_pair(2)

            # Format della stringa da mostrare
            line = f"{host['nome']:<15} {host['ip']:<15} [{stato_str}]  (prossimo check: {int(host['next_check']-now)} sec)"
            try:
                stdscr.addstr(row, 0, line, color)
            except curses.error:
                pass  # in caso di finestra troppo piccola
            row += 1

        stdscr.refresh()
        # Controllo dell'input: se viene premuto 'q' esce
        try:
            key = stdscr.getch()
            if key == ord('q'):
                break
        except:
            pass

def main():
    hosts = load_config()
    curses.wrapper(curses_loop, hosts)

if __name__ == "__main__":
    main()
