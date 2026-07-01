"""Services de atendimento de requisições.

Separação para retirada, registro de atendimento e devolução.
"""

from __future__ import annotations

import logging

from decimal import Decimal, InvalidOperation

from django.db import transaction

from apps.accounts.models import User
from apps.accounts.papeis import papel_efetivo
from apps.core.exceptions import DadosInvalidos, EstadoInvalido
from apps.estoque.models import SaldoEstoque
from apps.estoque.services import (
    OrigemMovimentacaoEstoque,
    consumir_e_liberar_reservas_para_atendimento,
    registrar_devolucao_estoque,
)
from apps.estoque.types import ItemAtendimentoSaldo
from apps.notificacoes.models import TipoNotificacao
from apps.notificacoes.services import criar_notificacoes_para
from apps.requisicoes.models import (
    EstadoRequisicao,
    EventoTimeline,
    ItemRequisicao,
    Operacao,
    Requisicao,
    TimelineRequisicao,
)
from apps.requisicoes.policies import (
    exigir_pode_atender_retirada,
    exigir_pode_registrar_devolucao,
    exigir_pode_separar_para_retirada,
)
from apps.requisicoes.transitions import verificar_transicao_valida
from apps.requisicoes.types import LinhaAtendimento

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
# TR-015/TR-015B: separar para retirada
# ---------------------------------------------------------------------------


@transaction.atomic
def separar_para_retirada(
    *,
    ator_id: int,
    requisicao_id: int,
) -> Requisicao:
    """Separa para retirada uma requisição já autorizada (TR-015/TR-015B).

    AUTORIZADA -> PRONTA_PARA_RETIRADA. Mantém o saldo reservado da
    autorização e não toca em saldo físico.

    TR-015B: bloqueia se qualquer item autorizado tiver divergência crítica
    (saldo_fisico < saldo_reservado) ou físico insuficiente para a operação.
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

    papel = papel_efetivo(ator)
    exigir_pode_separar_para_retirada(papel, requisicao)

    if requisicao.estado != EstadoRequisicao.AUTORIZADA:
        raise EstadoInvalido(
            'Esta requisição não está autorizada para separação.',
            code='estado_origem_invalido',
        )
    verificar_transicao_valida(Operacao.SEPARAR_PARA_RETIRADA, requisicao)
    if not requisicao.itens.filter(quantidade_autorizada__gt=0).exists():
        raise EstadoInvalido(
            'Esta requisição não possui itens com quantidade autorizada.',
            code='itens_autorizados_insuficientes',
        )

    itens_autorizados = list(
        requisicao.itens.filter(quantidade_autorizada__gt=0)
        .select_related('material')
        .order_by('id')
    )
    material_ids = [item.material_id for item in itens_autorizados]

    saldos_agrupados: dict[int, list[SaldoEstoque]] = {}
    for saldo in (
        SaldoEstoque.objects.select_for_update()
        .filter(material_id__in=material_ids)
        .order_by('estoque_id', 'material_id', 'id')
    ):
        saldos_agrupados.setdefault(saldo.material_id, []).append(saldo)

    for item in itens_autorizados:
        saldos_do_material = saldos_agrupados.get(item.material_id)
        if not saldos_do_material:
            raise DadosInvalidos(
                f"Saldo de estoque não encontrado para '{item.material.nome}'.",
                code='separacao_bloqueada',
            )
        if len(saldos_do_material) > 1:
            raise DadosInvalidos(
                f"Saldo de estoque ambíguo para '{item.material.nome}'. "
                f'Corrija o estoque ou cancele a requisição via TR-013.',
                code='separacao_bloqueada',
            )
        saldo = saldos_do_material[0]
        qty_autorizada = item.quantidade_autorizada
        assert (
            qty_autorizada is not None
        )  # garantido por filter(quantidade_autorizada__gt=0)
        if saldo.divergente or saldo.saldo_fisico < qty_autorizada:
            raise DadosInvalidos(
                f'Estoque insuficiente para separação do material '
                f"'{item.material.nome}'. "
                f'Corrija o estoque ou cancele a requisição via TR-013.',
                code='separacao_bloqueada',
            )

    requisicao.estado = EstadoRequisicao.PRONTA_PARA_RETIRADA
    requisicao.save(update_fields=['estado', 'atualizado_em'])

    TimelineRequisicao.objects.create(
        requisicao=requisicao,
        evento=EventoTimeline.SEPARACAO_RETIRADA,
        ator=ator,
        estado_resultante=EstadoRequisicao.PRONTA_PARA_RETIRADA,
    )

    return requisicao


# ---------------------------------------------------------------------------
# TR-016/TR-017/TR-018: registrar atendimento
# ---------------------------------------------------------------------------


@transaction.atomic
def registrar_atendimento(
    *,
    ator_id: int,
    requisicao_id: int,
    itens: list[LinhaAtendimento],
    retirante_nome: str,
    observacao: str = '',
) -> Requisicao:
    """Registra atendimento total ou parcial (TR-016 / TR-017 / TR-018).

    PRONTA_PARA_RETIRADA -> ATENDIDA. Baixa físico apenas do entregue; consome
    reserva entregue e libera reserva não entregue. Atendimento sem nenhuma
    entrega é bloqueado (TR-018). Entrega menor que autorizada (incluindo
    zero) exige justificativa por item.
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

    if requisicao.estado != EstadoRequisicao.PRONTA_PARA_RETIRADA:
        raise EstadoInvalido(
            'Esta requisição não está pronta para retirada.',
            code='estado_origem_invalido',
        )
    papel = papel_efetivo(ator)
    exigir_pode_atender_retirada(papel, requisicao)
    verificar_transicao_valida(Operacao.REGISTRAR_ATENDIMENTO, requisicao)

    retirante = (retirante_nome or '').strip()
    if not retirante:
        raise DadosInvalidos(
            'Informe o nome do retirante.',
            code='retirante_obrigatorio',
        )

    itens_autorizados = list(
        requisicao.itens.select_related('material')
        .filter(quantidade_autorizada__gt=0)
        .order_by('id')
    )
    if not itens_autorizados:
        raise EstadoInvalido(
            'Esta requisição não possui itens com quantidade autorizada.',
            code='itens_autorizados_insuficientes',
        )

    payload_por_item: dict[int, LinhaAtendimento] = {}
    for entrada in itens:
        try:
            item_id = int(entrada.item_id)
            entregue = Decimal(str(entrada.quantidade_entregue))
        except (AttributeError, TypeError, InvalidOperation, ValueError) as exc:
            raise DadosInvalidos(
                'Item de atendimento inválido.',
                code='item_invalido',
            ) from exc
        if not entregue.is_finite():
            raise DadosInvalidos(
                'Quantidade entregue inválida.',
                code='quantidade_entregue_invalida',
            )
        if item_id in payload_por_item:
            raise DadosInvalidos(
                'Item duplicado no atendimento.',
                code='item_duplicado',
            )
        payload_por_item[item_id] = LinhaAtendimento(
            item_id=item_id,
            quantidade_entregue=entregue,
            justificativa=str(entrada.justificativa or '').strip(),
        )

    ids_autorizados = {item.id for item in itens_autorizados}
    if set(payload_por_item.keys()) != ids_autorizados:
        raise DadosInvalidos(
            'Atendimento deve cobrir exatamente os itens autorizados.',
            code='itens_atendimento_incompletos',
        )

    total_entregue = Decimal('0')
    houve_liberacao = False
    eh_total = True
    for item in itens_autorizados:
        entrada = payload_por_item[item.id]
        entregue = entrada.quantidade_entregue
        autorizada = item.quantidade_autorizada
        assert autorizada is not None  # filtrado por quantidade_autorizada__gt=0
        if entregue < 0 or entregue > autorizada:
            raise DadosInvalidos(
                'Quantidade entregue inválida.',
                code='quantidade_entregue_invalida',
            )
        if entregue < autorizada:
            eh_total = False
            houve_liberacao = True
            if not entrada.justificativa:
                raise DadosInvalidos(
                    'Justificativa obrigatória para entrega menor que autorizada.',
                    code='justificativa_obrigatoria',
                )
        total_entregue += entregue

    if total_entregue == 0:
        raise EstadoInvalido(
            'Atendimento exige ao menos um item entregue maior que zero.',
            code='atendimento_sem_entrega',
        )

    payload_estoque: list[ItemAtendimentoSaldo] = []
    for item in itens_autorizados:
        autorizada = item.quantidade_autorizada
        assert autorizada is not None  # filtrado por quantidade_autorizada__gt=0
        payload_estoque.append(
            {
                'material_id': item.material_id,
                'quantidade_autorizada': autorizada,
                'quantidade_entregue': payload_por_item[item.id].quantidade_entregue,
            }
        )
    consumir_e_liberar_reservas_para_atendimento(
        itens=payload_estoque,
        ator_id=ator.pk,
        origem=OrigemMovimentacaoEstoque.de_requisicao(requisicao),
    )

    for item in itens_autorizados:
        entrada = payload_por_item[item.id]
        autorizada = item.quantidade_autorizada
        assert autorizada is not None  # filtrado por quantidade_autorizada__gt=0
        item.quantidade_entregue = entrada.quantidade_entregue
        item.justificativa_entrega = (
            entrada.justificativa if entrada.quantidade_entregue < autorizada else ''
        )
        item.save(update_fields=['quantidade_entregue', 'justificativa_entrega'])

    requisicao.estado = EstadoRequisicao.ATENDIDA
    requisicao.save(update_fields=['estado', 'atualizado_em'])

    observacao_limpa = (observacao or '').strip()
    metadata_principal: dict[str, object] = {'retirante': retirante}
    if observacao_limpa:
        metadata_principal['observacao'] = observacao_limpa
    if houve_liberacao:
        metadata_principal['liberou_reserva'] = True

    TimelineRequisicao.objects.create(
        requisicao=requisicao,
        evento=(
            EventoTimeline.ATENDIMENTO_TOTAL
            if eh_total
            else EventoTimeline.ATENDIMENTO_PARCIAL
        ),
        ator=ator,
        estado_resultante=EstadoRequisicao.ATENDIDA,
        metadata=metadata_principal,
    )

    if houve_liberacao:
        TimelineRequisicao.objects.create(
            requisicao=requisicao,
            evento=EventoTimeline.LIBERACAO_RESERVA,
            ator=ator,
            estado_resultante=EstadoRequisicao.ATENDIDA,
        )

    _criador_id = requisicao.criador_id
    _beneficiario_id = requisicao.beneficiario_id
    _req_id = requisicao.pk
    transaction.on_commit(
        lambda: _notificar_pos_commit(
            _criador_id, _beneficiario_id, _req_id, TipoNotificacao.ATENDIMENTO
        )
    )

    return requisicao


# ---------------------------------------------------------------------------
# TR-020: registrar devolução
# ---------------------------------------------------------------------------


@transaction.atomic
def registrar_devolucao(
    *,
    ator_id: int,
    requisicao_id: int,
    item_id: int,
    quantidade: Decimal,
    observacao: str = '',
) -> Requisicao:
    """Registra devolução de material vinculada a requisição atendida (TR-020).

    ATENDIDA → ATENDIDA. Incrementa saldo_fisico; não altera estado nem reserva.
    Emite MovimentacaoEstoque(tipo=devolucao) + TimelineRequisicao(DEVOLUCAO_REGISTRADA).
    Lock: Requisicao primeiro, SaldoEstoque depois (ADR-0005, EST-06).
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

    if requisicao.estado != EstadoRequisicao.ATENDIDA:
        raise EstadoInvalido(
            'Devolução só pode ser registrada em requisição atendida.',
            code='estado_origem_invalido',
        )

    papel = papel_efetivo(ator)
    exigir_pode_registrar_devolucao(papel, requisicao)
    verificar_transicao_valida(Operacao.REGISTRAR_DEVOLUCAO, requisicao)

    if quantidade <= 0:
        raise DadosInvalidos(
            'A quantidade devolvida deve ser maior que zero.',
            code='quantidade_invalida',
        )

    try:
        item = ItemRequisicao.objects.select_related('material').get(
            pk=item_id, requisicao=requisicao
        )
    except ItemRequisicao.DoesNotExist:
        raise DadosInvalidos(
            'Item não pertence à requisição informada.',
            code='item_nao_pertence_requisicao',
        ) from None

    registrar_devolucao_estoque(
        requisicao_id=requisicao_id,
        material_id=item.material_id,
        quantidade=quantidade,
        ator_id=ator_id,
    )

    observacao_limpa = (observacao or '').strip()
    metadata: dict[str, object] = {
        'quantidade': str(quantidade),
        'item_id': item_id,
    }
    if observacao_limpa:
        metadata['observacao'] = observacao_limpa

    TimelineRequisicao.objects.create(
        requisicao=requisicao,
        evento=EventoTimeline.DEVOLUCAO_REGISTRADA,
        ator=ator,
        estado_resultante=EstadoRequisicao.ATENDIDA,
        metadata=metadata,
    )

    return requisicao
