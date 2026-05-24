"""Autorização contextual para requisições.

Fonte de verdade para todas as decisões de permissão relacionadas a requisições.
Views e services chamam as mesmas funções — sem duplicação de lógica.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db.models import QuerySet

from apps.accounts.models import SetorClassificacao, VinculoAuxiliar
from apps.core.exceptions import PermissaoNegada
from apps.requisicoes.models import Requisicao

if TYPE_CHECKING:
    from apps.accounts.models import User


# ---------------------------------------------------------------------------
# Funções auxiliares de derivação de papel
# ---------------------------------------------------------------------------


def _eh_almoxarifado(usuario: User) -> bool:
    """True se o usuário tem papel ativo de chefe ou auxiliar de almoxarifado."""
    # Chefe de almoxarifado
    try:
        setor_chefiado = usuario.setor_chefiado
        if (
            setor_chefiado.classificacao == SetorClassificacao.ALMOXARIFADO
            and setor_chefiado.ativo
        ):
            return True
    except Exception:
        pass
    # Auxiliar de almoxarifado
    return VinculoAuxiliar.objects.filter(
        usuario=usuario,
        ativo=True,
        setor__classificacao=SetorClassificacao.ALMOXARIFADO,
        setor__ativo=True,
    ).exists()


def _setores_escopo_setor(usuario: User) -> list[int]:
    """IDs de setores não-almox onde o usuário tem papel ativo (chefe ou auxiliar)."""
    ids: set[int] = set()
    # Chefe de setor
    try:
        setor_chefiado = usuario.setor_chefiado
        if (
            setor_chefiado.classificacao != SetorClassificacao.ALMOXARIFADO
            and setor_chefiado.ativo
        ):
            ids.add(setor_chefiado.pk)
    except Exception:
        pass
    # Auxiliares de setor não-almox
    vinculos = (
        VinculoAuxiliar.objects.filter(
            usuario=usuario,
            ativo=True,
            setor__ativo=True,
        )
        .exclude(setor__classificacao=SetorClassificacao.ALMOXARIFADO)
        .values_list('setor_id', flat=True)
    )
    ids.update(vinculos)
    return list(ids)


# ---------------------------------------------------------------------------
# pode_ser_beneficiario
# ---------------------------------------------------------------------------


def pode_ser_beneficiario(usuario: User) -> bool:
    """True se o usuário pode ser beneficiário de uma requisição.

    Beneficiário elegível = usuário ativo com setor não-nulo.
    Reutilizado em queryset, policy e service.
    """
    return bool(usuario.is_active and usuario.setor_id is not None)


# ---------------------------------------------------------------------------
# Escopo de criação
# ---------------------------------------------------------------------------


@dataclass
class EscopoCriacaoRequisicao:
    """Contexto de criação de requisição calculado a partir do ator."""

    modo_beneficiario: str  # "proprio" | "setor" | "qualquer"
    pode_criar_para_si: bool
    setores_escopo_ids: list[int]
    beneficiarios: QuerySet | None = None


def resolver_escopo_criacao_requisicao(ator: User) -> EscopoCriacaoRequisicao:
    """Resolve o escopo de criação de requisição para o ator.

    Lança PermissaoNegada se o ator não pode criar requisições.
    Precedência por maior escopo: qualquer > setor > proprio.
    """
    from apps.accounts.models import User as UserModel

    if not ator.is_active:
        raise PermissaoNegada('Usuário inativo não pode criar requisições.')

    pode_criar_para_si = pode_ser_beneficiario(ator)

    # Superusuário → escopo total
    if ator.is_superuser:
        qs = (
            UserModel.objects.filter(is_active=True, setor__isnull=False)
            .exclude(pk=ator.pk)
            .select_related('setor')
        )
        return EscopoCriacaoRequisicao(
            modo_beneficiario='qualquer',
            pode_criar_para_si=pode_criar_para_si,
            setores_escopo_ids=[],
            beneficiarios=qs,
        )

    # Almoxarifado (chefe ou auxiliar) → qualquer setor
    if _eh_almoxarifado(ator):
        qs = (
            UserModel.objects.filter(is_active=True, setor__isnull=False)
            .exclude(pk=ator.pk)
            .select_related('setor')
        )
        return EscopoCriacaoRequisicao(
            modo_beneficiario='qualquer',
            pode_criar_para_si=pode_criar_para_si,
            setores_escopo_ids=[],
            beneficiarios=qs,
        )

    # Chefe ou auxiliar de setor não-almox → escopo restrito ao(s) setor(es)
    setores_ids = _setores_escopo_setor(ator)
    if setores_ids:
        qs = (
            UserModel.objects.filter(
                is_active=True,
                setor__isnull=False,
                setor__in=setores_ids,
            )
            .exclude(pk=ator.pk)
            .select_related('setor')
        )
        return EscopoCriacaoRequisicao(
            modo_beneficiario='setor',
            pode_criar_para_si=pode_criar_para_si,
            setores_escopo_ids=setores_ids,
            beneficiarios=qs,
        )

    # Solicitante puro → apenas para si
    if not pode_criar_para_si:
        raise PermissaoNegada(
            'Usuário sem setor não pode criar requisições.',
            code='sem_setor',
        )
    return EscopoCriacaoRequisicao(
        modo_beneficiario='proprio',
        pode_criar_para_si=True,
        setores_escopo_ids=[],
        beneficiarios=UserModel.objects.none(),
    )


# ---------------------------------------------------------------------------
# pode_criar_para_beneficiario
# ---------------------------------------------------------------------------


def pode_criar_para_beneficiario(ator: User, beneficiario: User) -> bool:
    """True se o ator pode criar requisição para o beneficiário dado."""
    if not ator.is_active:
        return False
    if not pode_ser_beneficiario(beneficiario):
        return False
    if ator.pk == beneficiario.pk:
        return pode_ser_beneficiario(ator)
    if ator.is_superuser:
        return True
    if _eh_almoxarifado(ator):
        return True
    setores_ids = _setores_escopo_setor(ator)
    if setores_ids and beneficiario.setor_id in setores_ids:
        return True
    return False


def exigir_pode_criar_para_beneficiario(ator: User, beneficiario: User) -> None:
    if not pode_criar_para_beneficiario(ator, beneficiario):
        raise PermissaoNegada(
            f'Você não tem permissão para criar requisições em nome de {beneficiario.nome}.',
            code='beneficiario_fora_do_escopo',
        )


# ---------------------------------------------------------------------------
# pode_editar_rascunho
# ---------------------------------------------------------------------------


def pode_editar_rascunho(ator: User, requisicao: Requisicao) -> bool:
    """True se o ator é o criador da requisição.

    Verificação de estado (RASCUNHO) é feita pelo service via transitions.py,
    que lança EstadoInvalido. Esta policy só trata autorização de ator.
    """
    return ator.is_active and ator.pk == requisicao.criador_id


def exigir_pode_editar_rascunho(ator: User, requisicao: Requisicao) -> None:
    if not pode_editar_rascunho(ator, requisicao):
        raise PermissaoNegada(
            'Apenas o criador pode editar um rascunho.',
            code='editar_rascunho_negado',
        )


# ---------------------------------------------------------------------------
# pode_enviar_rascunho
# ---------------------------------------------------------------------------


def pode_enviar_rascunho(ator: User, requisicao: Requisicao) -> bool:
    """True se o ator é o criador da requisição.

    Verificação de estado (RASCUNHO) é responsabilidade do service via
    transitions.py, que lança EstadoInvalido. Esta policy só trata
    autorização de ator.
    """
    return ator.is_active and ator.pk == requisicao.criador_id


def exigir_pode_enviar_rascunho(ator: User, requisicao: Requisicao) -> None:
    if not pode_enviar_rascunho(ator, requisicao):
        raise PermissaoNegada(
            'Apenas o criador pode enviar este rascunho para autorização.',
            code='enviar_rascunho_negado',
        )
