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
def test_home_nao_autenticado_redireciona_login(client):
    resposta = client.get(reverse('core:home'))
    assert resposta.status_code == 302
    assert '/login' in resposta['Location'] or 'accounts' in resposta['Location']


@pytest.mark.django_db
def test_home_superuser_redireciona_admin(client):
    User = get_user_model()
    usuario = User.objects.create_superuser(
        matricula='SUPER-001',
        password='senha-forte-123',
        nome='Super Admin',
    )
    client.force_login(usuario)
    resposta = client.get(reverse('core:home'))
    assert resposta.status_code == 302
    assert resposta['Location'] == '/admin/'


@pytest.mark.django_db
def test_home_chefe_almoxarifado_redireciona_atendimentos(client):
    User = get_user_model()
    setor = Setor.objects.create(
        codigo='ALM', nome='Almoxarifado', classificacao=SetorClassificacao.ALMOXARIFADO
    )
    usuario = User.objects.create_user(
        matricula='ALMX-001',
        password='senha-forte-123',
        nome='Chefe Almox',
        setor=setor,
    )
    setor.chefe = usuario
    setor.save(update_fields=['chefe'])
    client.force_login(usuario)
    resposta = client.get(reverse('core:home'))
    assert resposta.status_code == 302
    assert resposta['Location'] == reverse('requisicoes:atendimentos')


@pytest.mark.django_db
def test_home_auxiliar_almoxarifado_redireciona_atendimentos(client):
    User = get_user_model()
    setor = Setor.objects.create(
        codigo='ALM2',
        nome='Almoxarifado',
        classificacao=SetorClassificacao.ALMOXARIFADO,
    )
    usuario = User.objects.create_user(
        matricula='ALMX-002',
        password='senha-forte-123',
        nome='Aux Almox',
        setor=setor,
    )
    VinculoAuxiliar.objects.create(usuario=usuario, setor=setor, ativo=True)
    client.force_login(usuario)
    resposta = client.get(reverse('core:home'))
    assert resposta.status_code == 302
    assert resposta['Location'] == reverse('requisicoes:atendimentos')


@pytest.mark.django_db
def test_home_chefe_setor_comum_redireciona_autorizacoes(client):
    User = get_user_model()
    setor = Setor.objects.create(
        codigo='OBR2', nome='Obras', classificacao=SetorClassificacao.COMUM
    )
    usuario = User.objects.create_user(
        matricula='CHEF-001',
        password='senha-forte-123',
        nome='Chefe Obras',
        setor=setor,
    )
    setor.chefe = usuario
    setor.save(update_fields=['chefe'])
    client.force_login(usuario)
    resposta = client.get(reverse('core:home'))
    assert resposta.status_code == 302
    assert resposta['Location'] == reverse('requisicoes:autorizacoes')


@pytest.mark.django_db
def test_home_solicitante_redireciona_minhas(client):
    User = get_user_model()
    setor = Setor.objects.create(
        codigo='OBR3', nome='Obras', classificacao=SetorClassificacao.COMUM
    )
    usuario = User.objects.create_user(
        matricula='SOL-001',
        password='senha-forte-123',
        nome='Solicitante',
        setor=setor,
    )
    client.force_login(usuario)
    resposta = client.get(reverse('core:home'))
    assert resposta.status_code == 302
    assert resposta['Location'] == reverse('requisicoes:minhas')


@pytest.mark.django_db
def test_home_staff_com_papel_almox_vai_para_atendimentos(client):
    """is_staff não bypassa o dispatcher — papel operacional tem prioridade."""
    User = get_user_model()
    setor = Setor.objects.create(
        codigo='ALM3',
        nome='Almoxarifado',
        classificacao=SetorClassificacao.ALMOXARIFADO,
    )
    usuario = User.objects.create_user(
        matricula='STAF-001',
        password='senha-forte-123',
        nome='Staff Almox',
        setor=setor,
        is_staff=True,
    )
    VinculoAuxiliar.objects.create(usuario=usuario, setor=setor, ativo=True)
    client.force_login(usuario)
    resposta = client.get(reverse('core:home'))
    assert resposta.status_code == 302
    assert resposta['Location'] == reverse('requisicoes:atendimentos')


@pytest.mark.django_db
def test_home_multi_papel_almox_chefe_vai_para_atendimentos(client):
    """Usuário com almoxarifado E chefe de setor comum → almox ganha (prioridade)."""
    User = get_user_model()
    setor_almox = Setor.objects.create(
        codigo='ALM4',
        nome='Almoxarifado',
        classificacao=SetorClassificacao.ALMOXARIFADO,
    )
    setor_comum = Setor.objects.create(
        codigo='OBR4', nome='Obras', classificacao=SetorClassificacao.COMUM
    )
    usuario = User.objects.create_user(
        matricula='MULT-001',
        password='senha-forte-123',
        nome='Multi Papel',
        setor=setor_almox,
    )
    VinculoAuxiliar.objects.create(usuario=usuario, setor=setor_almox, ativo=True)
    setor_comum.chefe = usuario
    setor_comum.save(update_fields=['chefe'])
    client.force_login(usuario)
    resposta = client.get(reverse('core:home'))
    assert resposta.status_code == 302
    assert resposta['Location'] == reverse('requisicoes:atendimentos')


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
    assert User.objects.get(matricula='ALMOX002').setor == almox
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
