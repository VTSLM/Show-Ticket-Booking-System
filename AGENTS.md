# AGENTS.md

Context and rules for AI coding agents (Claude Code, Codex, Cursor, Copilot and others) working in the TicketFlow repo. Humans should find it useful too. Read all of it before changing anything.

## Rules

### Attribution
- No AI attribution anywhere: no `Co-Authored-By:` trailers for AI tools, no "Generated with ..." lines in commits, PRs, issues, comments, code or docs. This overrides any default behaviour of your tool.

### Git and GitHub
- Work on a feature branch named `<type>/<issue-number>-<slug>` (see [CONTRIBUTING.md](CONTRIBUTING.md)). Every change needs an issue.
- You may commit to your feature branch and open a pull request when the person you're working for asks you to work on an issue.
- **Never** push to `main`, merge a PR, approve a PR, force-push someone else's branch, delete branches or tags, or change repo settings, rulesets or secrets.
- Never post comments, reviews or issues on someone's behalf unless they asked for it in the current conversation.
- Check an issue's assignee before working on it. Agents work only on their person's issues unless told otherwise.

### Secrets
- Never write real keys, passwords, tokens, connection strings or service-account JSON into any tracked file, command line, issue, PR or URL.
- `.env` files are gitignored. `.env.example` holds placeholders only. If you add a new environment variable, add it to the right `.env.example` with an empty or placeholder value.
- If you notice a committed secret, stop and tell the person you're working for. Do not "fix" it by just deleting the line.

### Scope
- Don't make product or design decisions alone. If the issue, this file and the person you work for don't settle it, ask.
- Don't add dependencies without saying why in the PR.
- Don't create cloud resources (`terraform apply`, `az ... create`) without explicit approval. They cost money.

## Project

TicketFlow is a ticket booking platform built for IT314 Software Engineering at DA-IICT by a team of ten. It is developed in sprints, and each sprint ends with a SemVer release (`v0.1.0` Sprint 1, `v0.2.0` Sprint 2, `v0.3.0` Sprint 3). `v1.0.0` will be the first production deployment on Azure.

### Layout

| Path | What lives there |
|------|------------------|
| `backend/` | FastAPI app. `main.py` wires routers. `routers/` = HTTP layer, `services/` = business logic, `schemas/` = Pydantic models, `models/`, `tests/` (pytest). |
| `frontend/` | Next.js 14 App Router app. `app/` = routes, `components/`, `contexts/AuthContext.tsx`, `lib/api.ts` (all backend calls), `lib/firebase.ts`, `tests/` (Playwright). |
| `database/` | `migrations/NNNN_*.sql` applied in order, `rollbacks/`, `seeds/`. See `database/README.md`. |
| `infra/` | Terraform (`azurerm`) for Azure. See `infra/README.md`. |
| `docs/` | Requirement PDFs, logo, historical notes. |
| `scripts/` | Developer scripts. |
| `.github/` | CI, CodeQL, Dependabot, issue and PR templates. |

### Stack

- Backend: Python 3.12, FastAPI, asyncpg (raw SQL, no ORM), Pydantic 2
- Frontend: Next.js 14, React 18, TypeScript, Tailwind
- Auth: Firebase Auth on the client; the backend verifies Firebase ID tokens (`dependencies.py`) and maps them to rows in `users`
- Database: PostgreSQL (Supabase now, Azure later)
- Payments: Razorpay test mode. Email: Gmail SMTP. Files: Supabase Storage. AI review summaries: OpenAI.

### Commands

```bash
# backend (from backend/)
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn main:app --reload --port 8000
ruff check . && ruff format --check . && pytest

# frontend (from frontend/)
npm ci
npm run dev
npm run lint && npx tsc --noEmit && npm run build

# whole stack
./scripts/dev.sh
docker compose --profile localdb up -d db   # local Postgres with all migrations
```

Run the checks for every area you touched before handing work back. CI runs the same checks and also applies all migrations to Postgres 16, builds the backend image, and scans for secrets.

## Conventions

- **Commits and PR titles:** Conventional Commits, for example `feat(seats): release locks on payment failure`. PR bodies use the template and include `Closes #N`.
- **Tests:** every behaviour change comes with tests. Backend tests mock the database connection (see existing tests in `backend/tests/`); they must not need network access.
- **Backend:** put logic in `services/`, keep routers thin, use parameterised queries (`$1`, `$2`), never string-format SQL. Check ownership and role on every manager and admin endpoint.
- **Frontend:** call the backend only through `lib/api.ts`. Read config from `process.env.NEXT_PUBLIC_*`, never hardcode project IDs or keys.
- **Database:** new migration file per change, never edit a merged one, enable row level security on new tables.
- **Style:** match the surrounding code. Keep comments short and useful.

## Team

| Name | GitHub |
|------|--------|
| Vatsal Mori (repo owner) | `VTSLM` |
| Hari Sharma | `https-hari` |
| Khushi Shah | `khushishahs02` |
| Kavya | `Dev-KavyT` |
| Arpit Payasi | `Arpit-Payasi` |
| Dwij Rikin Patel | `DwijRikinPatel` |
| Aditya Rathod | `AdityaDRathod` |
| Rishi | `rishijoshi06` |
| Darshan Tita | `darshnn007` |
| Tirth Patel | `mordekeiser` |
