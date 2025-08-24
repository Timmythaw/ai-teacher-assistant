# AI Teacher Assistant

An AI-powered assistant for educators to turn course materials into structured lesson plans and assessments, save results to a database, create Google Forms, email students, and review responses—all from a simple web UI.

This repository contains a Flask web app, AI “agents” for domain tasks (assessment, lesson plan, email, timetable), integrations for Google APIs, and a Tailwind-based UI.

## Highlights

- Assessments from PDFs
  - Upload a course/lecture PDF to generate MCQs/short answers with answers and optional rubric
  - Preview as Markdown, save to DB, and create a Google Form
- Lesson plan generation
  - Upload a course outline PDF and generate a structured, weekly lesson plan with Markdown preview
- Email students (single or batch)
  - Draft or send emails (Gmail) and optionally include Google Form links
- Batches and students
  - Create batches and upload students via CSV
- Google Forms responses
  - Fetch responses and basic analytics for assessments delivered via Google Forms

> Note: An Orchestrator and chat UX are included as a preview, but they’re optional and not required for normal usage. See “Preview: Orchestrator and Chat” at the end.

---

## Quick start

### Prerequisites
- Python 3.12+
- A Supabase project (for persistence)
- Google Cloud project (Forms API and Gmail)
- OAuth credentials: `credentials.json` in the project root

### Install
```bash
# Clone
git clone https://github.com/Timmythaw/ai-teacher-assistant.git
cd ai-teacher-assistant

# Install deps (choose one)
pip install -r requirements.txt
# or
uv pip install -r requirements.txt
```

### Configure environment
Set these variables (for local dev you can export them in your shell):

```bash
export SUPABASE_URL="https://<your-project>.supabase.co"
export SUPABASE_KEY="<service-role-or-anon-key>"

# Optional
export PORT=5000                         # Flask port
export MAX_CONTENT_LENGTH_MB=20          # Upload limit (MB)
export UPLOAD_DIR="uploads"             # Where files are stored
```

### Google setup (one time)
1) Enable APIs in Google Cloud: Gmail API and Google Forms API

2) Create OAuth Client credentials and download `credentials.json`

3) First run will prompt a browser auth; it creates `token.json` (and sometimes `token.pickle`) in the repo.

### Run the app
```bash
python app.py
# or
uv run python app.py
```
Open http://localhost:${PORT:-5000}

---

## UI overview

- Dashboard (home)
  - Cards to jump to: Batches, Send Email, Generate Lesson Plan, Lesson Plans, Generate Assessment, Assessments
- Batches
  - Create a batch and upload a CSV of students (columns: `name`, `email`)
- Generate Lesson Plan
  - Upload a course outline PDF and generate a plan; preview Markdown and save
- Lesson Plans (list)
  - Browse saved plans; open and preview Markdown
- Generate Assessment
  - Upload a PDF and configure type, difficulty, and count; preview Markdown and save
- Assessments (list + detail)
  - Browse saved assessments; open detail to create a Google Form; view Form URL
- Send Email
  - Draft or send emails; supports batch sending to students in a batch

Optional/Preview
- Chat (Orchestrator preview). A stub template exists (`templates/chat.html`), but no default route is wired; enable at your discretion.

---

## Data model (Supabase)

The app expects these tables (simplified view):

- `batches`: id (uuid), name (text), created_at (timestamp)
- `students`: id/uuid, batch_id (uuid, FK), name (text), email (text)
- `lesson_plans`: id (uuid), pdf_path (text), options (jsonb), result (jsonb), created_at
- `assessments`: id (uuid), pdf_path (text), options (jsonb), result (jsonb), google_form (jsonb), created_at

The UI will still work with empty tables; create them in Supabase before use.

---

## Key endpoints

Assessment
- POST `/generate-assessment-test` (multipart)
  - Form fields: `pdf` (file), `type` (MCQ|Essay…), `difficulty` (Easy|Medium|Hard), `count` (int), `rubric` (checkbox)
  - Returns JSON with `_markdown` containing a Markdown preview
- POST `/api/assessments` (json)
  - Body: `{ original_filename?, pdf_path?, options?, result, google_form? }`
  - Saves to Supabase; returns `id`
- POST `/api/assessments/<uuid>/create-form`
  - Creates a Google Form from the saved assessment; persists `google_form` (formId/formUrl)
- GET `/assessments` (page) and `/assessments/<uuid>` (detail page)

Lesson plans
- POST `/generate-lesson-plan` (multipart)
  - Form fields: `course_outline` (file)
  - Returns JSON with `_markdown` for preview
- GET `/lesson-plans` (page)
- POST `/api/lesson-plans` (json)

Email
- GET `/email` (page)
- POST `/api/email/send-batch` (json)
  - `{ batch_id, subject, notes, tone?, action? (send|draft), assessment_id? }`
  - If `assessment_id` has a Google Form, we append the link to notes

Batch & students
- GET `/batches` (page)
- POST `/add-new-batch` (multipart)
  - Form fields: `batch_name` (text), `students_csv` (file with columns name,email)
  - Inserts batch + students
- GET `/api/batches` and `/api/batches/<id>/students`

Utilities
- None beyond the endpoints above. File uploads are handled inline by POST routes that accept `multipart/form-data` (e.g., `/generate-assessment-test`, `/generate-lesson-plan`, `/add-new-batch`).

---

## Agents and rendering

- AssessmentAgent
  - `generate_assessment(pdf_path, spec)` → dict: `{ title?, difficulty?, type?, questions: [...], rubric? }`
  - Markdown via `core/md_render.py: render_assessment_markdown`
- LessonPlanAgent
  - `generate_plan({ course_outline: pdf_path }, weeks, class_size, sections_per_week)`
  - Markdown via `core/md_render.py: render_lesson_plan_markdown`
- EmailAgent
  - Sends or drafts via Gmail; see `/api/email/send-batch`
- TimetableAgent
  - Suggests schedules from a plan (optional)

---

## Development

Project layout (selected):
```
app.py
agents/
  assessment_agent.py
  lesson_plan_agent.py
  timetable_agent.py
  email_agent.py
  orchestra.py
core/
  md_render.py
  google_client.py
  config.py
  pdf_tool.py
integrations/
  form_creator.py
  form_response.py
  gmail_tool.py
  calendar_tool.py
templates/
  base.html
  index.html
  email.html
  lesson_plans_list.html
  assessments_list.html
  assessment_detail.html
  course_batches.html
  lesson_generator.html
  assessments.html
  chat.html        # preview
  dashboard.html   # preview
uploads/
```

Testing & notebooks
- `test_forms.py`, `test/google_calendar_test.py`
- `notebooks/` include integration and agent experiments

---

## Troubleshooting

- Gmail/Google auth fails
  - Ensure `credentials.json` exists at project root and you completed the OAuth flow
  - Delete `token.json` if scopes changed and re-auth
- Google Forms creation: 403/permission errors
  - Confirm Forms API is enabled and OAuth client has access
- Supabase insert/read failures
  - Verify `SUPABASE_URL`/`SUPABASE_KEY` and table schemas exist
- Large files rejected
  - Increase `MAX_CONTENT_LENGTH_MB` or split the source document

---

## Preview: Orchestrator and Chat (optional)

This codebase includes early work toward an Orchestrator and a chat-style UI (see `agents/orchestra.py` and `templates/chat.html`). They can be adapted to:
- Interpret prompts (e.g., “Generate assessment from my lecture PDF”)
- Route to the correct agent and request missing files
- Render results in Markdown inline in chat
- Offer save-to-DB and download actions

These features are provided as a preview and are not required for normal usage. By default, a `/chat` route is not registered—wire one up if you want to explore the chat flow locally.

---

## License

MIT License. See `LICENSE`.
