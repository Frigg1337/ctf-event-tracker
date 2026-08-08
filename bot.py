import sys
import requests
from datetime import datetime, timedelta

# --- KONFIGURASI ---
DAYS_AHEAD = 14  # Cari event untuk 14 hari ke depan
LIMIT = 10       # Maksimal event yang ditampilkan

def get_upcoming_ctfs():
    # Setup waktu (Unix Timestamp)
    now = datetime.now()
    start_timestamp = int(now.timestamp())
    end_timestamp = int((now + timedelta(days=DAYS_AHEAD)).timestamp())

    # URL API CTFtime
    url = f"https://ctftime.org/api/v1/events/?limit={LIMIT}&start={start_timestamp}&finish={end_timestamp}"
    
    # User-Agent wajib ada (Identitas Bot)
    headers = {
        'User-Agent': 'Mozilla/5.0 (CTF-Tracker-Bot/1.0; +https://github.com/)'
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Gagal mengambil data dari CTFtime: {e}")
        return None

def update_readme(events):
    if events is None:
        print("API gagal, README.md tidak diubah agar data terakhir tetap tersimpan.")
        return

    # Header README
    content = "# 📡 CTF Event Tracker\n\n"
    content += "Repository ini otomatis mengupdate jadwal CTF dari [CTFtime](https://ctftime.org) setiap 2 jam.\n\n"
    
    # Bagian Tabel
    content += "### 🚩 Upcoming Events (Next 14 Days)\n"
    content += "| Nama Event | Tanggal Mulai (UTC) | Durasi | Format | Rating |\n"
    content += "|------------|---------------------|--------|--------|--------|\n"

    if not events:
        content += "| *Tidak ada event ditemukan* | - | - | - | - |\n"
    else:
        for event in events:
            # --- PERBAIKAN DI SINI ---
            # Mengganti karakter '|' dengan '-' agar tabel Markdown tidak pecah
            name = event['title'].replace('|', '-')
            
            start_iso = event['start'].replace('T', ' ')[:16] 
            
            # Format Durasi
            dur_days = event['duration']['days']
            dur_hours = event['duration']['hours']
            duration = f"{dur_days}d {dur_hours}h" if dur_days > 0 else f"{dur_hours}h"
            
            format_ctf = event['format']
            weight = event['weight'] if event['weight'] is not None else "Belum ada"

            content += f"| **{name}** | {start_iso} | {duration} | {format_ctf} | {weight} |\n"

    # Footer
    local_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    content += f"\n\n---\n*Last updated: {local_time} (Server Time)*"

    # Tulis ke file README.md
    with open("README.md", "w", encoding='utf-8') as f:
        f.write(content)

if __name__ == "__main__":
    print("Memulai tracking...")
    events = get_upcoming_ctfs()
    if events is None:
        print("Gagal memperbarui README.md. Data terakhir tetap dipertahankan.")
        sys.exit(1)
    update_readme(events)
    print("Selesai! README.md berhasil diupdate.")
