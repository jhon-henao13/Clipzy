from flask import Flask, request, jsonify, render_template, send_from_directory
import yt_dlp
import os
import time
import random

app = Flask(__name__)

DOWNLOAD_FOLDER = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Lista de User-Agents para rotación
user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.101 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
]

# Elimina archivos en DOWNLOAD_FOLDER con más de max_age segundos
def clean_old_files(max_age_seconds=3600):
    now = time.time()
    for filename in os.listdir(DOWNLOAD_FOLDER):
        file_path = os.path.join(DOWNLOAD_FOLDER, filename)
        if os.path.isfile(file_path):
            file_age = now - os.path.getmtime(file_path)
            if file_age > max_age_seconds:
                try:
                    os.remove(file_path)
                    print(f"Archivo eliminado por antigüedad: {filename}")
                except Exception as e:
                    print(f"Error eliminando archivo {filename}: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/download', methods=['POST'])
def download_video():
    data = request.json
    url = data.get('url')
    format_type = data.get('format', 'video')

    if not url:
        return jsonify({"error": "URL no proporcionada"}), 400

    # Limpiar archivos antiguos antes de la nueva descarga
    clean_old_files(max_age_seconds=3600)  # 1 hora

    # Retraso para evitar detección de bots
    time.sleep(1)

    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
        'quiet': True,
        'http_headers': {
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.youtube.com/',
        },
        'retries': 3,
        'fragment_retries': 3,
        'extractor_retries': 3,  # Añadido para reintentos en extractores
        'ignoreerrors': False,
    }

    if format_type == 'audio':
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        ydl_opts['format'] = 'bestvideo+bestaudio/best'
        ydl_opts['merge_output_format'] = 'mp4'

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

            if format_type == 'audio':
                filename = os.path.splitext(filename)[0] + ".mp3"

        return jsonify({
            "success": True,
            "title": info.get('title'),
            "filename": os.path.basename(filename),
            "url": url,
            "thumbnail": info.get('thumbnail'),
            "download_url": f"/download/{os.path.basename(filename)}"
        })

    except Exception as e:
        error_message = str(e)
        if "Sign in to confirm you’re not a bot" in error_message:
            error_message = "Este video requiere inicio de sesión o está restringido por YouTube. Prueba con un video público o enlaces de TikTok, Instagram o Pinterest."
        return jsonify({"error": error_message}), 500


@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(DOWNLOAD_FOLDER, filename, as_attachment=True)

counter_file = "counter.txt"

@app.route('/api/counter')
def get_counter():
    with open(counter_file, 'r') as f:
        count = int(f.read())
    return jsonify({"visits": count})

@app.route('/api/increment', methods=['POST'])
def increment_counter():
    with open(counter_file, 'r+') as f:
        count = int(f.read())
        count += 1
        f.seek(0)
        f.write(str(count))
        f.truncate()
    return jsonify({"new_count": count})

def initialize_counter():
    if not os.path.exists(counter_file):
        with open(counter_file, 'w') as f:
            f.write("0")


@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')



if __name__ == '__main__':
    initialize_counter()
    app.run(debug=True)