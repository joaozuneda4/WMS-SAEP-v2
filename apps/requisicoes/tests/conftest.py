from decimal import Decimal

import pytest

from apps.accounts.models import Setor, SetorClassificacao, User, VinculoAuxiliar
from apps.estoque.models import Estoque, Material, SaldoEstoque, UnidadeMedida

SENHA = 'senha-forte-123'


@pytest.fixture
def setor_almoxarifado(db):
    return Setor.objects.create(
        codigo='ALMOX',
        nome='Almoxarifado',
        classificacao=SetorClassificacao.ALMOXARIFADO,
    )


@pytest.fixture
def setor_obras(db):
    return Setor.objects.create(codigo='OBRAS', nome='Obras')


@pytest.fixture
def setor_administrativo(db):
    return Setor.objects.create(codigo='ADM', nome='Administrativo')


@pytest.fixture
def user_obras(setor_obras):
    return User.objects.create_user(
        matricula='OBRAS001',
        password=SENHA,
        nome='Usuário Obras',
        setor=setor_obras,
    )


@pytest.fixture
def chefe_obras(setor_obras):
    user = User.objects.create_user(
        matricula='OBRAS002',
        password=SENHA,
        nome='Chefe Obras',
        setor=setor_obras,
    )
    setor_obras.chefe = user
    setor_obras.save(update_fields=['chefe'])
    return user


@pytest.fixture
def user_administrativo(setor_administrativo):
    return User.objects.create_user(
        matricula='ADM001',
        password=SENHA,
        nome='Usuário Administrativo',
        setor=setor_administrativo,
    )


@pytest.fixture
def auxiliar_obras(setor_obras):
    user = User.objects.create_user(
        matricula='OBRAS003',
        password=SENHA,
        nome='Auxiliar Obras',
        setor=setor_obras,
    )
    VinculoAuxiliar.objects.create(usuario=user, setor=setor_obras)
    return user


@pytest.fixture
def auxiliar_almoxarifado(setor_obras, setor_almoxarifado):
    user = User.objects.create_user(
        matricula='ALMOX001',
        password=SENHA,
        nome='Auxiliar Almoxarifado',
        setor=setor_obras,
    )
    VinculoAuxiliar.objects.create(usuario=user, setor=setor_almoxarifado)
    return user


@pytest.fixture
def estoque_principal(db):
    return Estoque.objects.create(codigo='EST-PRINCIPAL', nome='Estoque Principal')


@pytest.fixture
def material_papel(estoque_principal):
    material = Material.objects.create(
        codigo='MAT-001',
        nome='Papel A4',
        unidade=UnidadeMedida.UNIDADE,
    )
    SaldoEstoque.objects.create(
        estoque=estoque_principal,
        material=material,
        saldo_fisico=Decimal('10.000'),
        saldo_reservado=Decimal('2.000'),
    )
    return material


@pytest.fixture
def material_caneta(estoque_principal):
    material = Material.objects.create(
        codigo='MAT-002',
        nome='Caneta esferográfica',
        unidade=UnidadeMedida.UNIDADE,
    )
    SaldoEstoque.objects.create(
        estoque=estoque_principal,
        material=material,
        saldo_fisico=Decimal('20.000'),
    )
    return material
