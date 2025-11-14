from flask import Flask, request, jsonify, render_template, send_from_directory, Response
from yt_dlp import YoutubeDL
import os
import time
import random
import unicodedata
import re
import uuid
import subprocess


app = Flask(__name__)

DOWNLOAD_FOLDER = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Lista de User-Agents rotativos actualizados (más realistas)
user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
]

cookie_file_path = "youtube_cookies.txt"

# --- Soporte para cookies desde variables de entorno ---
import tempfile

# Si existe la variable YT_COOKIES en el entorno, la guardamos en un archivo temporal
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
    return filename.strip("_")


def clean_old_files(max_age_seconds=3600):
    """Elimina archivos viejos"""
    now = time.time()
    for filename in os.listdir(DOWNLOAD_FOLDER):
        path = os.path.join(DOWNLOAD_FOLDER, filename)
        if os.path.isfile(path) and now - os.path.getmtime(path) > max_age_seconds:
            try:
                os.remove(path)
                print(f"🧹 Archivo eliminado: {filename}")
            except Exception as e:
                print(f"⚠️ Error al eliminar {filename}: {e}")



def download_with_binary(url, output_path, cookies=None, user_agent=None, format_type="best"):
    cmd = [
        "/usr/local/bin/yt-dlp",
        "-o", output_path,
        "-f", format_type,
        "--merge-output-format", "mp4",
        "--no-playlist",
        "--geo-bypass",
        "--retries", "5",
        "--fragment-retries", "5",
        "--no-warnings",
        "--quiet"
    ]
    
    if cookies and os.path.exists(cookies):
        cmd += ["--cookies", cookies]
    
    if user_agent:
        cmd += ["--user-agent", user_agent]
    
    result = subprocess.run(cmd + [url], capture_output=True, text=True)
    
    if result.returncode != 0:
        raise Exception(result.stderr)
    
    # Extraer el nombre del archivo descargado
    output_file = None
    for line in result.stdout.splitlines():
        if "[download] Destination:" in line:
            output_file = line.split(":")[-1].strip()
            break
    return output_file



@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/download', methods=['POST'])
def download_video():
    data = request.json
    url = data.get("url")
    format_type = data.get("format", "best")

    filename = None

    if not url:
        return jsonify({"error": "URL no proporcionada"}), 400

    clean_old_files()

    temp_id = str(uuid.uuid4())
    output_path = os.path.join(DOWNLOAD_FOLDER, f"{temp_id}.%(ext)s")


    # Determinar formato
    if format_type == "audio":
        ytdl_format = "bestaudio/best"
        postprocessors = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "0"
        }]

    elif format_type == "1080p":
        ytdl_format = "bestvideo[height<=1080]+bestaudio/best"
        postprocessors = []
    elif format_type == "720p":
        ytdl_format = "bestvideo[height<=720]+bestaudio/best"
        postprocessors = []
    else:
        ytdl_format = "bestvideo+bestaudio/best"
        postprocessors = []

    # Configuración de yt-dlp
    ydl_opts = {
        "outtmpl": output_path,
        "format": ytdl_format,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "geo_bypass": True,
        "retries": 5,
        "fragment_retries": 5,
        "cookiefile": cookie_file_path if os.path.exists(cookie_file_path) else None,
        "postprocessors": postprocessors,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [],
        "http_headers": {
            "User-Agent": random.choice(user_agents)
        },
        "noprogress": True,
        "ignoreerrors": False
    }




    # Lista de formatos fallback: intenta varias opciones hasta que funcione
    fallback_formats = [
        ytdl_format,          # formato principal según la selección
        "bestvideo+bestaudio/best",  # fallback general video+audio
        "bestaudio/best",     # fallback solo audio
        "best"                # último recurso
    ]


    info = None
    last_error = None

    for fmt in fallback_formats:
        ydl_opts["format"] = fmt
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)

                if info is None:
                    return jsonify({"error": "No se pudo descargar el video"}), 500

                filename = ydl.prepare_filename(info)
            print(f"✅ Video descargado usando formato: {fmt}")
            break  # si funciona, salimos del loop
        except Exception as e:
            last_error = e
            continue

    if info is None:
        err = str(last_error)
        if "HTTP Error 403" in err:
            err = "YouTube bloqueó temporalmente esta descarga. Usa cookies válidas."
        elif "Sign in to confirm you’re not a bot" in err:
            err = "Este video requiere inicio de sesión o verificación de edad."
        elif "Video unavailable" in err:
            err = "El video no está disponible en tu región o fue eliminado."
        return jsonify({"error": err}), 500


    if filename and os.path.exists(filename):
        ext = os.path.splitext(filename)[1]  # Obtiene extensión real
        new_name = f"video_{temp_id}{ext}"
        new_path = os.path.join(DOWNLOAD_FOLDER, new_name)
        os.rename(filename, new_path)
    else:
        return jsonify({"error": "No se pudo encontrar el archivo descargado."}), 500



    return jsonify({
        "success": True,
        "title": info.get("title", "Video descargado"),
        "thumbnail": info.get("thumbnail", ""),
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
                chunk = f.read(4096)
                if not chunk:
                    break
                yield chunk

    return Response(
        generate(),
        mimetype="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "X-Accel-Buffering": "no",
            "Content-Length": str(os.path.getsize(file_path))
        }
    )


# Contador simple
counter_file = "counter.txt"


def initialize_counter():
    if not os.path.exists(counter_file):
        with open(counter_file, "w") as f:
            f.write("0")


@app.route('/api/counter')
def get_counter():
    with open(counter_file, "r") as f:
        return jsonify({"visits": int(f.read())})


import threading
counter_lock = threading.Lock()

@app.route('/api/increment', methods=['POST'])
def increment_counter():
    with counter_lock:
        with open(counter_file, "r+") as f:
            count = int(f.read()) + 1
            f.seek(0)
            f.write(str(count))
            f.truncate()
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
