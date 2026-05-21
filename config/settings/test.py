"""Configurações da suíte de testes (pytest-django).

A suíte roda contra PostgreSQL: o pytest-django cria a base de testes a
partir de ``DATABASE_URL``. Não usar SQLite.
"""

from .base import *  # noqa: F401,F403
