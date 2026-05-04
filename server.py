"""
StudyMate AI — FastAPI Backend Server
Exposes REST endpoints for the frontend to call the agent.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import uvicorn
import sqlite3
import json
from agent import StudyMateAgent

app = FastAPI(title="StudyMate AI API", version="1.0.0")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend
app.mount("/static", StaticFiles(directory="."), name="static")

# Initialize agent once
agent = StudyMateAgent()


class StudyGoalRequest(BaseModel):
    goal: str
    email: Optional[str] = None
    exam_date: Optional[str] = None


class QuestionRequest(BaseModel):
    question: str
    topic: Optional[str] = ""


class QuizRequest(BaseModel):
    topic: str
    num_questions: int = 5


class ProgressRequest(BaseModel):
    topic: str
    subtopic: Optional[str] = ""
    score: Optional[float] = None
    notes: Optional[str] = ""


@app.get("/")
def root():
    return {"message": "StudyMate AI Agent API", "status": "running", "version": "1.0.0"}


@app.post("/api/study")
def create_study_plan(req: StudyGoalRequest):
    """Main agent endpoint — runs all steps."""
    try:
        results = agent.run(
            user_goal=req.goal,
            user_email=req.email,
            exam_date=req.exam_date
        )
        return {"success": True, "data": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ask")
def ask_question(req: QuestionRequest):
    """Answer a study question using Gemini."""
    try:
        answer = agent.answer_question(req.question, context=req.topic)
        return {"success": True, "answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/quiz")
def generate_quiz(req: QuizRequest):
    """Generate quiz questions for a topic."""
    try:
        questions = agent.generate_quiz(req.topic, req.num_questions)
        return {"success": True, "questions": questions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/progress")
def save_progress(req: ProgressRequest):
    """Save study session progress."""
    try:
        result = agent._track_progress(req.topic, req.subtopic, req.score, req.notes)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/progress/{topic}")
def get_progress(topic: str):
    """Get study progress for a topic."""
    conn = sqlite3.connect("studymate.db")
    c = conn.cursor()
    c.execute("""
        SELECT topic, subtopic, date, quiz_score, notes, completed
        FROM study_sessions WHERE topic LIKE ?
        ORDER BY created_at DESC LIMIT 50
    """, (f"%{topic}%",))
    rows = c.fetchall()
    conn.close()
    sessions = [
        {"topic": r[0], "subtopic": r[1], "date": r[2],
         "score": r[3], "notes": r[4], "completed": r[5]}
        for r in rows
    ]
    return {"success": True, "sessions": sessions}


@app.get("/api/plans")
def get_plans():
    """Get all active study plans."""
    conn = sqlite3.connect("studymate.db")
    c = conn.cursor()
    c.execute("SELECT id, subject, exam_date, created_at FROM study_plans WHERE active=1")
    rows = c.fetchall()
    conn.close()
    return {
        "success": True,
        "plans": [{"id": r[0], "subject": r[1], "exam_date": r[2], "created_at": r[3]} for r in rows]
    }


@app.get("/api/stats")
def get_stats():
    """Get overall study statistics."""
    conn = sqlite3.connect("studymate.db")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM study_sessions WHERE completed=1")
    completed = c.fetchone()[0]
    c.execute("SELECT AVG(quiz_score) FROM study_sessions WHERE quiz_score IS NOT NULL")
    avg_score = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(DISTINCT topic) FROM study_sessions")
    topics = c.fetchone()[0]
    conn.close()
    return {
        "success": True,
        "stats": {
            "sessions_completed": completed,
            "avg_quiz_score": round(avg_score, 1),
            "topics_studied": topics
        }
    }


if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8080, reload=True)
