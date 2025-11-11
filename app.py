from flask import Flask, request, jsonify, render_template, send_from_directory
import yt_dlp
import os
import time
import random
import unicodedata
import re

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

# Crear el archivo de cookies desde variable de entorno (si existe)
if not os.path.exists(cookie_file_path) and os.getenv("YT_COOKIES"):
    with open(cookie_file_path, "w", encoding="utf-8") as f:
        f.write(os.getenv("YT_COOKIES"))



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

    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
        'merge_output_format': 'mp4',
        'quiet': True,
        'noplaylist': True,
        'continuedl': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'retries': 3,
        'fragment_retries': 3,
        'extractor_retries': 3,
        'ignoreerrors': False,
        'http_headers': {
            'User-Agent': random.choice(user_agents),
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Referer': 'https://www.youtube.com/',
            'Accept': '*/*',
            'DNT': '1',
        },
    }

    # Cookies si existen
    if os.path.exists(cookie_file_path):
        ydl_opts["cookiefile"] = cookie_file_path

    # Formatos
    if format_type == 'audio':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }],
        })
    elif format_type == '1080p':
        ydl_opts['format'] = 'bestvideo[height<=1080]+bestaudio/best'
    elif format_type == '720p':
        ydl_opts['format'] = 'bestvideo[height<=720]+bestaudio/best'
    elif format_type == '480p':
        ydl_opts['format'] = 'bestvideo[height<=480]+bestaudio/best'
    else:
        ydl_opts['format'] = 'bestvideo+bestaudio/best'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            raw_filename = ydl.prepare_filename(info)
            ext = os.path.splitext(raw_filename)[1]
            safe_name = sanitize_filename(info.get("title", "video")) + ext
            new_path = os.path.join(DOWNLOAD_FOLDER, safe_name)
            os.rename(raw_filename, new_path)

        return jsonify({
            "success": True,
            "title": info.get("title"),
            "filename": safe_name,
            "thumbnail": info.get("thumbnail"),
            "download_url": f"/download/{safe_name}"
        })

    except Exception as e:
        err = str(e)
        if "HTTP Error 403" in err:
            err = "YouTube bloqueó temporalmente esta descarga. Espera unos minutos o usa cookies válidas."
        elif "Sign in to confirm you’re not a bot" in err:
            err = "Este video requiere inicio de sesión o verificación de edad."
        elif "Video unavailable" in err:
            err = "El video no está disponible en tu región o fue eliminado."
        return jsonify({"error": err}), 500


@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join(DOWNLOAD_FOLDER, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "Archivo no encontrado."}), 404
    return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)


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


@app.route('/api/increment', methods=['POST'])
def increment_counter():
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
