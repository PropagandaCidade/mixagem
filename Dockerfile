FROM python:3.11-slim

# Instala o FFmpeg (O Motor de Áudio)
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

# Porta padrão do Railway
ENV PORT 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "main:app"]