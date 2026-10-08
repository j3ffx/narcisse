# Narcisse — contributor notes

Self-OSINT tool: you describe your own identity, Narcisse finds the public traces of it, links them in
an interactive graph, scores each one, and helps you remove what you can. It runs entirely on your
machine: a Python backend (FastAPI, SQLite) listening on loopback, and a React UI (strict TypeScript,
Vite). This file is the contributor guide for humans and AI assistants alike; `README.md` covers what
the tool does and the ethical frame.

## Commands

```bash
npm ci && uv sync                # install (npm ci also points git at .githooks/)
npm run dev                      # API with reload + Vite on http://localhost:5173 (demo, own data dir)
npm run build                    # builds the UI into the Python package
uv run narcisse serve            # built UI + API on 127.0.0.1, opens the browser (--demo for the fake module)
npm run check                    # everything CI runs, but gitleaks on the history and the e2e tests
npm run e2e                      # Playwright against `narcisse serve --demo`, on a temporary data dir
```

`npm ci` points git at `.githooks/`:

- `pre-commit` runs gitleaks on the staged changes (install: `scoop install gitleaks`,
  `brew install gitleaks`…);
- `commit-msg` rejects messages that don't follow the commit rules below;
- `post-commit` re-dates each commit at noon UTC (see Privacy);
- `pre-push` runs `check:private`, the date check and the commit check.

## Commits

Follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/) strictly:

```
type(scope)!: imperative description, lowercase, no trailing period

Body explaining *why* (the diff already shows what).
```

- **Types:** `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `build`, `ci`, `chore`, `style`, `revert`.
- **Scope** is optional; `scripts/check-commits.mjs` holds the authoritative list of types and scopes.
- Header of 72 characters or fewer. One logical change and one type per commit.
- Code, comments and commit messages are in English; the UI and the user docs are in French.
- Work happens on `main`; every push runs the CI.

## Privacy of the public repository

The repository is public, and the tool handles identity data. Nothing personal goes into code, tests,
fixtures, docs, commit messages or commit metadata.

- **No personal data:** fixtures, tests and demo data use fictitious identities only: names like
  « Jeanne Exemple », the domains `example.org`/`.com`/`.net` and the `.test`/`.invalid` TLDs, phone
  numbers from the ranges reserved for fiction.
- **Identity:** commit with a GitHub `noreply` address. `check:private` rejects any other.
- **Times:** commit times show when someone works. The `post-commit` hook keeps only the day (noon UTC);
  `npm run fix:dates` re-dates unpushed commits made without the hook (rebases, other machines).
  Release tags are lightweight, as an annotated one would record the time.
- **Docs only when they belong in public:** no personal to-do lists, plans or notes. Local working notes
  stay in `.claude/` (ignored).
- **Secrets:** none needed. Optional tokens live in the user's settings, or in `.env` (ignored) during
  development, documented in `.env.example`. gitleaks scans the staged changes and, in CI, the history.
- `.private-patterns` (ignored, one regex per line) lists your own private strings: `check:private`
  scans tracked files and commit messages for them.
- **Never scan a real identity during development**, yours included: use demo mode.

## Invariants (discuss before changing)

- **Free only.** No paid API, no mandatory key to a paid service. A free token (a GitHub personal
  token…) may lift limits, as an option; everything works without it.
- **Public sources only.** No bypassing authentication, paywalls or captchas, no exploiting flaws, no
  fake accounts.
- **Passive by default.** _Passive_: public APIs and pages, DNS/RDAP, archives, open registries.
  _Light active_ (e.g. "is this e-mail registered on X?" through a password-reset form): opt-in,
  module by module, **off by default**, explained in the UI before it is turned on. Crawling honours
  `robots.txt`, is rate-limited per domain and sends an honest, identifiable User-Agent.
- **Nothing is sent on the user's behalf.** Narcisse prepares removal requests (letters, links,
  pre-filled forms); the user always sends them.
- **100 % local, no telemetry.** The server binds to `127.0.0.1` only, refuses requests whose `Host`
  isn't loopback (DNS rebinding), and accepts state-changing requests only from its own origin with a
  JSON body (another website open in the browser can't drive it). Nothing leaves the machine except
  requests to the hosts a source module declares and, if the user configured one, to their LLM.
- **User data lives outside the repository**, in the OS data directory (`platformdirs`), overridable
  with `NARCISSE_DATA_DIR`.
- **Licences are checked** before reusing a tool or dataset. The project is GPL-3.0-only, compatible
  with what it draws on so far: Maigret, Sherlock, JustDeleteMe (MIT), holehe, PhoneInfoga (GPL-3.0),
  WhatsMyName's data (CC BY-SA 4.0, credited).
- **Results stream.** A module yields findings one by one; each is stored and pushed to the UI as it
  arrives. No module returns its findings in one block.
- **Every source says what it is.** A source that stops working says so; the demo module is labelled
  as fake wherever it shows, and exists only in demo mode.
- **Errors:** the UI shows a human message (an error code translated by the UI); stack traces go to
  the log file only.
- **Accessibility:** contrast ≥ 4.5:1 (tokens), visible focus, keyboard reachable, `alt` text,
  `prefers-reduced-motion` respected (scripted motion included), light and dark themes.

## Layout

- `src/narcisse/`: Python package. `engine/` (scheduling, events, HTTP for modules), `modules/` (one
  file per source), `api/`, `storage/` (models, Alembic migrations: `scripts/new-migration.py`).
  `tests/`: pytest (`tests/fakes.py` holds modules whose timing tests control).
- `web/`: the UI (Vite, React, Tailwind, shadcn/ui in `src/components/ui/`, TanStack Query, wouter).
  `src/lib/live.ts` applies the live events to the query cache. `npm run build` writes the UI into
  `src/narcisse/web/static/` (ignored), which the Python package serves and ships. `web/e2e/`:
  Playwright against `narcisse serve --demo` on a temporary data dir.
- `scripts/`: repository checks and git hook helpers.

## Dependencies

Keep them few, and say why in the commit that adds one. Lock files (`uv.lock`, `package-lock.json`)
are written by their tool, never edited by hand. Dependabot proposes grouped updates every Monday.

## Releases

Semantic versioning. `0.1.0` comes out once the tool is usable for real. After it: `0.x.0` for a big
batch of features, `0.x.y` for fixes that matter between them; the smallest touches get no version of
their own and wait for the next one. `1.0.0` once no improvement is left in sight. `CHANGELOG.md` (in
French, for users) says what each version brings; a lightweight tag `vX.Y.Z` makes
`.github/workflows/release.yml` publish the GitHub release with that version's notes.
