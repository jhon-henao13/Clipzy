from flask import Flask, request, jsonify, render_template, send_from_directory, make_response
import datetime
from yt_dlp import YoutubeDL
import os
import time
import random
import uuid
import threading
import urllib.parse
import re
import shutil
import traceback
from yt_dlp.networking.impersonate import ImpersonateTarget

app = Flask(__name__)

DOWNLOAD_FOLDER = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

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
        return jsonify({"success": False, "error": "Falta la URL"}), 400

    clean_old_files()
    temp_id = str(uuid.uuid4())

    # Detectar plataforma de forma consolidada
    domain = url.lower()
    is_tiktok = "tiktok" in domain
    is_instagram = "instagram" in domain
    is_facebook = "facebook" in domain or "fb.watch" in domain
    is_youtube = "youtube" in domain or "youtu.be" in domain
    is_pornhub = "pornhub" in domain
    is_twitter = "twitter.com" in domain or "x.com" in domain


    postprocessors = []
    if format_type == "audio":
        ytdl_format = "bestaudio/best"
        postprocessors = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        # Simplificamos la cadena de formato para evitar el SyntaxError
        # Esta sintaxis es mucho más robusta para YouTube, Pornhub y TikTok
        if format_type == "1080p":
            ytdl_format = "bestvideo[height<=1080]+bestaudio/best"
        elif format_type == "720p":
            ytdl_format = "bestvideo[height<=720]+bestaudio/best"
        else:
            ytdl_format = "bestvideo+bestaudio/best"
        
        postprocessors = [{
            'key': 'FFmpegVideoRemuxer',
            'preferedformat': 'mp4',
        }]


    # Función para crear opciones - NUEVA INSTANCIA CADA VEZ
    def create_ydl_opts(output_template, use_cookies=True):
        url_low = url.lower()
        
        # 1. Configuración Base
        opts = {
            "outtmpl": output_template,
            "quiet": False,
            "no_warnings": True,
            "no_warnings": False,
            "noplaylist": True,
            "format": ytdl_format,
            "ffmpeg_location": "/usr/bin/ffmpeg",
            "ignoreerrors": True,
            "postprocessors": postprocessors,
            "geo_bypass": True,
            "nocheckcertificate": True,
            "impersonate": ImpersonateTarget('chrome', '110'),
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "keep-alive",
            }
        }

        # 2. Ajustes por plataforma
        if is_youtube:
            # Quitamos los clients que fallan sin cookies y forzamos web
            opts["extractor_args"] = {
                "youtube": {
                    "player_client": ["web", "mweb"],
                    "player_skip": ["configs", "js"],
                }
            }
            # Forzamos compatibilidad máxima
            opts["format"] = "bestvideo[ext=mp4]+bestaudio[m4a]/best[ext=mp4]/best"


        elif is_tiktok:
            opts["extractor_args"] = {"tiktok": {"web_client_name": "android_v2"}}

        elif is_instagram:
            opts["add_header"] = ["Accept-Encoding: gzip, deflate, br"]

        elif is_pornhub:
            # Pornhub odia los headers complejos y las cookies de otros sitios
            opts["http_headers"] = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            }
            opts["cookiefile"] = None 
            opts["age_limit"] = 18
            opts["impersonate"] = None # Pornhub falla con impersonate a veces
            

        # 3. Aplicar Cookies Globales (si existen)
        if use_cookies and os.path.exists(cookie_file_path) and os.path.getsize(cookie_file_path) > 10:
            opts["cookiefile"] = cookie_file_path

        return opts


    info = None
    new_name = None
    final_title = "Descarga"
    thumbnail = ""
    output_path = os.path.join(DOWNLOAD_FOLDER, f"{temp_id}_%(title)s.%(ext)s")

    # Intentar proceso de descarga unificado
    try:
        current_opts = create_ydl_opts(output_path, use_cookies=True)
        
        with YoutubeDL(current_opts) as ydl:
            print(f"📥 Procesando: {url}")
            # Extraer y descargar en un solo paso
            info = ydl.extract_info(url, download=True)

            if info:
                final_title = info.get("title", "video")
                thumbnail = info.get("thumbnail", "")
                
            # Buscar el archivo que empieza con nuestro UUID
            time.sleep(1) # Pequeño margen para que el SO suelte el archivo tras FFmpeg
            files = [f for f in os.listdir(DOWNLOAD_FOLDER) if f.startswith(temp_id)]
            if files:
                new_name = files[0]

    except Exception as e:
        error_detallado = traceback.format_exc()
        print(f"❌ ERROR CRÍTICO:\n{error_detallado}")
        if not new_name:
            try:
                # Fallback ultra-básico: Sin cookies, sin impersonate, formato simple
                fallback_opts = {
                    "outtmpl": output_path,
                    "format": "best",
                    "ffmpeg_location": "/usr/bin/ffmpeg",
                    "nocheckcertificate": True,
                    "quiet": False
                }
                with YoutubeDL(fallback_opts) as ydl_f:
                    info = ydl_f.extract_info(url, download=True)
                    files = [f for f in os.listdir(DOWNLOAD_FOLDER) if f.startswith(temp_id)]
                    if files: new_name = files[0]
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
    return render_template('terms.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')


@app.route('/robots.txt')
def robots():
    content = """
User-agent: *
Allow: /
Disallow: /api/download
Disallow: /api/increment

Sitemap: https://clipzy.koyeb.app/sitemap.xml
    """
    response = make_response(content)
    response.headers["Content-Type"] = "text/plain"
    return response

@app.route('/sitemap.xml')
def sitemap():
    # Obtener la fecha actual para el sitemap
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    
    # Aquí puedes agregar más URLs si tienes páginas de términos, etc.
    pages = [
        {'loc': 'https://clipzy.koyeb.app/', 'lastmod': today, 'priority': '1.0'},
        {'loc': 'https://clipzy.koyeb.app/terms', 'lastmod': today, 'priority': '0.5'},
        {'loc': 'https://clipzy.koyeb.app/privacy', 'lastmod': today, 'priority': '0.5'},
    ]
    
    sitemap_xml = render_template('sitemap_template.xml', pages=pages)
    response = make_response(sitemap_xml)
    response.headers["Content-Type"] = "application/xml"
    return response



if __name__ == '__main__':
    initialize_counter()
    app.run(host='0.0.0.0', port=8000)

