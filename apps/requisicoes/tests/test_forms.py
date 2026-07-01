"""Testes de forms e formset de rascunho."""

from decimal import Decimal

import pytest

from apps.requisicoes.forms import ItemAtendimentoFormSet, ItemRequisicaoFormSet
from apps.requisicoes.types import LinhaAtendimento


def _build_formset_data(itens: list[dict], deletados: list[int] = None) -> dict:
    """Monta POST data para o formset de itens."""
    deletados = deletados or []
    total = len(itens)
    data = {
        'itens-TOTAL_FORMS': str(total),
        'itens-INITIAL_FORMS': '0',
        'itens-MIN_NUM_FORMS': '0',
        'itens-MAX_NUM_FORMS': '1000',
    }
    for i, item in enumerate(itens):
        data[f'itens-{i}-material_id'] = str(item.get('material_id', ''))
        data[f'itens-{i}-material_label'] = item.get('material_label', '')
        data[f'itens-{i}-quantidade_solicitada'] = str(
            item.get('quantidade_solicitada', '')
        )
        if i in deletados:
            data[f'itens-{i}-DELETE'] = 'on'
    return data


@pytest.mark.django_db
def test_formset_valido_com_um_item(material_disponivel):
    data = _build_formset_data(
        [
            {
                'material_id': material_disponivel.pk,
                'material_label': str(material_disponivel),
                'quantidade_solicitada': '5',
            },
        ]
    )
    fs = ItemRequisicaoFormSet(data, prefix='itens')
    assert fs.is_valid(), fs.errors


@pytest.mark.django_db
def test_formset_duplicidade_levanta_erro(material_disponivel):
    data = _build_formset_data(
        [
            {
                'material_id': material_disponivel.pk,
                'material_label': str(material_disponivel),
                'quantidade_solicitada': '5',
            },
            {
                'material_id': material_disponivel.pk,
                'material_label': str(material_disponivel),
                'quantidade_solicitada': '3',
            },
        ]
    )
    fs = ItemRequisicaoFormSet(data, prefix='itens')
    assert not fs.is_valid()
    # Erro na linha duplicada
    assert any('material_label' in f.errors or f.non_field_errors() for f in fs.forms)


@pytest.mark.django_db
def test_formset_duplicidade_ignora_linha_deletada(material_disponivel):
    """Linha marcada como DELETE não conta para verificação de duplicidade."""
    data = _build_formset_data(
        [
            {
                'material_id': material_disponivel.pk,
                'material_label': str(material_disponivel),
                'quantidade_solicitada': '5',
            },
            {
                'material_id': material_disponivel.pk,
                'material_label': str(material_disponivel),
                'quantidade_solicitada': '3',
            },
        ],
        deletados=[1],  # segunda linha deletada
    )
    fs = ItemRequisicaoFormSet(data, prefix='itens')
    assert fs.is_valid(), fs.errors


def test_formset_sem_linhas_validas_levanta_erro():
    """Formset sem nenhuma linha válida deve falhar."""
    data = {
        'itens-TOTAL_FORMS': '1',
        'itens-INITIAL_FORMS': '0',
        'itens-MIN_NUM_FORMS': '0',
        'itens-MAX_NUM_FORMS': '1000',
        'itens-0-material_id': '',
        'itens-0-material_label': '',
        'itens-0-quantidade_solicitada': '',
    }
    fs = ItemRequisicaoFormSet(data, prefix='itens')
    assert not fs.is_valid()
    assert any('ao menos um item' in e for e in fs.non_form_errors())


@pytest.mark.django_db
def test_formset_linhas_validas_retorna_itens(
    material_disponivel, material_disponivel_2
):
    data = _build_formset_data(
        [
            {
                'material_id': material_disponivel.pk,
                'material_label': str(material_disponivel),
                'quantidade_solicitada': '5',
            },
            {
                'material_id': material_disponivel_2.pk,
                'material_label': str(material_disponivel_2),
                'quantidade_solicitada': '2',
            },
        ]
    )
    fs = ItemRequisicaoFormSet(data, prefix='itens')
    assert fs.is_valid()
    itens = fs.linhas_validas()
    assert len(itens) == 2
    assert all('material_id' in i and 'quantidade_solicitada' in i for i in itens)


def test_formset_atendimento_linhas_atendimento_retorna_vos_tipados():
    data = {
        'itens-TOTAL_FORMS': '2',
        'itens-INITIAL_FORMS': '0',
        'itens-MIN_NUM_FORMS': '0',
        'itens-MAX_NUM_FORMS': '1000',
        'itens-0-item_id': '1',
        'itens-0-quantidade_entregue': '5',
        'itens-0-justificativa': '',
        'itens-1-item_id': '2',
        'itens-1-quantidade_entregue': '1.5',
        'itens-1-justificativa': 'Entrega menor que autorizada',
    }
    fs = ItemAtendimentoFormSet(data, prefix='itens', item_ids_permitidos=[1, 2])
    assert fs.is_valid(), fs.errors

    linhas = fs.linhas_atendimento()

    assert linhas == [
        LinhaAtendimento(item_id=1, quantidade_entregue=Decimal('5'), justificativa=''),
        LinhaAtendimento(
            item_id=2,
            quantidade_entregue=Decimal('1.5'),
            justificativa='Entrega menor que autorizada',
        ),
    ]
    assert all(isinstance(linha, LinhaAtendimento) for linha in linhas)


def test_formset_atendimento_linhas_atendimento_ignora_formset_vazio():
    data = {
        'itens-TOTAL_FORMS': '0',
        'itens-INITIAL_FORMS': '0',
        'itens-MIN_NUM_FORMS': '0',
        'itens-MAX_NUM_FORMS': '1000',
    }
    fs = ItemAtendimentoFormSet(data, prefix='itens', item_ids_permitidos=[])
    assert fs.is_valid(), fs.errors
    assert fs.linhas_atendimento() == []


@pytest.mark.django_db
def test_formset_atendimento_rejeita_item_fora_da_lista_permitida():
    data = {
        'itens-TOTAL_FORMS': '1',
        'itens-INITIAL_FORMS': '0',
        'itens-MIN_NUM_FORMS': '0',
        'itens-MAX_NUM_FORMS': '1000',
        'itens-0-item_id': '999',
        'itens-0-quantidade_entregue': '1',
        'itens-0-justificativa': '',
    }
    fs = ItemAtendimentoFormSet(data, prefix='itens', item_ids_permitidos=[])
    assert not fs.is_valid()
    assert fs.forms[0].errors['item_id'] == ['Item inválido para esta requisição.']
