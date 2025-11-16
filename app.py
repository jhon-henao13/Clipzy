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
import urllib.parse


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
    tmp_cookie_path = "/app/yt_cookies.txt"
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
        "quiet": True,
        "noprogress": True,
        "no_warnings": False,
        "noplaylist": True,
        "socket_timeout": 60,
        "retries": 5,
        "fragment_retries": 5,
        "skip_unavailable_fragments": True,
        "ignoreerrors": False,  # Cambiar a False para ver errores REALES
        "postprocessors": postprocessors,
        "cookiefile": cookie_file_path if os.path.exists(cookie_file_path) else None,
        "http_headers": {
            "User-Agent": random.choice(user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Referer": "https://www.youtube.com/",
        },
        "socket_family": 4,  # IPv4 only
        "ratelimit": 0,
        "cachedir": False,
        "extractor_args": {
            "pornhub": {"age_gate": True, "skip": ["geo"], "skip_login": True},
            "tiktok": {"impersonate": "chrome", "playwright": True},
            "instagram": {"impersonate": "chrome", "playwright": True},
            "pinterest": {"impersonate": "chrome", "playwright": True},
            "youtube": {"player_client": ["web", "android_embedded"]},
       },

        "no_check_certificate": True,
        "allow_unplayable_formats": False,
        "fixup": "detect_or_warn"


    }

    if "pornhub" in url.lower():
        print(f"🔞 Descargando de Pornhub...")
        mobile_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
        ydl_opts["http_headers"]["User-Agent"] = mobile_ua
        ydl_opts["http_headers"]["Referer"] = "https://www.pornhub.com/"
        ydl_opts.update({
            "socket_timeout": 120,
            "retries": 15,
        })

    if "instagram.com" in url:
        ydl_opts["http_headers"]["Referer"] = "https://www.instagram.com/"
        ydl_opts["http_headers"]["X-IG-App-ID"] = "936619743392459"

    if "pinterest.com" in url:
        ydl_opts["http_headers"]["Referer"] = "https://www.pinterest.com/"

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
            
            # Solo marcar éxito si realmente extrajo info
            if info:
                print(f"✅ Descarga exitosa con formato: {fmt}")
                download_success = True
                break
            else:
                print(f"⚠️ No se extrajo información")
                continue
            
        except Exception as e:
            error_full = str(e)
            print(f"⚠️ Intento {attempt + 1} falló: {error_full}...")
            print(f"❌ Descarga fallida para: {url}")
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

                # ✅ FIX: Ignorar archivos .part (incompletos)
                if old_path.endswith('.part'):
                    print(f"⚠️ Archivo .part ignorado (descarga incompleta): {files[0]}")
                elif os.path.exists(old_path) and os.path.getsize(old_path) > 1024:
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


    # URL-encodear el nombre del archivo para que sea seguro en la ruta
    safe_name = urllib.parse.quote(new_name, safe='')
    return jsonify({
        "success": True,
        "title": title,
        "thumbnail": thumbnail,
        "download_url": f"/download/{safe_name}"
    })




@app.route('/download/<path:filename>')
def download_file(filename):
    # Flask decodifica automáticamente %20, pero por seguridad decodificamos
    decoded = urllib.parse.unquote(filename)
    # Evitar rutas fuera del folder
    safe_path = os.path.normpath(decoded)
    if safe_path.startswith(".."):
        return jsonify({"error": "Nombre de archivo inválido."}), 400

    if not os.path.exists(os.path.join(DOWNLOAD_FOLDER, safe_path)):
        return jsonify({"error": "Archivo no encontrado."}), 404

    # send_from_directory gestiona Content-Disposition y streaming de forma segura
    return send_from_directory(DOWNLOAD_FOLDER, safe_path, as_attachment=True, download_name=safe_path)


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