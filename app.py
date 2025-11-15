from flask import Flask, request, jsonify, render_template, send_from_directory, Response
from yt_dlp import YoutubeDL
import os
import time
import random
import unicodedata
import re
import uuid
import subprocess
import tempfile
import threading


app = Flask(__name__)

DOWNLOAD_FOLDER = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Lista de User-Agents rotativos actualizados (más realistas)
user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
]

cookie_file_path = "youtube_cookies.txt"

# --- Soporte para cookies desde variables de entorno ---
yt_cookies_env = os.getenv("YT_COOKIES")

if yt_cookies_env:
    tmp_cookie_path = os.path.join(tempfile.gettempdir(), "yt_cookies.txt")
    with open(tmp_cookie_path, "w", encoding="utf-8") as f:
        f.write(yt_cookies_env.strip())
    cookie_file_path = tmp_cookie_path
    print("✅ Cookies de YouTube cargadas desde variable de entorno.")
else:
    print("⚠️ No se encontró la variable YT_COOKIES. Se usará el archivo local si existe.")



def sanitize_filename(filename):
    """Limpia nombres de archivo inválidos o con acentos"""
    filename = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode("ascii")
    filename = re.sub(r"[^\w\s-]", "", filename)
    filename = re.sub(r"\s+", "_", filename)
    return filename.strip("_")[:100]  # Limitar a 100 caracteres


def clean_old_files(max_age_seconds=3600):
    """Elimina archivos viejos"""
    now = time.time()
    try:
        for filename in os.listdir(DOWNLOAD_FOLDER):
            path = os.path.join(DOWNLOAD_FOLDER, filename)
            if os.path.isfile(path) and now - os.path.getmtime(path) > max_age_seconds:
                try:
                    os.remove(path)
                    print(f"🧹 Archivo eliminado: {filename}")
                except Exception as e:
                    print(f"⚠️ Error al eliminar {filename}: {e}")
    except Exception as e:
        print(f"⚠️ Error en clean_old_files: {e}")


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/download', methods=['POST'])
def download_video():
    data = request.json
    url = data.get("url")
    format_type = data.get("format", "best")

    if not url:
        return jsonify({"error": "URL no proporcionada"}), 400

    clean_old_files()

    temp_id = str(uuid.uuid4())
    
    # ✅ CAMBIO 1: Usar %(title)s para nombre original
    output_path = os.path.join(DOWNLOAD_FOLDER, f"{temp_id}_%(title)s.%(ext)s")

    # Determinar formato
    if format_type == "audio":
        ytdl_format = "bestaudio/best"
        postprocessors = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "0"}]
    elif format_type == "1080p":
        ytdl_format = "bestvideo[height<=1080]+bestaudio/best"
        postprocessors = []
    elif format_type == "720p":
        ytdl_format = "bestvideo[height<=720]+bestaudio/best"
        postprocessors = []
    elif format_type == "480p":
        ytdl_format = "bestvideo[height<=480]+bestaudio/best"
        postprocessors = []
    else:
        ytdl_format = "bestvideo+bestaudio/best"
        postprocessors = []

    # ✅ CAMBIO 2: Configuración mejorada para YouTube
    ydl_opts = {
        "outtmpl": output_path,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "geo_bypass": True,
        "geo_bypass_country": "US",  # Cambiar a US
        "source_address": "0.0.0.0",  # Añadir
        "force_generic_extractor": False,  # Añadir
        "retries": 10,
        "fragment_retries": 10,
        "extractor_retries": 15,
        "socket_timeout": 90,
        "sleep_interval": 2,
        "sleep_interval_requests": 2,
        "cookiefile": cookie_file_path if os.path.exists(cookie_file_path) else None,
        "postprocessors": postprocessors,
        "no_warnings": False,
        "quiet": False,
        "http_headers": {
            "User-Agent": random.choice(user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        },
        "noprogress": True,
        "ignoreerrors": True,
        "skip_unavailable_fragments": True,
        "no_check_certificate": True,
        "prefer_free_formats": False,
        # ✅ CAMBIO 3: Configuración YouTube mejorada
        "extractor_args": {
            "youtube": {
                "player_client": ["ios", "web"],  # Usar cliente IOS como fallback
                "skip": ["hls"],
            },
            "pinterest": {
                "api_token": None,
            },
            "pornhub": {"age_gate": True, "skip": ["geo-restriction"], "skip_login": True},
            "instagram": {"check_comments": False},
        }
    }

    # Intentar formatos: principal PRIMERO, luego fallbacks
    formats_to_try = [ytdl_format]
    if format_type != "best":
        formats_to_try += ["bestvideo+bestaudio/best", "best"]

    info = None
    new_name = None
    download_success = False

    # ✅ FLUJO DE DESCARGA CON REINTENTOS MEJORADOS
    for attempt, fmt in enumerate(formats_to_try):
        ydl_opts["format"] = fmt
        print(f"📥 Intento {attempt + 1}/{len(formats_to_try)}: Formato '{fmt}' para URL: {url[:50]}...")
        
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
            print(f"✅ Descarga exitosa con formato: {fmt}")
            download_success = True
            break
            
        except Exception as e:
            error_msg = str(e)
            print(f"⚠️ Intento {attempt + 1} falló: {error_msg[:150]}...")
            time.sleep(2)  # Esperar más tiempo
            continue

    # ✅ CAMBIO 4: BÚSQUEDA DE ARCHIVOS CON NOMBRE ORIGINAL
    if download_success or info:
        time.sleep(3)
        
        try:
            files = [f for f in os.listdir(DOWNLOAD_FOLDER) if f.startswith(temp_id)]
            
            if files:
                old_path = os.path.join(DOWNLOAD_FOLDER, files[0])
                if os.path.exists(old_path) and os.path.getsize(old_path) > 1024:
                    # ✅ Mantener nombre original (ya viene con el título)
                    new_name = files[0]
                    print(f"✅ Archivo descargado correctamente: {new_name}")
                else:
                    print(f"⚠️ Archivo descargado pero está vacío o muy pequeño")
        except Exception as e:
            print(f"⚠️ Error al buscar archivos: {e}")

    # ✅ BÚSQUEDA FINAL
    if not new_name:
        print("⏳ Esperando más tiempo para búsqueda final...")
        time.sleep(4)
        
        try:
            files = [f for f in os.listdir(DOWNLOAD_FOLDER) if f.startswith(temp_id)]
            
            if files:
                old_path = os.path.join(DOWNLOAD_FOLDER, files[0])
                
                for _ in range(5):
                    if os.path.exists(old_path):
                        size = os.path.getsize(old_path)
                        if size > 1024:
                            time.sleep(1)
                            break
                    time.sleep(1)
                
                if os.path.exists(old_path) and os.path.getsize(old_path) > 1024:
                    new_name = files[0]
                    print(f"✅ Archivo recuperado en búsqueda final: {new_name}")
        except Exception as e:
            print(f"⚠️ Error en búsqueda final: {e}")

    # ✅ Respuesta final
    if not new_name:
        err = "❌ No se pudo descargar. YouTube puede estar bloqueando. Intenta con TikTok, Instagram o Pinterest."
        print(f"❌ Descarga fallida para: {url}")
        return jsonify({"error": err}), 500

    title = "Video descargado"
    thumbnail = ""
    
    if info:
        title = info.get("title", "Video descargado")
        thumbnail = info.get("thumbnail", "")

    return jsonify({
        "success": True,
        "title": title,
        "thumbnail": thumbnail,
        "download_url": f"/download/{new_name}"
    })


@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join(DOWNLOAD_FOLDER, filename)

    if not os.path.exists(file_path):
        return jsonify({"error": "Archivo no encontrado."}), 404
    
    def generate():
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(8192)  # Aumentar chunk size
                if not chunk:
                    break
                yield chunk

    # ✅ CAMBIO 5: Nombre de descarga original
    display_name = filename.split("_", 1)[1] if "_" in filename else filename

    return Response(
        generate(),
        mimetype="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename={display_name}",
            "X-Accel-Buffering": "no",
            "Content-Length": str(os.path.getsize(file_path))
        }
    )


# Contador simple
counter_file = "counter.txt"
counter_lock = threading.Lock()


def initialize_counter():
    if not os.path.exists(counter_file):
        with open(counter_file, "w") as f:
            f.write("0")


@app.route('/api/counter')
def get_counter():
    try:
        with open(counter_file, "r") as f:
            count = int(f.read())
    except:
        count = 0
    return jsonify({"visits": count})


@app.route('/api/increment', methods=['POST'])
def increment_counter():
    with counter_lock:
        try:
            with open(counter_file, "r+") as f:
                count = int(f.read()) + 1
                f.seek(0)
                f.write(str(count))
                f.truncate()
        except:
            count = 1
    return jsonify({"new_count": count})


@app.route('/terms')
def terms():
    return render_template("terms.html")


@app.route('/privacy')
def privacy():
    return render_template("privacy.html")


@app.route('/sw.js')
def monetag_verify():
    return send_from_directory(os.path.dirname(__file__), 'sw.js')


if __name__ == '__main__':
    initialize_counter()
    app.run(debug=True)