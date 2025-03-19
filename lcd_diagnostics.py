#!/usr/bin/env python3
from RPLCD.i2c import CharLCD
import time
import socket
import os
import shutil

# Configurazione del display: modifica l'indirizzo I2C se necessario (solitamente 0x27 o 0x3F)
lcd = CharLCD('PCF8574', 0x27)

def get_cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp = int(f.read().strip()) / 1000.0
        return temp
    except Exception:
        return 0

def get_uptime():
    try:
        with open("/proc/uptime", "r") as f:
            uptime_seconds = float(f.readline().split()[0])
            uptime_str = time.strftime("%H:%M:%S", time.gmtime(uptime_seconds))
        return uptime_str
    except Exception:
        return "N/A"

def get_ip_address():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip_address = s.getsockname()[0]
    except Exception:
        ip_address = "N/A"
    finally:
        s.close()
    return ip_address

def get_torrent_users():
    # Inserisci qui la logica per determinare il numero di utenti in download.
    # Questa funzione è un placeholder che restituisce un valore simulato.
    return 3

def get_ram_usage():
    try:
        meminfo = {}
        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts = line.split()
                key = parts[0].rstrip(':')
                value = int(parts[1])
                meminfo[key] = value
        mem_total = meminfo.get("MemTotal", 0)       # in kB
        mem_available = meminfo.get("MemAvailable", 0)  # in kB
        mem_used = mem_total - mem_available
        # Conversione in MB
        mem_total_mb = mem_total / 1024
        mem_used_mb = mem_used / 1024
        return mem_used_mb, mem_total_mb
    except Exception:
        return 0, 0

def get_sd_usage():
    try:
        usage = shutil.disk_usage('/')
        # Conversione da byte a GB
        total_gb = usage.total / (1024**3)
        used_gb = usage.used / (1024**3)
        free_gb = usage.free / (1024**3)
        return used_gb, total_gb, free_gb
    except Exception:
        return 0, 0, 0

def check_mount(path):
    if os.path.ismount(path):
        return "Montato"
    else:
        return "Non montato"

while True:
    # Pagina 1: Temperatura e Uptime
    temp = get_cpu_temp()
    uptime = get_uptime()
    lcd.clear()
    lcd.write_string("Temp: {:.1f} C".format(temp))
    lcd.crlf()
    lcd.write_string("Uptime: {}".format(uptime))
    time.sleep(6)

    # Pagina 2: IP e Hardware
    ip_address = get_ip_address()
    lcd.clear()
    lcd.write_string("{}".format(ip_address))
    lcd.crlf()
    lcd.write_string("ServerPi RPi3")
    time.sleep(6)

    # Pagina 3: Torrent e RAM
    torrent_users = get_torrent_users()
    ram_used, ram_total = get_ram_usage()
    lcd.clear()
    lcd.write_string("Torrent Up: {}".format(torrent_users))
    lcd.crlf()
    lcd.write_string("RAM: {:.0f}/{:.0f} MB".format(ram_used, ram_total))
    time.sleep(6)

    # Pagina 4: Spazio SD
    used_gb, total_gb, free_gb = get_sd_usage()
    lcd.clear()
    lcd.write_string("SD: {:.1f}/{:.1f}GB".format(used_gb, total_gb))
    lcd.crlf()
    lcd.write_string("Free: {:.1f}GB".format(free_gb))
    time.sleep(6)

    # Pagina 5: Stato mount USB
    usb_storage = check_mount("/media/usb_storage")
    usb_temp = check_mount("/media/usb_temp")
    lcd.clear()
    lcd.write_string("USB Backup:")
    lcd.crlf()
    lcd.write_string("{}".format(usb_storage))
    time.sleep(6)
    lcd.clear()
    lcd.write_string("USB Temp:")
    lcd.crlf()
    lcd.write_string("{}".format(usb_temp))
    time.sleep(6)

