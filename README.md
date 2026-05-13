# 📝 Todo App — FastAPI + Docker

Un'app To-Do minimale per imparare il vibe coding con Docker.

## Struttura del progetto

```
todoapp/
├── main.py              # Backend FastAPI (API REST)
├── static/
│   └── index.html       # Frontend HTML/JS vanilla
├── requirements.txt     # Dipendenze Python
├── Dockerfile           # Istruzioni per buildare l'immagine
└── docker-compose.yml   # Orchestrazione (comodo per sviluppo)
```

## Come avviare

### Opzione A — Docker diretto
```bash
# 1. Builda l'immagine
docker build -t todoapp .

# 2. Avvia il container
docker run -p 8000:8000 todoapp
```

### Opzione B — Docker Compose (consigliato per sviluppo)
```bash
docker compose up
```
> Con `--reload` nell'opzione B, il server si riavvia automaticamente ad ogni modifica del codice.

Apri il browser su **http://localhost:8000** 🎉

## API disponibili

| Metodo | Endpoint            | Descrizione         |
|--------|---------------------|---------------------|
| GET    | /api/todos          | Lista tutti i todo  |
| POST   | /api/todos          | Crea un todo        |
| PATCH  | /api/todos/{id}     | Aggiorna un todo    |
| DELETE | /api/todos/{id}     | Elimina un todo     |

Puoi anche esplorare la docs interattiva su **http://localhost:8000/docs** (generata automaticamente da FastAPI).

## Concetti Docker che impari qui

- **FROM** — scegli l'immagine base
- **WORKDIR** — imposta la directory di lavoro nel container
- **COPY** — copia file dal tuo PC nell'immagine
- **RUN** — esegue comandi durante la build
- **EXPOSE** — documenta la porta usata dall'app
- **CMD** — comando eseguito all'avvio del container
- **volumes** (compose) — sincronizza il codice locale con il container
