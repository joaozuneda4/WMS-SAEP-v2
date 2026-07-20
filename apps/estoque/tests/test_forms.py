"""Testes de forms e formset de itens de saída excepcional."""

from decimal import Decimal

import pytest

from apps.estoque.forms import ItemSaidaExcepcionalFormSet, SaidaExcepcionalForm


def _montar_dados_formset(
    itens: list[dict], deletados: list[int] | None = None
) -> dict:
    """Monta POST data para o formset de itens de saída excepcional."""
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
        data[f'itens-{i}-quantidade'] = str(item.get('quantidade', ''))
        if i in deletados:
            data[f'itens-{i}-DELETE'] = 'on'
    return data


@pytest.mark.django_db
def test_formset_valido_com_um_item(material_disponivel):
    data = _montar_dados_formset(
        [{'material_id': material_disponivel.pk, 'quantidade': '5'}]
    )
    fs = ItemSaidaExcepcionalFormSet(data, prefix='itens')
    assert fs.is_valid(), fs.errors


@pytest.mark.django_db
def test_formset_linhas_validas_retorna_dicts_com_quantidade_decimal(
    material_disponivel,
):
    data = _montar_dados_formset(
        [{'material_id': material_disponivel.pk, 'quantidade': '5.5'}]
    )
    fs = ItemSaidaExcepcionalFormSet(data, prefix='itens')
    assert fs.is_valid(), fs.errors
    itens = fs.linhas_validas()
    assert itens == [
        {'material_id': material_disponivel.pk, 'quantidade': Decimal('5.5')}
    ]


@pytest.mark.django_db
def test_formset_duplicidade_levanta_erro(material_disponivel):
    data = _montar_dados_formset(
        [
            {'material_id': material_disponivel.pk, 'quantidade': '5'},
            {'material_id': material_disponivel.pk, 'quantidade': '3'},
        ]
    )
    fs = ItemSaidaExcepcionalFormSet(data, prefix='itens')
    assert not fs.is_valid()
    assert any(
        'material já foi adicionado' in erro
        for erro in fs.forms[1].errors.get('material_label', [])
    )


def test_formset_sem_linhas_validas_levanta_erro():
    data = _montar_dados_formset([{'material_id': '', 'quantidade': ''}])
    fs = ItemSaidaExcepcionalFormSet(data, prefix='itens')
    assert not fs.is_valid()
    assert any('ao menos um item' in e for e in fs.non_form_errors())


@pytest.mark.django_db
def test_formset_material_inativo_gera_erro_de_elegibilidade(estoque_principal):
    from apps.estoque.models import Material, SaldoEstoque, UnidadeMedida

    material = Material.objects.create(
        codigo='MAT099', nome='Furadeira', unidade=UnidadeMedida.UNIDADE, ativo=False
    )
    SaldoEstoque.objects.create(
        estoque=estoque_principal, material=material, saldo_fisico=10
    )
    data = _montar_dados_formset([{'material_id': material.pk, 'quantidade': '1'}])
    fs = ItemSaidaExcepcionalFormSet(
        data, prefix='itens', estoque_id=estoque_principal.pk
    )
    assert not fs.is_valid()
    assert any(
        'inelegível' in e or 'inativo' in e
        for f in fs.forms
        for e in f.errors.get('material_label', [])
    )


@pytest.mark.django_db
def test_formset_material_sem_saldo_gera_erro_de_elegibilidade(estoque_principal):
    from apps.estoque.models import Material, SaldoEstoque, UnidadeMedida

    material = Material.objects.create(
        codigo='MAT098', nome='Serra', unidade=UnidadeMedida.UNIDADE, ativo=True
    )
    SaldoEstoque.objects.create(
        estoque=estoque_principal, material=material, saldo_fisico=0
    )
    data = _montar_dados_formset([{'material_id': material.pk, 'quantidade': '1'}])
    fs = ItemSaidaExcepcionalFormSet(
        data, prefix='itens', estoque_id=estoque_principal.pk
    )
    assert not fs.is_valid()
    assert any(
        'inelegível' in e or 'saldo' in e
        for f in fs.forms
        for e in f.errors.get('material_label', [])
    )


@pytest.mark.django_db
def test_formset_material_com_saldo_em_outro_estoque_gera_erro_de_elegibilidade(
    estoque_principal,
):
    """Material elegível globalmente, mas sem saldo no estoque desta saída
    especificamente — deve ser rejeitado (escopo por estoque_id)."""
    from apps.estoque.models import Estoque, Material, SaldoEstoque, UnidadeMedida

    outro_estoque = Estoque.objects.create(codigo='EST02', nome='Estoque Secundário')
    material = Material.objects.create(
        codigo='MAT096', nome='Marreta', unidade=UnidadeMedida.UNIDADE, ativo=True
    )
    SaldoEstoque.objects.create(
        estoque=outro_estoque, material=material, saldo_fisico=10
    )
    data = _montar_dados_formset([{'material_id': material.pk, 'quantidade': '1'}])
    fs = ItemSaidaExcepcionalFormSet(
        data, prefix='itens', estoque_id=estoque_principal.pk
    )
    assert not fs.is_valid()
    assert any(
        'inelegível' in e for f in fs.forms for e in f.errors.get('material_label', [])
    )


def test_saida_excepcional_form_valido():
    form = SaidaExcepcionalForm(
        data={'motivo': 'avaria', 'observacao': 'Caixas molhadas'}
    )
    assert form.is_valid(), form.errors


def test_saida_excepcional_form_motivo_ausente():
    form = SaidaExcepcionalForm(data={'motivo': '', 'observacao': 'obs válida'})
    assert not form.is_valid()
    assert 'motivo' in form.errors


def test_saida_excepcional_form_motivo_invalido():
    form = SaidaExcepcionalForm(
        data={'motivo': 'nao_existe', 'observacao': 'obs válida'}
    )
    assert not form.is_valid()
    assert 'motivo' in form.errors


def test_saida_excepcional_form_observacao_ausente():
    form = SaidaExcepcionalForm(data={'motivo': 'avaria', 'observacao': ''})
    assert not form.is_valid()
    assert 'observacao' in form.errors


@pytest.mark.django_db
def test_formset_duplicidade_ignora_linha_deletada(material_disponivel):
    """Linha marcada como DELETE não conta para verificação de duplicidade."""
    data = _montar_dados_formset(
        [
            {'material_id': material_disponivel.pk, 'quantidade': '5'},
            {'material_id': material_disponivel.pk, 'quantidade': '3'},
        ],
        deletados=[1],
    )
    fs = ItemSaidaExcepcionalFormSet(data, prefix='itens')
    assert fs.is_valid(), fs.errors
