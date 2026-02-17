import os
import requests
from flask import Flask, request, jsonify, send_from_directory
from pydub import AudioSegment
import uuid
import traceback

app = Flask(__name__)

# Configura pasta temporária
UPLOAD_FOLDER = 'temp_audio'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def download_file(url, label):
    """ Baixa o arquivo e gera erro detalhado em caso de falha """
    print(f"[DOWNLOAD] Iniciando: {label} de {url}")
    local_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.mp3")
    
    try:
        # Timeout de 15 segundos para evitar travamentos
        with requests.get(url, stream=True, timeout=15) as r:
            if r.status_code != 200:
                raise Exception(f"Servidor retornou erro HTTP {r.status_code}")
            
            with open(local_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        print(f"[DOWNLOAD] Concluído: {label}")
        return local_path
    except Exception as e:
        print(f"[ERRO DOWNLOAD] {label}: {str(e)}")
        # Se falhou, garante que não deixou rastro
        if os.path.exists(local_path):
            os.remove(local_path)
        raise Exception(f"Falha ao baixar {label}: {str(e)}")

@app.route('/mix', methods=['POST'])
def mix_audio():
    # Lista para limpeza de arquivos temporários
    tmp_files = []
    
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "JSON não recebido ou inválido"}), 400

        print(f"[INFO] Nova solicitação recebida.")

        # 1. CARREGA A NARRAÇÃO (BASE)
        if 'narration_url' not in data:
            return jsonify({"success": False, "error": "URL da narração ausente"}), 400
            
        nar_file = download_file(data['narration_url'], "Narração")
        tmp_files.append(nar_file)
        combined = AudioSegment.from_file(nar_file)

        # 2. APLICA OS EFEITOS SONOROS (SFX)
        sfx_list = data.get('sfx_list', [])
        for i, sfx in enumerate(sfx_list):
            sfx_url = sfx.get('url')
            if not sfx_url: continue
            
            sfx_file = download_file(sfx_url, f"Efeito_{i}")
            tmp_files.append(sfx_file)
            
            effect = AudioSegment.from_file(sfx_file)
            
            # Ajuste de Volume
            vol = float(sfx.get('volume', 0))
            effect = effect + vol
            
            # Sobreposição (Time em Segundos -> Milissegundos)
            pos_ms = float(sfx.get('time', 0)) * 1000
            combined = combined.overlay(effect, position=pos_ms)

        # 3. APLICA A TRILHA SONORA (Se houver)
        if data.get('music_url'):
            mus_file = download_file(data['music_url'], "Trilha")
            tmp_files.append(mus_file)
            
            music = AudioSegment.from_file(mus_file)
            m_settings = data.get('music_settings', {})
            
            # Volume da trilha
            m_vol = float(m_settings.get('volume_db', -14))
            music = music + m_vol
            
            # Tempo de entrada da voz
            intro_ms = float(m_settings.get('intro_time', 2.0)) * 1000
            
            # A trilha é a base, a voz entra por cima dela
            combined = music.overlay(combined, position=intro_ms)

        # 4. EXPORTAÇÃO FINAL
        output_name = f"final_{uuid.uuid4()}.mp3"
        output_path = os.path.join(UPLOAD_FOLDER, output_name)
        
        combined.export(output_path, format="mp3", bitrate="192k")
        print(f"[SUCESSO] Mixagem concluída: {output_name}")

        host_url = request.host_url.rstrip('/')
        return jsonify({
            "success": True,
            "mixed_audio_url": f"{host_url}/download/{output_name}",
            "duration": combined.duration_seconds
        })

    except Exception as e:
        # LOG DETALHADO NO RAILWAY
        error_trace = traceback.format_exc()
        print(f"[ERRO CRÍTICO]\n{error_trace}")
        
        # RESPOSTA ÚTIL PARA O PHP
        return jsonify({
            "success": False, 
            "error": f"Erro no Motor Python: {str(e)}"
        }), 500

    finally:
        # LIMPEZA DE ARQUIVOS DE ORIGEM (MANTÉM APENAS O RESULTADO)
        for f in tmp_files:
            if os.path.exists(f):
                try: os.remove(f)
                except: pass

@app.route('/download/<filename>')
def download_output(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)