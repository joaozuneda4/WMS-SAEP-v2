"""Comandos de domínio de estoque.

Toda mutação de ``SaldoEstoque`` passa por este módulo.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import TypedDict

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.core.exceptions import ConflitoDominio, DadosInvalidos
from apps.estoque.models import (
    Estoque,
    ItemSaidaExcepcional,
    MovimentacaoEstoque,
    SaidaExcepcional,
    SaldoEstoque,
    SequenciaSaidaExcepcional,
    TipoMovimentacaoEstoque,
)


@dataclass(frozen=True)
class OrigemMovimentacaoEstoque:
    """Value object que identifica o documento de origem de uma movimentação.

    Exatamente uma das FKs deve ser preenchida; a outra deve ser None.
    """

    requisicao_id: int | None = None
    saida_excepcional_id: int | None = None

    def __post_init__(self):
        tem_requisicao = self.requisicao_id is not None
        tem_saida = self.saida_excepcional_id is not None
        if tem_requisicao == tem_saida:
            raise ValueError(
                'OrigemMovimentacaoEstoque exige exatamente uma origem preenchida.'
            )

    @classmethod
    def de_requisicao(cls, requisicao) -> 'OrigemMovimentacaoEstoque':
        return cls(requisicao_id=requisicao.pk)

    @classmethod
    def de_saida_excepcional(cls, saida) -> 'OrigemMovimentacaoEstoque':
        return cls(saida_excepcional_id=saida.pk)


def _registrar_movimentacao(
    *,
    tipo: str,
    material_id: int,
    estoque_id: int,
    delta_fisico: Decimal,
    delta_reservado: Decimal,
    origem: OrigemMovimentacaoEstoque,
    ator_id: int,
) -> None:
    """Cria uma linha no ledger de movimentações de estoque.

    Deve ser chamado dentro da mesma transaction.atomic do service mutante,
    após o save() do SaldoEstoque afetado.
    """
    _TIPOS_REQUISICAO = {
        TipoMovimentacaoEstoque.RESERVA,
        TipoMovimentacaoEstoque.LIBERACAO,
        TipoMovimentacaoEstoque.CONSUMO,
        TipoMovimentacaoEstoque.DEVOLUCAO,
        TipoMovimentacaoEstoque.ESTORNO_REQUISICAO,
    }
    _TIPOS_SAIDA = {
        TipoMovimentacaoEstoque.SAIDA_EXCEPCIONAL,
        TipoMovimentacaoEstoque.ESTORNO_SAIDA,
    }
    if tipo in _TIPOS_REQUISICAO and origem.requisicao_id is None:
        raise DadosInvalidos(
            'Movimentação de tipo requisição exige origem de requisição.',
            code='origem_movimentacao_incoerente',
        )
    if tipo in _TIPOS_SAIDA and origem.saida_excepcional_id is None:
        raise DadosInvalidos(
            'Movimentação de tipo saída exige origem de saída excepcional.',
            code='origem_movimentacao_incoerente',
        )
    MovimentacaoEstoque.objects.create(
        tipo=tipo,
        material_id=material_id,
        estoque_id=estoque_id,
        delta_fisico=delta_fisico,
        delta_reservado=delta_reservado,
        requisicao_id=origem.requisicao_id,
        saida_excepcional_id=origem.saida_excepcional_id,
        ator_id=ator_id,
    )


class ItemReservaEstoque(TypedDict):
    material_id: int
    quantidade_solicitada: Decimal


@transaction.atomic
def reservar_saldos_para_autorizacao(
    *,
    itens: list[ItemReservaEstoque],
    ator_id: int,
    origem: OrigemMovimentacaoEstoque,
) -> None:
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
        _registrar_movimentacao(
            tipo=TipoMovimentacaoEstoque.RESERVA,
            material_id=material_id,
            estoque_id=saldo.estoque_id,
            delta_fisico=Decimal('0'),
            delta_reservado=quantidade,
            origem=origem,
            ator_id=ator_id,
        )


class ItemLiberacaoReserva(TypedDict):
    material_id: int
    quantidade_reservada: Decimal


@transaction.atomic
def liberar_reservas_para_cancelamento(
    *,
    itens: list[ItemLiberacaoReserva],
    ator_id: int,
    origem: OrigemMovimentacaoEstoque,
) -> None:
    """Libera reserva integral em cancelamento sem tocar saldo físico.

    ``itens`` deve conter ``material_id`` e ``quantidade_reservada`` por item.
    A função trava saldos afetados em ordem determinística e valida tudo antes
    de qualquer mutação.
    """
    if not itens:
        raise DadosInvalidos(
            'A requisição precisa ter ao menos um item reservado para cancelar.',
            code='sem_itens',
        )

    material_ids: list[int] = []
    quantidade_por_material: dict[int, Decimal] = {}
    for item in itens:
        try:
            material_id = int(item['material_id'])
            quantidade = Decimal(str(item['quantidade_reservada']))
        except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
            raise DadosInvalidos(
                'Item inválido para liberação de reserva.',
                code='item_invalido',
            ) from exc

        if not quantidade.is_finite():
            raise DadosInvalidos(
                'Quantidade reservada deve ser maior que zero.',
                code='quantidade_reservada_invalida',
            )
        if quantidade <= 0:
            raise DadosInvalidos(
                'Quantidade reservada deve ser maior que zero.',
                code='quantidade_reservada_invalida',
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
        if saldo_existente.saldo_reservado < quantidade:
            raise ConflitoDominio(
                f"Reserva insuficiente para liberar '{saldo_existente.material.nome}'.",
                code='reserva_insuficiente',
            )

    for material_id, quantidade in quantidade_por_material.items():
        saldo = saldos_por_material[material_id][0]
        saldo.saldo_reservado = saldo.saldo_reservado - quantidade
        saldo.save(update_fields=['saldo_reservado'])
        _registrar_movimentacao(
            tipo=TipoMovimentacaoEstoque.LIBERACAO,
            material_id=material_id,
            estoque_id=saldo.estoque_id,
            delta_fisico=Decimal('0'),
            delta_reservado=-quantidade,
            origem=origem,
            ator_id=ator_id,
        )


class ItemAtendimentoSaldo(TypedDict):
    material_id: int
    quantidade_autorizada: Decimal
    quantidade_entregue: Decimal


@transaction.atomic
def consumir_e_liberar_reservas_para_atendimento(
    *,
    itens: list[ItemAtendimentoSaldo],
    ator_id: int,
    origem: OrigemMovimentacaoEstoque,
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
        entregue = entregue_por_material[material_id]
        autorizada = autorizada_por_material[material_id]
        saldo.saldo_fisico = saldo.saldo_fisico - entregue
        saldo.saldo_reservado = saldo.saldo_reservado - autorizada
        saldo.save(update_fields=['saldo_fisico', 'saldo_reservado'])
        _registrar_movimentacao(
            tipo=TipoMovimentacaoEstoque.CONSUMO,
            material_id=material_id,
            estoque_id=saldo.estoque_id,
            delta_fisico=-entregue,
            delta_reservado=-autorizada,
            origem=origem,
            ator_id=ator_id,
        )


@transaction.atomic
def registrar_saida_excepcional(
    *,
    ator_id: int,
    estoque_id: int,
    motivo: str,
    observacao: str,
    itens: list[dict],
) -> SaidaExcepcional:
    """Registra baixa administrativa direta de materiais no estoque.

    Cria SaidaExcepcional + ItemSaidaExcepcional, baixa saldo_fisico e emite
    SXP-AAAA-NNNNNN. Totalmente atômico (EST-saida-01).
    """
    from apps.estoque.policies import exigir_pode_registrar_saida_excepcional

    try:
        ator = User.objects.get(pk=ator_id)
        estoque = Estoque.objects.get(pk=estoque_id)
    except ObjectDoesNotExist as exc:
        raise DadosInvalidos(
            'Ator ou estoque inválido.', code='referencia_invalida'
        ) from exc

    exigir_pode_registrar_saida_excepcional(ator)

    if not itens:
        raise DadosInvalidos('A saída precisa ter ao menos um item.', code='sem_itens')

    material_ids: list[int] = []
    quantidade_por_material: dict[int, Decimal] = {}
    for item in itens:
        try:
            material_id = int(item['material_id'])
            quantidade = Decimal(str(item['quantidade']))
        except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
            raise DadosInvalidos('Item inválido.', code='item_invalido') from exc

        if quantidade <= 0:
            raise DadosInvalidos(
                'Quantidade deve ser maior que zero.', code='quantidade_invalida'
            )
        if material_id in quantidade_por_material:
            raise DadosInvalidos(
                'Material duplicado no mesmo documento.', code='material_duplicado'
            )
        material_ids.append(material_id)
        quantidade_por_material[material_id] = quantidade

    saldos = list(
        SaldoEstoque.objects.select_for_update()
        .select_related('material')
        .filter(material_id__in=material_ids, estoque_id=estoque_id)
        .order_by('material_id')
    )

    saldos_por_material: dict[int, SaldoEstoque] = {s.material_id: s for s in saldos}

    for material_id, quantidade in quantidade_por_material.items():
        saldo = saldos_por_material.get(material_id)
        if saldo is None:
            raise ConflitoDominio(
                'Saldo não encontrado para material.', code='saldo_nao_encontrado'
            )
        if not saldo.material.ativo:
            raise ConflitoDominio(
                f"Material '{saldo.material.nome}' está inativo.",
                code='material_inativo',
            )
        if saldo.saldo_fisico < quantidade:
            raise ConflitoDominio(
                f"Saldo físico insuficiente para '{saldo.material.nome}'.",
                code='saldo_insuficiente',
            )

    saida = SaidaExcepcional.objects.create(
        motivo=motivo,
        observacao=observacao,
        registrado_por=ator,
        estoque=estoque,
    )
    origem = OrigemMovimentacaoEstoque.de_saida_excepcional(saida)

    for material_id, quantidade in quantidade_por_material.items():
        ItemSaidaExcepcional.objects.create(
            saida=saida,
            material_id=material_id,
            quantidade=quantidade,
        )
        saldo = saldos_por_material[material_id]
        saldo.saldo_fisico = saldo.saldo_fisico - quantidade
        saldo.save(update_fields=['saldo_fisico'])
        _registrar_movimentacao(
            tipo=TipoMovimentacaoEstoque.SAIDA_EXCEPCIONAL,
            material_id=material_id,
            estoque_id=estoque_id,
            delta_fisico=-quantidade,
            delta_reservado=Decimal('0'),
            origem=origem,
            ator_id=ator_id,
        )

    ano = timezone.localdate().year
    sequencia, _ = SequenciaSaidaExcepcional.objects.select_for_update().get_or_create(
        ano=ano
    )
    sequencia.ultimo_numero += 1
    sequencia.save(update_fields=['ultimo_numero'])
    saida.numero_publico = f'SXP-{ano}-{sequencia.ultimo_numero:06d}'
    saida.save(update_fields=['numero_publico'])

    return saida


@transaction.atomic
def estornar_saida_excepcional(
    *,
    ator_id: int,
    saida_id: int,
    justificativa: str,
) -> SaidaExcepcional:
    """Estorna uma saída excepcional, restaurando saldo_fisico de cada item.

    Operação total e atômica (EST-saida-02). Sem estorno parcial.
    """
    from apps.estoque.models import EstadoSaidaExcepcional
    from apps.estoque.policies import exigir_pode_estornar_saida_excepcional

    try:
        ator = User.objects.get(pk=ator_id)
    except ObjectDoesNotExist as exc:
        raise DadosInvalidos('Ator inválido.', code='referencia_invalida') from exc

    exigir_pode_estornar_saida_excepcional(ator)

    if not justificativa or not justificativa.strip():
        raise DadosInvalidos(
            'A justificativa de estorno é obrigatória.', code='justificativa_vazia'
        )

    try:
        saida = SaidaExcepcional.objects.select_for_update().get(pk=saida_id)
    except ObjectDoesNotExist as exc:
        raise DadosInvalidos(
            'Saída excepcional não encontrada.', code='nao_encontrada'
        ) from exc

    if saida.estado == EstadoSaidaExcepcional.ESTORNADA:
        raise ConflitoDominio(
            'Esta saída já estornada não pode ser estornada novamente.',
            code='ja_estornada',
        )

    itens = list(saida.itens.select_related('material').all())
    material_ids = [item.material_id for item in itens]

    saldos = list(
        SaldoEstoque.objects.select_for_update()
        .filter(material_id__in=material_ids, estoque_id=saida.estoque_id)
        .order_by('material_id')
    )
    saldos_por_material = {s.material_id: s for s in saldos}
    origem = OrigemMovimentacaoEstoque.de_saida_excepcional(saida)

    for item in itens:
        saldo = saldos_por_material.get(item.material_id)
        if saldo is None:
            raise ConflitoDominio(
                f"Saldo não encontrado para material '{item.material.nome}' no estorno.",
                code='saldo_nao_encontrado_estorno',
            )
        saldo.saldo_fisico = saldo.saldo_fisico + item.quantidade
        saldo.save(update_fields=['saldo_fisico'])
        _registrar_movimentacao(
            tipo=TipoMovimentacaoEstoque.ESTORNO_SAIDA,
            material_id=item.material_id,
            estoque_id=saida.estoque_id,
            delta_fisico=item.quantidade,
            delta_reservado=Decimal('0'),
            origem=origem,
            ator_id=ator_id,
        )

    saida.estado = EstadoSaidaExcepcional.ESTORNADA
    saida.estornado_em = timezone.now()
    saida.estornado_por = ator
    saida.justificativa_estorno = justificativa.strip()
    saida.save(
        update_fields=[
            'estado',
            'estornado_em',
            'estornado_por',
            'justificativa_estorno',
        ]
    )

    return saida


def _registrar_atualizacao_estoque_relevante(*, linhas, estoque, importacao, ator):
    """Registra evento de timeline em requisições autorizadas afetadas por divergência crítica."""
    from django.db.models import F

    from apps.estoque.models import SaldoEstoque
    from apps.requisicoes.models import (
        EstadoRequisicao,
        EventoTimeline,
        ItemRequisicao,
        TimelineRequisicao,
    )

    # Todos os materiais existentes no import (excluir 'novo' — ainda sem material_id)
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


def confirmar_importacao_scpi(
    *,
    ator_id: int,
    conteudo_bytes: bytes,
    arquivo_nome: str,
    estoque_id: int,
):
    """Confirma importação SCPI: bloqueia reimportação, cria novos materiais e grava metadados."""
    import hashlib

    from django.db import IntegrityError, transaction

    from apps.accounts.models import User
    from apps.core.exceptions import ConflitoDominio, DadosInvalidos
    from apps.estoque.models import (
        Estoque,
        ImportacaoSCPI,
        Material,
        SaldoEstoque,
        StatusImportacaoSCPI,
        UnidadeMedida,
    )
    from apps.estoque.policies import exigir_pode_confirmar_importacao_scpi
    from apps.estoque.selectors import gerar_preview_importacao_scpi

    try:
        ator = User.objects.get(pk=ator_id)
    except User.DoesNotExist:
        raise DadosInvalidos('Usuário não encontrado.', code='usuario_nao_encontrado')

    exigir_pode_confirmar_importacao_scpi(ator)

    try:
        estoque = Estoque.objects.get(pk=estoque_id)
    except Estoque.DoesNotExist:
        raise DadosInvalidos('Estoque não encontrado.', code='estoque_nao_encontrado')

    arquivo_hash = hashlib.sha256(conteudo_bytes).hexdigest()

    linhas = gerar_preview_importacao_scpi(
        conteudo_bytes=conteudo_bytes,
        estoque_id=estoque_id,
    )

    total_novos = sum(1 for linha in linhas if linha.status == 'novo')
    total_divergentes = sum(1 for linha in linhas if linha.status == 'divergente')
    status = (
        StatusImportacaoSCPI.COM_ALERTAS
        if total_divergentes > 0
        else StatusImportacaoSCPI.CONCLUIDA
    )

    with transaction.atomic():
        if ImportacaoSCPI.objects.filter(arquivo_hash=arquivo_hash).exists():
            raise ConflitoDominio(
                'Este arquivo já foi importado anteriormente. Reimportação bloqueada.',
                code='reimportacao_bloqueada',
            )

        for linha in linhas:
            if linha.status != 'novo':
                continue
            material = Material.objects.create(
                codigo=linha.cadpro,
                nome=linha.denominacao_scpi or linha.cadpro,
                unidade=UnidadeMedida.UNIDADE,
                ativo=True,
            )
            SaldoEstoque.objects.create(
                estoque=estoque,
                material=material,
                saldo_fisico=linha.saldo_scpi,
                saldo_reservado=0,
            )

        try:
            importacao = ImportacaoSCPI.objects.create(
                arquivo_nome=arquivo_nome,
                arquivo_hash=arquivo_hash,
                importado_por=ator,
                estoque=estoque,
                status=status,
                total_linhas=len(linhas),
                total_novos=total_novos,
                total_divergentes=total_divergentes,
            )
        except IntegrityError:
            raise ConflitoDominio(
                'Este arquivo já foi importado anteriormente. Reimportação bloqueada.',
                code='reimportacao_bloqueada',
            )

        _registrar_atualizacao_estoque_relevante(
            linhas=linhas,
            estoque=estoque,
            importacao=importacao,
            ator=ator,
        )

    return importacao
