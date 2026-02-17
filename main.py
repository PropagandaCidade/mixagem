import os
import requests
from flask import Flask, request, jsonify, send_from_directory
from pydub import AudioSegment
import uuid

app = Flask(__name__)

# Pasta temporária para processamento
UPLOAD_FOLDER = 'temp_audio'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def download_file(url):
    local_filename = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.mp3")
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return local_filename

@app.route('/mix', methods=['POST'])
def mix_audio():
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "JSON inválido"}), 400

        # 1. Carrega a Narração (Base)
        narration_path = download_file(data['narration_url'])
        combined = AudioSegment.from_file(narration_path)

        # 2. Aplica os Efeitos Sonoros (SFX)
        sfx_list = data.get('sfx_list', [])
        for sfx in sfx_list:
            sfx_path = download_file(sfx['url'])
            effect = AudioSegment.from_file(sfx_path)
            
            # Ajusta volume do efeito
            effect = effect + float(sfx.get('volume', 0))
            
            # Sobrepõe na narração (tempo em ms)
            position_ms = float(sfx['time']) * 1000
            combined = combined.overlay(effect, position=position_ms)
            os.remove(sfx_path) # Limpa cache do efeito

        # 3. Aplica a Trilha Sonora (Se houver)
        if data.get('music_url'):
            music_path = download_file(data['music_url'])
            music = AudioSegment.from_file(music_path)
            settings = data.get('music_settings', {})
            
            # Ajusta volume da trilha
            music = music + float(settings.get('volume_db', -14))
            
            # Calcula o tempo de início da voz (offset)
            intro_ms = float(settings.get('intro_time', 2.0)) * 1000
            
            # Mixagem final: Trilha + Voz (com o atraso da intro)
            combined = music.overlay(combined, position=intro_ms)
            os.remove(music_path)

        # 4. Exporta o Resultado
        output_filename = f"mixed_{uuid.uuid4()}.mp3"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        combined.export(output_path, format="mp3", bitrate="192k")
        
        # Limpa narração original
        os.remove(narration_path)

        # URL de retorno (O Railway fornece o domínio automaticamente)
        host_url = request.host_url.rstrip('/')
        return jsonify({
            "success": True,
            "mixed_audio_url": f"{host_url}/download/{output_filename}",
            "duration": combined.duration_seconds
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/download/<filename>')
def download_output(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)