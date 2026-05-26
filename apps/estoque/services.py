"""Comandos de domínio de estoque.

Toda mutação de ``SaldoEstoque`` passa por este módulo.
"""

from decimal import Decimal
from typing import TypedDict

from django.db import transaction

from apps.core.exceptions import ConflitoDominio, DadosInvalidos
from apps.estoque.models import SaldoEstoque


class ItemReservaEstoque(TypedDict):
    material_id: int
    quantidade_solicitada: Decimal


@transaction.atomic
def reservar_saldos_para_autorizacao(*, itens: list[ItemReservaEstoque]) -> None:
    """Reserva saldo integral para autorização de requisição.

    ``itens`` deve conter ``material_id`` e ``quantidade_solicitada`` por item.
    A função trava saldos afetados em ordem determinística e só grava após
    validar todos os itens. Se houver mais de um saldo para o mesmo material,
    falha antes de mutar qualquer linha.
    """
    if not itens:
        raise DadosInvalidos(
            'A requisição precisa ter ao menos um item para autorizar.',
            code='sem_itens',
        )

    material_ids: list[int] = []
    quantidade_por_material: dict[int, Decimal] = {}
    for item in itens:
        try:
            material_id = int(item['material_id'])
            quantidade = Decimal(str(item['quantidade_solicitada']))
        except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
            raise DadosInvalidos(
                'Item inválido para reserva de estoque.',
                code='item_invalido',
            ) from exc

        if quantidade <= 0:
            raise DadosInvalidos(
                'Quantidade solicitada deve ser maior que zero.',
                code='quantidade_invalida',
            )

        if material_id in quantidade_por_material:
            quantidade_por_material[material_id] += quantidade
        else:
            material_ids.append(material_id)
            quantidade_por_material[material_id] = quantidade

    saldos = list(
        SaldoEstoque.objects.select_for_update()
        .select_related('estoque', 'material')
        .filter(material_id__in=material_ids)
        .order_by('estoque_id', 'material_id', 'id')
    )

    saldos_por_material: dict[int, list[SaldoEstoque]] = {}
    for saldo in saldos:
        saldos_por_material.setdefault(saldo.material_id, []).append(saldo)

    for material_id, quantidade in quantidade_por_material.items():
        saldos_do_material = saldos_por_material.get(material_id)
        if saldos_do_material is None:
            raise ConflitoDominio(
                'Saldo de estoque não encontrado para um dos materiais.',
                code='saldo_nao_encontrado',
            )
        if len(saldos_do_material) > 1:
            raise ConflitoDominio(
                (
                    f'Mais de um saldo encontrado para o material '
                    f"'{saldos_do_material[0].material.nome}'."
                ),
                code='saldo_ambiguo',
            )
        saldo_existente = saldos_do_material[0]
        if not saldo_existente.material.ativo:
            raise ConflitoDominio(
                f"Material '{saldo_existente.material.nome}' está inativo.",
                code='material_inativo',
            )
        if saldo_existente.divergente:
            raise ConflitoDominio(
                f"Saldo de estoque divergente para '{saldo_existente.material.nome}'.",
                code='saldo_divergente',
            )
        if saldo_existente.saldo_disponivel < quantidade:
            raise ConflitoDominio(
                f"Saldo insuficiente para reservar '{saldo_existente.material.nome}'.",
                code='saldo_insuficiente',
            )

    for material_id, quantidade in quantidade_por_material.items():
        saldo = saldos_por_material[material_id][0]
        saldo.saldo_reservado = saldo.saldo_reservado + quantidade
        saldo.save(update_fields=['saldo_reservado'])


class ItemAtendimentoSaldo(TypedDict):
    material_id: int
    quantidade_autorizada: Decimal
    quantidade_entregue: Decimal


@transaction.atomic
def consumir_e_liberar_reservas_para_atendimento(
    *, itens: list[ItemAtendimentoSaldo]
) -> None:
    """Baixa físico do entregue e libera reserva não entregue (TR-016/TR-017).

    Para cada item:
    - ``saldo_fisico -= quantidade_entregue``
    - ``saldo_reservado -= quantidade_autorizada`` (consome reserva integral
      criada na autorização; a parte ``autorizada - entregue`` corresponde à
      reserva liberada).

    Locks são adquiridos em ordem determinística ``(estoque_id, material_id, id)``.
    Todas as validações ocorrem antes de qualquer mutação.
    """
    if not itens:
        raise DadosInvalidos(
            'Lista de itens vazia para consumo de reserva.',
            code='sem_itens',
        )

    material_ids: list[int] = []
    autorizada_por_material: dict[int, Decimal] = {}
    entregue_por_material: dict[int, Decimal] = {}
    for item in itens:
        try:
            material_id = int(item['material_id'])
            autorizada = Decimal(str(item['quantidade_autorizada']))
            entregue = Decimal(str(item['quantidade_entregue']))
        except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
            raise DadosInvalidos(
                'Item inválido para consumo de reserva.',
                code='item_invalido',
            ) from exc

        if autorizada <= 0:
            raise DadosInvalidos(
                'Quantidade autorizada deve ser maior que zero.',
                code='quantidade_autorizada_invalida',
            )
        if entregue < 0 or entregue > autorizada:
            raise DadosInvalidos(
                'Quantidade entregue inválida.',
                code='quantidade_entregue_invalida',
            )

        if material_id in autorizada_por_material:
            autorizada_por_material[material_id] += autorizada
            entregue_por_material[material_id] += entregue
        else:
            material_ids.append(material_id)
            autorizada_por_material[material_id] = autorizada
            entregue_por_material[material_id] = entregue

    saldos = list(
        SaldoEstoque.objects.select_for_update()
        .select_related('estoque', 'material')
        .filter(material_id__in=material_ids)
        .order_by('estoque_id', 'material_id', 'id')
    )

    saldos_por_material: dict[int, list[SaldoEstoque]] = {}
    for saldo in saldos:
        saldos_por_material.setdefault(saldo.material_id, []).append(saldo)

    for material_id in material_ids:
        saldos_do_material = saldos_por_material.get(material_id)
        if saldos_do_material is None:
            raise ConflitoDominio(
                'Saldo de estoque não encontrado para um dos materiais.',
                code='saldo_nao_encontrado',
            )
        if len(saldos_do_material) > 1:
            raise ConflitoDominio(
                (
                    f'Mais de um saldo encontrado para o material '
                    f"'{saldos_do_material[0].material.nome}'."
                ),
                code='saldo_ambiguo',
            )
        saldo = saldos_do_material[0]
        if not saldo.material.ativo:
            raise ConflitoDominio(
                f"Material '{saldo.material.nome}' está inativo.",
                code='material_inativo',
            )
        entregue = entregue_por_material[material_id]
        autorizada = autorizada_por_material[material_id]
        if saldo.saldo_fisico < entregue:
            raise ConflitoDominio(
                f"Saldo físico insuficiente para entregar '{saldo.material.nome}'.",
                code='saldo_fisico_insuficiente',
            )
        if saldo.saldo_reservado < autorizada:
            raise ConflitoDominio(
                f"Reserva insuficiente para baixar em '{saldo.material.nome}'.",
                code='reserva_insuficiente',
            )

    for material_id in material_ids:
        saldo = saldos_por_material[material_id][0]
        saldo.saldo_fisico = saldo.saldo_fisico - entregue_por_material[material_id]
        saldo.saldo_reservado = (
            saldo.saldo_reservado - autorizada_por_material[material_id]
        )
        saldo.save(update_fields=['saldo_fisico', 'saldo_reservado'])
