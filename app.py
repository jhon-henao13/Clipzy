from flask import Flask, request, jsonify, render_template, send_from_directory
from yt_dlp import YoutubeDL
import os
import time
import random
import uuid
import threading
import urllib.parse
import re

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


def clean_filename(filename):
    """Limpia el nombre de archivo para que sea seguro"""
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    filename = re.sub(r'\s+', ' ', filename).strip()
    if len(filename) > 100:
        filename = filename[:100]
    return filename


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
    
    # Detectar plataforma
    is_youtube = "youtube" in url.lower() or "youtu.be" in url.lower()
    is_pornhub = "pornhub" in url.lower()


    postprocessors = []
    if format_type == "audio":
        ytdl_format = "bestaudio/best"
        postprocessors = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "0"}]
    else:
        # Aseguramos que siempre intente descargar video+audio y los una en mp4
        ytdl_format = "bestvideo+bestaudio/best"
        if format_type == "1080p":
            ytdl_format = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
        elif format_type == "720p":
            ytdl_format = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
        elif format_type == "480p":
            ytdl_format = "bestvideo[height<=480]+bestaudio/best[height<=480]/best"
        
        # Este postprocessor asegura que el archivo final sea compatible
        postprocessors = [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}]


    # Función para crear opciones - NUEVA INSTANCIA CADA VEZ
    def create_ydl_opts(output_template, use_cookies=True):

        url_low = url.lower()

        opts = {
            "outtmpl": output_template,
            "quiet": False,
            "no_warnings": False,
            "noplaylist": True,
            "socket_timeout": 60,
            "retries": 10,
            "fragment_retries": 10,
            "skip_unavailable_fragments": True,
            "ignoreerrors": False,
            "postprocessors": postprocessors,
            "http_chunk_size": 10485760,
            "geo_bypass": True,
            "youtube_include_dash_manifest": False, # Evita formatos pesados que piden login
            "extrinsic_batch": True, 
            "client_id": "ANDROID",
            "merge_output_format": "mp4" if format_type != "audio" else None,
            "nocheckcertificate": True,
            "wait_for_video": (5, 10),
        }

        if format_type != "audio":
            opts["merge_output_format"] = "mp4"

        # 2. Definir Headers Reales
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,video/mp4,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
        }

        if not ("tiktok.com" in url_low or "vt.tiktok" in url_low or "reddit.com" in url_low):
            headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"


        if is_youtube:
            headers["Referer"] = "https://www.youtube.com/"
            if use_cookies and os.path.exists(cookie_file_path):
                opts["cookiefile"] = cookie_file_path
            
            opts["extractor_args"] = {
                "youtube": {
                    "player_client": ["android", "web", "mweb"],
                    "player_skip": ["configs", "web"],
                }
            }

            opts["check_formats"] = False



        if "twitter.com" in url_low or "x.com" in url_low:
            headers["Referer"] = "https://x.com/"
            opts["check_formats"] = False

        # Para TikTok: Forzamos el uso de impersonate (Chrome)
        if "tiktok.com" in url_low or "vt.tiktok" in url_low:
            opts.update({
                "impersonate": "chrome",
                "extractor_args": {
                    "tiktok": {
                        "web_client_name": "android_v2",
                        "app_version": "33.5.4"
                    }
                },
            })

        # Para Reddit: Muy importante añadir impersonate también
        elif "reddit.com" in url_low:
            opts.update({
                "impersonate": "chrome",
                "add_header": ["Referer:https://www.reddit.com/"]
            })


        elif "instagram.com" in url_low:
            headers["Referer"] = "https://www.instagram.com/"
            # Instagram odia los servidores; esto ayuda un poco:
            opts["add_header"] = ["Accept-Encoding: gzip, deflate, br", "Connection: keep-alive"]


        elif "pinterest" in url_low:
            headers["Referer"] = "https://www.pinterest.com/"


        elif "facebook.com" in url_low or "fb.watch" in url_low:
            headers["Referer"] = "https://www.facebook.com/"


        elif is_pornhub:

            if os.path.exists("pornhub_cookies.txt"):
                opts["cookiefile"] = "pornhub_cookies.txt"

            headers.update({
                "Referer": "https://www.pornhub.com/",
                "Origin": "https://www.pornhub.com"
            })
            opts["age_limit"] = 18

        opts["http_headers"] = headers
        return opts


    info = None
    new_name = None
    final_title = "Descarga"
    thumbnail = ""
    output_path = os.path.join(DOWNLOAD_FOLDER, f"{temp_id}_%(title)s.%(ext)s")

    # Intentar proceso de descarga unificado
    try:
        ydl_opts = create_ydl_opts(output_path, use_cookies=True)
        ydl_opts["format"] = ytdl_format
        
        with YoutubeDL(ydl_opts) as ydl:
            print(f"📥 Iniciando extracción y descarga...")
            # download=True hace todo en un paso más seguro para redes sociales
            info = ydl.extract_info(url, download=True)
            if info:
                final_title = info.get("title", "Descarga")
                thumbnail = info.get("thumbnail", "")
                
            # Verificación inmediata del archivo
            files = [f for f in os.listdir(DOWNLOAD_FOLDER) if f.startswith(temp_id)]
            if files:
                file_path = os.path.join(DOWNLOAD_FOLDER, files[0])
                if os.path.getsize(file_path) > 1024:
                    new_name = files[0]

    except Exception as e:
        err = str(e)
        print(f"❌ Error durante la descarga: {err}")
        
        
        # Fallback universal para cualquier plataforma
        if not new_name:
            print("🔁 Reintentando con formato básico...")
            try:
                ydl_opts["format"] = "best"
                with YoutubeDL(ydl_opts) as ydl_f:
                    info = ydl_f.extract_info(url, download=True)
                    files = [f for f in os.listdir(DOWNLOAD_FOLDER) if f.startswith(temp_id)]
                    if files: 
                        file_path = os.path.join(DOWNLOAD_FOLDER, files[0])
                        if os.path.getsize(file_path) > 1024:
                            new_name = files[0]
            except Exception as e2:
                print(f"❌ Fallback fallido: {e2}")



    # Validar archivo
    if not new_name:
        files = [f for f in os.listdir(DOWNLOAD_FOLDER) if f.startswith(temp_id)]
        if files:
            file_path = os.path.join(DOWNLOAD_FOLDER, files[0])
            if os.path.getsize(file_path) > 1024:
                new_name = files[0]

    if not new_name:
        return jsonify({"error": "No se pudo descargar. Intenta con otra URL."}), 500

    # Renombrar archivo
    try:
        old_path = os.path.join(DOWNLOAD_FOLDER, new_name)
        file_ext = os.path.splitext(new_name)[1] or (".mp3" if format_type == "audio" else ".mp4")
        safe_title = clean_filename(final_title)
        new_filename = f"{safe_title}{file_ext}"
        new_path = os.path.join(DOWNLOAD_FOLDER, new_filename)
        
        counter = 1
        while os.path.exists(new_path):
            new_filename = f"{safe_title}_{counter}{file_ext}"
            new_path = os.path.join(DOWNLOAD_FOLDER, new_filename)
            counter += 1
        
        os.rename(old_path, new_path)
        new_name = new_filename
        print(f"✅ Archivo renombrado: {new_name}")
    except Exception as e:
        print(f"⚠️ No se pudo renombrar: {e}")

    safe_name = urllib.parse.quote(new_name, safe='')
    return jsonify({
        "success": True,
        "title": final_title,
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

