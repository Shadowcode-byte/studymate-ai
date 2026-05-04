# StudyMate AI — Project Synopsis
### Hackathon: Building Agents for Real-World Challenges

---

## 1. Problem Statement

Every college student faces the same struggle: you have an exam coming up, you know *what* to study — but you have no idea *how* to organize it. You spend hours scrolling resources, manually adding events to your calendar, and still forget to revise. No existing tool connects all these steps automatically.

**StudyMate AI solves this by acting as your personal study manager — an agent that does all of that for you.**

---

## 2. Solution Overview

StudyMate AI is a multi-step AI agent built on Gemini 1.5 Pro and Google Cloud Agent Builder. It takes a single natural-language goal ("I have a Data Structures exam in 2 weeks") and autonomously:

1. **Searches the web** for the best study resources (using Gemini grounding with Google Search)
2. **Generates a personalized day-by-day plan** tailored to the student's timeline
3. **Schedules study sessions** in Google Calendar via MCP — with reminders
4. **Sends an email** via Gmail MCP with the complete plan in a formatted HTML email
5. **Tracks progress** in a local SQLite database and generates adaptive quiz questions

The key differentiator: this is **not a chatbot**. It uses tool calls and real-world integrations to *take action*, not just provide information.

---

## 3. Technical Architecture

```
User (Browser UI)
       │  HTTP
       ▼
FastAPI REST Server (Python)
       │
       ▼
StudyMate Agent (Gemini 1.5 Pro)
  ├── Tool: search_study_resources()     → Gemini grounding + Google Search API
  ├── Tool: create_study_plan()          → Gemini structured output (JSON)
  ├── MCP:  Google Calendar Integration → Creates calendar events, reads free slots
  ├── MCP:  Gmail Integration           → Sends formatted HTML study plan email
  └── Tool: track_progress()            → SQLite local database (studymate.db)
```

**Key Technologies:**
- **AI Model:** Gemini 1.5 Pro (via `google-generativeai` SDK)
- **Agent Framework:** Google Cloud Agent Builder
- **Partner MCP Servers:** Google Calendar MCP, Gmail MCP
- **Backend:** Python + FastAPI
- **Database:** SQLite (local, persistent)
- **Frontend:** Vanilla HTML/CSS/JS — dark-themed, responsive UI
- **Auth:** Google OAuth 2.0 with token refresh

---

## 4. MCP Partner Integration (Core Requirement)

### Google Calendar MCP
- **What it does:** Creates study block events with titles like "📚 StudyMate: DSA — Linked Lists"
- **Smart scheduling:** First reads the user's existing calendar to find free slots (7–9 PM default)
- **Reminders:** Sets 30-minute popup + 60-minute email reminders for each session
- **Exam day:** Creates a special "Mock Exam" event 2 days before the actual exam

### Gmail MCP
- **Study plan email:** Sends a beautifully formatted HTML email with the full week-by-week plan
- **Weekly summaries:** After each week, emails the student their quiz scores and progress
- **Exam reminders:** Sends motivational reminder emails 3 days and 1 day before the exam

---

## 5. Multi-Step Agent Reasoning

The agent doesn't just call APIs blindly. It uses Gemini's reasoning to:

**Input:** "Help me prepare for my OS exam in 10 days"

**Agent's internal reasoning:**
```
→ Parse: Subject=OS, Days=10, Level=B.Tech
→ Search: Find OS study resources for undergrad CSE
→ Plan: 10 days × 2h = 20h total, distribute across: 
         Processes(2d) → Memory(2d) → File System(2d) → 
         Scheduling(2d) → Mock Exam(1d) → Revision(1d)
→ Schedule: Create 10 events in Google Calendar
→ Notify: Email formatted plan to student
→ Track: Initialize progress database for OS
```

This is genuine multi-step planning and execution, not just a Q&A.

---

## 6. Target Users & Impact

**Primary:** ~4 million B.Tech students in India (plus millions globally)

**Why this matters:**
- Average student spends 45 min/day just organizing study materials
- 67% of students report "not knowing where to start" before exams
- StudyMate AI compresses the planning overhead to under 60 seconds

**Expansion potential:**
- Integration with university LMS systems (Moodle, Google Classroom)
- Group study coordination via Workspace MCP
- WhatsApp/Telegram reminders via messaging MCPs
- Voice interface for hands-free study planning

---

## 7. Design Decisions

- **Dark theme:** Easier on eyes during late-night study sessions
- **Agent step visualization:** Shows the user what the agent is doing in real time — builds trust and transparency
- **Live chat panel:** Allows follow-up questions mid-session
- **Weekly calendar view:** Visual plan is easier to follow than bullet lists
- **Mono font for tool calls:** Distinguishes agent actions from human conversation

---

## 8. Challenges & Solutions

| Challenge | Solution |
|-----------|----------|
| Gemini sometimes returns non-JSON | Added try/catch with sensible fallback plans |
| Google Calendar OAuth complexity | Wrapped in `get_google_creds()` with token refresh |
| Avoiding calendar conflicts | Agent reads existing events before scheduling |
| Making a "study plan" actually personalized | Gemini prompt includes level, available hours, days |

---

## 9. What Makes It Unique

Most "study apps" are either flashcard tools (passive) or AI chatbots (reactive). StudyMate AI is **proactive and agentic** — it does the work without being asked step by step. The MCP integrations turn it from a planner into an *executor*.

---

## 10. Demo Flow (for judges)

1. Open the web UI
2. Type: "I have a Data Structures exam in 14 days, help me prepare"
3. Watch the agent step panel show each action in real time:
   - ✅ Parse Goal → ✅ Web Search → ⚡ Build Plan → ⚡ Calendar → ⚡ Email
4. See the 14-day study plan appear in the weekly view
5. Check your Google Calendar — 14 events have been automatically created
6. Check your email — a formatted study plan has been sent

**Total time: under 30 seconds.**

---

## 11. Open Source

Repository: `https://github.com/[username]/studymate-ai`  
License: **MIT** (visible in README and LICENSE file)

---

*StudyMate AI — Built with Gemini, powered by curiosity, made for every student pulling an all-nighter the night before exams.*
