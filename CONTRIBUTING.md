# Contributing to TicketFlow

This is how the team works on this repo. It applies to everyone, including AI coding tools (see [AGENTS.md](AGENTS.md)).

## The short version

1. **Open or pick an issue.** No code without an issue.
2. **Assign yourself** and move the card to *In Progress* on the project board.
3. **Branch** from an up-to-date `main`: `<type>/<issue-number>-<short-slug>`.
4. **Commit** with [Conventional Commits](https://www.conventionalcommits.org).
5. **Open a PR** that says `Closes #<issue>`, fill in the template, request a reviewer.
6. **Get one approval** and green CI, resolve every conversation.
7. **Squash and merge.** The branch is deleted automatically.

`main` is protected. Nobody pushes to it directly, admins included.

## 1. Issues

Every change, however small, starts with an issue. Use the templates (Bug, Feature, Task).

- **Title:** short and specific. "Seat lock not released after payment failure", not "Seat bug".
- **Labels:** one `type:` label and at least one `area:` label.
  - `type: bug | feature | docs | chore | test | security | infra`
  - `area: backend | frontend | database | infra | ci | docs`
- **Milestone:** the current sprint, for example `Sprint 3 (v0.3.0)`.
- **Assignee:** whoever is doing the work. Check the assignee before starting. If someone else has it, ask on the issue first.
- **Project:** add it to the TicketFlow board. Columns are *Todo*, *In Progress* and *Done*.

Use issue comments for discussion and decisions, not private chats, so the reasoning stays with the work. Do not paste secrets, real customer data or `.env` contents into issues.

Security problems go through [SECURITY.md](SECURITY.md), not public issues.

## 2. Branches

Cut branches from the latest `main`:

```bash
git switch main && git pull
git switch -c feat/123-wishlist-sharing
```

| Type | Use for |
|------|---------|
| `feat` | New features |
| `fix` | Bug fixes |
| `docs` | Documentation only |
| `test` | Adding or fixing tests |
| `chore` | Tooling, refactors, dependency bumps |
| `ci` | Workflows |
| `infra` | Terraform and deployment |

Keep branches short-lived. Rebase on `main` if it falls behind:

```bash
git fetch origin && git rebase origin/main
git push --force-with-lease
```

Only force-push your own feature branch, never `main` or someone else's branch.

## 3. Commits

Format: `<type>(<optional scope>): <summary in imperative mood>`

```text
feat(seats): release locks when payment fails
fix(auth): block admin login without invite code
docs: add Azure deployment notes
test(browse): cover fuzzy search ranking
```

- Scopes match the area: `auth`, `browse`, `seats`, `payments`, `tickets`, `reviews`, `support`, `manager`, `admin`, `db`, `infra`, `ci`.
- One logical change per commit. Commit messages explain *why* when it isn't obvious.
- No AI attribution lines (`Co-Authored-By` an AI tool, "Generated with ...").

PR titles follow the same format, because the PR title becomes the squash commit on `main`.

## 4. Pull requests

- Link the issue with `Closes #123` so it closes on merge.
- Fill in every section of the template. Screenshots for UI changes.
- Keep PRs small, ideally under 400 changed lines. Split large work into several PRs.
- Open a **draft PR** early if you want feedback before it is finished.
- Request at least one reviewer. Pick someone who knows the area (see the team table in the README).
- Before requesting review, run the checks locally:

```bash
cd backend && ruff check . && pytest
cd frontend && npm run lint && npx tsc --noEmit && npm run build
```

### Merge requirements (enforced on `main`)

- 1 approving review from someone other than the author
- All review conversations resolved
- CI green
- Squash merge only, no force-pushes or deletion of `main`

## 5. Reviews and comments

Reviewing is part of the job, not a favour. Aim to review within one working day.

**As a reviewer**
- Check that the change does what the issue asks, is tested, and doesn't leak secrets or break other features.
- Pull the branch and run it for anything non-trivial.
- Be specific and kind. Explain *why*, and suggest a fix where you can (GitHub suggestions are great for small ones).
- Prefix optional comments with `nit:` so the author knows they don't block.
- Use **Request changes** only for things that must change before merge. Otherwise **Comment** or **Approve**.

**As an author**
- Reply to every comment. Either change the code or explain why not.
- The person who opened a conversation resolves it once they're satisfied.
- Don't merge with unresolved conversations or by dismissing reviews.

## 6. Database changes

- Add a new file in `database/migrations/` named `NNNN_description.sql` with the next free number.
- Never edit a merged migration. Write a new one.
- CI applies every migration to an empty Postgres. Your PR must keep the chain working.
- Say in the PR description whether the shared database needs the migration applied, and who will apply it.

See [database/README.md](database/README.md).

### Dependencies

- Dependabot PRs are switched off (`.github/dependabot.yml`). Don't merge one if it appears; close it.
- To upgrade a package, open an issue and a `chore/` branch, change `requirements.txt` or `package.json` + `package-lock.json` yourself, and say in the PR why the upgrade is needed and how you tested it.
- Major-version upgrades (Next.js, React, Tailwind, Python) need their own issue and agreement from the team first.

## 7. Secrets

- Never commit `.env`, `.env.local`, service account JSON, keys or tokens. They are gitignored; keep it that way.
- `.env.example` files hold placeholders only.
- CI scans every push for secrets. If you commit one by mistake, tell a maintainer immediately so the key can be rotated. Deleting the file in a later commit is not enough.

## 8. Definition of done

A change is done when:

- [ ] It does what the issue describes
- [ ] Tests cover the new behaviour (pytest for backend, Playwright for user flows where practical)
- [ ] CI is green and the PR is approved
- [ ] Docs are updated (README, `.env.example`, database README) where relevant
- [ ] It is merged and the issue is closed

## 9. Releases

Each sprint ends with a release. A maintainer:

1. Updates [CHANGELOG.md](CHANGELOG.md).
2. Tags `main`: `git tag -a v0.3.0 -m "v0.3.0: Sprint 3" && git push origin v0.3.0`.
3. Creates a GitHub Release from the tag with features, owners and merged PRs.

Versions follow SemVer. `v0.x` until the first production deployment, which becomes `v1.0.0`.

## 10. Code style

- **Python:** linted with `ruff` (bug-catching rules for now, widened over time). Type hints on new functions. Business logic goes in `services/`, HTTP handling in `routers/`.
- **TypeScript:** ESLint with `next/core-web-vitals`. No `any` in new code where a type is reasonable. API calls go through `lib/api.ts`.
- **SQL:** lower-case keywords or upper-case, but be consistent within a file. Enable row level security on new tables.

Questions? Open a discussion on the relevant issue or ask in the team channel.
