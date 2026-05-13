import os
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


# ── DB setup ──────────────────────────────────────────────────────────────────

DATABASE_URL = os.environ["DATABASE_URL"].replace(
    "postgresql://", "postgresql+asyncpg://"
)

engine = create_async_engine(DATABASE_URL, echo=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# ── Models ────────────────────────────────────────────────────────────────────

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

    # relationship: quando carichi un Project, puoi accedere a .tasks e .notes
    # cascade="all, delete-orphan" = se elimini il progetto, elimina anche task e note
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    notes = relationship("Note", back_populates="project", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id         = Column(String, primary_key=True, default=new_id)
    title      = Column(String, nullable=False)
    done       = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)

    # ForeignKey collega ogni task al suo progetto
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    project    = relationship("Project", back_populates="tasks")


class Note(Base):
    __tablename__ = "notes"

    id         = Column(String, primary_key=True, default=new_id)
    content    = Column(Text, nullable=False)
    created_at = Column(DateTime, default=now)

    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    project    = relationship("Project", back_populates="notes")


# ── Lifespan: crea tutte le tabelle all'avvio ─────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(lifespan=lifespan)


# ── Pydantic schemas ──────────────────────────────────────────────────────────

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


# ── Serializers ───────────────────────────────────────────────────────────────

def project_to_dict(p: Project) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "created_at": p.created_at.isoformat(),
    }

def task_to_dict(t: Task) -> dict:
    return {
        "id": t.id,
        "title": t.title,
        "done": t.done,
        "project_id": t.project_id,
        "created_at": t.created_at.isoformat(),
    }

def note_to_dict(n: Note) -> dict:
    return {
        "id": n.id,
        "content": n.content,
        "project_id": n.project_id,
        "created_at": n.created_at.isoformat(),
    }


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
        result = await db.execute(
            select(Task).where(Task.project_id == project_id).order_by(Task.created_at)
        )
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
        result = await db.execute(
            select(Note).where(Note.project_id == project_id).order_by(Note.created_at.desc())
        )
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


# ── Frontend ──────────────────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/{full_path:path}")
def serve_frontend(full_path: str):
    return FileResponse("static/index.html")
