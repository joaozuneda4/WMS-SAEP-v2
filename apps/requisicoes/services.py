"""Services de domínio para requisições."""

from decimal import Decimal, InvalidOperation

from django.db import transaction

from apps.accounts.models import User
from apps.accounts.policies import exigir_pode_criar_requisicao_para
from apps.core.exceptions import ConflitoDominio, DadosInvalidos
from apps.estoque.models import Material, SaldoEstoque
from apps.requisicoes.models import (
    EstadoRequisicao,
    EventoTimeline,
    ItemRequisicao,
    Requisicao,
    TimelineRequisicao,
)


def _normalizar_quantidade(valor) -> Decimal:
    try:
        quantidade = Decimal(str(valor))
    except (InvalidOperation, ValueError) as exc:
        raise DadosInvalidos(
            'Informe uma quantidade válida.',
            code='quantidade_invalida',
        ) from exc
    if quantidade <= 0:
        raise DadosInvalidos(
            'A quantidade solicitada deve ser maior que zero.',
            code='quantidade_invalida',
        )
    return quantidade


def _validar_itens_elegiveis(itens) -> list[tuple[Material, Decimal]]:
    if not itens:
        raise DadosInvalidos(
            'A requisição deve ter ao menos um item.',
            code='requisicao_sem_itens',
        )

    material_ids = [item['material_id'] for item in itens]
    if len(set(material_ids)) != len(material_ids):
        raise DadosInvalidos(
            'A requisição não pode repetir o mesmo material.',
            code='material_repetido',
        )

    materiais = Material.objects.in_bulk(material_ids)
    saldos = {
        saldo.material_id: saldo
        for saldo in SaldoEstoque.objects.select_related('material', 'estoque').filter(
            material_id__in=material_ids,
            estoque__ativo=True,
        )
    }

    itens_validados = []
    for item in itens:
        material = materiais.get(item['material_id'])
        if material is None:
            raise DadosInvalidos(
                'Material informado não existe.',
                code='material_inexistente',
            )
        quantidade = _normalizar_quantidade(item['quantidade_solicitada'])
        saldo = saldos.get(material.id)
        if not material.ativo:
            raise DadosInvalidos(
                f'O material {material.nome} está inativo.',
                code='material_inativo',
            )
        if saldo is None:
            raise DadosInvalidos(
                f'O material {material.nome} não possui saldo disponível.',
                code='material_sem_saldo',
            )
        if saldo.divergente:
            raise ConflitoDominio(
                f'O material {material.nome} está com divergência de estoque.',
                code='material_divergente',
            )
        if saldo.saldo_disponivel < quantidade:
            raise ConflitoDominio(
                f'O material {material.nome} não possui saldo disponível suficiente.',
                code='saldo_insuficiente',
            )
        itens_validados.append((material, quantidade))
    return itens_validados


def criar_rascunho_requisicao(
    *,
    ator_id: int,
    beneficiario_id: int,
    itens,
    observacao_geral: str = '',
) -> Requisicao:
    """Cria uma requisição em rascunho com itens e evento de criação."""

    with transaction.atomic():
        ator = User.objects.select_related('setor').get(pk=ator_id)
        beneficiario = User.objects.select_related('setor').get(pk=beneficiario_id)
        exigir_pode_criar_requisicao_para(ator, beneficiario)

        setor_beneficiario = beneficiario.setor
        if setor_beneficiario is None:
            raise DadosInvalidos(
                'Beneficiário precisa pertencer a um setor ativo.',
                code='beneficiario_sem_setor',
            )

        itens_validados = _validar_itens_elegiveis(itens)
        requisicao = Requisicao.objects.create(
            criador=ator,
            beneficiario=beneficiario,
            setor_beneficiario=setor_beneficiario,
            estado=EstadoRequisicao.RASCUNHO,
            observacao_geral=observacao_geral.strip(),
        )
        ItemRequisicao.objects.bulk_create(
            [
                ItemRequisicao(
                    requisicao=requisicao,
                    material=material,
                    quantidade_solicitada=quantidade,
                )
                for material, quantidade in itens_validados
            ]
        )
        TimelineRequisicao.objects.create(
            requisicao=requisicao,
            evento=EventoTimeline.CRIACAO,
            ator=ator,
            estado_resultante=EstadoRequisicao.RASCUNHO,
        )
    return requisicao
