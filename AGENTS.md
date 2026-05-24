@/Users/jmzr/.codex/RTK.md

<!-- context7 -->
Use Context7 MCP to fetch current documentation whenever the user asks about a library, framework, SDK, API, CLI tool, or cloud service -- even well-known ones like Tailwind or Django. This includes API syntax, configuration, version migration, library-specific debugging, setup instructions, and CLI tool usage. Use even when you think you know the answer -- your training data may not reflect recent changes. Prefer this over web search for library docs.
<!-- context7 -->

## Context7 library IDs quick reference:
- Django 6: `/django/django/6_0a1`
- DRF: `/websites/django-rest-framework`
- django-htmx: `/adamchainz/django-htmx`
- Tailwind CSS: `/tailwindlabs/tailwindcss.com`
- Alpine.js: `/websites/alpinejs_dev`

<!-- serena -->
Use Serena MCP for semantic codebase understanding and symbol-aware code navigation whenever the user asks about an existing project, repository, module, class, function, or implementation detail.
<!-- serena -->

## Agent skills

### Issue tracker

Issues and PRDs are tracked in GitHub Issues for `JMZR-SAEP/WMS-SAEP-v2`. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the default triage vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, and `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context repo. Use `docs/agents/domain.md` as the routing guide for domain documentation.

If docs and memory disagree, trust live docs/code first and update Serena memory when the decision is durable.

### Design handoff

For UI/frontend work, use `.design/` as the required design handoff before implementing or reviewing screens.

Read the applicable files first:

- `.design/INFORMATION_ARCHITECTURE.md` for routes, navigation, page hierarchy, user flows, labels, and URL strategy.
- `.design/TASKS.md` for the current UI build breakdown generated from the briefs.
- `.design/<area>/DESIGN_BRIEF.md` for screen-specific UX, layout, interaction, responsive, accessibility, copy, and out-of-scope decisions.

`.design/` guides implementation and review, but it does not override accepted ADRs, `docs/design-system.md`, `docs/CONVENTIONS.md`, domain rules, tests, or live code. If `.design/` conflicts with those sources, surface the conflict before implementing.

When implementing UI from `.design/`, keep the scope to the referenced brief/task unless the user explicitly expands it.

### Code conventions

Do not duplicate project rules here. Use these sources:

- Layered architecture and implementation rules: `docs/CONVENTIONS.md` and ADR-0004.
- Service/policy/domain-exception contract: ADR-0011.
- Test strategy: ADR-0010.
- Server-rendered frontend and design system: `docs/design-system.md` and ADR-0008.
- UI/frontend handoff: `.design/`, especially `.design/INFORMATION_ARCHITECTURE.md`, `.design/TASKS.md`, and the relevant `.design/<area>/DESIGN_BRIEF.md`.
- Seed/dev data contract: ADR-0009.

## Project commands

- Run tests: `uv run pytest -q -ra --tb=short --strict-markers --disable-warnings`
- Format code: `uv run ruff format .`
- Check format: `uv run ruff format --check .`
- Lint: `uv run ruff check .`
- Type check: `uv run mypy apps`

> **Never use redirections, pipes, `tail`, `head`, `grep`, or output truncation.** When a command fails, use the `[full output: ...]` path emitted by the RTK Tee System to inspect the complete raw output without rerunning the command.

## Ephemeral development environment

The local environment is disposable in dev.

- the local database may be deleted and recreated;
- the default flow is reset database -> apply migrations -> load minimal data, when the corresponding command exists;
- local migrations are unversioned and ignored by `.gitignore`;
- `make init` must be used during the initial project setup to create .venv and install dependencies;
- at this stage of the project, every edit to `models` or schema must be followed by `make setup`, so the workflow does not depend on manual migration management;
- app migrations must be treated as ephemeral artifacts: before testing or completing an implementation that changes the schema, delete and recreate the local migrations from scratch, simulating a clean first execution of the app;
- creating new migration files is not part of the normal delivery in this ephemeral context;
- the source of truth for structural changes is `models`, constraints, indexes, domain rules, and tests; local migrations only materialize the local database;
- tasks without structural changes may follow an incremental flow; a full reset is mandatory only for schema/model changes or when the local environment is inconsistent;
- ADR-0009 defines `seed_dev`/`make seed-dev` as the intended local seed contract, but do not assume it is runnable until the Makefile and command exist in the live tree;

## Language convention

- Domain identifiers use PT-BR: models, fields, choices, services, policies, selectors, and domain functions/variables. This keeps code aligned with the ubiquitous language and the `CONTEXT.md` glossary.
- The technical/framework surface stays in English where the framework imposes it: app package names (e.g. `accounts`), inherited Django attributes (`is_active`, `is_staff`, `is_superuser`, `USERNAME_FIELD`), and standard hooks.
- URLs use PT-BR slugs (e.g. `/requisicoes/`, `/requisicoes/nova/`).
- Documentation and code comments must use PT-BR.
- Django models must always define `verbose_name` and `verbose_name_plural` in PT-BR.

## Git workflow

- **Never commit directly to main** — always create a feature branch first.
- Confirm the current branch before any commit operation.
- Branch names: `feat/{desc}`, `fix/{desc}`, `refactor/{desc}`, `test/{desc}`, `docs/{desc}`, `chore/{desc}`.
- Commits must be small, cohesive, and reversible — one logical unit per commit.
