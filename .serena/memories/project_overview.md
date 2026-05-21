# WMS-SAEP-v2 overview
- Last verified: 2026-05-21.
- Django 6 project for WMS-SAEP, single-context almoxarifado system: requisitions, authorization, fulfillment, stock control, notifications, and server-rendered UI.
- Current stack: Python >=3.13, Django >=6.0,<6.1, django-environ, django-htmx, psycopg, pytest, pytest-django, Tailwind CSS v4 via npm scripts.
- Database contract: PostgreSQL via `DATABASE_URL`; no silent SQLite fallback in `config/settings/base.py`. Test settings also use PostgreSQL through pytest-django.
- Apps present: `apps.accounts` (Setor, User by matricula, VinculoAuxiliar), `apps.estoque` (Material, Estoque, SaldoEstoque), `apps.requisicoes` (SequenciaRequisicao, Requisicao, ItemRequisicao, TimelineRequisicao), `apps.notificacoes`, `apps.core` (shared UI, management commands, base templates).
- Canonical dev seed lives in `apps/core/management/commands/seed_dev.py` and follows ADR-0009: `SEED_DEV_HABILITADO=true`, `DEBUG=True`, canonical sectors/users/materials/stock/saldos/sequencia, default password `senha@dev`.
- Project docs are authoritative when memory differs: root `AGENTS.md`, `CONTEXT.md`, `docs/CONVENTIONS.md`, `docs/adr/`, and `docs/agents/domain.md`.
- Project path: `/Users/jmzr/Dev/WMS-SAEP-v2` on Darwin/macOS.