from __future__ import annotations
from datetime import datetime, timedelta
import os, pytz
from sqlalchemy.orm import Session
from db import get_session, init_db, User, Task, FocusSession, ManualTrack, Reflection, Streak
from calendar_integration import create_event
def get_tz(user: User):
    return pytz.timezone(user.tz or os.getenv("TZ", "UTC"))
def ensure_user(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if not user:
        user = User(id=user_id, tz=os.getenv("TZ", "UTC"))
        session.add(user); session.commit()
    return user
def set_reminders(session: Session, user_id: int, morning: int, evening: int):
    user = ensure_user(session, user_id)
    user.morning_hour = morning; user.evening_hour = evening; session.commit(); return user
def add_task(session: Session, user_id: int, name: str, start=None, end=None):
    t = Task(user_id=user_id, name=name, planned_start=start, planned_end=end); session.add(t); session.commit(); return t
def mark_completed(session: Session, user_id: int, task_id: int, done=True):
    t = session.get(Task, task_id); 
    if t and t.user_id == user_id: t.completed = done; session.commit(); return t
    return None
def list_today_tasks(session: Session, user_id: int, tz_name="UTC"):
    tz = pytz.timezone(tz_name); now = datetime.now(tz)
    start = tz.localize(datetime(now.year, now.month, now.day, 0, 0)).astimezone(pytz.UTC).replace(tzinfo=None)
    end = (tz.localize(datetime(now.year, now.month, now.day, 0, 0)) + timedelta(days=1)).astimezone(pytz.UTC).replace(tzinfo=None)
    return session.query(Task).filter(Task.user_id==user_id, Task.created_at>=start, Task.created_at<end).order_by(Task.id.asc()).all()
def start_focus(session: Session, user_id: int, work_min=50, break_min=10):
    f = FocusSession(user_id=user_id, start_at=datetime.utcnow(), work_minutes=work_min, break_minutes=break_min); session.add(f); session.commit(); return f
def stop_focus(session: Session, user_id: int):
    f = session.query(FocusSession).filter(FocusSession.user_id==user_id, FocusSession.end_at==None).order_by(FocusSession.id.desc()).first()
    if not f: return None
    f.end_at = datetime.utcnow(); session.commit(); return f
def start_manual(session: Session, user_id: int, name: str):
    running = session.query(ManualTrack).filter(ManualTrack.user_id==user_id, ManualTrack.end_at==None).all()
    for r in running: r.end_at = datetime.utcnow()
    m = ManualTrack(user_id=user_id, task_name=name, start_at=datetime.utcnow()); session.add(m); session.commit(); return m
def stop_manual(session: Session, user_id: int):
    m = session.query(ManualTrack).filter(ManualTrack.user_id==user_id, ManualTrack.end_at==None).order_by(ManualTrack.id.desc()).first()
    if not m: return None
    m.end_at = datetime.utcnow(); session.commit(); return m
def add_reflection(session: Session, user_id: int, went_well: str, improve: str, tomorrow: str):
    r = Reflection(user_id=user_id, went_well=went_well, improve=improve, focus_tomorrow=tomorrow); session.add(r); session.commit(); return r
def today_summary(session: Session, user_id: int, tz_name="UTC"):
    tz = pytz.timezone(tz_name); now = datetime.now(tz)
    start = tz.localize(datetime(now.year, now.month, now.day, 0, 0)).astimezone(pytz.UTC).replace(tzinfo=None)
    end = (tz.localize(datetime(now.year, now.month, now.day, 0, 0)) + timedelta(days=1)).astimezone(pytz.UTC).replace(tzinfo=None)
    focus = session.query(FocusSession).filter(FocusSession.user_id==user_id, FocusSession.start_at>=start, FocusSession.start_at<end).all()
    total_focus_min = sum(int(((f.end_at or datetime.utcnow()) - f.start_at).total_seconds() // 60) for f in focus)
    tracks = session.query(ManualTrack).filter(ManualTrack.user_id==user_id, ManualTrack.start_at>=start, ManualTrack.start_at<end).all()
    manual_min = sum(int(((t.end_at or datetime.utcnow()) - t.start_at).total_seconds() // 60) for t in tracks)
    tasks = list_today_tasks(session, user_id, tz_name); completed = sum(1 for t in tasks if t.completed)
    return {"total_focus_min": total_focus_min, "manual_min": manual_min, "tasks_total": len(tasks), "tasks_done": completed}
def upsert_streak_for_today(session: Session, user_id: int, met_goal: bool):
    day_utc = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    st = session.query(Streak).filter(Streak.user_id==user_id, Streak.day==day_utc).first()
    if not st: st = Streak(user_id=user_id, day=day_utc, met_goal=met_goal); session.add(st)
    else: st.met_goal = met_goal
    session.commit(); return st
def get_consecutive_days(session: Session, user_id: int):
    days = 0; d = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    while True:
        st = session.query(Streak).filter(Streak.user_id==user_id, Streak.day==d).first()
        if st and st.met_goal: days += 1; d = d - timedelta(days=1)
        else: break
    return days
def create_calendar_event_for_task(session: Session, user: User, task_id: int, start_local: str, duration_min: int):
    import pytz
    t = session.get(Task, task_id); 
    if not t or t.user_id != user.id: return None, "Task not found"
    tz = pytz.timezone(user.tz or "UTC")
    now = datetime.now(tz); h, m = map(int, start_local.split(":"))
    start_dt_local = tz.localize(datetime(now.year, now.month, now.day, h, m))
    end_dt_local = start_dt_local + timedelta(minutes=duration_min)
    link = create_event(t.name, start_dt_local.isoformat(), end_dt_local.isoformat(), timezone=user.tz or "UTC")
    import pytz as _p; t.planned_start = start_dt_local.astimezone(_p.UTC).replace(tzinfo=None); t.planned_end = end_dt_local.astimezone(_p.UTC).replace(tzinfo=None)
    session.commit(); return link, None
def _parse_hhmm(s: str): h, m = s.split(":"); return int(h), int(m)
def autoschedule_mits(session: Session, user: User, task_ids: list[int]):
    tz = get_tz(user); now = datetime.now(tz)
    sh, sm = _parse_hhmm(os.getenv("WORK_START", "09:00")); eh, em = _parse_hhmm(os.getenv("WORK_END", "18:00"))
    block_min = int(os.getenv("MIT_BLOCK_MIN", "60"))
    start_today = tz.localize(datetime(now.year, now.month, now.day, sh, sm))
    end_today = tz.localize(datetime(now.year, now.month, now.day, eh, em))
    start_time = max(now + timedelta(minutes=15), start_today)
    if start_time > end_today:
        next_day = now + timedelta(days=1)
        start_time = tz.localize(datetime(next_day.year, next_day.month, next_day.day, sh, sm))
    results = []; cur = start_time
    for tid in task_ids:
        end = cur + timedelta(minutes=block_min)
        if end > tz.localize(datetime(cur.year, cur.month, cur.day, eh, em)):
            next_day = cur + timedelta(days=1)
            cur = tz.localize(datetime(next_day.year, next_day.month, next_day.day, sh, sm)); end = cur + timedelta(minutes=block_min)
        t = session.get(Task, tid); link = create_event(f"MIT: {t.name}", cur.isoformat(), end.isoformat(), timezone=user.tz or "UTC")
        import pytz as _p; t.planned_start = cur.astimezone(_p.UTC).replace(tzinfo=None); t.planned_end = end.astimezone(_p.UTC).replace(tzinfo=None)
        session.commit(); results.append((tid, link)); cur = end + timedelta(minutes=5)
    return results
def weekly_report(session: Session, user_id: int, tz_name="UTC"):
    tz = pytz.timezone(tz_name); now = datetime.now(tz); days = []
    for i in range(6, -1, -1):
        d = now - timedelta(days=i)
        start_local = tz.localize(datetime(d.year, d.month, d.day, 0, 0)); end_local = start_local + timedelta(days=1)
        start = start_local.astimezone(pytz.UTC).replace(tzinfo=None); end = end_local.astimezone(pytz.UTC).replace(tzinfo=None)
        focus = session.query(FocusSession).filter(FocusSession.user_id==user_id, FocusSession.start_at>=start, FocusSession.start_at<end).all()
        focus_min = sum(int(((f.end_at or datetime.utcnow()) - f.start_at).total_seconds() // 60) for f in focus)
        tracks = session.query(ManualTrack).filter(ManualTrack.user_id==user_id, ManualTrack.start_at>=start, ManualTrack.start_at<end).all()
        manual_min = sum(int(((t.end_at or datetime.utcnow()) - t.start_at).total_seconds() // 60) for t in tracks)
        tasks = session.query(Task).filter(Task.user_id==user_id, Task.created_at>=start, Task.created_at<end).all()
        tasks_done = sum(1 for t in tasks if t.completed); tasks_total = len(tasks)
        days.append({"label": start_local.strftime("%a %m/%d"), "focus_min": focus_min, "manual_min": manual_min, "tasks_done": tasks_done, "tasks_total": tasks_total})
    return {"days": days, "total_focus": sum(d["focus_min"] for d in days), "total_manual": sum(d["manual_min"] for d in days),
            "total_done": sum(d["tasks_done"] for d in days), "total_tasks": sum(d["tasks_total"] for d in days),
            "best_day": max(days, key=lambda x: x["focus_min"]) if days else None}
