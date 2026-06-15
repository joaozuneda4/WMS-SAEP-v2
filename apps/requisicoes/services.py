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
from typing import TYPE_CHECKING, TypedDict

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.core.exceptions import ConflitoDominio, DadosInvalidos, EstadoInvalido
from apps.estoque.models import Material, SaldoEstoque, TipoMovimentacaoEstoque
from apps.estoque.selectors import entregue_liquida_por_item
from apps.estoque.services import (
    ItemAtendimentoSaldo,
    ItemLiberacaoReserva,
    OrigemMovimentacaoEstoque,
    _registrar_movimentacao,
    liberar_reservas_para_cancelamento,
    consumir_e_liberar_reservas_para_atendimento,
    reservar_saldos_para_autorizacao,
)
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
    exigir_pode_cancelar_requisicao,
    exigir_pode_copiar_requisicao,
    exigir_pode_criar_para_beneficiario,
    exigir_pode_editar_rascunho,
    exigir_pode_enviar_rascunho,
    exigir_pode_recusar_requisicao,
    exigir_pode_retornar_para_rascunho,
    exigir_pode_atender_retirada,
    exigir_pode_registrar_devolucao,
    exigir_pode_separar_para_retirada,
    pode_ser_beneficiario,
)
from apps.requisicoes.selectors import material_eh_elegivel
from apps.requisicoes.transitions import verificar_transicao_valida

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Tipos auxiliares
# ---------------------------------------------------------------------------


class ItemInput(TypedDict):
    material_id: int
    quantidade_solicitada: Decimal


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


# ---------------------------------------------------------------------------
# TR-003 / TR-004: descarte e cancelamento de rascunho
# ---------------------------------------------------------------------------


def _descartar_rascunho_impl(
    *,
    requisicao: Requisicao,
    ator_id: int,
    justificativa: str | None = None,
) -> None:
    try:
        ator = User.objects.get(pk=ator_id)
    except User.DoesNotExist:
        raise DadosInvalidos(
            'Ator não encontrado.', code='ator_nao_encontrado'
        ) from None

    if requisicao.estado != EstadoRequisicao.RASCUNHO:
        raise EstadoInvalido(
            'Esta requisição não está em rascunho.',
            code='estado_origem_invalido',
        )
    if requisicao.numero_publico is not None:
        raise EstadoInvalido(
            'Este rascunho já foi enviado e não pode ser descartado.',
            code='estado_origem_invalido',
        )

    exigir_pode_cancelar_requisicao(ator, requisicao)
    requisicao.delete()


@transaction.atomic
def descartar_rascunho(*, ator_id: int, requisicao_id: int) -> None:
    """Descarta rascunho nunca enviado sem registrar timeline (TR-003)."""
    try:
        requisicao = Requisicao.objects.select_for_update().get(pk=requisicao_id)
    except Requisicao.DoesNotExist:
        raise DadosInvalidos(
            'Requisição não encontrada.', code='requisicao_nao_encontrada'
        ) from None

    _descartar_rascunho_impl(requisicao=requisicao, ator_id=ator_id)


@transaction.atomic
def cancelar_ou_descartar_requisicao(
    *,
    ator_id: int,
    requisicao_id: int,
    justificativa: str | None = None,
) -> Requisicao | None:
    """Cancela ou descarta requisição antes da retirada final."""
    try:
        requisicao = Requisicao.objects.select_for_update().get(pk=requisicao_id)
    except Requisicao.DoesNotExist:
        raise DadosInvalidos(
            'Requisição não encontrada.', code='requisicao_nao_encontrada'
        ) from None

    if (
        requisicao.estado == EstadoRequisicao.RASCUNHO
        and requisicao.numero_publico is None
    ):
        _descartar_rascunho_impl(
            requisicao=requisicao,
            ator_id=ator_id,
            justificativa=justificativa,
        )
        return None

    justificativa_cancelamento = (
        ''
        if requisicao.estado == EstadoRequisicao.AGUARDANDO_AUTORIZACAO
        else justificativa or ''
    )

    return _cancelar_requisicao_impl(
        requisicao=requisicao,
        ator_id=ator_id,
        justificativa=justificativa_cancelamento,
    )


def _cancelar_requisicao_impl(
    *,
    requisicao: Requisicao,
    ator_id: int,
    justificativa: str | None = None,
) -> Requisicao:
    try:
        ator = User.objects.get(pk=ator_id)
    except User.DoesNotExist:
        raise DadosInvalidos(
            'Ator não encontrado.', code='ator_nao_encontrado'
        ) from None

    if requisicao.estado not in (
        EstadoRequisicao.RASCUNHO,
        EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        EstadoRequisicao.AUTORIZADA,
        EstadoRequisicao.PRONTA_PARA_RETIRADA,
    ):
        raise EstadoInvalido(
            'Esta requisição não pode ser cancelada.',
            code='estado_origem_invalido',
        )

    exigir_pode_cancelar_requisicao(ator, requisicao)

    justificativa_limpa = (justificativa or '').strip()

    if requisicao.estado == EstadoRequisicao.RASCUNHO:
        if requisicao.numero_publico is None:
            raise EstadoInvalido(
                'Este rascunho ainda não foi enviado e deve ser descartado.',
                code='estado_origem_invalido',
            )
        verificar_transicao_valida(requisicao.estado, EstadoRequisicao.CANCELADA)
        requisicao.estado = EstadoRequisicao.CANCELADA
        requisicao.save(update_fields=['estado', 'atualizado_em'])

        TimelineRequisicao.objects.create(
            requisicao=requisicao,
            evento=EventoTimeline.CANCELAMENTO,
            ator=ator,
            estado_resultante=EstadoRequisicao.CANCELADA,
            justificativa='',
        )

        return requisicao

    if requisicao.estado == EstadoRequisicao.AGUARDANDO_AUTORIZACAO:
        verificar_transicao_valida(requisicao.estado, EstadoRequisicao.CANCELADA)
        requisicao.estado = EstadoRequisicao.CANCELADA
        requisicao.save(update_fields=['estado', 'atualizado_em'])

        TimelineRequisicao.objects.create(
            requisicao=requisicao,
            evento=EventoTimeline.CANCELAMENTO,
            ator=ator,
            estado_resultante=EstadoRequisicao.CANCELADA,
            justificativa=justificativa_limpa,
        )

        return requisicao

    if not justificativa_limpa:
        raise DadosInvalidos(
            'Informe a justificativa do cancelamento.',
            code='justificativa_cancelamento_obrigatoria',
        )

    if requisicao.estado not in (
        EstadoRequisicao.AUTORIZADA,
        EstadoRequisicao.PRONTA_PARA_RETIRADA,
    ):
        raise EstadoInvalido(
            'Esta requisição não pode ser cancelada.',
            code='estado_origem_invalido',
        )
    verificar_transicao_valida(requisicao.estado, EstadoRequisicao.CANCELADA)

    itens_reservados = list(
        requisicao.itens.select_related('material')
        .filter(quantidade_autorizada__gt=0)
        .order_by('id')
    )
    if not itens_reservados:
        raise DadosInvalidos(
            'A requisição precisa ter itens autorizados para ser cancelada.',
            code='sem_itens_autorizados',
        )

    itens_liberacao: list[ItemLiberacaoReserva] = []
    for item in itens_reservados:
        quantidade_autorizada = item.quantidade_autorizada
        assert quantidade_autorizada is not None
        itens_liberacao.append(
            {
                'material_id': item.material_id,
                'quantidade_reservada': quantidade_autorizada,
            }
        )

    liberar_reservas_para_cancelamento(
        itens=itens_liberacao,
        ator_id=ator.pk,
        origem=OrigemMovimentacaoEstoque.de_requisicao(requisicao),
    )

    requisicao.estado = EstadoRequisicao.CANCELADA
    requisicao.save(update_fields=['estado', 'atualizado_em'])

    TimelineRequisicao.objects.create(
        requisicao=requisicao,
        evento=EventoTimeline.CANCELAMENTO,
        ator=ator,
        estado_resultante=EstadoRequisicao.CANCELADA,
        justificativa=justificativa_limpa,
        metadata={'liberou_reserva': True},
    )

    return requisicao


@transaction.atomic
def cancelar_requisicao(
    *,
    ator_id: int,
    requisicao_id: int,
    justificativa: str = '',
) -> Requisicao:
    """Cancela requisição antes da retirada final (TR-004/TR-012/TR-013/TR-014)."""
    try:
        requisicao = Requisicao.objects.select_for_update().get(pk=requisicao_id)
    except Requisicao.DoesNotExist:
        raise DadosInvalidos(
            'Requisição não encontrada.', code='requisicao_nao_encontrada'
        ) from None

    justificativa_cancelamento = (
        ''
        if requisicao.estado == EstadoRequisicao.AGUARDANDO_AUTORIZACAO
        else justificativa
    )

    return _cancelar_requisicao_impl(
        requisicao=requisicao,
        ator_id=ator_id,
        justificativa=justificativa_cancelamento,
    )


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

    return requisicao


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

    return requisicao


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

    exigir_pode_separar_para_retirada(ator, requisicao)

    if requisicao.estado != EstadoRequisicao.AUTORIZADA:
        raise EstadoInvalido(
            'Esta requisição não está autorizada para separação.',
            code='estado_origem_invalido',
        )
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

    verificar_transicao_valida(requisicao.estado, EstadoRequisicao.PRONTA_PARA_RETIRADA)

    requisicao.estado = EstadoRequisicao.PRONTA_PARA_RETIRADA
    requisicao.save(update_fields=['estado', 'atualizado_em'])

    TimelineRequisicao.objects.create(
        requisicao=requisicao,
        evento=EventoTimeline.SEPARACAO_RETIRADA,
        ator=ator,
        estado_resultante=EstadoRequisicao.PRONTA_PARA_RETIRADA,
    )

    return requisicao


class ItemAtendimentoEntrada(TypedDict):
    item_id: int
    quantidade_entregue: Decimal
    justificativa: str


@transaction.atomic
def registrar_atendimento(
    *,
    ator_id: int,
    requisicao_id: int,
    itens: list[ItemAtendimentoEntrada],
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
    exigir_pode_atender_retirada(ator, requisicao)
    verificar_transicao_valida(requisicao.estado, EstadoRequisicao.ATENDIDA)

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

    payload_por_item: dict[int, ItemAtendimentoEntrada] = {}
    for entrada in itens:
        try:
            item_id = int(entrada['item_id'])
            entregue = Decimal(str(entrada['quantidade_entregue']))
        except (KeyError, TypeError, InvalidOperation, ValueError) as exc:
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
        payload_por_item[item_id] = {
            'item_id': item_id,
            'quantidade_entregue': entregue,
            'justificativa': str(entrada.get('justificativa') or '').strip(),
        }

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
        entregue = entrada['quantidade_entregue']
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
            if not entrada['justificativa']:
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
                'quantidade_entregue': payload_por_item[item.id]['quantidade_entregue'],
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
        item.quantidade_entregue = entrada['quantidade_entregue']
        item.justificativa_entrega = (
            entrada['justificativa']
            if entrada['quantidade_entregue'] < autorizada
            else ''
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

    return requisicao


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

    exigir_pode_registrar_devolucao(ator, requisicao)
    verificar_transicao_valida(requisicao.estado, EstadoRequisicao.ATENDIDA)

    if quantidade <= 0:
        raise DadosInvalidos(
            'A quantidade devolvida deve ser maior que zero.',
            code='quantidade_invalida',
        )

    entregue_liquida = entregue_liquida_por_item(
        requisicao_id=requisicao_id, item_id=item_id
    )
    if quantidade > entregue_liquida:
        raise ConflitoDominio(
            'A quantidade devolvida excede a entregue líquida do item.',
            code='quantidade_excede_entregue_liquida',
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

    saldos = list(
        SaldoEstoque.objects.select_for_update()
        .select_related('material')
        .filter(material_id=item.material_id)
        .order_by('estoque_id', 'id')
    )
    if not saldos:
        raise ConflitoDominio(
            'Saldo de estoque não encontrado para o material.',
            code='saldo_nao_encontrado',
        )
    if len(saldos) > 1:
        raise ConflitoDominio(
            f"Mais de um saldo encontrado para o material '{saldos[0].material.nome}'.",
            code='saldo_ambiguo',
        )
    saldo = saldos[0]

    if not saldo.material.ativo:
        raise ConflitoDominio(
            f"Material '{saldo.material.nome}' está inativo.",
            code='material_inativo',
        )

    saldo.saldo_fisico = saldo.saldo_fisico + quantidade
    saldo.save(update_fields=['saldo_fisico'])

    origem = OrigemMovimentacaoEstoque.de_requisicao(requisicao)
    _registrar_movimentacao(
        tipo=TipoMovimentacaoEstoque.DEVOLUCAO,
        material_id=item.material_id,
        estoque_id=saldo.estoque_id,
        delta_fisico=quantidade,
        delta_reservado=Decimal('0'),
        origem=origem,
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


# ---------------------------------------------------------------------------
# REQ-09: copiar requisição
# ---------------------------------------------------------------------------


@transaction.atomic
def copiar_requisicao(
    *,
    ator_id: int,
    requisicao_id: int,
) -> Requisicao:
    """Cria rascunho copiando todos os itens de requisição atendida ou recusada.

    REQ-09: não copia quantidade_autorizada nem quantidade_entregue.
    Itens inelegíveis são incluídos — elegibilidade é validada no envio (TR-005).
    """
    try:
        ator = User.objects.get(pk=ator_id)
    except User.DoesNotExist:
        raise DadosInvalidos('Ator não encontrado.', code='ator_nao_encontrado')

    try:
        origem = (
            Requisicao.objects.select_for_update(of=('self',))
            .select_related('beneficiario__setor', 'setor_beneficiario')
            .get(pk=requisicao_id)
        )
    except Requisicao.DoesNotExist:
        raise DadosInvalidos(
            'Requisição não encontrada.', code='requisicao_nao_encontrada'
        )

    estados_copiavel = {EstadoRequisicao.ATENDIDA, EstadoRequisicao.RECUSADA}
    if origem.estado not in estados_copiavel:
        raise EstadoInvalido(
            'Só é possível copiar requisições atendidas ou recusadas.',
            code='estado_invalido',
        )

    exigir_pode_copiar_requisicao(ator, origem)

    beneficiario = origem.beneficiario
    if not pode_ser_beneficiario(beneficiario):
        raise DadosInvalidos(
            f'{beneficiario.nome} não pode ser beneficiário: usuário inativo ou sem setor.',
            code='beneficiario_inelegivel',
        )

    setor_beneficiario = beneficiario.setor
    assert setor_beneficiario is not None

    itens_origem = list(origem.itens.all())
    if not itens_origem:
        raise DadosInvalidos(
            'A requisição de origem não possui itens.',
            code='sem_itens',
        )

    novo_rascunho = Requisicao.objects.create(
        estado=EstadoRequisicao.RASCUNHO,
        numero_publico=None,
        criador=ator,
        beneficiario=beneficiario,
        setor_beneficiario=setor_beneficiario,
        observacao_geral=origem.observacao_geral,
    )

    ItemRequisicao.objects.bulk_create(
        [
            ItemRequisicao(
                requisicao=novo_rascunho,
                material_id=item.material_id,
                quantidade_solicitada=item.quantidade_solicitada,
            )
            for item in itens_origem
        ]
    )

    TimelineRequisicao.objects.create(
        requisicao=novo_rascunho,
        evento=EventoTimeline.CRIACAO,
        ator=ator,
        estado_resultante=EstadoRequisicao.RASCUNHO,
    )

    return novo_rascunho
