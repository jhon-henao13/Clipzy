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
    
    # Determinar formato - ULTRA SIMPLIFICADO
    if format_type == "audio":
        ytdl_format = "bestaudio/best"
        postprocessors = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "0"}]
    elif format_type == "1080p":
        ytdl_format = "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
    elif format_type == "720p":
        ytdl_format = "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
    elif format_type == "480p":
        ytdl_format = "bestvideo[height<=480]+bestaudio/best[height<=480]/best"
    else:
        ytdl_format = "best"
        postprocessors = []
    
    if format_type != "audio":
        postprocessors = []

    # Función para crear opciones - NUEVA INSTANCIA CADA VEZ
    def create_ydl_opts(output_template, use_cookies=True):
        opts = {
            "outtmpl": output_template,
            "quiet": False,
            "no_warnings": False,
            "noplaylist": True,
            "socket_timeout": 30,
            "retries": 5,
            "fragment_retries": 5,
            "postprocessors": postprocessors,
            
            # --- EL SECRETO PARA EVITAR BLOQUEOS ---
            "impersonate": "chrome",  # Esto imita el TLS/JA3 de Chrome
            "http_chunk_size": 10485760, # Descarga en pedazos de 10MB para evitar cortes
        }
        
        if format_type != "audio":
            opts["merge_output_format"] = "mp4"
    
        # Configuración YouTube (PO Token y Clientes)
        if is_youtube:
            if use_cookies and os.path.exists(cookie_file_path):
                opts["cookiefile"] = cookie_file_path
            
            # Usamos clientes que suelen pedir menos validación de PO Token
            opts["extractor_args"] = {
                "youtube": {
                    "player_client": ["tv", "ios"], 
                    "player_skip": ["webpage", "configs"],
                }
            }
    
        # Configuración Pornhub y Adultos
        elif is_pornhub:
            opts["age_limit"] = 18
            # PH bloquea headers custom, mejor dejamos que yt-dlp use sus internos con impersonate
        
        return opts

    info = None
    new_name = None
    final_title = "Descarga"
    thumbnail = ""

    print(f"📥 Descargando: {url[:60]}...")

    # Para YouTube y Pornhub, descargar directamente sin obtener info primero
    # Para otras plataformas, intentar obtener info primero
    output_path = os.path.join(DOWNLOAD_FOLDER, f"{temp_id}_%(title)s.%(ext)s")
    
    if not is_youtube and not is_pornhub:
        # Para otras plataformas, obtener título primero
        try:
            info_opts = create_ydl_opts(output_path, use_cookies=False)
            info_opts["format"] = "best"
            with YoutubeDL(info_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    final_title = info.get("title", "Descarga")
                    thumbnail = info.get("thumbnail", "")
                    print(f"📝 Título: {final_title}")
        except Exception as e:
            print(f"⚠️ Error al obtener info: {e}")

    # Intentar descargar
    try:
        ydl_opts = create_ydl_opts(output_path, use_cookies=True)
        ydl_opts["format"] = ytdl_format
        
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
            # Buscar archivo descargado
            files = [f for f in os.listdir(DOWNLOAD_FOLDER) if f.startswith(temp_id)]
            if files:
                file_path = os.path.join(DOWNLOAD_FOLDER, files[0])
                if os.path.getsize(file_path) > 1024:
                    new_name = files[0]
                    # Obtener info del archivo descargado si no la tenemos
                    if not info:
                        try:
                            info = ydl.extract_info(url, download=False)
                            if info:
                                final_title = info.get("title", "Descarga")
                                thumbnail = info.get("thumbnail", "")
                        except:
                            pass
                    print(f"✅ Archivo listo: {new_name}")
                    
    except Exception as e:
        err = str(e)
        print(f"❌ Error inicial: {err}")
        
        # YouTube: fallbacks
        if is_youtube:
            # Fallback 1: Formato simple
            if "Requested format is not available" in err or "format" in err.lower():
                print("🔁 Fallback YouTube: formato 'best'...")
                try:
                    fallback_path = os.path.join(DOWNLOAD_FOLDER, f"{temp_id}_%(title)s.%(ext)s")
                    ydl_fallback = create_ydl_opts(fallback_path, use_cookies=True)
                    ydl_fallback["format"] = "best"
                    with YoutubeDL(ydl_fallback) as ydl2:
                        ydl2.download([url])
                        files = [f for f in os.listdir(DOWNLOAD_FOLDER) if f.startswith(temp_id)]
                        if files:
                            file_path = os.path.join(DOWNLOAD_FOLDER, files[0])
                            if os.path.getsize(file_path) > 1024:
                                new_name = files[0]
                                try:
                                    info = ydl2.extract_info(url, download=False)
                                    if info:
                                        final_title = info.get("title", "Descarga")
                                        thumbnail = info.get("thumbnail", "")
                                except:
                                    pass
                except Exception as e2:
                    print(f"❌ Fallback YouTube falló: {e2}")
            
            # Fallback 2: Cliente web
            if not new_name and ("Sign in to confirm" in err or "cookies" in err or "player response" in err):
                print("🔁 Fallback YouTube: cliente web...")
                try:
                    fallback_path = os.path.join(DOWNLOAD_FOLDER, f"{temp_id}_%(title)s.%(ext)s")
                    ydl_fallback = create_ydl_opts(fallback_path, use_cookies=True)
                    ydl_fallback["format"] = "best"
                    ydl_fallback["extractor_args"] = {
                        "youtube": {
                            "player_client": ["web"],
                            "player_skip": []
                        }
                    }
                    with YoutubeDL(ydl_fallback) as ydl2:
                        ydl2.download([url])
                        files = [f for f in os.listdir(DOWNLOAD_FOLDER) if f.startswith(temp_id)]
                        if files:
                            file_path = os.path.join(DOWNLOAD_FOLDER, files[0])
                            if os.path.getsize(file_path) > 1024:
                                new_name = files[0]
                                try:
                                    info = ydl2.extract_info(url, download=False)
                                    if info:
                                        final_title = info.get("title", "Descarga")
                                        thumbnail = info.get("thumbnail", "")
                                except:
                                    pass
                except Exception as e2:
                    print(f"❌ Fallback YouTube también falló: {e2}")
                    return jsonify({"error": "YouTube requiere cookies válidas. Verifica YT_COOKIES en Koyeb."}), 400
        
        # Pornhub: NO usar extractor genérico (descarga videos promocionales)
        elif is_pornhub:
            if "Unable to extract" in err or "PornHub" in err:
                print("🔁 Fallback Pornhub: mejorando headers...")
                try:
                    fallback_path = os.path.join(DOWNLOAD_FOLDER, f"{temp_id}_%(title)s.%(ext)s")
                    ydl_fallback = create_ydl_opts(fallback_path, use_cookies=False)
                    ydl_fallback["format"] = "best"
                    # Headers aún más realistas
                    ydl_fallback["http_headers"]["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                    ydl_fallback["http_headers"]["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
                    with YoutubeDL(ydl_fallback) as ydl2:
                        ydl2.download([url])
                        files = [f for f in os.listdir(DOWNLOAD_FOLDER) if f.startswith(temp_id)]
                        if files:
                            file_path = os.path.join(DOWNLOAD_FOLDER, files[0])
                            if os.path.getsize(file_path) > 1024:
                                new_name = files[0]
                                # Verificar que no sea un video promocional
                                if "pornhub" in new_name.lower() and "(" in new_name.lower():
                                    print("⚠️ Video promocional detectado, descartando...")
                                    try:
                                        os.remove(file_path)
                                        new_name = None
                                    except:
                                        pass
                                else:
                                    try:
                                        info = ydl2.extract_info(url, download=False)
                                        if info:
                                            final_title = info.get("title", "Descarga")
                                            thumbnail = info.get("thumbnail", "")
                                    except:
                                        pass
                except Exception as e2:
                    print(f"❌ Fallback Pornhub falló: {e2}")

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