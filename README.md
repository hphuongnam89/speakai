# SpeakLab — local MVC demo

## Requires

- macOS/Linux, Python 3.13, Docker Desktop + Compose.
- Local Ollama and the Whisper model are used by the background worker for advisory practice scoring; model inference is never run by the web request.

## Run the Compose demo

```sh
cp .env.example .env
# Replace the demo password and secret in .env; never use these demo values outside a local machine.
docker compose up --build
```

Open `http://127.0.0.1:18080/`. Compose starts the Django development server, PostgreSQL, Redis, and one Celery worker. The worker runs Whisper transcription and Ollama scoring in the background. Ollama remains native on the Mac and is reached from the worker through `host.docker.internal`.

To create synthetic demo accounts, first replace all three `DEMO_*_PASSWORD` values in `.env`, then run:

```sh
docker compose exec web python manage.py seed_demo
```

The command creates `demo-student`, `demo-teacher`, and `demo-admin`, their role groups, and a synthetic GT1 course enrollment/teacher assignment so the local practice demo is reachable. It creates no academic questions or official exams. It is safe to repeat and refuses placeholder passwords or conflicting accounts. Passwords are hashed by Django and never printed. The non-staff `demo-admin` can manage `demo-*` accounts from the in-app **Tài khoản demo** page; a separate superuser is still required for Django Admin.

Stop containers without deleting the database volume:

```sh
docker compose down
```

## Run Django directly on macOS

```sh
cp .env.example .env
# Edit .env with local values; do not commit it.
docker compose up -d db
python3.13 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
set -a; source .env; set +a
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo
python manage.py check
python manage.py runserver 127.0.0.1:18080
```

Open `http://127.0.0.1:18080/`. Use the superuser only for Django Admin. Demo accounts are created only when the explicit seed command is run.

Troubleshooting: if a port is occupied, change `WEB_PORT` or `HOST_DB_PORT` in `.env`; never stop another project's container to free a port. Inspect this project with `docker compose ps` and `docker compose logs --tail=50 web worker`. PostgreSQL applies `POSTGRES_PASSWORD` only when its data volume is initialized. If an existing volume reports password authentication failure, preserve the volume and restore its prior local credential or deliberately update the database role; do not use `docker compose down -v` as a shortcut.

## Current boundary

Implemented: MVC project, public welcome page, Django login/logout, server-side student/teacher/admin dashboard gates, idempotent synthetic demo account/group seeding, liveness/readiness endpoints, Compose web/PostgreSQL/Redis/Celery worker, JSON console logs, CSP/security headers and smoke tests.

P2-01/P2-02: empty course/enrollment/question schema plus teacher-course assignments, question-bank CRUD/preview, review lifecycle, provenance fields and version history. Teachers are scoped to active assigned courses; admins configure courses, assignments and tags in Django Admin. Versions are immutable after submission, revisions copy into a new draft, and only approved versions are eligible for later exam selection. Course bands may overlap A1–C1. No questions or rubric content are seeded.

P2-03: rubric drafts are scoped to assigned courses and identify a section, task type, flexible CEFR range and source. Criteria can have optional max points and per-level descriptors; no weights, grade bands or academic descriptors are prefilled. Publish requires a source, criteria and descriptor coverage for each declared level. Published versions and their child criteria are locked; revisions create a new draft and append before/after audit snapshots.

P2-05 demo: students can request original practice prompts from local Ollama by course, CEFR level, topic, number of questions and per-question response time; record, review and submit audio. Audio is stored in the local Compose media volume. The demo teacher/admin can review attempts and listen to audio within their access scope. AI-generated prompts are clearly practice-only, not official exam questions. Submitted practice attempts are queued for local Whisper transcription and Ollama AI draft scoring; a teacher/admin must review the audio and publish the final score and feedback.

Not implemented yet: official exam attempts, rubric-weighted official grading, final grade appeals and student-facing transcript editing. P2-04 remains a separate deterministic sample preview from approved question versions. AI practice scoring is advisory only and must not be described as an official grade. No real student data/audio belongs in this repo.

## Design and framework references

- Django authentication: https://docs.djangoproject.com/en/5.2/topics/auth/default/
- Django management commands: https://docs.djangoproject.com/en/5.2/howto/custom-management-commands/
- Django CSRF: https://docs.djangoproject.com/en/5.2/howto/csrf/
- Django ModelForms: https://docs.djangoproject.com/en/5.2/topics/forms/modelforms/
- Django transactions: https://docs.djangoproject.com/en/5.2/topics/db/transactions/
- Django template autoescaping: https://docs.djangoproject.com/en/5.2/ref/templates/language/#automatic-html-escaping
- Django deployment/security checklist: https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/
- Project baseline and stack decision: `../records/ENVIRONMENT-BASELINE.md`, `../records/ADR-001-mvc-stack.md`.
## P2-02 — Question bank workflow

- Teacher/admin question-bank pages support draft creation, preview, draft editing, review requests, approval/change requests, retirement, and immutable revision history.
- Teachers only see courses with an active `CourseTeachingAssignment`; staff configure courses, teacher assignments, and optional tags in Django Admin.
- New versions must start as drafts. Submitted/approved content and tags are locked; edits to an approved question create the next draft version. Review records are append-only, and authors cannot review their own version.
- Form fields are explicitly allowlisted; course scope, role, status transitions, and all mutations are checked server-side. State-changing actions require POST/CSRF.
- No academic questions or rubric content are seeded. Teachers must cite and verify the relevant course source before submitting a question.

Validation: `python manage.py check`, `python manage.py makemigrations --check --dry-run`, and `python manage.py test core` (run using the project's Docker image/Compose environment).

## P2-04 — Exam blueprint and sample preview

- Staff create versioned blueprints per course, recording the verified paper/answer source; each slot sets section, task type, question count, CEFR range, language, preparation/response seconds, and a published matching rubric version.
- Publication validates source, slots, course/section/task compatibility, and rubric descriptor coverage. Published versions and generated sample snapshots are immutable; edits require a new revision and append-only audit events.
- A teacher/admin chooses one topic for the entire sample. The sampler only uses approved, sourced question versions matching the slot configuration, stores the seed, candidate pool, exclusions, selected question/rubric snapshots, and can reproduce a sample using the same seed.
- If any slot lacks enough unique eligible questions, generation fails with per-slot shortage details. It never silently broadens topic/level/task filters. Sample previews are not published exams.
- No question bank, rubric, question count, timing, or grade threshold is prefilled with invented academic content. GT2–GT4 remain unconfigured until source material is supplied.

Validation: P2-04 migration applies and rolls back; `makemigrations --check --dry-run` reports no changes; focused and complete core suites run against an isolated PostgreSQL Compose project.
