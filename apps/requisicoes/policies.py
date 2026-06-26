"""Autorização contextual para requisições.

Fonte de verdade para todas as decisões de permissão relacionadas a requisições.
Views e services chamam as mesmas funções — sem duplicação de lógica.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db.models import QuerySet

from apps.accounts.papeis import papel_efetivo
from apps.core.exceptions import PermissaoNegada
from apps.requisicoes.models import EstadoRequisicao, Requisicao

if TYPE_CHECKING:
    from apps.accounts.models import User


# ---------------------------------------------------------------------------
# Funções auxiliares de derivação de papel
# ---------------------------------------------------------------------------


def _eh_almoxarifado(usuario: User) -> bool:
    """True se o usuário tem papel ativo de chefe ou auxiliar de almoxarifado."""
    return papel_efetivo(usuario).eh_almoxarifado


def _setores_escopo_setor(usuario: User) -> list[int]:
    """IDs de setores não-almox onde o usuário tem papel ativo (chefe ou auxiliar)."""
    return list(papel_efetivo(usuario).setores_em_escopo)


def _setor_chefiado_ativo(usuario: User) -> int | None:
    """PK do setor ativo chefiado pelo usuário, ou None se não chefia nenhum ativo."""
    return papel_efetivo(usuario).setor_chefiado_ativo_id


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


# ---------------------------------------------------------------------------
# Fila de autorização, retorno e recusa
# ---------------------------------------------------------------------------


def pode_ver_fila_autorizacao(ator: User) -> bool:
    """True se o ator tem papel de chefia autorizadora."""
    if not ator.is_active:
        return False
    if ator.is_superuser:
        return True
    return _setor_chefiado_ativo(ator) is not None


def exigir_pode_ver_fila_autorizacao(ator: User) -> None:
    if not pode_ver_fila_autorizacao(ator):
        raise PermissaoNegada(
            'Você não tem permissão para ver a fila de autorização.',
            code='fila_autorizacao_negada',
        )


def pode_retornar_para_rascunho(ator: User, requisicao: Requisicao) -> bool:
    """True se o ator é criador ou beneficiário ativo da requisição."""
    if not ator.is_active:
        return False
    if ator.is_superuser:
        return True
    return ator.pk == requisicao.criador_id or ator.pk == requisicao.beneficiario_id


def exigir_pode_retornar_para_rascunho(ator: User, requisicao: Requisicao) -> None:
    if not pode_retornar_para_rascunho(ator, requisicao):
        raise PermissaoNegada(
            'Apenas o criador ou beneficiário pode retornar esta requisição para rascunho.',
            code='retornar_rascunho_negado',
        )


def pode_cancelar_requisicao(ator: User, requisicao: Requisicao) -> bool:
    """True se o ator pode cancelar a requisição no estado atual."""
    if not ator.is_active:
        return False
    estados_cancelaveis = (
        EstadoRequisicao.RASCUNHO,
        EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        EstadoRequisicao.AUTORIZADA,
        EstadoRequisicao.PRONTA_PARA_RETIRADA,
    )
    if requisicao.estado not in estados_cancelaveis:
        return False
    if ator.is_superuser:
        return True

    if requisicao.estado == EstadoRequisicao.RASCUNHO:
        return ator.pk == requisicao.criador_id
    if requisicao.estado == EstadoRequisicao.AGUARDANDO_AUTORIZACAO:
        return ator.pk == requisicao.criador_id or ator.pk == requisicao.beneficiario_id
    if requisicao.estado in (
        EstadoRequisicao.AUTORIZADA,
        EstadoRequisicao.PRONTA_PARA_RETIRADA,
    ):
        if ator.pk == requisicao.criador_id or ator.pk == requisicao.beneficiario_id:
            return True
        return _eh_almoxarifado(ator)
    return False


def exigir_pode_cancelar_requisicao(ator: User, requisicao: Requisicao) -> None:
    if not pode_cancelar_requisicao(ator, requisicao):
        raise PermissaoNegada(
            'Você não tem permissão para cancelar esta requisição.',
            code='cancelar_requisicao_negada',
        )


def pode_recusar_requisicao(ator: User, requisicao: Requisicao) -> bool:
    """True se o ator chefia o setor do beneficiário."""
    if not ator.is_active:
        return False
    if ator.is_superuser:
        return True
    setor_id = _setor_chefiado_ativo(ator)
    return bool(setor_id is not None and requisicao.setor_beneficiario_id == setor_id)


def exigir_pode_recusar_requisicao(ator: User, requisicao: Requisicao) -> None:
    if not pode_recusar_requisicao(ator, requisicao):
        raise PermissaoNegada(
            'Você não tem permissão para recusar esta requisição.',
            code='recusar_requisicao_negada',
        )


def pode_autorizar_requisicao(ator: User, requisicao: Requisicao) -> bool:
    """True se o ator chefia o setor do beneficiário ou é superuser."""
    return pode_recusar_requisicao(ator, requisicao)


def exigir_pode_autorizar_requisicao(ator: User, requisicao: Requisicao) -> None:
    if not pode_autorizar_requisicao(ator, requisicao):
        raise PermissaoNegada(
            'Você não tem permissão para autorizar esta requisição.',
            code='autorizar_requisicao_negada',
        )


# ---------------------------------------------------------------------------
# pode_ver_fila_atendimento / pode_separar_para_retirada
# ---------------------------------------------------------------------------


def pode_ver_fila_atendimento(ator: User) -> bool:
    """True se o ator tem papel operacional de almoxarifado."""
    if not ator.is_active:
        return False
    if ator.is_superuser:
        return True
    return _eh_almoxarifado(ator)


def exigir_pode_ver_fila_atendimento(ator: User) -> None:
    if not pode_ver_fila_atendimento(ator):
        raise PermissaoNegada(
            'Você não tem permissão para acessar a fila de atendimento.',
            code='ver_fila_atendimento_negada',
        )


def pode_separar_para_retirada(ator: User, requisicao: Requisicao) -> bool:
    """True se o ator estiver ativo e for almoxarifado (chefe/auxiliar) ou superusuário."""
    if not ator.is_active:
        return False
    if ator.is_superuser:
        return True
    return _eh_almoxarifado(ator)


def exigir_pode_separar_para_retirada(ator: User, requisicao: Requisicao) -> None:
    if not pode_separar_para_retirada(ator, requisicao):
        raise PermissaoNegada(
            'Você não tem permissão para separar esta requisição para retirada.',
            code='separar_retirada_negada',
        )


def pode_registrar_devolucao(ator: User, requisicao: Requisicao) -> bool:
    """True se ator ativo, requisição atendida e almoxarifado (chefe ou auxiliar) ou superusuário."""
    if not ator.is_active:
        return False
    if requisicao.estado != EstadoRequisicao.ATENDIDA:
        return False
    if ator.is_superuser:
        return True
    return _eh_almoxarifado(ator)


def exigir_pode_registrar_devolucao(ator: User, requisicao: Requisicao) -> None:
    if not pode_registrar_devolucao(ator, requisicao):
        raise PermissaoNegada(
            'Você não tem permissão para registrar devolução desta requisição.',
            code='registrar_devolucao_negada',
        )


def pode_atender_retirada(ator: User, requisicao: Requisicao) -> bool:
    """True se o ator pode registrar atendimento desta requisição."""
    if not ator.is_active:
        return False
    if requisicao.estado != EstadoRequisicao.PRONTA_PARA_RETIRADA:
        return False
    if ator.is_superuser:
        return True
    return _eh_almoxarifado(ator)


def exigir_pode_atender_retirada(ator: User, requisicao: Requisicao) -> None:
    if not pode_atender_retirada(ator, requisicao):
        raise PermissaoNegada(
            'Você não tem permissão para registrar o atendimento desta requisição.',
            code='atender_retirada_negada',
        )


def pode_copiar_requisicao(ator: 'User', requisicao: Requisicao) -> bool:
    """True se o ator pode copiar a requisição para novo rascunho (REQ-09)."""
    if not ator.is_active:
        return False
    if ator.is_superuser:
        return True
    return pode_criar_para_beneficiario(ator, requisicao.beneficiario)


def exigir_pode_copiar_requisicao(ator: 'User', requisicao: Requisicao) -> None:
    if not pode_copiar_requisicao(ator, requisicao):
        raise PermissaoNegada(
            'Você não tem permissão para copiar esta requisição.',
            code='copiar_requisicao_negada',
        )


def pode_estornar_requisicao(ator: 'User', requisicao: Requisicao) -> bool:
    """True se ator ativo, requisição atendida e chefe de almoxarifado (ou superusuário).

    Auxiliar de almoxarifado não possui esta permissão (TR-021).
    """
    if not ator.is_active:
        return False
    if requisicao.estado != EstadoRequisicao.ATENDIDA:
        return False
    if ator.is_superuser:
        return True
    return papel_efetivo(ator).eh_chefe_de_almoxarifado


def exigir_pode_estornar_requisicao(ator: 'User', requisicao: Requisicao) -> None:
    if not pode_estornar_requisicao(ator, requisicao):
        raise PermissaoNegada(
            'Apenas chefe de almoxarifado pode estornar uma requisição atendida.',
            code='estornar_requisicao_negada',
        )
