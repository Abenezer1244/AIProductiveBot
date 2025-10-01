from __future__ import annotations
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import os
DB_PATH = os.environ.get("DB_PATH", "data.db")
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)
Base = declarative_base()
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=False)
    tz = Column(String, default="UTC")
    morning_hour = Column(Integer, default=9)
    evening_hour = Column(Integer, default=21)
class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True)
    name = Column(String)
    planned_start = Column(DateTime, nullable=True)
    planned_end = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed = Column(Boolean, default=False)
class FocusSession(Base):
    __tablename__ = "focus_sessions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True)
    start_at = Column(DateTime)
    end_at = Column(DateTime, nullable=True)
    work_minutes = Column(Integer, default=50)
    break_minutes = Column(Integer, default=10)
class ManualTrack(Base):
    __tablename__ = "manual_tracks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True)
    task_name = Column(String)
    start_at = Column(DateTime)
    end_at = Column(DateTime, nullable=True)
class Reflection(Base):
    __tablename__ = "reflections"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    went_well = Column(String)
    improve = Column(String)
    focus_tomorrow = Column(String)
class Streak(Base):
    __tablename__ = "streaks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, index=True)
    day = Column(DateTime)
    met_goal = Column(Boolean, default=False)
def init_db():
    Base.metadata.create_all(bind=engine)
def get_session() -> Session:
    return SessionLocal()
