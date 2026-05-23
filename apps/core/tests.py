"""Testes do seed canônico de desenvolvimento."""

from decimal import Decimal

import pytest
from django.contrib.auth import authenticate, get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Setor, SetorClassificacao, VinculoAuxiliar
from apps.estoque.models import Estoque, Material, SaldoEstoque, UnidadeMedida
from apps.requisicoes.models import SequenciaRequisicao


@pytest.mark.django_db
def test_home_usa_layout_autenticado(client):
    User = get_user_model()
    usuario = User.objects.create_user(
        matricula='HOME-001',
        password='senha-forte-123',
        nome='Operador Home',
    )
    client.force_login(usuario)

    resposta = client.get(reverse('core:home'))
    conteudo = resposta.content.decode()

    assert resposta.status_code == 200
    assert '<header' in conteudo
    assert '<main' in conteudo
    assert 'max-w-5xl' in conteudo
    assert 'p-6' in conteudo
    assert 'Operador Home' in conteudo
    assert 'HOME-001' in conteudo


def test_seed_dev_exige_flag_de_ambiente_local(settings, monkeypatch):
    settings.DEBUG = True
    monkeypatch.delenv('SEED_DEV_HABILITADO', raising=False)

    with pytest.raises(CommandError, match='SEED_DEV_HABILITADO'):
        call_command('seed_dev')


def test_seed_dev_exige_debug_ativo(settings, monkeypatch):
    settings.DEBUG = False
    monkeypatch.setenv('SEED_DEV_HABILITADO', 'true')

    with pytest.raises(CommandError, match='DEBUG=True'):
        call_command('seed_dev')


@pytest.mark.django_db
def test_seed_dev_cria_elenco_canonico_e_converge(settings, monkeypatch):
    settings.DEBUG = True
    monkeypatch.setenv('SEED_DEV_HABILITADO', 'true')

    call_command('seed_dev')

    Material.objects.filter(codigo='MAT-001').update(nome='Papel alterado')
    SequenciaRequisicao.objects.filter(
        ano=timezone.localdate().year,
    ).update(ultimo_numero=7)

    call_command('seed_dev')

    assert Setor.objects.count() == 2
    almox = Setor.objects.get(codigo='ALMOX')
    obras = Setor.objects.get(codigo='OBRAS')
    assert almox.classificacao == SetorClassificacao.ALMOXARIFADO
    assert obras.classificacao == SetorClassificacao.COMUM
    assert almox.chefe.matricula == 'ALMOX001'
    assert obras.chefe.matricula == 'OBRAS001'

    User = get_user_model()
    assert User.objects.count() == 6
    assert User.objects.get(matricula='SUPER001').is_superuser
    assert User.objects.get(matricula='ALMOX002').setor == obras
    assert VinculoAuxiliar.objects.filter(ativo=True).count() == 2
    assert VinculoAuxiliar.objects.get(usuario__matricula='ALMOX002').setor == almox
    assert VinculoAuxiliar.objects.get(usuario__matricula='OBRAS002').setor == obras

    assert Material.objects.count() == 3
    assert Material.objects.get(codigo='MAT-001').nome == 'Papel A4'
    assert Material.objects.get(codigo='MAT-001').unidade == UnidadeMedida.UNIDADE
    assert Material.objects.get(codigo='MAT-003').unidade == UnidadeMedida.ROLO
    estoque = Estoque.objects.get(codigo='EST-PRINCIPAL')
    assert SaldoEstoque.objects.count() == 3
    assert SaldoEstoque.objects.get(
        estoque=estoque,
        material__codigo='MAT-001',
    ).saldo_fisico == Decimal('50.000')
    assert SaldoEstoque.objects.get(
        estoque=estoque,
        material__codigo='MAT-002',
    ).saldo_fisico == Decimal('10.000')
    assert SaldoEstoque.objects.get(
        estoque=estoque,
        material__codigo='MAT-003',
    ).saldo_reservado == Decimal('0.000')

    sequencia = SequenciaRequisicao.objects.get(ano=timezone.localdate().year)
    assert sequencia.ultimo_numero == 7

    usuario = authenticate(username='ALMOX001', password='senha@dev')
    assert usuario is not None


@pytest.mark.django_db
def test_seed_dev_recusa_conflito_semantico_do_setor_almoxarifado(
    settings,
    monkeypatch,
):
    settings.DEBUG = True
    monkeypatch.setenv('SEED_DEV_HABILITADO', 'true')
    Setor.objects.create(
        codigo='ALMOX-2',
        nome='Almoxarifado paralelo',
        classificacao=SetorClassificacao.ALMOXARIFADO,
    )

    with pytest.raises(CommandError, match='setor classificado como Almoxarifado'):
        call_command('seed_dev')

    assert not Setor.objects.filter(codigo='ALMOX').exists()
