#!/usr/bin/env python3
import socket
import sys
import re
import time
import json
import threading
import os
import struct
import random

# Configurazioni base
SERVER   = "irc.libera.chat"
PORT     = 6667
CHANNEL  = "#canale"
BOTNICK  = "nickname"  # Nick valido: non inizia con numero

# Password per autenticazione NickServ
BOT_PASSWORD = "password"  # Sostituisci con la password registrata per il nick

# Utenti autorizzati per file sharing e admin (separa eventuali privilegi se necessario)
FILE_ALLOWED_USERS = ["nickname", "UtenteAutorizzato"]
ADMINS            = ["nickname"]  # Solo questi potranno usare i comandi avanzati

# File per statistiche e log
STATS_FILE    = "irc_bot_stats.json"
LOG_FILE      = "irc_bot.log"
SAVE_INTERVAL = 60  # secondi

# Directory per file condivisi
SHARED_DIR = "shared_files"          # File disponibili per download
UPLOAD_DIR = os.path.join(SHARED_DIR, "uploaded")  # File inviati dagli utenti

# Per il resume, salviamo i trasferimenti attivi
# La chiave sarà (utente, filename, port)
ACTIVE_DCC_TRANSFERS = {}

# Range di porte per DCC (da aprire sul router: ad es. 50000-50100)
DCC_PORT_MIN = 50000
DCC_PORT_MAX = 50100

def choose_dcc_port():
    return random.randint(DCC_PORT_MIN, DCC_PORT_MAX)

class IRCBot:
    def __init__(self, server, port, channel, botnick):
        self.server    = server
        self.port      = port
        self.channel   = channel
        self.botnick   = botnick
        self.ircsock   = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.start_time = time.time()
        
        # Statistiche del canale
        self.stats = {
            "messages": 0,
            "joins": 0,
            "parts": 0,
            "quits": 0,
            "users": {}
        }
        self.running   = True
        self.last_save = time.time()
        self.lock      = threading.Lock()
        
        # Creazione cartelle per i file se non esistono
        if not os.path.exists(SHARED_DIR):
            os.makedirs(SHARED_DIR)
        if not os.path.exists(UPLOAD_DIR):
            os.makedirs(UPLOAD_DIR)
        
        # Carica statistiche precedenti se esistono
        if os.path.exists(STATS_FILE):
            self.load_stats()
    
    def log_message(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        line = f"[{timestamp}] {message}\n"
        with open(LOG_FILE, "a") as f:
            f.write(line)
        print(line.strip())
    
    def save_stats(self):
        with self.lock:
            try:
                with open(STATS_FILE, "w") as f:
                    json.dump(self.stats, f, indent=4)
                self.log_message("Statistiche salvate su file.")
            except Exception as e:
                self.log_message(f"Errore nel salvataggio delle statistiche: {e}")
    
    def load_stats(self):
        try:
            with open(STATS_FILE, "r") as f:
                self.stats = json.load(f)
            self.log_message("Statistiche caricate da file.")
        except Exception as e:
            self.log_message(f"Errore nel caricamento delle statistiche: {e}")
    
    def connect(self):
        self.log_message(f"Connessione a {self.server}:{self.port}...")
        self.ircsock.connect((self.server, self.port))
        self.send_cmd("NICK " + self.botnick)
        self.send_cmd("USER {0} {0} {0} :Python IRC Bot Esteso".format(self.botnick))
        time.sleep(2)
        # Autenticazione NickServ (se la password è impostata)
        if BOT_PASSWORD:
            self.send_cmd("PRIVMSG NickServ :IDENTIFY " + BOT_PASSWORD)
            self.log_message("Autenticazione NickServ inviata.")
        time.sleep(1)
        self.send_cmd("JOIN " + self.channel)
    
    def send_cmd(self, command):
        self.log_message(">> " + command)
        self.ircsock.send((command + "\r\n").encode("utf-8"))
    
    def run(self):
        buffer = ""
        while self.running:
            try:
                data = self.ircsock.recv(2048).decode("utf-8", errors="ignore")
            except Exception as e:
                self.log_message("Errore nella ricezione: " + str(e))
                break
            if not data:
                self.log_message("Connessione chiusa dal server.")
                break
            buffer += data
            while "\r\n" in buffer:
                line, buffer = buffer.split("\r\n", 1)
                self.log_message("<< " + line)
                self.handle_line(line)
            if time.time() - self.last_save > SAVE_INTERVAL:
                self.save_stats()
                self.last_save = time.time()
        self.save_stats()
    
    def handle_line(self, line):
        # Gestione PING
        if line.startswith("PING"):
            self.send_cmd("PONG " + line.split()[1])
            return
        
        parts = line.split(" ")
        if len(parts) < 2:
            return
        
        cmd = parts[1]
        
        # Gestione dei messaggi CTCP (per DCC)
        if "PRIVMSG" in parts and "\x01" in line:
            m = re.match(r":([^!]+)!", parts[0])
            if not m:
                return
            nick = m.group(1)
            target = parts[2]
            msg = " ".join(parts[3:])[1:]
            if msg.startswith("DCC"):
                self.handle_ctcp(nick, target, msg)
                return
        
        # Gestione degli eventi JOIN, PART e QUIT
        if cmd == "JOIN":
            m = re.match(r":([^!]+)!", parts[0])
            if m:
                nick = m.group(1)
                with self.lock:
                    self.stats["joins"] += 1
                self.send_cmd("PRIVMSG " + self.channel + " :Benvenuto, " + nick + "!")
                # Se l'utente è un admin, assegnagli OP
                if nick in ADMINS:
                    self.send_cmd("MODE " + self.channel + " +o " + nick)
            return
        
        elif cmd == "PART":
            m = re.match(r":([^!]+)!", parts[0])
            if m:
                nick = m.group(1)
                with self.lock:
                    self.stats["parts"] += 1
                self.log_message(f"{nick} ha lasciato il canale.")
            return
        
        elif cmd == "QUIT":
            m = re.match(r":([^!]+)!", parts[0])
            if m:
                nick = m.group(1)
                with self.lock:
                    self.stats["quits"] += 1
                self.log_message(f"{nick} ha disconnesso dal server.")
            return
        
        # Gestione dei messaggi PRIVMSG non CTCP
        if cmd == "PRIVMSG":
            m = re.match(r":([^!]+)!", parts[0])
            if not m:
                return
            nick = m.group(1)
            target = parts[2]
            msg = " ".join(parts[3:])[1:]
            
            with self.lock:
                self.stats["messages"] += 1
                if nick not in self.stats["users"]:
                    self.stats["users"][nick] = 0
                self.stats["users"][nick] += 1
            
            # Se il messaggio inizia con "!" lo consideriamo un comando
            if msg.startswith("!"):
                self.handle_command(nick, msg)
            return
    
    def handle_ctcp(self, sender, target, msg):
        """Gestisce i messaggi CTCP DCC: SEND (upload), RESUME e ACCEPT per il resume."""
        tokens = msg.strip("\x01").split()
        if len(tokens) < 2:
            return
        subcmd = tokens[1].upper()
        if subcmd == "SEND":
            if target == self.botnick:
                if sender not in FILE_ALLOWED_USERS:
                    self.send_cmd("PRIVMSG " + sender + " :Non sei autorizzato ad inviare file.")
                    return
                self.dcc_receive(sender, msg)
        elif subcmd == "RESUME":
            self.handle_dcc_resume(sender, msg)
    
    def handle_command(self, nick, msg):
        """Gestisce i comandi testuali inviati in chat."""
        cmd_parts = msg.strip().split(" ")
        command = cmd_parts[0][1:].lower()  # rimuove il carattere '!'
        # Comandi avanzati per admin
        if command in ["stats", "uptime", "kick", "shutdown"]:
            if nick not in ADMINS:
                self.send_cmd("PRIVMSG " + nick + " :Non sei autorizzato ad usare questo comando.")
                return
            self.handle_admin_command(nick, msg)
            return
        # Comandi di file sharing e help
        if command == "help":
            help_msg = ("Comandi disponibili: !help, !files, !get <filename>, !stats, !uptime, !kick <nick>, !shutdown")
            self.send_cmd("PRIVMSG " + self.channel + " :" + help_msg)
        elif command == "files":
            files = os.listdir(SHARED_DIR)
            files_list = [f for f in files if os.path.isfile(os.path.join(SHARED_DIR, f))]
            response = "Files disponibili: " + ", ".join(files_list) if files_list else "Nessun file disponibile."
            self.send_cmd("PRIVMSG " + self.channel + " :" + response)
        elif command == "get":
            if len(cmd_parts) >= 2:
                filename = cmd_parts[1]
                if nick not in FILE_ALLOWED_USERS:
                    self.send_cmd("PRIVMSG " + nick + " :Non sei autorizzato a scaricare file.")
                    return
                threading.Thread(target=self.dcc_send, args=(filename, nick)).start()
            else:
                self.send_cmd("PRIVMSG " + self.channel + " :Utilizzo: !get <filename>")
        else:
            self.send_cmd("PRIVMSG " + self.channel + " :Comando non riconosciuto.")
    
    def handle_admin_command(self, nick, msg):
        """Gestisce i comandi avanzati inviati dagli admin."""
        cmd_parts = msg.strip().split(" ")
        command = cmd_parts[0][1:].lower()
        if command == "stats":
            with self.lock:
                response = (f"Stats: Messaggi: {self.stats['messages']}, Joins: {self.stats['joins']}, "
                            f"Parts: {self.stats['parts']}, Quits: {self.stats['quits']}, "
                            f"Utenti: {len(self.stats['users'])}.")
            self.send_cmd("PRIVMSG " + self.channel + " :" + response)
        elif command == "uptime":
            elapsed = int(time.time() - self.start_time)
            hours, rem = divmod(elapsed, 3600)
            minutes, seconds = divmod(rem, 60)
            uptime_str = f"{hours}h {minutes}m {seconds}s"
            self.send_cmd("PRIVMSG " + self.channel + " :Uptime: " + uptime_str)
        elif command == "kick":
            if len(cmd_parts) >= 2:
                target = cmd_parts[1]
                self.send_cmd("KICK " + self.channel + " " + target + " :Kicked by admin")
            else:
                self.send_cmd("PRIVMSG " + self.channel + " :Utilizzo: !kick <nick>")
        elif command == "shutdown":
            self.send_cmd("PRIVMSG " + self.channel + " :Shutting down as requested by admin.")
            self.running = False
            self.ircsock.close()
            sys.exit(0)
    
    def dcc_send(self, filename, user):
        """Invia un file tramite DCC SEND (con supporto a resume)."""
        file_path = os.path.join(SHARED_DIR, filename)
        if not os.path.exists(file_path):
            self.send_cmd("PRIVMSG " + user + " :File non trovato.")
            return
        filesize = os.path.getsize(file_path)
        port = choose_dcc_port()
        my_ip = socket.gethostbyname(socket.gethostname())
        ip_int = struct.unpack("!I", socket.inet_aton(my_ip))[0]
        dcc_msg = f"\x01DCC SEND {filename} {ip_int} {port} {filesize}\x01"
        self.send_cmd("PRIVMSG " + user + " :" + dcc_msg)
        self.log_message(f"Richiesta DCC SEND per file {filename} a {user} sulla porta {port}")
        key = (user, filename, port)
        ACTIVE_DCC_TRANSFERS[key] = {"file_path": file_path, "filesize": filesize, "offset": 0}
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(('', port))
            s.listen(1)
            s.settimeout(60)
            conn, addr = s.accept()
            self.log_message(f"Connessione DCC da {addr} per invio file {filename}")
            current_offset = 0
            with open(file_path, "rb") as f:
                while current_offset < filesize:
                    chunk = f.read(1024)
                    if not chunk:
                        break
                    try:
                        conn.sendall(chunk)
                    except Exception as e:
                        self.log_message(f"Trasferimento interrotto a {current_offset} byte: {e}")
                        ACTIVE_DCC_TRANSFERS[key]["offset"] = current_offset
                        return
                    current_offset += len(chunk)
                    ACTIVE_DCC_TRANSFERS[key]["offset"] = current_offset
            self.log_message(f"File {filename} inviato a {user}")
            conn.close()
            if key in ACTIVE_DCC_TRANSFERS:
                del ACTIVE_DCC_TRANSFERS[key]
        except Exception as e:
            self.log_message(f"Errore durante DCC SEND: {e}")
        finally:
            s.close()
    
    def handle_dcc_resume(self, sender, msg):
        """
        Gestisce la richiesta di resume di un trasferimento DCC.
        Il messaggio atteso è:
           "\x01DCC RESUME <filename> <port> <offset>\x01"
        """
        tokens = msg.strip("\x01").split()
        if len(tokens) < 4:
            self.log_message("Formato DCC RESUME non valido.")
            return
        try:
            filename = tokens[2]
            port = int(tokens[3])
            offset = int(tokens[4])
        except Exception as e:
            self.log_message(f"Errore nel parsing di DCC RESUME: {e}")
            return
        key = (sender, filename, port)
        if key not in ACTIVE_DCC_TRANSFERS:
            self.log_message("Nessun trasferimento attivo per questo file (resume request).")
            return
        record = ACTIVE_DCC_TRANSFERS[key]
        if offset >= record["filesize"]:
            self.log_message("Offset invalido per il file.")
            return
        accept_msg = f"\x01DCC ACCEPT {filename} {port} {offset}\x01"
        self.send_cmd("PRIVMSG " + sender + " :" + accept_msg)
        self.log_message(f"Inviato DCC ACCEPT per {filename} a {sender} per resume da offset {offset}")
        threading.Thread(target=self.dcc_send_resume, args=(sender, record["file_path"], filename, port, record["filesize"], offset, key)).start()
    
    def dcc_send_resume(self, user, file_path, filename, port, filesize, offset, key):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(('', port))
            s.listen(1)
            s.settimeout(60)
            self.log_message(f"In attesa di connessione DCC per resume del file {filename} sulla porta {port}")
            conn, addr = s.accept()
            self.log_message(f"Connessione DCC per resume da {addr} per file {filename}")
            with open(file_path, "rb") as f:
                f.seek(offset)
                current_offset = offset
                while current_offset < filesize:
                    chunk = f.read(1024)
                    if not chunk:
                        break
                    try:
                        conn.sendall(chunk)
                    except Exception as e:
                        self.log_message(f"Trasferimento resume interrotto a {current_offset} byte: {e}")
                        ACTIVE_DCC_TRANSFERS[key]["offset"] = current_offset
                        return
                    current_offset += len(chunk)
            self.log_message(f"File {filename} inviato (resume completato) a {user}")
            conn.close()
            if key in ACTIVE_DCC_TRANSFERS:
                del ACTIVE_DCC_TRANSFERS[key]
        except Exception as e:
            self.log_message(f"Errore durante DCC SEND (resume): {e}")
        finally:
            s.close()
    
    def dcc_receive(self, sender, msg):
        """
        Gestisce il trasferimento in upload tramite DCC SEND.
        Il formato atteso è:
           "\x01DCC SEND <filename> <ip_int> <port> <filesize>\x01"
        Se il trasferimento viene interrotto, il client potrà tentare un resume.
        """
        try:
            tokens = msg.strip("\x01").split()
            if len(tokens) < 5:
                self.log_message("Formato DCC SEND non valido per upload.")
                return
            filename = tokens[2]
            ip_int = int(tokens[3])
            port = int(tokens[4])
            filesize = int(tokens[5])
            ip = socket.inet_ntoa(struct.pack("!I", ip_int))
            self.log_message(f"Ricevuto DCC SEND da {sender} per file {filename} ({filesize} bytes) da {ip}:{port}")
            dest_path = os.path.join(UPLOAD_DIR, filename)
            resume_offset = os.path.getsize(dest_path) if os.path.exists(dest_path) else 0
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(60)
            s.connect((ip, port))
            mode = "ab" if resume_offset > 0 else "wb"
            with open(dest_path, mode) as f:
                total_received = resume_offset
                while total_received < filesize:
                    chunk = s.recv(1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    total_received += len(chunk)
            self.log_message(f"File {filename} ricevuto da {sender} e salvato in {dest_path}")
            s.close()
            self.send_cmd("PRIVMSG " + sender + " :Upload di " + filename + " completato.")
        except Exception as e:
            self.log_message(f"Errore durante DCC RECEIVE (upload): {e}")

if __name__ == "__main__":
    bot = IRCBot(SERVER, PORT, CHANNEL, BOTNICK)
    try:
        bot.connect()
        bot.run()
    except KeyboardInterrupt:
        bot.log_message("Chiusura del bot per KeyboardInterrupt.")
        bot.running = False
        bot.save_stats()
        sys.exit(0)

