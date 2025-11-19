from flask import Flask, request, jsonify, render_template, send_from_directory
from yt_dlp import YoutubeDL
import os
import time
import random
import uuid
import threading
import urllib.parse

app = Flask(__name__)

DOWNLOAD_FOLDER = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
]

cookie_file_path = "youtube_cookies.txt"

# Cargar cookies desde env
yt_cookies_env = os.getenv("YT_COOKIES")
if yt_cookies_env:
    tmp_cookie_path = "/app/yt_cookies.txt"
    try:
        with open(tmp_cookie_path, "w", encoding="utf-8") as f:
            f.write(yt_cookies_env.strip())
        cookie_file_path = tmp_cookie_path
        print("✅ Cookies de YouTube cargadas.")
        if os.path.exists(cookie_file_path) and os.path.getsize(cookie_file_path) > 0:
            print(f"✅ Archivo de cookies verificado: {os.path.getsize(cookie_file_path)} bytes")
        else:
            print("⚠️ Archivo de cookies vacío o no encontrado.")
    except Exception as e:
        print(f"⚠️ Error al escribir cookies: {e}")
else:
    print("⚠️ No se encontró YT_COOKIES.")


def clean_old_files(max_age_seconds=3600):
    """Elimina archivos viejos"""
    now = time.time()
    try:
        for filename in os.listdir(DOWNLOAD_FOLDER):
            path = os.path.join(DOWNLOAD_FOLDER, filename)
            if os.path.isfile(path) and now - os.path.getmtime(path) > max_age_seconds:
                try:
                    os.remove(path)
                except:
                    pass
    except:
        pass


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

    # Detectar plataforma
    is_youtube = "youtube" in url.lower() or "youtu.be" in url.lower()
    is_pornhub = "pornhub" in url.lower()
    
    # Determinar formato con fallback automático (más flexible)
    if format_type == "audio":
        ytdl_format = "bestaudio/best"
        postprocessors = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "0"}]
    elif format_type == "1080p":
        # Fallback automático: si no hay 1080p, intenta 720p, luego best
        ytdl_format = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/bestvideo[height<=720]+bestaudio/best[height<=720]/best"
        postprocessors = []
    elif format_type == "720p":
        # Fallback automático: si no hay 720p, intenta 480p, luego best
        ytdl_format = "bestvideo[height<=720]+bestaudio/best[height<=720]/bestvideo[height<=480]+bestaudio/best[height<=480]/best"
        postprocessors = []
    elif format_type == "480p":
        # Fallback automático: si no hay 480p, usa best
        ytdl_format = "bestvideo[height<=480]+bestaudio/best[height<=480]/best"
        postprocessors = []
    else:
        # Formato más flexible con múltiples fallbacks
        ytdl_format = "bestvideo*+bestaudio/best*/best"
        postprocessors = []

    # Configuración base
    ydl_opts = {
        "outtmpl": output_path,
        "merge_output_format": "mp4",
        "quiet": False,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 60,
        "retries": 5,
        "fragment_retries": 5,
        "skip_unavailable_fragments": True,
        "ignoreerrors": False,
        "postprocessors": postprocessors,
        "http_headers": {
            "User-Agent": random.choice(user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Referer": "https://www.google.com/",
        },
    }

    # Cookies de YouTube si existen
    if os.path.exists(cookie_file_path) and os.path.getsize(cookie_file_path) > 0:
        ydl_opts["cookiefile"] = cookie_file_path
        print(f"🍪 Usando cookies desde: {cookie_file_path}")

    # Ajustes específicos por plataforma
    if is_youtube:
        ydl_opts["http_headers"]["Referer"] = "https://www.youtube.com/"
        # Opciones específicas para YouTube
        if os.path.exists(cookie_file_path):
            ydl_opts["extractor_args"] = {
                "youtube": {
                    "player_client": ["android", "web"],
                    "player_skip": ["webpage"]
                }
            }
    elif "tiktok" in url.lower():
        ydl_opts["http_headers"]["Referer"] = "https://www.tiktok.com/"
    elif "instagram" in url.lower():
        ydl_opts["http_headers"]["Referer"] = "https://www.instagram.com/"
    elif "pinterest" in url.lower():
        ydl_opts["http_headers"]["Referer"] = "https://www.pinterest.com/"
    elif is_pornhub:
        print("🔞 Descargando de Pornhub...")
        # Para Pornhub, NO usar force_generic_extractor primero, intentar extractor nativo
        ydl_opts["http_headers"].update({
            "Referer": "https://www.pornhub.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        })

    info = None
    new_name = None

    print(f"📥 Descargando: {url[:60]}...")

    # Intentar descarga
    try:
        ydl_opts["format"] = ytdl_format
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as e:
        err = str(e)
        print(f"❌ Error inicial: {err}")
        
        # YouTube: manejar errores de formato y autenticación
        if is_youtube:
            if "Requested format is not available" in err or "format" in err.lower():
                print("🔁 Fallback YouTube: intentando con formato más simple...")
                ydl_fallback = dict(ydl_opts)
                ydl_fallback["format"] = "best"  # Formato más simple
                try:
                    with YoutubeDL(ydl_fallback) as ydl2:
                        info = ydl2.extract_info(url, download=True)
                except Exception as e2:
                    print(f"❌ Fallback formato simple falló: {e2}")
                    # Último intento: solo best sin merge
                    try:
                        ydl_fallback2 = dict(ydl_opts)
                        ydl_fallback2["format"] = "best"
                        ydl_fallback2.pop("merge_output_format", None)
                        with YoutubeDL(ydl_fallback2) as ydl3:
                            info = ydl3.extract_info(url, download=True)
                    except Exception as e3:
                        print(f"❌ Último fallback falló: {e3}")
            
            elif "Sign in to confirm" in err or "cookies" in err or "player response" in err:
                print("🔁 Fallback YouTube: intentando con cliente web...")
                ydl_fallback = dict(ydl_opts)
                ydl_fallback["extractor_args"] = {
                    "youtube": {
                        "player_client": ["web"],
                        "player_skip": []
                    }
                }
                try:
                    with YoutubeDL(ydl_fallback) as ydl2:
                        info = ydl2.extract_info(url, download=True)
                except Exception as e2:
                    print(f"❌ Fallback YouTube también falló: {e2}")
                    return jsonify({"error": "YouTube requiere cookies válidas. Verifica que YT_COOKIES esté en formato Netscape y actualizado en Koyeb."}), 400
        
        # Pornhub: intentar diferentes estrategias
        elif is_pornhub:
            # Estrategia 1: Sin extractor genérico (ya intentado), probar con diferentes headers
            if "Unable to extract" in err or "PornHub" in err:
                print("🔁 Fallback Pornhub: intentando con extractor genérico...")
                ydl_fallback = dict(ydl_opts)
                ydl_fallback["force_generic_extractor"] = True
                ydl_fallback["http_headers"]["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
                try:
                    with YoutubeDL(ydl_fallback) as ydl2:
                        info = ydl2.extract_info(url, download=True)
                except Exception as e2:
                    print(f"❌ Fallback genérico falló: {e2}")
                    # Estrategia 2: Probar sin restricciones de formato
                    try:
                        ydl_fallback2 = dict(ydl_fallback)
                        ydl_fallback2["format"] = "best"
                        ydl_fallback2["ignoreerrors"] = True
                        with YoutubeDL(ydl_fallback2) as ydl3:
                            info = ydl3.extract_info(url, download=True)
                    except Exception as e3:
                        print(f"❌ Fallback Pornhub también falló: {e3}")

    # Si hubo extracción, validar archivo
    if info:
        print("✅ Extracción exitosa")
        time.sleep(2)
        files = [f for f in os.listdir(DOWNLOAD_FOLDER) if f.startswith(temp_id)]
        if files:
            file_path = os.path.join(DOWNLOAD_FOLDER, files[0])
            if os.path.getsize(file_path) > 1024:
                new_name = files[0]
                print(f"✅ Archivo listo: {new_name}")

    if not new_name:
        return jsonify({"error": "No se pudo descargar. Intenta con otra URL."}), 500

    title = info.get("title", "Descarga") if info else "Descarga"
    thumbnail = info.get("thumbnail", "") if info else ""

    safe_name = urllib.parse.quote(new_name, safe='')
    return jsonify({
        "success": True,
        "title": title,
        "thumbnail": thumbnail,
        "download_url": f"/download/{safe_name}"
    })


@app.route('/download/<path:filename>')
def download_file(filename):
    decoded = urllib.parse.unquote(filename)
    safe_path = os.path.normpath(decoded)
    
    if safe_path.startswith("..") or not os.path.exists(os.path.join(DOWNLOAD_FOLDER, safe_path)):
        return jsonify({"error": "Archivo no encontrado"}), 404

    return send_from_directory(DOWNLOAD_FOLDER, safe_path, as_attachment=True, download_name=safe_path)


# Contador
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
    return "Términos de Servicio"

@app.route('/privacy')
def privacy():
    return "Política de Privacidad"

if __name__ == '__main__':
    initialize_counter()
    app.run(debug=False)