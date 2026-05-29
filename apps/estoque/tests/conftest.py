"""Fixtures compartilhadas pelos testes de estoque.

Sem factory_boy, sem seed_dev como pré-condição (ADR-0010).
"""

import pytest

from apps.accounts.models import Setor, SetorClassificacao, User, VinculoAuxiliar
from apps.estoque.models import Estoque


@pytest.fixture
def setor_almoxarifado(db):
    return Setor.objects.create(
        codigo='ALM', nome='Almoxarifado', classificacao=SetorClassificacao.ALMOXARIFADO
    )


@pytest.fixture
def setor_obras(db):
    return Setor.objects.create(
        codigo='OBR', nome='Obras', classificacao=SetorClassificacao.COMUM
    )


@pytest.fixture
def chefe_almoxarifado(db, setor_almoxarifado):
    u = User.objects.create_user(
        matricula='021',
        nome='Roberto Chefe Almox',
        password='senha',
        setor=setor_almoxarifado,
    )
    setor_almoxarifado.chefe = u
    setor_almoxarifado.save(update_fields=['chefe'])
    return u


@pytest.fixture
def aux_almoxarifado(db, setor_almoxarifado):
    u = User.objects.create_user(
        matricula='020',
        nome='Luisa Aux Almox',
        password='senha',
        setor=setor_almoxarifado,
    )
    VinculoAuxiliar.objects.create(usuario=u, setor=setor_almoxarifado, ativo=True)
    return u


@pytest.fixture
def solicitante(db, setor_obras):
    return User.objects.create_user(
        matricula='001',
        nome='Joao Solicitante',
        password='senha',
        setor=setor_obras,
    )


@pytest.fixture
def superuser(db, setor_obras):
    return User.objects.create_superuser(
        matricula='900',
        nome='Super Usuario',
        password='senha',
        setor=setor_obras,
    )


@pytest.fixture
def usuario_inativo(db, setor_almoxarifado):
    u = User.objects.create_user(
        matricula='098',
        nome='Inativo Almox',
        password='senha',
        setor=setor_almoxarifado,
        is_active=False,
    )
    setor_almoxarifado.chefe = u
    setor_almoxarifado.save(update_fields=['chefe'])
    return u


@pytest.fixture
def estoque_principal(db):
    return Estoque.objects.create(codigo='EST01', nome='Estoque Principal')


@pytest.fixture
def material_disponivel(db, estoque_principal):
    from apps.estoque.models import Material, SaldoEstoque, UnidadeMedida

    m = Material.objects.create(
        codigo='MAT001', nome='Parafuso M6', unidade=UnidadeMedida.UNIDADE, ativo=True
    )
    SaldoEstoque.objects.create(
        estoque=estoque_principal, material=m, saldo_fisico=100, saldo_reservado=10
    )
    return m
