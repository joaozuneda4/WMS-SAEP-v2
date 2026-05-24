"""Services de domínio para requisições.

Único ponto de mutação de estado das requisições. Cada service:
- assinatura keyword-only com ator_id (nunca instância User)
- abre transaction.atomic para toda escrita de domínio
- chama exigir_pode_* antes de qualquer efeito
- registra eventos de TimelineRequisicao
- retorna a entidade principal alterada
- lança exceções de apps.core.exceptions, nunca exceções HTTP
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.core.exceptions import DadosInvalidos
from apps.estoque.models import Material
from apps.requisicoes.models import (
    EstadoRequisicao,
    EventoTimeline,
    ItemRequisicao,
    Requisicao,
    SequenciaRequisicao,
    TimelineRequisicao,
)
from apps.requisicoes.policies import (
    exigir_pode_criar_para_beneficiario,
    exigir_pode_editar_rascunho,
    exigir_pode_enviar_rascunho,
    pode_ser_beneficiario,
)
from apps.requisicoes.selectors import material_eh_elegivel
from apps.requisicoes.transitions import verificar_transicao_valida

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Tipos auxiliares
# ---------------------------------------------------------------------------

ItemInput = dict  # {'material_id': int, 'quantidade_solicitada': Decimal}


# ---------------------------------------------------------------------------
# TR-001: criar requisição
# ---------------------------------------------------------------------------


@transaction.atomic
def criar_requisicao(
    *,
    ator_id: int,
    beneficiario_id: int,
    itens: list[ItemInput],
    observacao_geral: str = '',
) -> Requisicao:
    """Cria um rascunho de requisição com ao menos um item.

    TR-001: N/A → RASCUNHO.
    Não chama verificar_transicao_valida — não há estado de origem.
    """
    try:
        ator = User.objects.get(pk=ator_id)
    except User.DoesNotExist:
        raise DadosInvalidos(
            'Ator não encontrado.', code='ator_nao_encontrado'
        ) from None
    try:
        beneficiario = User.objects.select_related('setor').get(pk=beneficiario_id)
    except User.DoesNotExist:
        raise DadosInvalidos(
            'Beneficiário não encontrado.', code='beneficiario_nao_encontrado'
        ) from None

    # Autorização
    exigir_pode_criar_para_beneficiario(ator, beneficiario)

    # Beneficiário precisa ter setor (snapshot)
    if not pode_ser_beneficiario(beneficiario):
        raise DadosInvalidos(
            f'{beneficiario.nome} não pode ser beneficiário: usuário inativo ou sem setor.',
            code='beneficiario_inelegivel',
        )

    setor_beneficiario = beneficiario.setor
    assert setor_beneficiario is not None  # garantido por pode_ser_beneficiario acima

    # Validar itens
    if not itens:
        raise DadosInvalidos(
            'A requisição precisa ter ao menos um item.',
            code='sem_itens',
        )

    _validar_itens(itens)

    # Criar cabeçalho
    requisicao = Requisicao.objects.create(
        estado=EstadoRequisicao.RASCUNHO,
        numero_publico=None,
        criador=ator,
        beneficiario=beneficiario,
        setor_beneficiario=setor_beneficiario,
        observacao_geral=observacao_geral,
    )

    # Criar itens
    ItemRequisicao.objects.bulk_create(
        [
            ItemRequisicao(
                requisicao=requisicao,
                material_id=item['material_id'],
                quantidade_solicitada=item['quantidade_solicitada'],
            )
            for item in itens
        ]
    )

    # Timeline
    TimelineRequisicao.objects.create(
        requisicao=requisicao,
        evento=EventoTimeline.CRIACAO,
        ator=ator,
        estado_resultante=EstadoRequisicao.RASCUNHO,
    )

    return requisicao


# ---------------------------------------------------------------------------
# TR-002: editar rascunho
# ---------------------------------------------------------------------------


@transaction.atomic
def editar_rascunho(
    *,
    ator_id: int,
    requisicao_id: int,
    itens: list[ItemInput],
    observacao_geral: str = '',
) -> Requisicao:
    """Edita itens e observação de um rascunho existente.

    TR-002: RASCUNHO → RASCUNHO.
    Beneficiário, setor e criador são imutáveis nesta operação.
    """
    try:
        ator = User.objects.get(pk=ator_id)
    except User.DoesNotExist:
        raise DadosInvalidos(
            'Ator não encontrado.', code='ator_nao_encontrado'
        ) from None
    try:
        requisicao = Requisicao.objects.select_for_update().get(pk=requisicao_id)
    except Requisicao.DoesNotExist:
        raise DadosInvalidos(
            'Requisição não encontrada.', code='requisicao_nao_encontrada'
        ) from None

    # Autorização
    exigir_pode_editar_rascunho(ator, requisicao)

    # Valida transição de estado
    verificar_transicao_valida(requisicao.estado, EstadoRequisicao.RASCUNHO)

    # Validar itens
    if not itens:
        raise DadosInvalidos(
            'A requisição precisa ter ao menos um item.',
            code='sem_itens',
        )

    _validar_itens(itens)

    # Substituir itens atomicamente
    requisicao.itens.all().delete()
    ItemRequisicao.objects.bulk_create(
        [
            ItemRequisicao(
                requisicao=requisicao,
                material_id=item['material_id'],
                quantidade_solicitada=item['quantidade_solicitada'],
            )
            for item in itens
        ]
    )

    # Atualizar campos editáveis
    requisicao.observacao_geral = observacao_geral
    requisicao.save(update_fields=['observacao_geral', 'atualizado_em'])

    return requisicao


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# TR-005: enviar rascunho para autorização
# ---------------------------------------------------------------------------


@transaction.atomic
def enviar_para_autorizacao(
    *,
    ator_id: int,
    requisicao_id: int,
) -> Requisicao:
    """Envia um rascunho para autorização (TR-005).

    RASCUNHO → AGUARDANDO_AUTORIZACAO.

    No primeiro envio emite ``REQ-AAAA-NNNNNN`` via SequenciaRequisicao sob
    lock (ADR-0003). Reenvio de rascunho retornado preserva o número público
    (REQ-04). Não reserva nem baixa estoque (TR-005, EST-02).
    """
    try:
        ator = User.objects.get(pk=ator_id)
    except User.DoesNotExist:
        raise DadosInvalidos(
            'Ator não encontrado.', code='ator_nao_encontrado'
        ) from None
    try:
        requisicao = Requisicao.objects.select_for_update().get(pk=requisicao_id)
    except Requisicao.DoesNotExist:
        raise DadosInvalidos(
            'Requisição não encontrada.', code='requisicao_nao_encontrada'
        ) from None

    exigir_pode_enviar_rascunho(ator, requisicao)

    verificar_transicao_valida(
        requisicao.estado, EstadoRequisicao.AGUARDANDO_AUTORIZACAO
    )

    if not requisicao.itens.exists():
        raise DadosInvalidos(
            'A requisição precisa ter ao menos um item para ser enviada.',
            code='sem_itens',
        )

    if requisicao.numero_publico is None:
        ano = timezone.now().year
        sequencia, _ = SequenciaRequisicao.objects.select_for_update().get_or_create(
            ano=ano
        )
        sequencia.ultimo_numero += 1
        sequencia.save(update_fields=['ultimo_numero'])
        requisicao.numero_publico = f'REQ-{ano}-{sequencia.ultimo_numero:06d}'

    requisicao.estado = EstadoRequisicao.AGUARDANDO_AUTORIZACAO
    requisicao.save(update_fields=['estado', 'numero_publico', 'atualizado_em'])

    TimelineRequisicao.objects.create(
        requisicao=requisicao,
        evento=EventoTimeline.ENVIO_AUTORIZACAO,
        ator=ator,
        estado_resultante=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
    )

    return requisicao


def _validar_itens(itens: list[ItemInput]) -> None:
    """Valida elegibilidade e quantidade de cada item.

    Lança DadosInvalidos para qualquer item inválido.
    """
    material_ids: list[int] = []
    for item in itens:
        if (
            not isinstance(item, dict)
            or 'material_id' not in item
            or 'quantidade_solicitada' not in item
        ):
            raise DadosInvalidos(
                'Item inválido: material e quantidade são obrigatórios.',
                code='item_invalido',
            )
        material_ids.append(item['material_id'])

    # Detectar duplicidade
    if len(material_ids) != len(set(material_ids)):
        raise DadosInvalidos(
            'A requisição não pode ter o mesmo material mais de uma vez.',
            code='material_duplicado',
        )

    materiais = {m.pk: m for m in Material.objects.filter(pk__in=material_ids)}

    for item in itens:
        material = materiais.get(item['material_id'])
        if material is None:
            raise DadosInvalidos(
                'Material não encontrado.',
                code='material_nao_encontrado',
            )

        try:
            quantidade = Decimal(str(item['quantidade_solicitada']))
        except (InvalidOperation, ValueError, TypeError):
            raise DadosInvalidos(
                f"Quantidade solicitada de '{material.nome}' é inválida.",
                code='quantidade_invalida',
            )
        if quantidade <= 0:
            raise DadosInvalidos(
                f"Quantidade solicitada de '{material.nome}' deve ser maior que zero.",
                code='quantidade_invalida',
            )

        if not material.ativo:
            raise DadosInvalidos(
                f"Material '{material.nome}' está inativo e não pode ser requisitado.",
                code='material_inativo',
            )

        if not material_eh_elegivel(material):
            raise DadosInvalidos(
                f"Material '{material.nome}' não tem saldo disponível ou possui divergência crítica.",
                code='material_sem_saldo',
            )
