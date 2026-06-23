"""Policies de acesso para gestão de cadastro (accounts)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.accounts.models import User


def pode_gerir_cadastro(ator: 'User') -> bool:
    """Superusuário pode gerir usuários, setores e vínculos auxiliares."""
    return bool(ator.is_active and ator.is_superuser)


def exigir_pode_gerir_cadastro(ator: 'User') -> None:
    from apps.core.exceptions import PermissaoNegada

    if not pode_gerir_cadastro(ator):
        raise PermissaoNegada('Apenas superusuários podem gerir cadastros.')
