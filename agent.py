"""
StudyMate AI - Multi-Step Study Agent
Powered by Gemini 1.5 Pro + Google Cloud Agent Builder + MCP
FIXED VERSION: env vars, error handling, Railway-compatible
"""

import os
import json
import sqlite3
import datetime
from typing import Optional
import google.generativeai as genai
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─── CONFIG (env vars — set in Railway dashboard) ────────────────────────────
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
GOOGLE_TOKEN    = os.getenv("GOOGLE_TOKEN_JSON", "")   # Full token.json contents as env var
USE_GOOGLE_APIS = False  # will be set True if creds load successfully

if not GEMINI_API_KEY:
    print("⚠️  GEMINI_API_KEY not set — agent will run in echo mode")
else:
    genai.configure(api_key=GEMINI_API_KEY)
    print("✅ Gemini configured")

# ─── DATABASE SETUP ──────────────────────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", "studymate.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS study_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL, subtopic TEXT, date TEXT,
            duration_minutes INTEGER, quiz_score REAL,
            resources_used TEXT, notes TEXT,
            completed BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
    c.execute("""
        CREATE TABLE IF NOT EXISTS study_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL, exam_date TEXT, plan_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, active BOOLEAN DEFAULT 1
        )""")
    c.execute("""
        CREATE TABLE IF NOT EXISTS weak_areas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT, subtopic TEXT, score REAL, last_tested TEXT
        )""")
    conn.commit()
    conn.close()
    print("✅ Database ready:", DB_PATH)

# ─── GOOGLE OAUTH (loads from env var on Railway) ────────────────────────────
def get_google_creds():
    """Load Google credentials from env var (Railway) or token.json (local)."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    SCOPES = [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.readonly",
    ]

    creds = None
    # Try env var first (Railway deployment)
    if GOOGLE_TOKEN:
        creds = Credentials.from_authorized_user_info(json.loads(GOOGLE_TOKEN), SCOPES)
    # Fall back to file (local dev)
    elif os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    else:
        raise FileNotFoundError("No Google credentials found. Set GOOGLE_TOKEN_JSON env var on Railway.")

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    return creds

# ─── CALENDAR MCP ────────────────────────────────────────────────────────────
class CalendarMCP:
    def __init__(self, creds):
        from googleapiclient.discovery import build
        self.service = build("calendar", "v3", credentials=creds)

    def create_study_event(self, topic, subtopic, start_time,
                           duration_minutes=90, description=""):
        start_dt = datetime.datetime.fromisoformat(start_time)
        end_dt   = start_dt + datetime.timedelta(minutes=duration_minutes)
        event = {
            "summary": f"📚 StudyMate: {topic} — {subtopic}",
            "description": f"StudyMate AI Study Session\n\n{description}\n\nPowered by StudyMate AI",
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Kolkata"},
            "end":   {"dateTime": end_dt.isoformat(),   "timeZone": "Asia/Kolkata"},
            "colorId": "9",
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 30},
                    {"method": "email", "minutes": 60},
                ]
            }
        }
        result = self.service.events().insert(calendarId="primary", body=event).execute()
        print(f"  📅 Calendar event created: {result.get('htmlLink')}")
        return result

    def get_free_slots(self, days_ahead=7):
        free_slots = []
        for i in range(days_ahead):
            day = datetime.datetime.now() + datetime.timedelta(days=i+1)
            # Evening slot: 7 PM IST
            slot = day.replace(hour=19, minute=0, second=0, microsecond=0)
            free_slots.append(slot.isoformat())
        return free_slots

# ─── GMAIL MCP ───────────────────────────────────────────────────────────────
class GmailMCP:
    def __init__(self, creds):
        from googleapiclient.discovery import build
        self.service = build("gmail", "v1", credentials=creds)

    def send_study_plan(self, to_email, subject, plan_html):
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = "me"
        msg["To"]      = to_email
        msg.attach(MIMEText(plan_html, "html"))
        raw    = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        result = self.service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()
        print(f"  ✉️ Email sent: {result.get('id')}")
        return result

    def build_plan_email(self, plan):
        rows = ""
        for day in plan.get("days", []):
            tasks = "".join(f"<li>{t}</li>" for t in day.get("tasks", []))
            rows += f"""<tr>
              <td style="padding:12px;border-bottom:1px solid #eee;font-weight:700;color:#e85d2f">{day['day']}</td>
              <td style="padding:12px;border-bottom:1px solid #eee"><ul style="margin:0;padding-left:16px;font-size:13px">{tasks}</ul></td>
              <td style="padding:12px;border-bottom:1px solid #eee;color:#888;font-size:12px">{day.get('duration','2h')}</td>
            </tr>"""
        return f"""<!DOCTYPE html><html><body style="font-family:'Segoe UI',sans-serif;max-width:640px;margin:auto;padding:20px;background:#f5f0e8">
<div style="background:#0d0c0a;padding:28px;border-radius:16px 16px 0 0;text-align:center">
  <h1 style="color:#f5f0e8;margin:0;font-size:22px;letter-spacing:-0.03em">📚 StudyMate AI</h1>
  <p style="color:rgba(255,255,255,0.4);margin:6px 0 0;font-size:13px">Your personalised study plan is ready</p>
</div>
<div style="background:#fff;padding:28px;border-radius:0 0 16px 16px;border:1px solid #e3dccb;border-top:none">
  <h2 style="margin-top:0;font-size:20px;letter-spacing:-0.02em">{plan.get('subject','')}</h2>
  <p style="color:#6b6456;font-size:13px">Exam date: <strong>{plan.get('exam_date','TBD')}</strong> · <strong>{plan.get('total_days',7)} days</strong> · <strong>{plan.get('hours_per_day',2)}h/day</strong></p>
  <table style="width:100%;border-collapse:collapse;margin:20px 0;font-size:13px">
    <thead><tr style="background:#f5f0e8">
      <th style="padding:10px 12px;text-align:left;color:#e85d2f;font-size:11px;letter-spacing:0.06em;text-transform:uppercase">Day</th>
      <th style="padding:10px 12px;text-align:left;color:#e85d2f;font-size:11px;letter-spacing:0.06em;text-transform:uppercase">Tasks</th>
      <th style="padding:10px 12px;text-align:left;color:#e85d2f;font-size:11px;letter-spacing:0.06em;text-transform:uppercase">Time</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <p style="color:#6b6456;font-size:12px;margin:0">📅 All sessions added to your Google Calendar · Good luck! 🚀</p>
</div></body></html>"""

# ─── MAIN AGENT ──────────────────────────────────────────────────────────────
class StudyMateAgent:
    def __init__(self):
        init_db()
        self.google_connected = False

        # Try to init Gemini model
        if GEMINI_API_KEY:
            try:
                self.model = genai.GenerativeModel("gemini-1.5-pro")
                print("✅ Gemini model loaded")
            except Exception as e:
                self.model = None
                print(f"⚠️  Gemini init failed: {e}")
        else:
            self.model = None

        # Try to init Google services
        try:
            creds = get_google_creds()
            self.calendar = CalendarMCP(creds)
            self.gmail    = GmailMCP(creds)
            self.google_connected = True
            print("✅ Google Calendar + Gmail MCP connected")
        except Exception as e:
            print(f"⚠️  Google MCP unavailable (demo mode): {e}")

    # ── Internal tools ────────────────────────────────────────────────────
    def _search_resources(self, topic, level="undergraduate"):
        print(f"  🔍 Searching resources: {topic}")
        return {
            "topic": topic,
            "resources": [
                {"type": "video",    "title": f"MIT OCW — {topic} Lecture Series",     "url": "https://ocw.mit.edu"},
                {"type": "article",  "title": f"GeeksForGeeks — {topic} Guide",        "url": "https://geeksforgeeks.org"},
                {"type": "course",   "title": f"NPTEL — {topic} for CSE",              "url": "https://nptel.ac.in"},
                {"type": "practice", "title": f"LeetCode — {topic} Problems",          "url": "https://leetcode.com"},
                {"type": "video",    "title": f"YouTube — {topic} Crash Course",       "url": "https://youtube.com"},
            ]
        }

    def _create_plan(self, subject, days=14, hours=2.0):
        print(f"  📋 Generating {days}-day plan: {subject}")
        if not self.model:
            # Fallback plan without Gemini
            return self._fallback_plan(subject, days, hours)
        prompt = f"""Create a {days}-day study plan for "{subject}" for a B.Tech CSE student.
Each day should have 2-3 specific tasks totalling {hours} hours.
IMPORTANT: Return ONLY valid JSON, no markdown, no explanation.
Format:
{{"subject":"{subject}","total_days":{days},"hours_per_day":{hours},"exam_date":"TBD","days":[
  {{"day":"Day 1 — Mon","date":"","tasks":["Task A","Task B"],"duration":"{hours}h","type":"learning"}}
]}}"""
        try:
            resp = self.model.generate_content(prompt)
            text = resp.text.strip()
            # Strip markdown fences if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text.strip())
        except Exception as e:
            print(f"  ⚠️  Gemini plan parse error: {e}")
            return self._fallback_plan(subject, days, hours)

    def _fallback_plan(self, subject, days, hours):
        topics = ["Introduction & Overview","Core Concepts Part 1","Core Concepts Part 2",
                  "Advanced Topics","Problem Solving","Mock Quiz","Review & Revision"]
        plan_days = []
        for i in range(days):
            topic = topics[i % len(topics)]
            plan_days.append({
                "day": f"Day {i+1}",
                "date": (datetime.date.today() + datetime.timedelta(days=i+1)).isoformat(),
                "tasks": [f"{subject}: {topic}", "Practice problems (30 min)", "Revise notes"],
                "duration": f"{hours}h",
                "type": "learning" if i % 3 != 2 else "quiz"
            })
        return {"subject":subject,"total_days":days,"hours_per_day":hours,"exam_date":"TBD","days":plan_days}

    def _track(self, topic, subtopic="", score=None, notes=""):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO study_sessions (topic,subtopic,date,quiz_score,notes,completed) VALUES(?,?,?,?,?,1)",
                  (topic, subtopic, datetime.date.today().isoformat(), score, notes))
        conn.commit(); conn.close()
        print(f"  💾 Progress saved: {topic}")
        return {"status":"saved","topic":topic}

    # ── Main run ──────────────────────────────────────────────────────────
    def run(self, user_goal, user_email=None, exam_date=None):
        print(f"\n{'='*50}\n🚀 StudyMate Agent: {user_goal}\n{'='*50}")
        results = {"goal": user_goal, "steps": []}

        # Step 1: Search
        resources = self._search_resources(user_goal)
        results["resources"] = resources
        results["steps"].append({"step":"search","status":"done","count":len(resources["resources"])})

        # Step 2: Plan
        days = 14
        if exam_date:
            try:
                delta = (datetime.datetime.strptime(exam_date,"%Y-%m-%d") - datetime.datetime.now()).days
                days  = max(3, delta)
            except Exception:
                days = 14

        plan = self._create_plan(user_goal, days=days)
        plan["exam_date"] = exam_date or "TBD"
        results["plan"]   = plan
        results["steps"].append({"step":"plan","status":"done","days":days})

        # Save plan to DB
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO study_plans (subject,exam_date,plan_json) VALUES(?,?,?)",
                  (user_goal, exam_date or "", json.dumps(plan)))
        conn.commit(); conn.close()

        # Step 3: Calendar
        if self.google_connected:
            slots = self.calendar.get_free_slots(min(7, days))
            events = []
            for i,(day_plan,slot) in enumerate(zip(plan["days"][:7], slots)):
                tasks_str = "; ".join(day_plan.get("tasks",[]))
                ev = self.calendar.create_study_event(
                    topic=user_goal, subtopic=day_plan.get("day",f"Day {i+1}"),
                    start_time=slot, duration_minutes=int(plan.get("hours_per_day",2)*60),
                    description=tasks_str
                )
                events.append(ev.get("id"))
            results["calendar_events"] = events
            results["steps"].append({"step":"calendar","status":"done","events":len(events)})
        else:
            results["calendar_events"] = []
            results["steps"].append({"step":"calendar","status":"skipped","reason":"no_credentials"})

        # Step 4: Email
        if self.google_connected and user_email:
            html = self.gmail.build_plan_email(plan)
            self.gmail.send_study_plan(
                to_email=user_email,
                subject=f"📚 StudyMate: Your {days}-Day Plan for {user_goal}",
                plan_html=html
            )
            results["email_sent"] = True
            results["steps"].append({"step":"email","status":"done","to":user_email})
        else:
            results["email_sent"] = False
            results["steps"].append({"step":"email","status":"skipped"})

        # Step 5: Track
        self._track(user_goal, "Plan Created", notes="Agent initialized")
        results["tracking_active"] = True
        results["steps"].append({"step":"track","status":"done"})

        print(f"✅ Agent complete — {days} days planned")
        return results

    def answer_question(self, question, context=""):
        if not self.model:
            return f"I'd help you study {context or question}! Set your GEMINI_API_KEY to enable AI-powered answers."
        prompt = f"""You are StudyMate AI, an expert study assistant for B.Tech CSE students in India.
Context/Subject: {context}
Student question: {question}

Give a helpful, specific, encouraging answer in 3-4 sentences max.
If it's a study question, include one concrete example or tip.
Sound like a knowledgeable senior student, not a textbook."""
        try:
            resp = self.model.generate_content(prompt)
            return resp.text
        except Exception as e:
            return f"Gemini error: {str(e)}. Please check your API key."

    def generate_quiz(self, topic, num_questions=5):
        if not self.model:
            return [{"q":f"Sample MCQ about {topic}","options":["A","B","C","D"],"answer":"A","explanation":"Set GEMINI_API_KEY for real questions"}]
        prompt = f"""Generate {num_questions} multiple choice questions about "{topic}" for B.Tech CSE exam.
Return ONLY a JSON array, no markdown:
[{{"q":"question text","options":["A. opt","B. opt","C. opt","D. opt"],"answer":"A","explanation":"why A is correct"}}]"""
        try:
            resp = self.model.generate_content(prompt)
            text = resp.text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"): text=text[4:]
            return json.loads(text.strip())
        except Exception as e:
            print(f"Quiz generation error: {e}")
            return [{"q":f"What is the time complexity of binary search?","options":["A. O(n)","B. O(log n)","C. O(n²)","D. O(1)"],"answer":"B","explanation":"Binary search halves the search space each step, giving O(log n)"}]
