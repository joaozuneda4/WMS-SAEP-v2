"""Services de ciclo de vida das requisições.

Transições de estado: criação, edição, envio, retorno, recusa, autorização e estorno.
"""

from __future__ import annotations

import logging

from decimal import Decimal, InvalidOperation
from typing import TypedDict

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.accounts.models import User
from apps.core.exceptions import DadosInvalidos, EstadoInvalido
from apps.estoque.models import Material, SaldoEstoque
from apps.estoque.services import (
    OrigemMovimentacaoEstoque,
    estornar_requisicao_estoque,
    reservar_saldos_para_autorizacao,
)
from apps.notificacoes.models import TipoNotificacao
from apps.notificacoes.services import criar_notificacoes_para
from apps.requisicoes.models import (
    EstadoRequisicao,
    EventoTimeline,
    ItemRequisicao,
    Requisicao,
    SequenciaRequisicao,
    TimelineRequisicao,
)
from apps.requisicoes.policies import (
    exigir_pode_autorizar_requisicao,
    exigir_pode_criar_para_beneficiario,
    exigir_pode_editar_rascunho,
    exigir_pode_enviar_rascunho,
    exigir_pode_estornar_requisicao,
    exigir_pode_recusar_requisicao,
    exigir_pode_retornar_para_rascunho,
    pode_ser_beneficiario,
)
from apps.requisicoes.selectors import material_eh_elegivel
from apps.requisicoes.transitions import verificar_transicao_valida

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers internos — notificações pós-commit
# ---------------------------------------------------------------------------


def _notificar_pos_commit(
    criador_id: int, beneficiario_id: int, req_id: int, tipo: str
) -> None:
    try:
        criar_notificacoes_para(
            criador_id=criador_id,
            beneficiario_id=beneficiario_id,
            requisicao_id=req_id,
            tipo=tipo,
        )
    except Exception:
        logger.exception(
            'Falha ao criar notificações pós-commit: tipo=%s requisicao_id=%s',
            tipo,
            req_id,
        )


# ---------------------------------------------------------------------------
# Tipos auxiliares
# ---------------------------------------------------------------------------


class ItemInput(TypedDict):
    material_id: int
    quantidade_solicitada: Decimal


# ---------------------------------------------------------------------------
# Helpers internos — validação de itens
# ---------------------------------------------------------------------------


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
        if not quantidade.is_finite() or quantidade <= 0:
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
    if requisicao.estado != EstadoRequisicao.RASCUNHO:
        raise EstadoInvalido(
            'Esta requisição não está em rascunho.',
            code='estado_origem_invalido',
        )
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

    itens_envio = list(requisicao.itens.values('material_id', 'quantidade_solicitada'))
    if not itens_envio:
        raise DadosInvalidos(
            'A requisição precisa ter ao menos um item para ser enviada.',
            code='sem_itens',
        )
    _validar_itens(itens_envio)

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


# ---------------------------------------------------------------------------
# TR-006: retornar para rascunho
# ---------------------------------------------------------------------------


@transaction.atomic
def retornar_para_rascunho(
    *,
    ator_id: int,
    requisicao_id: int,
    observacao: str = '',
) -> Requisicao:
    """Retorna requisição aguardando autorização para rascunho (TR-006)."""
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

    exigir_pode_retornar_para_rascunho(ator, requisicao)
    if requisicao.estado != EstadoRequisicao.AGUARDANDO_AUTORIZACAO:
        raise EstadoInvalido(
            'Esta requisição não está aguardando autorização.',
            code='estado_origem_invalido',
        )
    verificar_transicao_valida(requisicao.estado, EstadoRequisicao.RASCUNHO)

    requisicao.estado = EstadoRequisicao.RASCUNHO
    requisicao.save(update_fields=['estado', 'atualizado_em'])

    TimelineRequisicao.objects.create(
        requisicao=requisicao,
        evento=EventoTimeline.RETORNO_RASCUNHO,
        ator=ator,
        estado_resultante=EstadoRequisicao.RASCUNHO,
        justificativa=(observacao or '').strip(),
    )

    return requisicao


# ---------------------------------------------------------------------------
# TR-011: recusar requisição
# ---------------------------------------------------------------------------


@transaction.atomic
def recusar_requisicao(
    *,
    ator_id: int,
    requisicao_id: int,
    motivo: str,
) -> Requisicao:
    """Recusa integralmente uma requisição aguardando autorização (TR-011)."""
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

    exigir_pode_recusar_requisicao(ator, requisicao)
    verificar_transicao_valida(requisicao.estado, EstadoRequisicao.RECUSADA)

    motivo_limpo = (motivo or '').strip()
    if not motivo_limpo:
        raise DadosInvalidos(
            'Informe o motivo da recusa.',
            code='motivo_recusa_obrigatorio',
        )

    requisicao.estado = EstadoRequisicao.RECUSADA
    requisicao.save(update_fields=['estado', 'atualizado_em'])

    TimelineRequisicao.objects.create(
        requisicao=requisicao,
        evento=EventoTimeline.RECUSA,
        ator=ator,
        estado_resultante=EstadoRequisicao.RECUSADA,
        justificativa=motivo_limpo,
    )

    _criador_id = requisicao.criador_id
    _beneficiario_id = requisicao.beneficiario_id
    _req_id = requisicao.pk
    transaction.on_commit(
        lambda: _notificar_pos_commit(
            _criador_id, _beneficiario_id, _req_id, TipoNotificacao.RECUSA
        )
    )

    return requisicao


# ---------------------------------------------------------------------------
# TR-008: autorizar requisição
# ---------------------------------------------------------------------------


@transaction.atomic
def autorizar_requisicao(
    *,
    ator_id: int,
    requisicao_id: int,
) -> Requisicao:
    """Autoriza integralmente uma requisição aguardando autorização.

    TR-008: AGUARDANDO_AUTORIZACAO -> AUTORIZADA.
    Reserva saldo integral sem baixa física. Quando o ator é o beneficiário,
    o evento de timeline recebe ``metadata["auto_autorizacao"] = true``.
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

    exigir_pode_autorizar_requisicao(ator, requisicao)

    if requisicao.estado != EstadoRequisicao.AGUARDANDO_AUTORIZACAO:
        raise EstadoInvalido(
            'Esta requisição não está aguardando autorização.',
            code='estado_origem_invalido',
        )
    verificar_transicao_valida(requisicao.estado, EstadoRequisicao.AUTORIZADA)

    itens = list(requisicao.itens.select_related('material').order_by('id'))
    if not itens:
        raise DadosInvalidos(
            'A requisição precisa ter ao menos um item para ser autorizada.',
            code='sem_itens',
        )
    _validar_itens(
        [
            {
                'material_id': item.material_id,
                'quantidade_solicitada': item.quantidade_solicitada,
            }
            for item in itens
        ]
    )

    reservar_saldos_para_autorizacao(
        itens=[
            {
                'material_id': item.material_id,
                'quantidade_solicitada': item.quantidade_solicitada,
            }
            for item in itens
        ],
        ator_id=ator.pk,
        origem=OrigemMovimentacaoEstoque.de_requisicao(requisicao),
    )

    for item in itens:
        item.quantidade_autorizada = item.quantidade_solicitada
        item.save(update_fields=['quantidade_autorizada'])

    requisicao.estado = EstadoRequisicao.AUTORIZADA
    requisicao.save(update_fields=['estado', 'atualizado_em'])

    metadata: dict[str, object] = {}
    if ator.pk == requisicao.beneficiario_id:
        metadata['auto_autorizacao'] = True

    TimelineRequisicao.objects.create(
        requisicao=requisicao,
        evento=EventoTimeline.AUTORIZACAO_TOTAL,
        ator=ator,
        estado_resultante=EstadoRequisicao.AUTORIZADA,
        metadata=metadata,
    )

    _criador_id = requisicao.criador_id
    _beneficiario_id = requisicao.beneficiario_id
    _req_id = requisicao.pk
    transaction.on_commit(
        lambda: _notificar_pos_commit(
            _criador_id, _beneficiario_id, _req_id, TipoNotificacao.AUTORIZACAO
        )
    )

    return requisicao


# ---------------------------------------------------------------------------
# TR-021: estornar requisição
# ---------------------------------------------------------------------------


@transaction.atomic
def estornar_requisicao(
    *,
    ator_id: int,
    requisicao_id: int,
    justificativa: str,
) -> Requisicao:
    """Estorna requisição atendida, revertendo entregue líquida ao saldo físico (TR-021).

    ATENDIDA → ESTORNADA. Emite MovimentacaoEstoque(tipo=estorno_requisicao) por item
    com entregue_liquida > 0 + TimelineRequisicao(ESTORNO).
    Lock: Requisicao primeiro, depois SaldoEstoque em ordem crescente (ADR-0005, EST-06).
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

    exigir_pode_estornar_requisicao(ator, requisicao)

    if requisicao.estado != EstadoRequisicao.ATENDIDA:
        raise EstadoInvalido(
            'Estorno só pode ser registrado em requisição atendida.',
            code='estado_origem_invalido',
        )

    verificar_transicao_valida(requisicao.estado, EstadoRequisicao.ESTORNADA)

    justificativa_limpa = (justificativa or '').strip()
    if not justificativa_limpa:
        raise DadosInvalidos(
            'A justificativa de estorno é obrigatória.',
            code='justificativa_vazia',
        )

    itens = list(requisicao.itens.values_list('material_id', flat=True))
    estornar_requisicao_estoque(
        requisicao_id=requisicao_id,
        material_ids=list(itens),
        ator_id=ator_id,
    )

    requisicao.estado = EstadoRequisicao.ESTORNADA
    requisicao.save(update_fields=['estado', 'atualizado_em'])

    TimelineRequisicao.objects.create(
        requisicao=requisicao,
        evento=EventoTimeline.ESTORNO,
        ator=ator,
        estado_resultante=EstadoRequisicao.ESTORNADA,
        metadata={'justificativa': justificativa_limpa},
    )

    return requisicao


def registrar_timeline_divergencia_importacao(
    *, linhas, estoque, importacao, ator
) -> None:
    """Cria TimelineRequisicao para requisições autorizadas afetadas por divergência crítica.

    Chamado como hook por confirmar_importacao_scpi dentro da mesma transação.
    Divergência crítica = saldo_fisico < saldo_reservado após importação SCPI.
    """
    existing_material_ids = [
        linha.material_id for linha in linhas if linha.material_id is not None
    ]
    if not existing_material_ids:
        return

    saldos_criticos = {
        s.material_id: s
        for s in SaldoEstoque.objects.filter(
            material_id__in=existing_material_ids,
            estoque=estoque,
            saldo_fisico__lt=F('saldo_reservado'),
        )
        .select_for_update()
        .order_by('estoque_id', 'material_id', 'id')
        .only('material_id', 'saldo_fisico', 'saldo_reservado')
    }
    if not saldos_criticos:
        return

    material_info = {
        linha.material_id: {
            'codigo': linha.cadpro,
            'nome': linha.nome_material or linha.denominacao_scpi,
        }
        for linha in linhas
        if linha.material_id in saldos_criticos
    }

    itens = list(
        ItemRequisicao.objects.filter(
            material_id__in=saldos_criticos.keys(),
            requisicao__estado=EstadoRequisicao.AUTORIZADA,
            quantidade_autorizada__gt=0,
        ).select_related('requisicao')
    )
    if not itens:
        return

    req_materiais: dict[int, list[dict]] = {}
    for item in itens:
        req_id = item.requisicao_id
        if req_id not in req_materiais:
            req_materiais[req_id] = []
        req_materiais[req_id].append(material_info[item.material_id])

    req_por_id = {item.requisicao_id: item.requisicao for item in itens}

    TimelineRequisicao.objects.bulk_create(
        [
            TimelineRequisicao(
                requisicao=req_por_id[req_id],
                evento=EventoTimeline.ATUALIZACAO_ESTOQUE_RELEVANTE,
                ator=ator,
                estado_resultante=None,
                metadata={
                    'importacao_id': importacao.pk,
                    'materiais': mats,
                },
            )
            for req_id, mats in req_materiais.items()
        ]
    )

    _snapshot = [
        (req.pk, req.criador_id, req.beneficiario_id) for req in req_por_id.values()
    ]

    def _notificar_divergencia():
        for req_pk, criador_id, beneficiario_id in _snapshot:
            try:
                criar_notificacoes_para(
                    criador_id=criador_id,
                    beneficiario_id=beneficiario_id,
                    requisicao_id=req_pk,
                    tipo=TipoNotificacao.DIVERGENCIA_ESTOQUE,
                )
            except Exception:
                logger.exception(
                    'Falha ao criar notificação de divergência pós-commit: requisicao_id=%s',
                    req_pk,
                )

    transaction.on_commit(_notificar_divergencia)
