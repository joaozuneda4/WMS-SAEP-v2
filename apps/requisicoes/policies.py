"""Autorização contextual para requisições.

Fonte de verdade para todas as decisões de permissão relacionadas a requisições.
Views e services chamam as mesmas funções — sem duplicação de lógica.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.db.models import QuerySet

from apps.core.exceptions import PermissaoNegada
from apps.requisicoes.models import EstadoRequisicao, Requisicao

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.accounts.papeis import PapelEfetivo


# ---------------------------------------------------------------------------
# pode_ser_beneficiario
# ---------------------------------------------------------------------------


def pode_ser_beneficiario(papel: 'PapelEfetivo') -> bool:
    """True se o papel indica que o ator pode ser beneficiário de uma requisição."""
    return papel.pode_ser_beneficiario


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


def resolver_escopo_criacao_requisicao(
    papel: 'PapelEfetivo',
) -> EscopoCriacaoRequisicao:
    """Resolve o escopo de criação de requisição para o ator.

    Lança PermissaoNegada se o ator não pode criar requisições.
    Precedência por maior escopo: qualquer > setor > proprio.
    """
    from apps.accounts.models import User as UserModel

    if not papel.ativo:
        raise PermissaoNegada('Usuário inativo não pode criar requisições.')

    pode_criar_para_si = papel.pode_ser_beneficiario

    # Superusuário → escopo total
    if papel.eh_superusuario:
        qs = (
            UserModel.objects.filter(is_active=True, setor__isnull=False)
            .exclude(pk=papel.ator_id)
            .select_related('setor')
        )
        return EscopoCriacaoRequisicao(
            modo_beneficiario='qualquer',
            pode_criar_para_si=pode_criar_para_si,
            setores_escopo_ids=[],
            beneficiarios=qs,
        )

    # Almoxarifado (chefe ou auxiliar) → qualquer setor
    if papel.eh_almoxarifado:
        qs = (
            UserModel.objects.filter(is_active=True, setor__isnull=False)
            .exclude(pk=papel.ator_id)
            .select_related('setor')
        )
        return EscopoCriacaoRequisicao(
            modo_beneficiario='qualquer',
            pode_criar_para_si=pode_criar_para_si,
            setores_escopo_ids=[],
            beneficiarios=qs,
        )

    # Chefe ou auxiliar de setor não-almox → escopo restrito ao(s) setor(es)
    setores_ids = list(papel.setores_em_escopo)
    if setores_ids:
        qs = (
            UserModel.objects.filter(
                is_active=True,
                setor__isnull=False,
                setor__in=setores_ids,
            )
            .exclude(pk=papel.ator_id)
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


def pode_criar_para_beneficiario(papel: 'PapelEfetivo', beneficiario: 'User') -> bool:
    """True se o ator pode criar requisição para o beneficiário dado."""
    if not papel.ativo:
        return False
    if not (beneficiario.is_active and beneficiario.setor_id is not None):
        return False
    if papel.ator_id == beneficiario.pk:
        return papel.pode_ser_beneficiario
    if papel.eh_superusuario:
        return True
    if papel.eh_almoxarifado:
        return True
    if papel.setores_em_escopo and beneficiario.setor_id in papel.setores_em_escopo:
        return True
    return False


def exigir_pode_criar_para_beneficiario(
    papel: 'PapelEfetivo', beneficiario: 'User'
) -> None:
    if not pode_criar_para_beneficiario(papel, beneficiario):
        raise PermissaoNegada(
            f'Você não tem permissão para criar requisições em nome de {beneficiario.nome}.',
            code='beneficiario_fora_do_escopo',
        )


# ---------------------------------------------------------------------------
# pode_editar_rascunho
# ---------------------------------------------------------------------------


def pode_editar_rascunho(papel: 'PapelEfetivo', requisicao: Requisicao) -> bool:
    """True se o ator é o criador da requisição.

    Verificação de estado (RASCUNHO) é feita pelo service via transitions.py,
    que lança EstadoInvalido. Esta policy só trata autorização de ator.
    """
    return papel.ativo and (
        papel.eh_superusuario or papel.ator_id == requisicao.criador_id
    )


def exigir_pode_editar_rascunho(papel: 'PapelEfetivo', requisicao: Requisicao) -> None:
    if not pode_editar_rascunho(papel, requisicao):
        raise PermissaoNegada(
            'Apenas o criador pode editar um rascunho.',
            code='editar_rascunho_negado',
        )


# ---------------------------------------------------------------------------
# pode_enviar_rascunho
# ---------------------------------------------------------------------------


def pode_enviar_rascunho(papel: 'PapelEfetivo', requisicao: Requisicao) -> bool:
    """True se o ator é o criador ou superusuário.

    Verificação de estado (RASCUNHO) é responsabilidade do service via
    transitions.py, que lança EstadoInvalido. Esta policy só trata
    autorização de ator.
    """
    return papel.ativo and (
        papel.eh_superusuario or papel.ator_id == requisicao.criador_id
    )


def exigir_pode_enviar_rascunho(papel: 'PapelEfetivo', requisicao: Requisicao) -> None:
    if not pode_enviar_rascunho(papel, requisicao):
        raise PermissaoNegada(
            'Apenas o criador pode enviar este rascunho para autorização.',
            code='enviar_rascunho_negado',
        )


# ---------------------------------------------------------------------------
# Fila de autorização, retorno e recusa
# ---------------------------------------------------------------------------


def pode_ver_fila_autorizacao(papel: 'PapelEfetivo') -> bool:
    """True se o ator tem papel de chefia autorizadora."""
    if not papel.ativo:
        return False
    if papel.eh_superusuario:
        return True
    return papel.setor_chefiado_ativo_id is not None


def exigir_pode_ver_fila_autorizacao(papel: 'PapelEfetivo') -> None:
    if not pode_ver_fila_autorizacao(papel):
        raise PermissaoNegada(
            'Você não tem permissão para ver a fila de autorização.',
            code='fila_autorizacao_negada',
        )


def pode_retornar_para_rascunho(papel: 'PapelEfetivo', requisicao: Requisicao) -> bool:
    """True se o ator é criador ou beneficiário ativo da requisição."""
    if not papel.ativo:
        return False
    if papel.eh_superusuario:
        return True
    return (
        papel.ator_id == requisicao.criador_id
        or papel.ator_id == requisicao.beneficiario_id
    )


def exigir_pode_retornar_para_rascunho(
    papel: 'PapelEfetivo', requisicao: Requisicao
) -> None:
    if not pode_retornar_para_rascunho(papel, requisicao):
        raise PermissaoNegada(
            'Apenas o criador ou beneficiário pode retornar esta requisição para rascunho.',
            code='retornar_rascunho_negado',
        )


def pode_cancelar_requisicao(papel: 'PapelEfetivo', requisicao: Requisicao) -> bool:
    """True se o ator pode cancelar a requisição no estado atual."""
    if not papel.ativo:
        return False
    estados_cancelaveis = (
        EstadoRequisicao.RASCUNHO,
        EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        EstadoRequisicao.AUTORIZADA,
        EstadoRequisicao.PRONTA_PARA_RETIRADA,
    )
    if requisicao.estado not in estados_cancelaveis:
        return False
    if papel.eh_superusuario:
        return True

    if requisicao.estado == EstadoRequisicao.RASCUNHO:
        return papel.ator_id == requisicao.criador_id
    if requisicao.estado == EstadoRequisicao.AGUARDANDO_AUTORIZACAO:
        return (
            papel.ator_id == requisicao.criador_id
            or papel.ator_id == requisicao.beneficiario_id
        )
    if requisicao.estado in (
        EstadoRequisicao.AUTORIZADA,
        EstadoRequisicao.PRONTA_PARA_RETIRADA,
    ):
        if (
            papel.ator_id == requisicao.criador_id
            or papel.ator_id == requisicao.beneficiario_id
        ):
            return True
        return papel.eh_almoxarifado
    return False


def exigir_pode_cancelar_requisicao(
    papel: 'PapelEfetivo', requisicao: Requisicao
) -> None:
    if not pode_cancelar_requisicao(papel, requisicao):
        raise PermissaoNegada(
            'Você não tem permissão para cancelar esta requisição.',
            code='cancelar_requisicao_negada',
        )


def pode_recusar_requisicao(papel: 'PapelEfetivo', requisicao: Requisicao) -> bool:
    """True se o ator chefia o setor do beneficiário."""
    if not papel.ativo:
        return False
    if papel.eh_superusuario:
        return True
    setor_id = papel.setor_chefiado_ativo_id
    return bool(setor_id is not None and requisicao.setor_beneficiario_id == setor_id)


def exigir_pode_recusar_requisicao(
    papel: 'PapelEfetivo', requisicao: Requisicao
) -> None:
    if not pode_recusar_requisicao(papel, requisicao):
        raise PermissaoNegada(
            'Você não tem permissão para recusar esta requisição.',
            code='recusar_requisicao_negada',
        )


def pode_autorizar_requisicao(papel: 'PapelEfetivo', requisicao: Requisicao) -> bool:
    """True se o ator chefia o setor do beneficiário ou é superuser."""
    return pode_recusar_requisicao(papel, requisicao)


def exigir_pode_autorizar_requisicao(
    papel: 'PapelEfetivo', requisicao: Requisicao
) -> None:
    if not pode_autorizar_requisicao(papel, requisicao):
        raise PermissaoNegada(
            'Você não tem permissão para autorizar esta requisição.',
            code='autorizar_requisicao_negada',
        )


# ---------------------------------------------------------------------------
# pode_ver_fila_atendimento / pode_separar_para_retirada
# ---------------------------------------------------------------------------


def pode_ver_fila_atendimento(papel: 'PapelEfetivo') -> bool:
    """True se o ator tem papel operacional de almoxarifado."""
    if not papel.ativo:
        return False
    if papel.eh_superusuario:
        return True
    return papel.eh_almoxarifado


def exigir_pode_ver_fila_atendimento(papel: 'PapelEfetivo') -> None:
    if not pode_ver_fila_atendimento(papel):
        raise PermissaoNegada(
            'Você não tem permissão para acessar a fila de atendimento.',
            code='ver_fila_atendimento_negada',
        )


def pode_separar_para_retirada(papel: 'PapelEfetivo', requisicao: Requisicao) -> bool:
    """True se o ator estiver ativo e for almoxarifado (chefe/auxiliar) ou superusuário."""
    if not papel.ativo:
        return False
    if papel.eh_superusuario:
        return True
    return papel.eh_almoxarifado


def exigir_pode_separar_para_retirada(
    papel: 'PapelEfetivo', requisicao: Requisicao
) -> None:
    if not pode_separar_para_retirada(papel, requisicao):
        raise PermissaoNegada(
            'Você não tem permissão para separar esta requisição para retirada.',
            code='separar_retirada_negada',
        )


def pode_registrar_devolucao(papel: 'PapelEfetivo', requisicao: Requisicao) -> bool:
    """True se ator ativo, requisição atendida e almoxarifado (chefe ou auxiliar) ou superusuário."""
    if not papel.ativo:
        return False
    if requisicao.estado != EstadoRequisicao.ATENDIDA:
        return False
    if papel.eh_superusuario:
        return True
    return papel.eh_almoxarifado


def exigir_pode_registrar_devolucao(
    papel: 'PapelEfetivo', requisicao: Requisicao
) -> None:
    if not pode_registrar_devolucao(papel, requisicao):
        raise PermissaoNegada(
            'Você não tem permissão para registrar devolução desta requisição.',
            code='registrar_devolucao_negada',
        )


def pode_atender_retirada(papel: 'PapelEfetivo', requisicao: Requisicao) -> bool:
    """True se o ator pode registrar atendimento desta requisição."""
    if not papel.ativo:
        return False
    if requisicao.estado != EstadoRequisicao.PRONTA_PARA_RETIRADA:
        return False
    if papel.eh_superusuario:
        return True
    return papel.eh_almoxarifado


def exigir_pode_atender_retirada(papel: 'PapelEfetivo', requisicao: Requisicao) -> None:
    if not pode_atender_retirada(papel, requisicao):
        raise PermissaoNegada(
            'Você não tem permissão para registrar o atendimento desta requisição.',
            code='atender_retirada_negada',
        )


def pode_copiar_requisicao(papel: 'PapelEfetivo', requisicao: Requisicao) -> bool:
    """True se o ator pode copiar a requisição para novo rascunho (REQ-09)."""
    if not papel.ativo:
        return False
    if papel.eh_superusuario:
        return True
    return pode_criar_para_beneficiario(papel, requisicao.beneficiario)


def exigir_pode_copiar_requisicao(
    papel: 'PapelEfetivo', requisicao: Requisicao
) -> None:
    if not pode_copiar_requisicao(papel, requisicao):
        raise PermissaoNegada(
            'Você não tem permissão para copiar esta requisição.',
            code='copiar_requisicao_negada',
        )


def pode_estornar_requisicao(papel: 'PapelEfetivo', requisicao: Requisicao) -> bool:
    """True se ator ativo, requisição atendida e chefe de almoxarifado (ou superusuário).

    Auxiliar de almoxarifado não possui esta permissão (TR-021).
    """
    if not papel.ativo:
        return False
    if requisicao.estado != EstadoRequisicao.ATENDIDA:
        return False
    if papel.eh_superusuario:
        return True
    return papel.eh_chefe_de_almoxarifado


def exigir_pode_estornar_requisicao(
    papel: 'PapelEfetivo', requisicao: Requisicao
) -> None:
    if not pode_estornar_requisicao(papel, requisicao):
        raise PermissaoNegada(
            'Apenas chefe de almoxarifado pode estornar uma requisição atendida.',
            code='estornar_requisicao_negada',
        )


def pode_consultar_historico_requisicoes(papel: 'PapelEfetivo') -> bool:
    """Pode navegar o histórico system-wide de requisições.

    Espelha o universo de ``historico_requisicoes_visiveis_para``: superuser,
    almoxarifado (chefe/aux) ou chefe/aux de setor não-almox (setores_em_escopo
    não vazio). Solicitante puro e inativo: não — continuam usando
    ``requisicoes:minhas``.
    """
    if not papel.ativo:
        return False
    if papel.eh_superusuario:
        return True
    return papel.eh_almoxarifado or bool(papel.setores_em_escopo)


def exigir_pode_consultar_historico_requisicoes(papel: 'PapelEfetivo') -> None:
    if not pode_consultar_historico_requisicoes(papel):
        raise PermissaoNegada(
            'Você não tem permissão para consultar o histórico de requisições.',
            code='permissao_negada',
        )
