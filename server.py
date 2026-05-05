"""
StudyMate AI — FastAPI Backend (FIXED for Railway deployment)
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import uvicorn, sqlite3, json, os
from agent import StudyMateAgent, DB_PATH

app = FastAPI(title="StudyMate AI API", version="1.0.0")

# CORS — allow your Vercel frontend + localhost
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,    # Set to your Vercel URL in Railway env vars
    allow_methods=["GET","POST","OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Serve index.html at root if it exists (optional)
@app.get("/")
def root():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"message":"StudyMate AI API","status":"running","version":"1.0.0",
            "docs":"/docs","endpoints":["/api/ask","/api/study","/api/quiz","/api/progress","/api/stats"]}

# ── Init agent once at startup ──
agent = StudyMateAgent()

# ── Request models ──
class StudyRequest(BaseModel):
    goal: str
    email: Optional[str] = None
    exam_date: Optional[str] = None   # format: YYYY-MM-DD

class AskRequest(BaseModel):
    question: str
    topic: Optional[str] = ""

class QuizRequest(BaseModel):
    topic: str
    num_questions: Optional[int] = 5

class ProgressRequest(BaseModel):
    topic: str
    subtopic: Optional[str] = ""
    score: Optional[float] = None
    notes: Optional[str] = ""

# ── Endpoints ──
@app.post("/api/study")
def create_study_plan(req: StudyRequest):
    """
    Main agent endpoint — runs all 6 steps.
    Returns: plan, resources, calendar events, email status.
    """
    if not req.goal or len(req.goal.strip()) < 3:
        raise HTTPException(400, "Goal must be at least 3 characters")
    try:
        result = agent.run(user_goal=req.goal.strip(), user_email=req.email, exam_date=req.exam_date)
        # Extract a human-readable summary for the frontend chat
        plan  = result.get("plan", {})
        days  = plan.get("total_days", 14)
        subs  = plan.get("subject", req.goal)
        result["message"] = f"Your {days}-day plan for '{subs}' is ready! I've found {len(result.get('resources',{}).get('resources',[]))} resources, {len(result.get('calendar_events',[]))} calendar events created, and {'email sent ✉️' if result.get('email_sent') else 'no email (add your address)'}."
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(500, f"Agent error: {str(e)}")

@app.post("/api/ask")
def ask_question(req: AskRequest):
    """Answer a study question with Gemini."""
    if not req.question.strip():
        raise HTTPException(400, "Question cannot be empty")
    try:
        answer = agent.answer_question(req.question.strip(), context=req.topic)
        return {"success": True, "answer": answer}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/quiz")
def get_quiz(req: QuizRequest):
    """Generate MCQ quiz for a topic."""
    if not req.topic.strip():
        raise HTTPException(400, "Topic required")
    n = max(1, min(req.num_questions or 5, 20))
    try:
        questions = agent.generate_quiz(req.topic.strip(), n)
        return {"success": True, "topic": req.topic, "questions": questions}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/api/progress")
def save_progress(req: ProgressRequest):
    """Save a study session to the database."""
    try:
        result = agent._track(req.topic, req.subtopic or "", req.score, req.notes or "")
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(500, str(e))

@app.get("/api/progress/{topic}")
def get_progress(topic: str):
    """Get history for a topic."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""SELECT topic,subtopic,date,quiz_score,notes,completed
                 FROM study_sessions WHERE topic LIKE ?
                 ORDER BY created_at DESC LIMIT 50""", (f"%{topic}%",))
    rows = c.fetchall(); conn.close()
    return {"success": True, "sessions": [
        {"topic":r[0],"subtopic":r[1],"date":r[2],"score":r[3],"notes":r[4],"completed":r[5]}
        for r in rows
    ]}

@app.get("/api/plans")
def get_plans():
    """List all active study plans."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id,subject,exam_date,created_at FROM study_plans WHERE active=1 ORDER BY created_at DESC")
    rows = c.fetchall(); conn.close()
    return {"success": True, "plans": [
        {"id":r[0],"subject":r[1],"exam_date":r[2],"created_at":r[3]} for r in rows
    ]}

@app.get("/api/stats")
def get_stats():
    """Overall study statistics."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM study_sessions WHERE completed=1")
    completed = c.fetchone()[0]
    c.execute("SELECT AVG(quiz_score) FROM study_sessions WHERE quiz_score IS NOT NULL")
    avg = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(DISTINCT topic) FROM study_sessions")
    topics = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM study_plans WHERE active=1")
    plans = c.fetchone()[0]
    conn.close()
    return {"success": True, "stats": {
        "sessions_completed": completed,
        "avg_quiz_score": round(avg, 1),
        "topics_studied": topics,
        "active_plans": plans
    }}

@app.get("/health")
def health():
    return {
        "status": "ok",
        "gemini": bool(os.getenv("GEMINI_API_KEY")),
        "google_mcp": agent.google_connected,
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
