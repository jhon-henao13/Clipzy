from flask import Flask, request, jsonify, render_template, send_from_directory
import yt_dlp
import os
import time

app = Flask(__name__)

DOWNLOAD_FOLDER = os.path.join(os.getcwd(), "downloads")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

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

    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
        'quiet': True,
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
        return jsonify({"error": str(e)}), 500


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


if __name__ == '__main__':
    initialize_counter()
    app.run(debug=True)

