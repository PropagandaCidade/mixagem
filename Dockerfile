FROM python:3.11-slim

# Instala FFmpeg (Essencial para o Pydub)
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

# O Railway define a variável PORT automaticamente.
# Usamos a forma shell do CMD para permitir a expansão da variável $PORT
CMD gunicorn --bind 0.0.0.0:$PORT main:app --timeout 120