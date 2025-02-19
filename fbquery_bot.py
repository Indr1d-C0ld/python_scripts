#!/usr/bin/env python3
import os
import re
import requests
import subprocess
import time
import sys
import html

# Inserisci qui il token del tuo Bot Telegram
TOKEN = ""
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

# Nome del file su cui effettuare la ricerca
FILE_NAME = "fb_italy.txt"

# Dizionario per gestire lo stato di ogni chat
user_states = {}

# Funzione per rimuovere le sequenze di escape ANSI (per sicurezza)
ansi_escape = re.compile(r'\x1B\[[0-?]*[ -/]*[@-~]')
def strip_ansi_codes(text):
    return ansi_escape.sub('', text)

def send_message(chat_id, text, parse_mode=None):
    """
    Invia un messaggio tramite il metodo sendMessage dell'API Telegram.
    """
    url = f"{BASE_URL}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    if parse_mode:
        data["parse_mode"] = parse_mode
    try:
        response = requests.post(url, data=data)
        print(f"Inviato messaggio a {chat_id}: {text}", flush=True)
    except Exception as e:
        print("Errore nell'invio del messaggio:", e, flush=True)

def send_long_message(chat_id, text, parse_mode="HTML"):
    """
    Telegram limita i messaggi a 4096 caratteri.
    Questa funzione suddivide il testo in chunk, esegue l'escape per HTML e
    lo racchiude tra <pre>...</pre> in modo da mantenere l'aspetto "da terminale".
    """
    max_length = 4000  # Lasciamo spazio per i tag <pre> e </pre>
    for i in range(0, len(text), max_length):
        chunk = text[i:i+max_length]
        chunk_escaped = html.escape(chunk)
        formatted_chunk = f"<pre>{chunk_escaped}</pre>"
        send_message(chat_id, formatted_chunk, parse_mode=parse_mode)

def process_search(chat_id, keywords_text):
    """
    Esegue la ricerca sul file fb_italy.txt utilizzando ripgrep e awk,
    e invia l'output al chat_id. Tra ogni riga viene inserita una riga vuota
    per migliorarne la suddivisione.
    """
    keywords = keywords_text.split()
    if len(keywords) == 0:
        send_message(chat_id, "Nessuna parola chiave inserita. Esco.")
        return

    if not os.path.isfile(FILE_NAME):
        send_message(chat_id, f"Errore: il file {FILE_NAME} non esiste nella cartella corrente!")
        return

    # ------------------------------------------------------------------------------
    # 1) COSTRUZIONE DELLA PIPELINE DI RIPGREP PER RICERCA “AND” (case-insensitive)
    # ------------------------------------------------------------------------------
    command = f'rg --color=never -i "{keywords[0]}" "{FILE_NAME}"'
    for kw in keywords[1:]:
        command += f' | rg --color=never -i "{kw}"'

    # ------------------------------------------------------------------------------
    # 2) SCRIPT AWK PER FORMATTARE L'OUTPUT SENZA COLORAZIONE
    # ------------------------------------------------------------------------------
    # In questo caso lo script AWK si limita a stampare le righe così come sono.
    awk_script = r'''
BEGIN {
  nKeys = split(keywords, kwArray, " ");
}
{
  print $0;
}
'''

    full_command = f'{command} | awk -F ":" -v keywords="{ " ".join(keywords) }" \'{awk_script}\''
    
    header = f"\nCerco nel file '{FILE_NAME}' le righe contenenti (AND) tutte le keyword (case-insensitive): {' '.join(keywords)}\n"
    send_message(chat_id, header)

    try:
        result = subprocess.check_output(full_command, shell=True, universal_newlines=True, stderr=subprocess.STDOUT)
        result_clean = strip_ansi_codes(result)
        if not result_clean.strip():
            send_message(chat_id, "Nessun risultato trovato.")
        else:
            # Aggiunge una riga vuota tra ogni riga di output
            result_with_spaces = "\n\n".join(result_clean.splitlines())
            send_long_message(chat_id, result_with_spaces)
    except subprocess.CalledProcessError as e:
        send_message(chat_id, f"Errore nell'esecuzione della ricerca:\n{e.output}")

def handle_update(update):
    """
    Gestisce un singolo update (messaggio) ricevuto dal Bot.
    """
    if "message" in update:
        message = update["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")
        print(f"Ricevuto messaggio da {chat_id}: {text}", flush=True)
        if text and text.split()[0] == "/start":
            user_states[chat_id] = "awaiting_keywords"
            send_message(chat_id, "Benvenuto!\nInserisci le parole chiave (separate da spazio):")
        elif chat_id in user_states and user_states[chat_id] == "awaiting_keywords":
            process_search(chat_id, text)
            user_states[chat_id] = None
        else:
            send_message(chat_id, "Per iniziare, invia il comando /start.")

def main():
    """
    Loop principale: il bot utilizza il metodo getUpdates per controllare i nuovi messaggi.
    """
    print("Avvio del bot... (Polling per aggiornamenti)", flush=True)
    offset = None
    while True:
        try:
            print("Polling per aggiornamenti...", flush=True)
            url = f"{BASE_URL}/getUpdates?timeout=20"
            if offset:
                url += f"&offset={offset}"
            response = requests.get(url, timeout=30)
            print("Richiesta getUpdates effettuata.", flush=True)
            if response.status_code != 200:
                print("Errore in getUpdates:", response.text, flush=True)
                time.sleep(1)
                continue

            data = response.json()
            if not data.get("ok"):
                print("Risposta non ok:", data, flush=True)
                time.sleep(1)
                continue

            updates = data.get("result", [])
            if updates:
                print(f"Ricevuti {len(updates)} aggiornamenti.", flush=True)
            for update in updates:
                offset = update["update_id"] + 1
                handle_update(update)
        except Exception as e:
            print("Errore nel polling:", e, flush=True)
            time.sleep(1)

if __name__ == "__main__":
    main()
