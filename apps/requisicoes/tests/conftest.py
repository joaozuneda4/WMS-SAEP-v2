"""Fixtures compartilhadas pelos testes de requisicoes.

Sem factory_boy, sem seed_dev como pré-condição (ADR-0010).
Cada fixture cria apenas o necessário para os seus testes.
"""

import pytest

from apps.accounts.models import Setor, SetorClassificacao, User, VinculoAuxiliar
from apps.estoque.models import Estoque, Material, SaldoEstoque, UnidadeMedida
from apps.requisicoes.models import EstadoRequisicao, Requisicao


# ---------------------------------------------------------------------------
# Setores
# ---------------------------------------------------------------------------


@pytest.fixture
def setor_obras(db):
    return Setor.objects.create(
        codigo='OBR', nome='Obras', classificacao=SetorClassificacao.COMUM
    )


@pytest.fixture
def setor_ti(db):
    return Setor.objects.create(
        codigo='TI', nome='TI', classificacao=SetorClassificacao.COMUM
    )


@pytest.fixture
def setor_almoxarifado(db):
    return Setor.objects.create(
        codigo='ALM', nome='Almoxarifado', classificacao=SetorClassificacao.ALMOXARIFADO
    )


# ---------------------------------------------------------------------------
# Usuários
# ---------------------------------------------------------------------------


@pytest.fixture
def solicitante(db, setor_obras):
    """Usuário comum do setor Obras — solicitante puro."""
    u = User.objects.create_user(
        matricula='001',
        nome='João Solicitante',
        password='senha',
        setor=setor_obras,
    )
    return u


@pytest.fixture
def outro_usuario_obras(db, setor_obras):
    u = User.objects.create_user(
        matricula='002',
        nome='Maria Obras',
        password='senha',
        setor=setor_obras,
    )
    return u


@pytest.fixture
def usuario_ti(db, setor_ti):
    u = User.objects.create_user(
        matricula='003',
        nome='Carlos TI',
        password='senha',
        setor=setor_ti,
    )
    return u


@pytest.fixture
def chefe_obras(db, setor_obras):
    """Chefe do setor Obras."""
    u = User.objects.create_user(
        matricula='010',
        nome='Ana Chefe Obras',
        password='senha',
        setor=setor_obras,
    )
    setor_obras.chefe = u
    setor_obras.save(update_fields=['chefe'])
    return u


@pytest.fixture
def aux_obras(db, setor_obras):
    """Auxiliar de setor do setor Obras."""
    u = User.objects.create_user(
        matricula='011',
        nome='Pedro Aux Obras',
        password='senha',
        setor=setor_obras,
    )
    VinculoAuxiliar.objects.create(usuario=u, setor=setor_obras, ativo=True)
    return u


@pytest.fixture
def aux_almoxarifado(db, setor_almoxarifado):
    """Auxiliar de almoxarifado."""
    u = User.objects.create_user(
        matricula='020',
        nome='Luísa Aux Almox',
        password='senha',
        setor=setor_almoxarifado,
    )
    VinculoAuxiliar.objects.create(usuario=u, setor=setor_almoxarifado, ativo=True)
    return u


@pytest.fixture
def chefe_almoxarifado(db, setor_almoxarifado):
    """Chefe do almoxarifado."""
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
def superuser(db, setor_obras):
    """Superusuário técnico para testar bypass de permissão."""
    return User.objects.create_superuser(
        matricula='900',
        nome='Super Usuário',
        password='senha',
        setor=setor_obras,
    )


@pytest.fixture
def usuario_sem_setor(db):
    """Usuário ativo sem setor — não pode criar requisição para si."""
    return User.objects.create_user(
        matricula='099',
        nome='Sem Setor',
        password='senha',
        setor=None,
    )


@pytest.fixture
def usuario_inativo(db, setor_obras):
    u = User.objects.create_user(
        matricula='098',
        nome='Inativo',
        password='senha',
        setor=setor_obras,
        is_active=False,
    )
    return u


# ---------------------------------------------------------------------------
# Estoque e materiais
# ---------------------------------------------------------------------------


@pytest.fixture
def estoque_principal(db):
    return Estoque.objects.create(codigo='EST01', nome='Estoque Principal')


@pytest.fixture
def material_disponivel(db, estoque_principal):
    """Material ativo com saldo disponível."""
    m = Material.objects.create(
        codigo='MAT001',
        nome='Parafuso M6',
        unidade=UnidadeMedida.UNIDADE,
        ativo=True,
    )
    SaldoEstoque.objects.create(
        estoque=estoque_principal,
        material=m,
        saldo_fisico=100,
        saldo_reservado=10,
    )
    return m


@pytest.fixture
def material_sem_saldo(db, estoque_principal):
    """Material ativo sem saldo disponível (físico = reservado)."""
    m = Material.objects.create(
        codigo='MAT002',
        nome='Prego 17x27',
        unidade=UnidadeMedida.UNIDADE,
        ativo=True,
    )
    SaldoEstoque.objects.create(
        estoque=estoque_principal,
        material=m,
        saldo_fisico=5,
        saldo_reservado=5,
    )
    return m


@pytest.fixture
def material_divergente(db, estoque_principal):
    """Material com divergência crítica (físico < reservado)."""
    m = Material.objects.create(
        codigo='MAT003',
        nome='Tinta Branca 18L',
        unidade=UnidadeMedida.LITRO,
        ativo=True,
    )
    SaldoEstoque.objects.create(
        estoque=estoque_principal,
        material=m,
        saldo_fisico=2,
        saldo_reservado=5,  # divergente
    )
    return m


@pytest.fixture
def material_inativo(db, estoque_principal):
    """Material inativo — não pode ser requisitado."""
    m = Material.objects.create(
        codigo='MAT004',
        nome='Material Descontinuado',
        unidade=UnidadeMedida.UNIDADE,
        ativo=False,
    )
    SaldoEstoque.objects.create(
        estoque=estoque_principal,
        material=m,
        saldo_fisico=50,
        saldo_reservado=0,
    )
    return m


@pytest.fixture
def material_disponivel_2(db, estoque_principal):
    """Segundo material elegível para testes de múltiplos itens."""
    m = Material.objects.create(
        codigo='MAT005',
        nome='Fita Isolante',
        unidade=UnidadeMedida.ROLO,
        ativo=True,
    )
    SaldoEstoque.objects.create(
        estoque=estoque_principal,
        material=m,
        saldo_fisico=30,
        saldo_reservado=0,
    )
    return m


# ---------------------------------------------------------------------------
# Requisições para testes de histórico
# ---------------------------------------------------------------------------


@pytest.fixture
def req_historico_obras(db, solicitante, setor_obras):
    return Requisicao.objects.create(
        estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        numero_publico='REQ-2026-0010',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )


@pytest.fixture
def req_historico_ti(db, usuario_ti, outro_usuario_obras, setor_ti):
    """Criador e beneficiário distintos — cobre busca textual por beneficiário."""
    return Requisicao.objects.create(
        estado=EstadoRequisicao.AUTORIZADA,
        numero_publico='REQ-2026-0011',
        criador=usuario_ti,
        beneficiario=outro_usuario_obras,
        setor_beneficiario=setor_ti,
    )
