from decimal import Decimal

import pytest

from apps.core.exceptions import ConflitoDominio, DadosInvalidos, PermissaoNegada
from apps.estoque.models import SaldoEstoque
from apps.requisicoes.models import (
    EstadoRequisicao,
    EventoTimeline,
    ItemRequisicao,
    Requisicao,
    TimelineRequisicao,
)
from apps.requisicoes.services import criar_rascunho_requisicao


@pytest.mark.django_db
def test_cria_rascunho_para_si_com_itens_e_timeline(user_obras, material_papel):
    requisicao = criar_rascunho_requisicao(
        ator_id=user_obras.id,
        beneficiario_id=user_obras.id,
        itens=[
            {
                'material_id': material_papel.id,
                'quantidade_solicitada': Decimal('3.000'),
            }
        ],
        observacao_geral='Uso na secretaria.',
    )

    requisicao.refresh_from_db()
    item = ItemRequisicao.objects.get(requisicao=requisicao)
    evento = TimelineRequisicao.objects.get(requisicao=requisicao)

    assert requisicao.estado == EstadoRequisicao.RASCUNHO
    assert requisicao.numero_publico is None
    assert requisicao.criador == user_obras
    assert requisicao.beneficiario == user_obras
    assert requisicao.setor_beneficiario == user_obras.setor
    assert requisicao.observacao_geral == 'Uso na secretaria.'
    assert item.material == material_papel
    assert item.quantidade_solicitada == Decimal('3.000')
    assert item.quantidade_autorizada is None
    assert item.quantidade_entregue is None
    assert evento.evento == EventoTimeline.CRIACAO
    assert evento.ator == user_obras
    assert evento.estado_resultante == EstadoRequisicao.RASCUNHO


@pytest.mark.django_db
def test_criacao_de_rascunho_nao_muta_saldo(user_obras, material_papel):
    saldo = material_papel.saldos.get()
    saldo_fisico = saldo.saldo_fisico
    saldo_reservado = saldo.saldo_reservado

    criar_rascunho_requisicao(
        ator_id=user_obras.id,
        beneficiario_id=user_obras.id,
        itens=[
            {
                'material_id': material_papel.id,
                'quantidade_solicitada': Decimal('1.000'),
            }
        ],
    )

    saldo.refresh_from_db()
    assert saldo.saldo_fisico == saldo_fisico
    assert saldo.saldo_reservado == saldo_reservado
    assert Requisicao.objects.count() == 1


@pytest.mark.django_db
def test_auxiliar_de_setor_cria_para_beneficiario_do_mesmo_setor(
    auxiliar_obras,
    user_obras,
    material_papel,
):
    requisicao = criar_rascunho_requisicao(
        ator_id=auxiliar_obras.id,
        beneficiario_id=user_obras.id,
        itens=[
            {
                'material_id': material_papel.id,
                'quantidade_solicitada': Decimal('1.000'),
            }
        ],
    )

    assert requisicao.criador == auxiliar_obras
    assert requisicao.beneficiario == user_obras
    assert requisicao.setor_beneficiario == user_obras.setor


@pytest.mark.django_db
def test_chefe_de_setor_cria_para_beneficiario_do_proprio_setor(
    chefe_obras,
    user_obras,
    material_papel,
):
    requisicao = criar_rascunho_requisicao(
        ator_id=chefe_obras.id,
        beneficiario_id=user_obras.id,
        itens=[
            {
                'material_id': material_papel.id,
                'quantidade_solicitada': Decimal('1.000'),
            }
        ],
    )

    assert requisicao.criador == chefe_obras
    assert requisicao.beneficiario == user_obras
    assert requisicao.setor_beneficiario == user_obras.setor


@pytest.mark.django_db
def test_almoxarifado_cria_para_qualquer_setor(
    auxiliar_almoxarifado,
    user_administrativo,
    material_papel,
):
    requisicao = criar_rascunho_requisicao(
        ator_id=auxiliar_almoxarifado.id,
        beneficiario_id=user_administrativo.id,
        itens=[
            {
                'material_id': material_papel.id,
                'quantidade_solicitada': Decimal('1.000'),
            }
        ],
    )

    assert requisicao.criador == auxiliar_almoxarifado
    assert requisicao.beneficiario == user_administrativo
    assert requisicao.setor_beneficiario == user_administrativo.setor


@pytest.mark.django_db
def test_solicitante_nao_cria_para_terceiro(
    user_obras,
    user_administrativo,
    material_papel,
):
    with pytest.raises(PermissaoNegada) as exc_info:
        criar_rascunho_requisicao(
            ator_id=user_obras.id,
            beneficiario_id=user_administrativo.id,
            itens=[
                {
                    'material_id': material_papel.id,
                    'quantidade_solicitada': Decimal('1.000'),
                }
            ],
        )

    assert exc_info.value.code == 'criacao_beneficiario_negada'
    assert Requisicao.objects.count() == 0


@pytest.mark.django_db
def test_auxiliar_setor_nao_cria_para_auxiliar_almoxarifado(
    auxiliar_obras,
    auxiliar_almoxarifado,
    material_papel,
):
    with pytest.raises(PermissaoNegada) as exc_info:
        criar_rascunho_requisicao(
            ator_id=auxiliar_obras.id,
            beneficiario_id=auxiliar_almoxarifado.id,
            itens=[
                {
                    'material_id': material_papel.id,
                    'quantidade_solicitada': Decimal('1.000'),
                }
            ],
        )

    assert exc_info.value.code == 'criacao_beneficiario_negada'
    assert Requisicao.objects.count() == 0


@pytest.mark.django_db
def test_recusa_material_inativo(user_obras, material_papel):
    material_papel.ativo = False
    material_papel.save(update_fields=['ativo'])

    with pytest.raises(DadosInvalidos) as exc_info:
        criar_rascunho_requisicao(
            ator_id=user_obras.id,
            beneficiario_id=user_obras.id,
            itens=[
                {
                    'material_id': material_papel.id,
                    'quantidade_solicitada': Decimal('1.000'),
                }
            ],
        )

    assert exc_info.value.code == 'material_inativo'
    assert Requisicao.objects.count() == 0


@pytest.mark.django_db
def test_recusa_material_divergente(user_obras, material_papel):
    SaldoEstoque.objects.filter(material=material_papel).update(
        saldo_fisico=Decimal('1.000'),
        saldo_reservado=Decimal('2.000'),
    )

    with pytest.raises(ConflitoDominio) as exc_info:
        criar_rascunho_requisicao(
            ator_id=user_obras.id,
            beneficiario_id=user_obras.id,
            itens=[
                {
                    'material_id': material_papel.id,
                    'quantidade_solicitada': Decimal('1.000'),
                }
            ],
        )

    assert exc_info.value.code == 'material_divergente'
    assert Requisicao.objects.count() == 0


@pytest.mark.django_db
def test_recusa_material_sem_saldo_disponivel(user_obras, material_papel):
    with pytest.raises(ConflitoDominio) as exc_info:
        criar_rascunho_requisicao(
            ator_id=user_obras.id,
            beneficiario_id=user_obras.id,
            itens=[
                {
                    'material_id': material_papel.id,
                    'quantidade_solicitada': Decimal('9.000'),
                }
            ],
        )

    assert exc_info.value.code == 'saldo_insuficiente'
    assert Requisicao.objects.count() == 0


@pytest.mark.django_db
def test_recusa_quantidade_invalida(user_obras, material_papel):
    with pytest.raises(DadosInvalidos) as exc_info:
        criar_rascunho_requisicao(
            ator_id=user_obras.id,
            beneficiario_id=user_obras.id,
            itens=[
                {
                    'material_id': material_papel.id,
                    'quantidade_solicitada': Decimal('0.000'),
                }
            ],
        )

    assert exc_info.value.code == 'quantidade_invalida'
    assert Requisicao.objects.count() == 0
