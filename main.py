import os
import requests
from flask import Flask, request, jsonify, send_from_directory
from pydub import AudioSegment
import uuid
import traceback

app = Flask(__name__)

# Pasta temporária para processamento de áudio no Railway
UPLOAD_FOLDER = 'temp_audio'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def download_file(url, file_type):
    """ Baixa um arquivo de uma URL e loga o processo. """
    print(f"[DOWNLOAD] Tentando baixar {file_type} de: {url}")
    local_filename = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.mp3")
    try:
        with requests.get(url, stream=True, timeout=15) as r:
            r.raise_for_status()
            with open(local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        print(f"[DOWNLOAD] Sucesso! Arquivo salvo em: {local_filename}")
        return local_filename
    except requests.exceptions.RequestException as e:
        print(f"[DOWNLOAD] FALHA CRÍTICA ao baixar {file_type}: {e}")
        raise ValueError(f"Não foi possível acessar o arquivo de {file_type}. Verifique a URL e permissões. (Erro: {e})")


@app.route('/mix', methods=['POST'])
def mix_audio():
    narration_path = None
    sfx_paths = []
    music_path = None
    
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "JSON inválido"}), 400
        print(f"[INFO] Receita de mixagem recebida: {data}")

        # 1. Carrega a Narração (Base)
        narration_path = download_file(data['narration_url'], "narração")
        combined = AudioSegment.from_file(narration_path)
        print("[PROCESS] Narração carregada para a Pydub.")

        # 2. Aplica os Efeitos Sonoros (SFX)
        sfx_list = data.get('sfx_list', [])
        for sfx in sfx_list:
            sfx_path = download_file(sfx['url'], f"efeito {sfx.get('name', '')}")
            sfx_paths.append(sfx_path)
            effect = AudioSegment.from_file(sfx_path)
            
            effect += float(sfx.get('volume', 0))
            position_ms = float(sfx['time']) * 1000
            combined = combined.overlay(effect, position=position_ms)
        print(f"[PROCESS] {len(sfx_paths)} efeitos aplicados.")

        # 3. Aplica a Trilha Sonora (Se houver)
        if data.get('music_url'):
            music_path = download_file(data['music_url'], "trilha")
            music = AudioSegment.from_file(music_path)
            settings = data.get('music_settings', {})
            
            music += float(settings.get('volume_db', -14))
            intro_ms = float(settings.get('intro_time', 2.0)) * 1000
            combined = music.overlay(combined, position=intro_ms)
            print("[PROCESS] Trilha sonora aplicada.")

        # 4. Exporta o Resultado
        output_filename = f"mixed_{uuid.uuid4()}.mp3"
        output_path = os.path.join(UPLOAD_FOLDER, output_filename)
        print(f"[EXPORT] Exportando áudio final para: {output_path}")
        combined.export(output_path, format="mp3", bitrate="192k")
        
        host_url = request.host_url.rstrip('/')
        return jsonify({
            "success": True,
            "mixed_audio_url": f"{host_url}/download/{output_filename}",
            "duration": combined.duration_seconds
        })

    except Exception as e:
        print(f"[ERRO FATAL] {traceback.format_exc()}")
        return jsonify({"success": False, "error": f"Erro no motor de mixagem: {type(e).__name__} - {e}"}), 500

    finally:
        # Limpa todos os arquivos temporários
        if narration_path and os.path.exists(narration_path):
            os.remove(narration_path)
        if music_path and os.path.exists(music_path):
            os.remove(music_path)
        for path in sfx_paths:
            if os.path.exists(path):
                os.remove(path)
        print("[CLEANUP] Arquivos temporários limpos.")


@app.route('/download/<filename>')
def download_output(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)