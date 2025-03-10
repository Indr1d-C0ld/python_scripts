import socket
import json
import csv
import gzip
import time
import signal
import sys
from datetime import datetime
from math import radians, cos, sin, sqrt, atan2
from rich.console import Console
from rich.table import Table
from rich.live import Live

# Configurazione GPSD
GPSD_HOST = "127.0.0.1"
GPSD_PORT = 2947

# Configurazione logger
# 130 km/h = 36.1 m/s
SPEED_LIMIT = 36.1  # Velocità limite (m/s)
# Magazzino: 42.7676 11.1161
GEOFENCE_CENTER = (42.7676, 11.1161)  # Centro geofence (latitudine, longitudine)
GEOFENCE_RADIUS = 2000  # Raggio geofence in metri
LOG_FILENAME = f"gps_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
ALERT_LOG_FILENAME = "gps_alerts.log"

# Variabili globali
gpx_points = []
stop_flag = False  # Indica se lo script deve fermarsi in modo ordinato
console = Console()

def haversine(lat1, lon1, lat2, lon2):
    """Calcola la distanza tra due coordinate geografiche in metri."""
    R = 6371  # Raggio della Terra in km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c * 1000  # Distanza in metri

def get_gps_data():
    """Connette a gpsd e restituisce i dati JSON."""
    try:
        gps_socket = socket.create_connection((GPSD_HOST, GPSD_PORT), timeout=10)
        gps_socket.sendall(b'?WATCH={"enable":true,"json":true}\n')
        raw_data = gps_socket.recv(4096).decode('utf-8')
        gps_socket.close()
        return [json.loads(line) for line in raw_data.splitlines() if line.strip()]
    except Exception as e:
        console.log(f"Errore nella connessione a gpsd: {e}")
        return []

def save_to_csv(writer, data):
    """Salva i dati nel file CSV."""
    writer.writerow(data)

def save_to_gpx():
    """Salva i dati in formato GPX."""
    import gpxpy
    import gpxpy.gpx

    gpx = gpxpy.gpx.GPX()
    track = gpxpy.gpx.GPXTrack()
    gpx.tracks.append(track)
    segment = gpxpy.gpx.GPXTrackSegment()
    track.segments.append(segment)

    for point in gpx_points:
        segment.points.append(
            gpxpy.gpx.GPXTrackPoint(point['lat'], point['lon'], elevation=point.get('alt', 0))
        )

    gpx_filename = LOG_FILENAME.replace(".csv", ".gpx")
    with open(gpx_filename, "w") as gpx_file:
        gpx_file.write(gpx.to_xml())
    console.log(f"GPX salvato in {gpx_filename}")

def compress_log_file():
    """Comprimi il file CSV per risparmiare spazio."""
    compressed_filename = LOG_FILENAME + ".gz"
    with open(LOG_FILENAME, "rb") as f_in:
        with gzip.open(compressed_filename, "wb") as f_out:
            f_out.writelines(f_in)
    console.log(f"Log compresso salvato in {compressed_filename}")

def log_alert(message):
    """Registra avvisi in un file separato."""
    with open(ALERT_LOG_FILENAME, "a") as alert_file:
        alert_file.write(f"{datetime.now()}: {message}\n")

def display_live_data(lat, lon, alt, speed, in_geofence):
    """Mostra i dati GPS in tempo reale."""
    table = Table(title="Dati GPS in Tempo Reale")
    table.add_column("Latitudine", justify="right")
    table.add_column("Longitudine", justify="right")
    table.add_column("Altitudine (m)", justify="right")
    table.add_column("Velocità (m/s)", justify="right")
    table.add_column("Geofence", justify="right")
    table.add_row(str(lat), str(lon), str(alt), str(speed), "Dentro" if in_geofence else "Fuori")
    console.clear()
    console.print(table)

def handle_signal(sig, frame):
    """Gestisce i segnali di terminazione."""
    global stop_flag
    stop_flag = True
    console.log("\nSegnale ricevuto. Terminazione in corso...")

def main():
    global stop_flag
    with open(LOG_FILENAME, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Timestamp", "Latitude", "Longitude", "Altitude", "Speed", "Climb"])
        console.log(f"Salvando i dati in {LOG_FILENAME}...")

        try:
            with Live(console=console, refresh_per_second=1):
                while not stop_flag:
                    gps_data = get_gps_data()
                    for packet in gps_data:
                        if packet.get('class') == 'TPV':
                            timestamp = packet.get('time', "N/A")
                            lat = packet.get('lat', 0)
                            lon = packet.get('lon', 0)
                            alt = packet.get('alt', 0)
                            speed = packet.get('speed', 0)
                            in_geofence = haversine(lat, lon, *GEOFENCE_CENTER) <= GEOFENCE_RADIUS
                            
                            save_to_csv(writer, [timestamp, lat, lon, alt, speed, packet.get('climb', "N/A")])
                            gpx_points.append({"lat": lat, "lon": lon, "alt": alt})
                            display_live_data(lat, lon, alt, speed, in_geofence)

                            # Notifiche
                            if speed > SPEED_LIMIT:
                                log_alert(f"⚠️ Superata velocità massima: {speed:.2f} m/s")
                            if speed == 0:
                                log_alert(f"⛔ Velocità nulla (fermo)")
                            if in_geofence:
                                log_alert("✅ Entrato nell'area geografica")
                            else:
                                log_alert("❌ Uscito dall'area geografica")
                    time.sleep(1)
        except KeyboardInterrupt:
            stop_flag = True
        finally:
            console.log("Finalizzazione in corso...")
            save_to_gpx()
            compress_log_file()
            console.log("Script terminato con successo.")

if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_signal)  # Intercetta Ctrl+C
    signal.signal(signal.SIGTERM, handle_signal)  # Intercetta shutdown/reboot
    time.sleep(5)  # Ritardo per inizializzare il GPS
    main()

