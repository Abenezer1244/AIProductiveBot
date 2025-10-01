from __future__ import annotations
import os, logging
from datetime import time
import pytz
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ConversationHandler, ContextTypes, CallbackContext
from db import init_db, get_session
from logic import ensure_user, add_task, list_today_tasks, mark_completed, set_reminders, start_focus, stop_focus, start_manual, stop_manual, add_reflection, today_summary, upsert_streak_for_today, get_consecutive_days, create_calendar_event_for_task, autoschedule_mits, weekly_report
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("productivity-bot")
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN"); DEFAULT_TZ = os.getenv("TZ", "UTC")
MORNING_HOUR = int(os.getenv("MORNING_REMINDER_HOUR", "9")); EVENING_HOUR = int(os.getenv("EVENING_REMINDER_HOUR", "21"))
CALENDAR_AUTOSCHEDULE = os.getenv("CALENDAR_AUTOSCHEDULE", "0") == "1"
PLAN_MIT1, PLAN_MIT2, PLAN_MIT3 = range(3); REFLECT_WELL, REFLECT_IMPROVE, REFLECT_TMR = range(3,6)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    with get_session() as s:
        u = ensure_user(s, user_id); schedule_daily_jobs(context.application, update.effective_chat.id, u.tz or DEFAULT_TZ, u.morning_hour, u.evening_hour)
    await update.message.reply_text("👋 Welcome! Try: /plan, /focus, /weekly, /summary, /reflect", parse_mode=ParseMode.MARKDOWN)
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Commands: /plan /tasks /done <id> /focus <work> <break> /starttask /stoptask /summary /weekly /reflect /calendar <id> <HH:MM> <dur> /setreminders <h> <h> /export /wipe", parse_mode=ParseMode.MARKDOWN)
async def plan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Let's plan your day. What's **MIT #1**?"); context.user_data["mits"] = []; return PLAN_MIT1
async def plan_mit1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mits"].append(update.message.text.strip()); await update.message.reply_text("Great. What's **MIT #2**?"); return PLAN_MIT2
async def plan_mit2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mits"].append(update.message.text.strip()); await update.message.reply_text("Awesome. What's **MIT #3**? (or type `skip`)"); return PLAN_MIT3
async def plan_mit3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text.strip(); 
    if t.lower() != "skip": context.user_data["mits"].append(t)
    user_id = update.effective_user.id; task_ids = []
    with get_session() as s:
        u = ensure_user(s, user_id)
        for name in context.user_data["mits"]: task_ids.append(add_task(s, user_id, name).id)
        msg = f"✅ Saved {len(task_ids)} MITs."
        if CALENDAR_AUTOSCHEDULE and os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET") and os.getenv("GOOGLE_REFRESH_TOKEN"):
            try:
                results = autoschedule_mits(s, u, task_ids)
                if results:
                    links = "\n".join([f"- Task [{tid}] → {lnk}" for tid, lnk in results])
                    msg += f"\n📅 Auto-timeboxed to Calendar:\n{links}"
            except Exception as e:
                msg += f"\n(Calendar autoschedule skipped: {e})"
        else:
            if CALENDAR_AUTOSCHEDULE: msg += "\n(Calendar autoschedule ON but Google creds missing.)"
        msg += "\nUse /tasks to view or /done <id> to complete."
    await update.message.reply_text(msg); return ConversationHandler.END
async def focus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    work = int(context.args[0]) if len(context.args) >= 1 else 50; brk = int(context.args[1]) if len(context.args) >= 2 else 10
    user_id = update.effective_user.id; 
    with get_session() as s: start_focus(s, user_id, work, brk)
    await update.message.reply_text(f"⏳ Focus started for {work} min."); context.job_queue.run_once(focus_done_ping, when=work*60, chat_id=update.effective_chat.id, name=f"focus-{user_id}", data={"break": brk})
async def focus_done_ping(context: CallbackContext):
    await context.bot.send_message(context.job.chat_id, f"✅ Focus done! Take a {context.job.data.get('break', 10)} min break.")
async def starttask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("Usage: /starttask <task name>"); return
    name = " ".join(context.args); user_id = update.effective_user.id
    with get_session() as s: start_manual(s, user_id, name)
    await update.message.reply_text(f"▶️ Tracking: *{name}*", parse_mode=ParseMode.MARKDOWN)
async def stoptask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id; 
    with get_session() as s: m = stop_manual(s, user_id)
    if not m: await update.message.reply_text("No running manual task.")
    else:
        mins = int((m.end_at - m.start_at).total_seconds() // 60)
        await update.message.reply_text(f"⏹️ Stopped. {mins} min on *{m.task_name}*.", parse_mode=ParseMode.MARKDOWN)
async def reflect_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Reflection: What went well today?"); return REFLECT_WELL
async def reflect_well(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["reflect_well"] = update.message.text.strip(); await update.message.reply_text("What can improve tomorrow?"); return REFLECT_IMPROVE
async def reflect_improve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["reflect_improve"] = update.message.text.strip(); await update.message.reply_text("What's your #1 focus for tomorrow?"); return REFLECT_TMR
async def reflect_tmr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id; 
    with get_session() as s: add_reflection(s, user_id, context.user_data["reflect_well"], context.user_data["reflect_improve"], update.message.text.strip())
    await update.message.reply_text("✅ Reflection saved. Sleep well! 😴"); return ConversationHandler.END
async def summary_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    with get_session() as s:
        u = ensure_user(s, user_id); sm = today_summary(s, user_id, u.tz)
    await update.message.reply_text(f"📊 **Today**\nFocus: {sm['total_focus_min']} min\nManual: {sm['manual_min']} min\nTasks: {sm['tasks_done']}/{sm['tasks_total']} done\n", parse_mode=ParseMode.MARKDOWN)
async def tasks_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    with get_session() as s:
        u = ensure_user(s, user_id); tasks = list_today_tasks(s, user_id, u.tz)
    if not tasks: await update.message.reply_text("No tasks for today. Use /plan to add MITs."); return
    lines = ["🗒️ *Today's Tasks*"] + [f"{'✅' if t.completed else '⬜'} [{t.id}] {t.name}" for t in tasks]
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
async def done_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: await update.message.reply_text("Usage: /done <task_id>"); return
    user_id = update.effective_user.id
    try: tid = int(context.args[0])
    except ValueError: await update.message.reply_text("Task id must be a number."); return
    with get_session() as s: t = mark_completed(s, user_id, tid, True)
    await update.message.reply_text(f"🎉 Marked task [{tid}] as done." if t else "Couldn't find that task.")
async def setreminders_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2: await update.message.reply_text("Usage: /setreminders <morning_hour> <evening_hour>"); return
    morning = int(context.args[0]); evening = int(context.args[1]); user_id = update.effective_user.id
    with get_session() as s: u = set_reminders(s, user_id, morning, evening)
    schedule_daily_jobs(context.application, update.effective_chat.id, u.tz or DEFAULT_TZ, morning, evening); await update.message.reply_text(f"⏰ Reminders: {morning}:00 and {evening}:00")
async def morning_ping(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(context.job.chat_id, "☀️ Good morning! What are your 3 MITs? Use /plan.")
async def evening_ping(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(context.job.chat_id, "🌙 Time to reflect. Use /reflect to log your day in 60 seconds.")
async def nightly_streak_job(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id; user_id = context.job.data.get("user_id")
    with get_session() as s:
        u = ensure_user(s, user_id); sm = today_summary(s, user_id, u.tz)
        met = (sm["total_focus_min"] >= 60) or (sm["tasks_done"] >= 2); upsert_streak_for_today(s, user_id, met); streak = get_consecutive_days(s, user_id)
    badge = next((f"🏅 {m}-day streak!" for m in [3,7,14,30,60,100] if streak == m), None)
    txt = f"🔥 Streak: {streak} day(s) {'(goal met ✅)' if met else '(missed)'}."; 
    if badge: txt = badge + "\n" + txt
    await context.bot.send_message(chat_id, txt)
def schedule_daily_jobs(app, chat_id: int, tz_name: str, morning_hour: int, evening_hour: int):
    tz = pytz.timezone(tz_name); from datetime import time as dtime
    for name in [f"morning-{chat_id}", f"evening-{chat_id}", f"streak-{chat_id}"]:
        for j in app.job_queue.get_jobs_by_name(name): j.schedule_removal()
    app.job_queue.run_daily(morning_ping, time=dtime(hour=morning_hour, minute=0, tzinfo=tz), chat_id=chat_id, name=f"morning-{chat_id}")
    app.job_queue.run_daily(evening_ping, time=dtime(hour=evening_hour, minute=0, tzinfo=tz), chat_id=chat_id, name=f"evening-{chat_id}")
    app.job_queue.run_daily(nightly_streak_job, time=dtime(hour=23, minute=59, tzinfo=tz), chat_id=chat_id, name=f"streak-{chat_id}", data={"user_id": chat_id})
async def calendar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3: await update.message.reply_text("Usage: /calendar <task_id> <HH:MM> <duration_min>"); return
    try: tid = int(context.args[0]); hhmm = context.args[1]; dur = int(context.args[2])
    except Exception: await update.message.reply_text("Invalid arguments. Example: /calendar 12 14:30 90"); return
    user_id = update.effective_user.id
    with get_session() as s:
        u = ensure_user(s, user_id)
        try: link, err = create_calendar_event_for_task(s, u, tid, hhmm, dur)
        except Exception as e: await update.message.reply_text(f"Calendar error: {e}"); return
    await update.message.reply_text(err if err else f"📅 Event created: {link}")
async def weekly_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    with get_session() as s: u = ensure_user(s, user_id); rep = weekly_report(s, user_id, u.tz)
    lines = ["📈 *Weekly Report (last 7 days)*", f"Focus: {rep['total_focus']} min | Manual: {rep['total_manual']} min", f"Tasks: {rep['total_done']}/{rep['total_tasks']} completed", ""]
    if rep["best_day"]: lines[2] += f"\nBest day: {rep['best_day']['label']} ({rep['best_day']['focus_min']} min focus)"
    for d in rep["days"]: lines.append(f"{d['label']}: Focus {d['focus_min']}m, Manual {d['manual_min']}m, Tasks {d['tasks_done']}/{d['tasks_total']}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
from sqlalchemy import text as sqltext
async def export_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    with get_session() as s:
        tables = ["tasks","focus_sessions","manual_tracks","reflections","users","streaks"]; dump = {}
        for t in tables: rows = s.execute(sqltext(f"SELECT * FROM {t} WHERE user_id=:uid OR :t='users'"), {"uid": user_id, "t": t}).mappings().all(); dump[t] = [dict(r) for r in rows]
    await update.message.reply_document(document=("export.json", str(dump).encode("utf-8")), filename="export.json")
async def wipe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    with get_session() as s:
        for t in ["tasks","focus_sessions","manual_tracks","reflections","streaks"]: s.execute(sqltext(f"DELETE FROM {t} WHERE user_id=:u"), {"u": user_id})
        s.commit()
    await update.message.reply_text("🧹 Your data has been wiped.")
def main():
    if not BOT_TOKEN: raise SystemExit("BOT_TOKEN missing.")
    init_db(); app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start)); app.add_handler(CommandHandler("help", help_cmd))
    plan_conv = ConversationHandler(entry_points=[CommandHandler("plan", plan_start)], states={PLAN_MIT1: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_mit1)], PLAN_MIT2: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_mit2)], PLAN_MIT3: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_mit3)]}, fallbacks=[]); app.add_handler(plan_conv)
    reflect_conv = ConversationHandler(entry_points=[CommandHandler("reflect", reflect_start)], states={REFLECT_WELL: [MessageHandler(filters.TEXT & ~filters.COMMAND, reflect_well)], REFLECT_IMPROVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, reflect_improve)], REFLECT_TMR: [MessageHandler(filters.TEXT & ~filters.COMMAND, reflect_tmr)]}, fallbacks=[]); app.add_handler(reflect_conv)
    app.add_handler(CommandHandler("focus", focus_cmd)); app.add_handler(CommandHandler("starttask", starttask_cmd)); app.add_handler(CommandHandler("stoptask", stoptask_cmd)); app.add_handler(CommandHandler("tasks", tasks_cmd)); app.add_handler(CommandHandler("done", done_cmd))
    app.add_handler(CommandHandler("summary", summary_cmd)); app.add_handler(CommandHandler("setreminders", setreminders_cmd)); app.add_handler(CommandHandler("calendar", calendar_cmd)); app.add_handler(CommandHandler("weekly", weekly_cmd))
    app.add_handler(CommandHandler("export", export_cmd)); app.add_handler(CommandHandler("wipe", wipe_cmd))
    logger.info("Bot starting..."); app.run_polling()
if __name__ == "__main__": main()
