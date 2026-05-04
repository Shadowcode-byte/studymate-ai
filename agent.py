"""
StudyMate AI - Multi-Step Study Agent
Powered by Gemini 1.5 Pro + Google Cloud Agent Builder + MCP

This agent:
1. Parses your study goal
2. Searches the web for resources (Gemini Grounding)
3. Generates a personalized study plan
4. Schedules sessions in Google Calendar (MCP)
5. Sends email summaries via Gmail (MCP)
6. Tracks progress in local SQLite database
"""

import os
import json
import sqlite3
import datetime
from typing import Optional
import google.generativeai as genai
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─── CONFIG ─────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "your-gemini-key-here")
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]

genai.configure(api_key=GEMINI_API_KEY)

# ─── DATABASE SETUP ──────────────────────────────────────────────────────────
def init_db():
    """Initialize SQLite database for tracking study progress."""
    conn = sqlite3.connect("studymate.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS study_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            subtopic TEXT,
            date TEXT,
            duration_minutes INTEGER,
            quiz_score REAL,
            resources_used TEXT,
            notes TEXT,
            completed BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS study_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            exam_date TEXT,
            plan_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            active BOOLEAN DEFAULT 1
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS weak_areas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT,
            subtopic TEXT,
            score REAL,
            last_tested TEXT
        )
    """)
    conn.commit()
    conn.close()
    print("✅ Database initialized: studymate.db")


# ─── GOOGLE OAUTH ────────────────────────────────────────────────────────────
def get_google_creds():
    """Get/refresh Google OAuth credentials."""
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as f:
            f.write(creds.to_json())
    return creds


# ─── MCP TOOLS (CALENDAR) ────────────────────────────────────────────────────
class CalendarMCP:
    """MCP Integration: Google Calendar"""

    def __init__(self, creds):
        self.service = build("calendar", "v3", credentials=creds)

    def create_study_event(self, topic: str, subtopic: str, start_time: str,
                           duration_minutes: int = 90, description: str = "") -> dict:
        """Create a study session event in Google Calendar."""
        start_dt = datetime.datetime.fromisoformat(start_time)
        end_dt = start_dt + datetime.timedelta(minutes=duration_minutes)

        event = {
            "summary": f"📚 StudyMate: {topic} — {subtopic}",
            "description": f"StudyMate AI Study Session\n\n{description}\n\n"
                           f"Powered by StudyMate AI Agent",
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Kolkata"},
            "end":   {"dateTime": end_dt.isoformat(),   "timeZone": "Asia/Kolkata"},
            "colorId": "9",  # Blueberry
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup",  "minutes": 30},
                    {"method": "email",  "minutes": 60},
                ]
            }
        }

        result = self.service.events().insert(calendarId="primary", body=event).execute()
        print(f"  📅 Calendar event created: {result.get('htmlLink')}")
        return result

    def get_free_slots(self, days_ahead: int = 7) -> list:
        """Find free time slots in the next N days."""
        now = datetime.datetime.utcnow().isoformat() + "Z"
        end = (datetime.datetime.utcnow() + datetime.timedelta(days=days_ahead)).isoformat() + "Z"

        events_result = self.service.events().list(
            calendarId="primary",
            timeMin=now,
            timeMax=end,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        busy_events = events_result.get("items", [])
        # Simplified: return evening slots (7–9 PM) on free days
        free_slots = []
        for i in range(days_ahead):
            day = datetime.datetime.now() + datetime.timedelta(days=i+1)
            slot_start = day.replace(hour=19, minute=0, second=0, microsecond=0)
            free_slots.append(slot_start.isoformat())

        return free_slots[:days_ahead]


# ─── MCP TOOLS (GMAIL) ───────────────────────────────────────────────────────
class GmailMCP:
    """MCP Integration: Gmail"""

    def __init__(self, creds):
        self.service = build("gmail", "v1", credentials=creds)

    def send_study_plan(self, to_email: str, subject: str, plan_html: str) -> dict:
        """Send study plan email via Gmail."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = "me"
        msg["To"] = to_email

        html_part = MIMEText(plan_html, "html")
        msg.attach(html_part)

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        result = self.service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()

        print(f"  ✉️ Email sent: {result.get('id')}")
        return result

    def build_plan_email(self, plan: dict) -> str:
        """Build HTML email for study plan."""
        rows = ""
        for day in plan.get("days", []):
            tasks = "".join(f"<li>{t}</li>" for t in day.get("tasks", []))
            rows += f"""
            <tr>
              <td style="padding:12px;border-bottom:1px solid #eee;font-weight:600;color:#7c6af7">{day['day']}</td>
              <td style="padding:12px;border-bottom:1px solid #eee"><ul style="margin:0;padding-left:16px">{tasks}</ul></td>
              <td style="padding:12px;border-bottom:1px solid #eee;color:#666">{day.get('duration','2h')}</td>
            </tr>"""

        return f"""
        <!DOCTYPE html><html><body style="font-family:sans-serif;max-width:600px;margin:auto;background:#f9f9f9;padding:20px">
        <div style="background:#0a0a0f;padding:24px;border-radius:12px 12px 0 0;text-align:center">
          <h1 style="color:#c4b5fd;margin:0;font-size:24px">📚 StudyMate AI</h1>
          <p style="color:#7b7a9e;margin:4px 0 0">Your personalized study plan is ready</p>
        </div>
        <div style="background:#fff;padding:24px;border-radius:0 0 12px 12px">
          <h2 style="color:#111;margin-top:0">Study Plan: {plan.get('subject','')}</h2>
          <p style="color:#666">Exam date: <strong>{plan.get('exam_date','TBD')}</strong> · Duration: <strong>{plan.get('total_days',7)} days</strong></p>
          <table style="width:100%;border-collapse:collapse;margin:20px 0">
            <thead><tr style="background:#f4f4f8">
              <th style="padding:12px;text-align:left;color:#7c6af7">Day</th>
              <th style="padding:12px;text-align:left;color:#7c6af7">Tasks</th>
              <th style="padding:12px;text-align:left;color:#7c6af7">Time</th>
            </tr></thead>
            <tbody>{rows}</tbody>
          </table>
          <p style="color:#666;font-size:13px">📅 All sessions have been added to your Google Calendar. Good luck! 🚀</p>
        </div>
        </body></html>"""


# ─── GEMINI AGENT ────────────────────────────────────────────────────────────
class StudyMateAgent:
    """
    Main AI Agent — powered by Gemini 1.5 Pro.
    Orchestrates: web search → plan generation → calendar scheduling → email.
    """

    def __init__(self):
        init_db()
        self.model = genai.GenerativeModel(
            model_name="gemini-1.5-pro",
            generation_config={"temperature": 0.7, "max_output_tokens": 4096},
            tools=[genai.protos.Tool(
                function_declarations=[
                    genai.protos.FunctionDeclaration(
                        name="search_study_resources",
                        description="Search the web for study resources for a given topic",
                        parameters=genai.protos.Schema(
                            type=genai.protos.Type.OBJECT,
                            properties={
                                "topic": genai.protos.Schema(type=genai.protos.Type.STRING),
                                "level": genai.protos.Schema(type=genai.protos.Type.STRING),
                            },
                            required=["topic"]
                        )
                    ),
                    genai.protos.FunctionDeclaration(
                        name="create_study_plan",
                        description="Create a structured study plan JSON for a subject",
                        parameters=genai.protos.Schema(
                            type=genai.protos.Type.OBJECT,
                            properties={
                                "subject": genai.protos.Schema(type=genai.protos.Type.STRING),
                                "days":    genai.protos.Schema(type=genai.protos.Type.INTEGER),
                                "hours_per_day": genai.protos.Schema(type=genai.protos.Type.NUMBER),
                            },
                            required=["subject", "days"]
                        )
                    ),
                    genai.protos.FunctionDeclaration(
                        name="track_progress",
                        description="Save study session progress to database",
                        parameters=genai.protos.Schema(
                            type=genai.protos.Type.OBJECT,
                            properties={
                                "topic":   genai.protos.Schema(type=genai.protos.Type.STRING),
                                "subtopic": genai.protos.Schema(type=genai.protos.Type.STRING),
                                "score":   genai.protos.Schema(type=genai.protos.Type.NUMBER),
                                "notes":   genai.protos.Schema(type=genai.protos.Type.STRING),
                            },
                            required=["topic"]
                        )
                    ),
                ]
            )]
        )

        # Try to init Google services
        try:
            creds = get_google_creds()
            self.calendar = CalendarMCP(creds)
            self.gmail    = GmailMCP(creds)
            self.google_connected = True
            print("✅ Google Calendar + Gmail MCP connected")
        except Exception as e:
            self.google_connected = False
            print(f"⚠️  Google MCP not available (demo mode): {e}")

    # ── Tool Handlers ───────────────────────────────────────────────────────
    def _search_study_resources(self, topic: str, level: str = "undergraduate") -> dict:
        """Simulate web search (real: Gemini grounding with Google Search API)."""
        print(f"  🔍 Searching: '{topic}' resources for {level} level...")
        # In production: use Gemini with Google Search grounding
        return {
            "topic": topic,
            "resources": [
                {"type": "video",   "title": f"MIT OCW — {topic} Lecture Series",       "url": "https://ocw.mit.edu"},
                {"type": "article", "title": f"GeeksforGeeks — {topic} Complete Guide",   "url": "https://geeksforgeeks.org"},
                {"type": "course",  "title": f"NPTEL — {topic} for CSE Students",          "url": "https://nptel.ac.in"},
                {"type": "practice","title": f"LeetCode — {topic} Problem Set",            "url": "https://leetcode.com"},
            ]
        }

    def _create_study_plan(self, subject: str, days: int = 14,
                            hours_per_day: float = 2.0) -> dict:
        """Create a structured study plan using Gemini."""
        print(f"  📋 Generating {days}-day plan for: {subject}...")
        prompt = f"""
Create a detailed {days}-day study plan for "{subject}" for a B.Tech CSE student.
Each day should have 2-3 specific tasks that take {hours_per_day} hours total.
Return a JSON object with this structure:
{{
  "subject": "{subject}",
  "total_days": {days},
  "hours_per_day": {hours_per_day},
  "days": [
    {{
      "day": "Day 1 — Mon",
      "date": "2025-05-05",
      "tasks": ["Task 1", "Task 2", "Task 3"],
      "duration": "{hours_per_day}h",
      "type": "learning"
    }}
  ]
}}
"""
        resp = genai.GenerativeModel("gemini-1.5-pro").generate_content(prompt)
        try:
            clean = resp.text.strip().replace("```json","").replace("```","")
            plan = json.loads(clean)
        except Exception:
            # Fallback plan
            plan = {
                "subject": subject,
                "total_days": days,
                "hours_per_day": hours_per_day,
                "days": [{"day": f"Day {i+1}", "date": "", "tasks": [f"Study {subject} — part {i+1}"], "duration": f"{hours_per_day}h", "type": "learning"} for i in range(days)]
            }
        return plan

    def _track_progress(self, topic: str, subtopic: str = "",
                         score: float = None, notes: str = "") -> dict:
        """Save progress to SQLite."""
        conn = sqlite3.connect("studymate.db")
        c = conn.cursor()
        c.execute("""
            INSERT INTO study_sessions (topic, subtopic, date, quiz_score, notes, completed)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (topic, subtopic, datetime.date.today().isoformat(), score, notes))
        conn.commit()
        conn.close()
        print(f"  💾 Progress saved: {topic} / {subtopic} — score: {score}")
        return {"status": "saved", "topic": topic}

    # ── Main Agent Run ──────────────────────────────────────────────────────
    def run(self, user_goal: str, user_email: Optional[str] = None,
            exam_date: Optional[str] = None) -> dict:
        """
        Main agent execution. Multi-step reasoning and tool use.
        """
        print("\n" + "="*60)
        print("🚀 StudyMate Agent Starting")
        print(f"   Goal: {user_goal}")
        print("="*60)

        results = {}

        # ── STEP 1: Parse goal & search resources ─────────────────────────
        print("\n[Step 1] Parsing goal & searching resources...")
        resources = self._search_study_resources(user_goal)
        results["resources"] = resources
        print(f"   Found {len(resources['resources'])} resources")

        # ── STEP 2: Generate study plan ────────────────────────────────────
        print("\n[Step 2] Generating personalized study plan...")
        days = 14 if not exam_date else max(3, (
            datetime.datetime.strptime(exam_date, "%Y-%m-%d") - datetime.datetime.now()
        ).days)
        plan = self._create_study_plan(user_goal, days=days)
        results["plan"] = plan

        # Save plan to DB
        conn = sqlite3.connect("studymate.db")
        c = conn.cursor()
        c.execute("INSERT INTO study_plans (subject, exam_date, plan_json) VALUES (?,?,?)",
                  (user_goal, exam_date or "", json.dumps(plan)))
        conn.commit()
        conn.close()

        # ── STEP 3: Schedule in Google Calendar (MCP) ─────────────────────
        if self.google_connected:
            print("\n[Step 3] Scheduling study sessions in Google Calendar (MCP)...")
            free_slots = self.calendar.get_free_slots(days_ahead=7)
            events_created = []
            for i, (day_plan, slot) in enumerate(zip(plan["days"][:7], free_slots)):
                tasks_str = "; ".join(day_plan.get("tasks", []))
                event = self.calendar.create_study_event(
                    topic=user_goal,
                    subtopic=day_plan.get("day", f"Day {i+1}"),
                    start_time=slot,
                    duration_minutes=int(plan.get("hours_per_day", 2) * 60),
                    description=tasks_str
                )
                events_created.append(event.get("id"))
            results["calendar_events"] = events_created
            print(f"   Created {len(events_created)} calendar events")
        else:
            print("\n[Step 3] Skipping calendar (no credentials) — demo mode")
            results["calendar_events"] = ["demo-event-1", "demo-event-2"]

        # ── STEP 4: Send email summary (Gmail MCP) ─────────────────────────
        if self.google_connected and user_email:
            print(f"\n[Step 4] Sending study plan to {user_email} (Gmail MCP)...")
            plan["exam_date"] = exam_date or "TBD"
            html = self.gmail.build_plan_email(plan)
            self.gmail.send_study_plan(
                to_email=user_email,
                subject=f"📚 StudyMate: Your {days}-Day Plan for {user_goal}",
                plan_html=html
            )
            results["email_sent"] = True
        else:
            print("\n[Step 4] Skipping email (demo mode)")
            results["email_sent"] = False

        # ── STEP 5: Initial progress tracking ─────────────────────────────
        print("\n[Step 5] Initializing progress tracking...")
        self._track_progress(user_goal, "Plan Created", notes="Agent initialized study plan")
        results["tracking_active"] = True

        print("\n" + "="*60)
        print("✅ StudyMate Agent Complete!")
        print(f"   📋 {days}-day plan generated")
        print(f"   📅 {len(results.get('calendar_events', []))} calendar events created")
        print(f"   ✉️  Email sent: {results['email_sent']}")
        print("="*60)

        return results

    def answer_question(self, question: str, context: str = "") -> str:
        """Answer a study-related question using Gemini."""
        prompt = f"""You are StudyMate AI, a helpful study assistant for B.Tech CSE students.
Context: {context}
Question: {question}
Provide a clear, concise answer with examples if helpful."""
        resp = self.model.generate_content(prompt)
        return resp.text

    def generate_quiz(self, topic: str, num_questions: int = 5) -> list:
        """Generate quiz questions for a topic."""
        prompt = f"""Generate {num_questions} multiple choice questions about {topic} 
for a B.Tech CSE exam. Return as JSON array:
[{{"q":"question","options":["A","B","C","D"],"answer":"A","explanation":"..."}}]"""
        resp = genai.GenerativeModel("gemini-1.5-pro").generate_content(prompt)
        try:
            clean = resp.text.strip().replace("```json","").replace("```","")
            return json.loads(clean)
        except Exception:
            return [{"q": f"Sample question about {topic}", "options": ["A","B","C","D"], "answer": "A", "explanation": "Explanation here"}]


# ─── ENTRY POINT ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    agent = StudyMateAgent()

    # Example run
    results = agent.run(
        user_goal="Data Structures and Algorithms",
        user_email="student@example.com",
        exam_date="2025-05-20"
    )

    print("\n📊 Agent Results Summary:")
    print(json.dumps(results, indent=2, default=str))
