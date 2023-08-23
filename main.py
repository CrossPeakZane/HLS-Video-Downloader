from flask import Flask, request, send_file, render_template_string
import requests
from urllib.parse import urlparse, urljoin
import os
import re

app = Flask(__name__)

# Store debug information and video count
debug_info = []
video_count = 1

def append_debug_info(info):
    global debug_info
    debug_info.append(info)
    print(info)

def clear_files_and_debug_info():
    global debug_info
    global video_count
    debug_info = []
    video_count = 1
    for filename in os.listdir():
        if filename.endswith('.mp4'):
            os.remove(filename)
    print("Cleared files and debug information.")

def parse_m3u8(m3u8_content, base_url):
    lines = m3u8_content.split('\n')
    segments = []
    current_segment = None
    for line in lines:
        line = line.strip()
        if line.startswith('#EXTINF:'):
            current_segment = {}
        elif line.startswith('#EXT-X-BYTERANGE:') and current_segment is not None:
            byterange = re.findall(r'\d+', line)
            current_segment['byterange'] = (int(byterange[1]), int(byterange[0]) + int(byterange[1]))
        elif not line.startswith('#') and line and current_segment is not None:
            current_segment['url'] = urljoin(base_url, line)
            segments.append(current_segment)
            current_segment = None
    return segments

def download_segments(segments):
    video_data = b""
    for segment in segments:
        response = requests.get(segment['url'], headers={'Range': f"bytes={segment['byterange'][0]}-{segment['byterange'][1]-1}"})
        video_data += response.content
    return video_data

@app.route('/')
def root():
    global debug_info
    videos_html = ''.join([f'<video src="{video}" controls></video><br>' for video in os.listdir() if video.endswith('.mp4')])
    return render_template_string('<pre>{{ debug_info }}</pre><br>{{ videos|safe }}', debug_info="\n".join(debug_info), videos=videos_html)

@app.route('/download', methods=['POST'])
def download_video():
    global video_count
    try:
        data = request.json
        if 'url' in data:
            url = data['url']
            parsed_url = urlparse(url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path.rsplit('/', 1)[0]}/"

            append_debug_info("=== Download Started ===")
            append_debug_info("URL to download: " + url)

            master_m3u8_content = requests.get(url).text
            append_debug_info("Master M3U8 content: " + master_m3u8_content)

            master_segments = parse_m3u8(master_m3u8_content, base_url)
            append_debug_info("Parsed segments: " + str(master_segments))

            video_data = download_segments(master_segments)
            append_debug_info("Video data size: " + str(len(video_data)))

            mp4_output_file = f"{video_count}.mp4"
            video_count += 1

            with open(mp4_output_file, 'wb') as f:
                f.write(video_data)

            append_debug_info(f"MP4 file created: {mp4_output_file}")

            return send_file(mp4_output_file, as_attachment=True, mimetype='video/mp4')
        else:
            return "Invalid request data", 400
    except Exception as e:
        append_debug_info("Error: " + str(e))
        return str(e), 500

@app.route('/restart', methods=['GET'])
def restart():
    shutdown = request.environ.get('werkzeug.server.shutdown')
    if shutdown is None:
        return "Server restart failed.", 500
    shutdown()
    clear_files_and_debug_info()
    return "Server is restarting...", 200

if __name__ == '__main__':
    clear_files_and_debug_info()
    app.run(host='0.0.0.0', port=3000)