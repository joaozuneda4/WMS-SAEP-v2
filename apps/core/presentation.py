"""Tradutor puro de exceção de domínio → apresentação HTTP.

Independente de Django/HTMX/forms/templates.
A view materializa a resposta concreta (messages + redirect / JsonResponse / PermissionDenied).

severity: rege fluxo message+redirect (PRG/302) — status não se aplica aí.
status:   usado apenas em endpoints que respondem com código (JSON / PermissionDenied).
"""

from __future__ import annotations

from dataclasses import dataclass

from apps.core.exceptions import (
    ConflitoDominio,
    DadosInvalidos,
    ErroDominio,
    EstadoInvalido,
    PermissaoNegada,
)


@dataclass(frozen=True)
class ErroPresentation:
    status: int
    severity: str
    default_message: str


_MAPEAMENTO: dict[type[ErroDominio], ErroPresentation] = {
    PermissaoNegada: ErroPresentation(
        status=403,
        severity='error',
        default_message='Você não tem permissão para esta operação.',
    ),
    DadosInvalidos: ErroPresentation(
        status=422,
        severity='error',
        default_message='Dados inválidos para a operação.',
    ),
    EstadoInvalido: ErroPresentation(
        status=409,
        severity='warning',
        default_message='Transição de estado inválida.',
    ),
    ConflitoDominio: ErroPresentation(
        status=409,
        severity='warning',
        default_message='Conflito de domínio.',
    ),
}


def traduz_erro_dominio(exc: ErroDominio) -> ErroPresentation:
    """Traduz exceção de domínio em ErroPresentation (sem efeitos colaterais).

    Divergências canônicas (JSON, re-render HTMX) devem ser opt-out explícito na view.
    Subtipos sem entrada no mapa retornam fallback genérico (status=500, severity='error').
    """
    return _MAPEAMENTO.get(
        type(exc),
        ErroPresentation(status=500, severity='error', default_message=str(exc)),
    )
