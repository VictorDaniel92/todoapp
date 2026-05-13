# ── Stage 1: immagine base ───────────────────────────────────────────────────
FROM python:3.12-slim

# Evita che Python scriva file .pyc e che buferizzi stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Installa le dipendenze prima del codice (sfrutta la cache di Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia il codice dell'app
COPY main.py .
COPY static/ ./static/

# Esponi la porta su cui gira uvicorn
EXPOSE 8000

# Comando di avvio
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
