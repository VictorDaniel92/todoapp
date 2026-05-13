import os
import httpx
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from sqlalchemy import Column, String, Boolean, Text, DateTime, ForeignKey, select, delete
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship
import uuid
import json


# ── Config ────────────────────────────────────────────────────────────────────

DATABASE_URL = os.environ["DATABASE_URL"].replace(
    "postgresql://", "postgresql+asyncpg://"
)
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

# Modello Groq — llama-3.3-70b è il più capace nel tier gratuito
GROQ_MODEL = "llama-3.3-70b-versatile"

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


# ── Models ────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass

def new_id():
    return str(uuid.uuid4())[:8]

def now():
    return datetime.utcnow()


class Project(Base):
    __tablename__ = "projects"
    id          = Column(String, primary_key=True, default=new_id)
    name        = Column(String, nullable=False)
    description = Column(Text, default="")
    created_at  = Column(DateTime, default=now)
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    notes = relationship("Note", back_populates="project", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"
    id         = Column(String, primary_key=True, default=new_id)
    title      = Column(String, nullable=False)
    done       = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    project    = relationship("Project", back_populates="tasks")


class Note(Base):
    __tablename__ = "notes"
    id         = Column(String, primary_key=True, default=new_id)
    content    = Column(Text, nullable=False)
    created_at = Column(DateTime, default=now)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    project    = relationship("Project", back_populates="notes")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(lifespan=lifespan)


# ── Serializers ───────────────────────────────────────────────────────────────

def project_to_dict(p):
    return {"id": p.id, "name": p.name, "description": p.description, "created_at": p.created_at.isoformat()}

def task_to_dict(t):
    return {"id": t.id, "title": t.title, "done": t.done, "project_id": t.project_id, "created_at": t.created_at.isoformat()}

def note_to_dict(n):
    return {"id": n.id, "content": n.content, "project_id": n.project_id, "created_at": n.created_at.isoformat()}


# ── Pydantic ──────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = ""

class TaskCreate(BaseModel):
    title: str

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    done: Optional[bool] = None

class NoteCreate(BaseModel):
    content: str

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]


# ── Projects API ──────────────────────────────────────────────────────────────

@app.get("/api/projects")
async def list_projects():
    async with SessionLocal() as db:
        result = await db.execute(select(Project).order_by(Project.created_at.desc()))
        return [project_to_dict(p) for p in result.scalars().all()]

@app.post("/api/projects", status_code=201)
async def create_project(body: ProjectCreate):
    async with SessionLocal() as db:
        project = Project(id=new_id(), name=body.name, description=body.description)
        db.add(project)
        await db.commit()
        await db.refresh(project)
        return project_to_dict(project)

@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    async with SessionLocal() as db:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Progetto non trovato")
        return project_to_dict(project)

@app.delete("/api/projects/{project_id}", status_code=204)
async def delete_project(project_id: str):
    async with SessionLocal() as db:
        result = await db.execute(select(Project).where(Project.id == project_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Progetto non trovato")
        await db.execute(delete(Project).where(Project.id == project_id))
        await db.commit()


# ── Tasks API ─────────────────────────────────────────────────────────────────

@app.get("/api/projects/{project_id}/tasks")
async def list_tasks(project_id: str):
    async with SessionLocal() as db:
        result = await db.execute(select(Task).where(Task.project_id == project_id).order_by(Task.created_at))
        return [task_to_dict(t) for t in result.scalars().all()]

@app.post("/api/projects/{project_id}/tasks", status_code=201)
async def create_task(project_id: str, body: TaskCreate):
    async with SessionLocal() as db:
        task = Task(id=new_id(), title=body.title, project_id=project_id)
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task_to_dict(task)

@app.patch("/api/tasks/{task_id}")
async def update_task(task_id: str, body: TaskUpdate):
    async with SessionLocal() as db:
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=404, detail="Task non trovato")
        if body.title is not None:
            task.title = body.title
        if body.done is not None:
            task.done = body.done
        await db.commit()
        await db.refresh(task)
        return task_to_dict(task)

@app.delete("/api/tasks/{task_id}", status_code=204)
async def delete_task(task_id: str):
    async with SessionLocal() as db:
        result = await db.execute(select(Task).where(Task.id == task_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Task non trovato")
        await db.execute(delete(Task).where(Task.id == task_id))
        await db.commit()


# ── Notes API ─────────────────────────────────────────────────────────────────

@app.get("/api/projects/{project_id}/notes")
async def list_notes(project_id: str):
    async with SessionLocal() as db:
        result = await db.execute(select(Note).where(Note.project_id == project_id).order_by(Note.created_at.desc()))
        return [note_to_dict(n) for n in result.scalars().all()]

@app.post("/api/projects/{project_id}/notes", status_code=201)
async def create_note(project_id: str, body: NoteCreate):
    async with SessionLocal() as db:
        note = Note(id=new_id(), content=body.content, project_id=project_id)
        db.add(note)
        await db.commit()
        await db.refresh(note)
        return note_to_dict(note)

@app.delete("/api/notes/{note_id}", status_code=204)
async def delete_note(note_id: str):
    async with SessionLocal() as db:
        result = await db.execute(select(Note).where(Note.id == note_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Nota non trovata")
        await db.execute(delete(Note).where(Note.id == note_id))
        await db.commit()


# ── Agent ─────────────────────────────────────────────────────────────────────

# Groq usa il formato OpenAI: i tool si chiamano "functions"
AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Crea un nuovo task nel progetto corrente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Titolo del task"}
                },
                "required": ["title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": "Segna un task esistente come completato dato il suo ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "ID del task da completare"}
                },
                "required": ["task_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_note",
            "description": "Salva una nuova nota nel progetto corrente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Contenuto della nota"}
                },
                "required": ["content"]
            }
        }
    }
]


async def run_tool(tool_name: str, tool_input: dict, project_id: str, db) -> str:
    if tool_name == "create_task":
        task = Task(id=new_id(), title=tool_input["title"], project_id=project_id)
        db.add(task)
        await db.commit()
        return f"Task '{tool_input['title']}' creato con ID {task.id}."

    elif tool_name == "complete_task":
        result = await db.execute(select(Task).where(Task.id == tool_input["task_id"]))
        task = result.scalar_one_or_none()
        if not task:
            return f"Task con ID {tool_input['task_id']} non trovato."
        task.done = True
        await db.commit()
        return f"Task '{task.title}' segnato come completato."

    elif tool_name == "create_note":
        note = Note(id=new_id(), content=tool_input["content"], project_id=project_id)
        db.add(note)
        await db.commit()
        return f"Nota salvata."

    return "Tool non riconosciuto."


@app.post("/api/projects/{project_id}/chat")
async def chat(project_id: str, body: ChatRequest):
    async with SessionLocal() as db:
        # Carica contesto dal DB
        proj_result = await db.execute(select(Project).where(Project.id == project_id))
        project = proj_result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=404, detail="Progetto non trovato")

        tasks_result = await db.execute(select(Task).where(Task.project_id == project_id).order_by(Task.created_at))
        tasks = tasks_result.scalars().all()

        notes_result = await db.execute(select(Note).where(Note.project_id == project_id).order_by(Note.created_at.desc()))
        notes = notes_result.scalars().all()

        task_lines = "\n".join([
            f"  - [{'✓' if t.done else ' '}] (ID: {t.id}) {t.title}"
            for t in tasks
        ]) or "  Nessun task."

        note_lines = "\n".join([f"  - {n.content[:120]}" for n in notes]) or "  Nessuna nota."

        system_prompt = f"""Sei un assistente di project management integrato nell'app ProjectHub.
Stai lavorando sul progetto: "{project.name}"
Descrizione: {project.description or 'Nessuna descrizione'}

TASK ATTUALI:
{task_lines}

NOTE RECENTI:
{note_lines}

Puoi rispondere a domande sul progetto e usare i tool per creare task, completarli o salvare note.
Quando usi un tool, conferma sempre all'utente cosa hai fatto.
Rispondi sempre in italiano e in modo conciso."""

        # Groq usa il formato OpenAI: system message come primo elemento
        messages = [{"role": "system", "content": system_prompt}]
        messages += [{"role": m.role, "content": m.content} for m in body.messages]

        # Agentic loop
        async with httpx.AsyncClient(timeout=60) as client:
            while True:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {GROQ_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": GROQ_MODEL,
                        "messages": messages,
                        "tools": AGENT_TOOLS,
                        "tool_choice": "auto",
                        "max_tokens": 1024,
                    }
                )
                data = response.json()

                if response.status_code != 200:
                    raise HTTPException(status_code=500, detail=data.get("error", {}).get("message", "Errore API Groq"))

                choice = data["choices"][0]
                message = choice["message"]
                finish_reason = choice["finish_reason"]

                # Se il modello non chiama tool, restituiamo la risposta
                if finish_reason != "tool_calls":
                    return {"reply": message.get("content", "")}

                # Il modello vuole chiamare tool — aggiungiamo la sua risposta alla cronologia
                messages.append(message)

                # Eseguiamo ogni tool call
                for tool_call in message.get("tool_calls", []):
                    tool_name  = tool_call["function"]["name"]
                    tool_input = json.loads(tool_call["function"]["arguments"])
                    result_text = await run_tool(tool_name, tool_input, project_id, db)

                    # Il risultato va rimandato al modello con il tool_call_id
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": result_text,
                    })


# ── Frontend ──────────────────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/{full_path:path}")
def serve_frontend(full_path: str):
    return FileResponse("static/index.html")
