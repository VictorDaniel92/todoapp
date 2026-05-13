import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from sqlalchemy import Column, String, Boolean, select, delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
import uuid


# ── Database setup ────────────────────────────────────────────────────────────

DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_async_engine(DATABASE_URL, echo=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Todo(Base):
    __tablename__ = "todos"

    id   = Column(String, primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    text = Column(String, nullable=False)
    done = Column(Boolean, default=False, nullable=False)


# ── App lifecycle: crea le tabelle all'avvio ──────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(lifespan=lifespan)


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class TodoCreate(BaseModel):
    text: str

class TodoUpdate(BaseModel):
    text: Optional[str] = None
    done: Optional[bool] = None

def todo_to_dict(t: Todo) -> dict:
    return {"id": t.id, "text": t.text, "done": t.done, "test": "funziona!"}


# ── API ───────────────────────────────────────────────────────────────────────

@app.get("/api/todos")
async def list_todos():
    async with SessionLocal() as db:
        result = await db.execute(select(Todo))
        return [todo_to_dict(t) for t in result.scalars().all()]


@app.post("/api/todos", status_code=201)
async def create_todo(body: TodoCreate):
    async with SessionLocal() as db:
        todo = Todo(id=str(uuid.uuid4())[:8], text=body.text, done=False)
        db.add(todo)
        await db.commit()
        await db.refresh(todo)
        return todo_to_dict(todo)


@app.patch("/api/todos/{todo_id}")
async def update_todo(todo_id: str, body: TodoUpdate):
    async with SessionLocal() as db:
        result = await db.execute(select(Todo).where(Todo.id == todo_id))
        todo = result.scalar_one_or_none()
        if not todo:
            raise HTTPException(status_code=404, detail="Todo non trovato")
        if body.text is not None:
            todo.text = body.text
        if body.done is not None:
            todo.done = body.done
        await db.commit()
        await db.refresh(todo)
        return todo_to_dict(todo)


@app.delete("/api/todos/{todo_id}", status_code=204)
async def delete_todo(todo_id: str):
    async with SessionLocal() as db:
        result = await db.execute(select(Todo).where(Todo.id == todo_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Todo non trovato")
        await db.execute(delete(Todo).where(Todo.id == todo_id))
        await db.commit()


# ── Frontend ──────────────────────────────────────────────────────────────────

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/{full_path:path}")
def serve_frontend(full_path: str):
    return FileResponse("static/index.html")
