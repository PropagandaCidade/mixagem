import os
import requests
from flask import Flask, request, jsonify, send_from_directory
from pydub import AudioSegment
import uuid
import traceback

app = Flask(__name__)

# Pasta temporária
UPLOAD_FOLDER = 'temp_audio'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def download_file(url, label):
    """ Baixa o arquivo e gera erro detalhado em caso de falha """
    print(f"[DOWNLOAD] Iniciando: {label} de {url}")
    local_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.mp3")
    
    try:
        # Timeout de 30 segundos para downloads lentos
        with requests.get(url, stream=True, timeout=30) as r:
            if r.status_code != 200:
                raise Exception(f"Servidor retornou erro HTTP {r.status_code}")
            
            with open(local_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        print(f"[DOWNLOAD] Concluído: {label}")
        return local_path
    except Exception as e:
        print(f"[ERRO DOWNLOAD] {label}: {str(e)}")
        if os.path.exists(local_path):
            os.remove(local_path)
        raise Exception(f"Falha ao baixar {label}: {str(e)}")

@app.route('/mix', methods=['POST'])
def mix_audio():
    tmp_files = []
    
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "JSON invalido"}), 400

        print(f"[INFO] Nova solicitacao recebida.")

        # 1. Narração
        if 'narration_url' not in data:
            return jsonify({"success": False, "error": "URL da narracao ausente"}), 400
            
        nar_file = download_file(data['narration_url'], "Narracao")
        tmp_files.append(nar_file)
        combined = AudioSegment.from_file(nar_file)

        # 2. Efeitos
        sfx_list = data.get('sfx_list', [])
        for i, sfx in enumerate(sfx_list):
            sfx_url = sfx.get('url')
            if not sfx_url: continue
            
            sfx_file = download_file(sfx_url, f"Efeito_{i}")
            tmp_files.append(sfx_file)
            
            effect = AudioSegment.from_file(sfx_file)
            effect = effect + float(sfx.get('volume', 0))
            pos_ms = float(sfx.get('time', 0)) * 1000
            combined = combined.overlay(effect, position=pos_ms)

        # 3. Trilha
        if data.get('music_url'):
            mus_file = download_file(data['music_url'], "Trilha")
            tmp_files.append(mus_file)
            
            music = AudioSegment.from_file(mus_file)
            m_settings = data.get('music_settings', {})
            
            music = music + float(m_settings.get('volume_db', -14))
            intro_ms = float(m_settings.get('intro_time', 2.0)) * 1000
            
            combined = music.overlay(combined, position=intro_ms)

        # 4. Exportação
        output_name = f"final_{uuid.uuid4()}.mp3"
        output_path = os.path.join(UPLOAD_FOLDER, output_name)
        
        combined.export(output_path, format="mp3", bitrate="192k")
        print(f"[SUCESSO] Mixagem concluida: {output_name}")

        host_url = request.host_url.rstrip('/')
        return jsonify({
            "success": True,
            "mixed_audio_url": f"{host_url}/download/{output_name}",
            "duration": combined.duration_seconds
        })

    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"[ERRO CRITICO]\n{error_trace}")
        return jsonify({
            "success": False, 
            "error": f"Erro no Motor Python: {str(e)}"
        }), 500

    finally:
        for f in tmp_files:
            if os.path.exists(f):
                try: os.remove(f)
                except: pass

@app.route('/download/<filename>')
def download_output(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == '__main__':
    # Esta linha garante que, se rodar localmente, usa a porta 5000.
    # No Railway, o Gunicorn assume o controle através do Dockerfile.
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)