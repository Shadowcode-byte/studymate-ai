# 📚 StudyMate AI — Intelligent Study Agent

> *An AI agent that doesn't just answer questions — it plans, schedules, tracks, and emails your entire study journey.*

[![License: MIT](https://img.shields.io/badge/License-MIT-violet.svg)](https://opensource.org/licenses/MIT)
[![Gemini 1.5 Pro](https://img.shields.io/badge/Gemini-1.5%20Pro-blue)](https://ai.google.dev)
[![Google Cloud](https://img.shields.io/badge/Google%20Cloud-Agent%20Builder-red)](https://cloud.google.com)
[![MCP Protocol](https://img.shields.io/badge/MCP-Google%20Calendar%20%2B%20Gmail-green)](https://developers.google.com)

**Built for:** Building Agents for Real-World Challenges Hackathon  
**Category:** Personal Life / Education  
**Tech Stack:** Gemini 1.5 Pro · Google Cloud Agent Builder · Google Calendar MCP · Gmail MCP · FastAPI · SQLite

---

## 🎯 What It Does

StudyMate AI is a multi-step agent that handles your entire study workflow:

1. **🔍 Parses your study goal** — Understands topic, timeframe, and skill level
2. **🌐 Searches for resources** — Uses Gemini grounding with Google Search to find the best materials
3. **📋 Builds a study plan** — Generates a personalized day-by-day schedule
4. **📅 Schedules via Calendar MCP** — Automatically adds sessions to Google Calendar with reminders
5. **✉️ Emails via Gmail MCP** — Sends a formatted study plan to your inbox
6. **💾 Tracks progress** — Stores quiz scores and session data in a local SQLite database
7. **🎯 Adapts the plan** — Adjusts based on your progress and weak areas

---

## 🏗 Architecture

```
User Input
    │
    ▼
StudyMate Agent (Gemini 1.5 Pro)
    │
    ├── 🔍 Web Search Tool (Gemini Grounding + Google Search)
    ├── 📋 Plan Generator (Gemini Structured Output)
    ├── 📅 Google Calendar MCP  ← Partner Integration
    ├── ✉️  Gmail MCP            ← Partner Integration  
    └── 💾 SQLite Progress DB
    │
    ▼
FastAPI REST Server → HTML/JS Frontend
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Google Cloud project with Calendar + Gmail APIs enabled
- Gemini API key

### Installation

```bash
git clone https://github.com/your-username/studymate-ai
cd studymate-ai

# Install dependencies
pip install -r requirements.txt

# Set your Gemini API key
export GEMINI_API_KEY="your-key-here"

# Add Google OAuth credentials
# Download credentials.json from Google Cloud Console
# Place it in the backend/ folder

# Run the backend
cd backend
python server.py

# Open frontend
open frontend/index.html
# OR visit http://localhost:8080/static/index.html
```

### Running the Agent Directly

```python
from backend.agent import StudyMateAgent

agent = StudyMateAgent()
results = agent.run(
    user_goal="Data Structures and Algorithms",
    user_email="you@example.com",
    exam_date="2025-05-20"
)
print(results)
```

---

## 🔌 MCP Integrations

### Google Calendar MCP
- Creates study session events with timing, descriptions, and reminders
- Reads your calendar to find free slots before scheduling
- Sets 30-minute popup + 60-minute email reminders automatically

### Gmail MCP
- Sends beautifully formatted HTML study plan emails
- Weekly progress summary emails
- Exam reminder emails 3 days and 1 day before

---

## 📁 Project Structure

```
studymate-ai/
├── frontend/
│   └── index.html          # Interactive UI with live agent demo
├── backend/
│   ├── agent.py            # Core agent with Gemini + MCP tools
│   ├── server.py           # FastAPI REST API
│   └── studymate.db        # SQLite database (auto-created)
├── docs/
│   └── synopsis.md         # Project synopsis
├── credentials.json        # Google OAuth (you provide this)
├── requirements.txt
└── README.md
```

---

## 🔑 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/study` | Run full agent (plan + calendar + email) |
| POST | `/api/ask` | Ask a study question |
| POST | `/api/quiz` | Generate quiz questions |
| POST | `/api/progress` | Save session progress |
| GET  | `/api/progress/{topic}` | Get topic progress |
| GET  | `/api/stats` | Overall study statistics |
| GET  | `/api/plans` | List active study plans |

---

## 🧠 How the Agent Reasons

The agent uses Gemini's function calling to autonomously decide which tools to invoke:

```
Goal: "Help me study Operating Systems for exam in 10 days"
  └─ Agent reasons: "User has 10 days. Should search OS resources,
                    create 10-day plan, schedule 2h/day sessions,
                    send plan email, and set exam reminder."
  └─ Tool calls:
      1. search_study_resources("Operating Systems", "undergraduate")
      2. create_study_plan("OS", days=10, hours=2)
      3. calendar_mcp.create_events(10 sessions + 1 mock exam)
      4. gmail_mcp.send_plan(to=user_email)
      5. track_progress("OS", "Plan Created")
```

---

## 📊 Judging Criteria — How We Score

| Criterion | Our Approach |
|-----------|-------------|
| **Technical Implementation** | Gemini function calling, real MCP protocol, REST API, SQLite |
| **Design** | Clean dark-themed UI, interactive agent steps panel, live chat |
| **Potential Impact** | Helps millions of students in India prepare for exams efficiently |
| **Quality of Idea** | Unique: study agent vs chatbot — it *acts*, not just *talks* |

---

## 👨‍💻 About

Built by a 1st-year B.Tech CSE student who got tired of spending more time organizing study materials than actually studying.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) file.

```
MIT License
Copyright (c) 2026 StudyMate AI
Permission is hereby granted, free of charge, to any person obtaining a copy...
```
