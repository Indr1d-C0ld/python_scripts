#!/usr/bin/env python3
import requests
import time
import os
import subprocess

# Inserisci qui il token del tuo bot (ottenuto tramite BotFather)
TOKEN = ""
BASE_URL = f"https://api.telegram.org/bot{TOKEN}/"

# URL base del blog: modifica questo valore con il tuo dominio reale
BLOG_BASE_URL = "https://timrouter.dns.army/blog/"

# ID del canale Telegram dove postare il link del nuovo post
# Nota: per postare su un canale, il bot deve essere admin del canale.
REPOST_CHANNEL_ID = -1002363443306  # Modifica con l'ID del canale

def get_updates(offset=None, timeout=30):
    url = BASE_URL + "getUpdates"
    params = {'timeout': timeout}
    if offset:
        params['offset'] = offset
    response = requests.get(url, params=params)
    return response.json()

def send_message(chat_id, text):
    url = BASE_URL + "sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    requests.post(url, data=payload)

# Definizione degli stati della conversazione
STATE_AWAIT_TITLE = "await_title"
STATE_AWAIT_TAGS = "await_tags"
STATE_AWAIT_KEYWORDS = "await_keywords"
STATE_AWAIT_BODY = "await_body"

# Dizionario per memorizzare lo stato della conversazione per ogni chat_id
conversations = {}

def process_message(message):
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    # Comando per iniziare la creazione di un nuovo post
    if text == "/newpost":
        conversations[chat_id] = {
            "state": STATE_AWAIT_TITLE,
            "data": {"title": "", "tags": "", "keywords": "", "body": ""}
        }
        send_message(chat_id, "Inserisci il titolo del post:")
        return

    # Comando per annullare l'operazione
    if text == "/cancel":
        if chat_id in conversations:
            del conversations[chat_id]
        send_message(chat_id, "Operazione annullata.")
        return

    # Se non siamo in una conversazione, invita l'utente a inviare /newpost
    if chat_id not in conversations:
        send_message(chat_id, "Per creare un nuovo post, invia il comando /newpost")
        return

    # Gestione della conversazione in base allo stato corrente
    conv = conversations[chat_id]
    state = conv["state"]

    if state == STATE_AWAIT_TITLE:
        conv["data"]["title"] = text
        conv["state"] = STATE_AWAIT_TAGS
        send_message(chat_id, "Inserisci i tag separati da virgola (es. tag1, tag2):")
    elif state == STATE_AWAIT_TAGS:
        conv["data"]["tags"] = text
        conv["state"] = STATE_AWAIT_KEYWORDS
        send_message(chat_id, "Inserisci le parole chiave per il nome del post (verranno convertite in slug):")
    elif state == STATE_AWAIT_KEYWORDS:
        conv["data"]["keywords"] = text
        conv["state"] = STATE_AWAIT_BODY
        send_message(chat_id, "Inserisci il corpo del post. Invia /done quando hai finito:")
    elif state == STATE_AWAIT_BODY:
        if text == "/done":
            # Fine della raccolta, procedi con la creazione del post
            data = conv["data"]
            send_message(chat_id, "Creazione del post in corso, attendi prego...")
            # Prepara le variabili d'ambiente per lo script bash
            env = os.environ.copy()
            env["POST_TITLE"] = data["title"]
            env["POST_TAGS"] = data["tags"]
            env["POST_KEYWORDS"] = data["keywords"]
            env["POST_BODY"] = data["body"]
            try:
                subprocess.run(["/home/pi/blog/ask_new_post.sh"], env=env, check=True)
                send_message(chat_id, "Post creato e sito rigenerato con successo!")
                
                # Costruisci il link al nuovo post.
                # Assumiamo che il link sia composto da BLOG_BASE_URL/<keywords>
                new_post_link = BLOG_BASE_URL + "/" + data["keywords"]
                message_for_channel = f"Nuovo post: {data['title']}\nLeggi l'articolo completo qui: {new_post_link}"
                send_message(REPOST_CHANNEL_ID, message_for_channel)
            except subprocess.CalledProcessError as e:
                send_message(chat_id, f"Si è verificato un errore durante la creazione del post: {e}")
            # Termina la conversazione
            del conversations[chat_id]
        else:
            # Aggiungi il testo al corpo del post; se già presente, aggiungi un newline prima
            if conv["data"]["body"]:
                conv["data"]["body"] += "\n" + text
            else:
                conv["data"]["body"] = text
            send_message(chat_id, "Continua a inviare il corpo del post o invia /done per terminare.")
    else:
        send_message(chat_id, "Stato sconosciuto. Invia /cancel per annullare e riprova.")

def main():
    offset = None
    while True:
        updates = get_updates(offset)
        if "result" in updates:
            for update in updates["result"]:
                offset = update["update_id"] + 1
                if "message" in update:
                    process_message(update["message"])
        time.sleep(1)

if __name__ == "__main__":
    main()
