"""Testes do módulo accounts.papeis — PapelEfetivo VO e papel_efetivo() resolver."""

import pytest

from apps.accounts.papeis import PapelEfetivo


# ---------------------------------------------------------------------------
# Sem banco — VO puro
# ---------------------------------------------------------------------------


def test_papel_efetivo_construivel_sem_banco():
    """PapelEfetivo pode ser instanciado com escalares, sem acesso ao banco."""
    papel = PapelEfetivo(
        eh_almoxarifado=False,
        eh_chefe_de_almoxarifado=False,
        setores_em_escopo=(),
        setor_chefiado_ativo_id=None,
        pode_ser_beneficiario=True,
    )
    assert papel.eh_almoxarifado is False
    assert papel.eh_chefe_de_almoxarifado is False
    assert papel.setores_em_escopo == ()
    assert papel.setor_chefiado_ativo_id is None
    assert papel.pode_ser_beneficiario is True


def test_papel_efetivo_e_imutavel():
    """PapelEfetivo levanta FrozenInstanceError ao tentar reatribuir campo."""
    from dataclasses import FrozenInstanceError

    papel = PapelEfetivo(
        eh_almoxarifado=False,
        eh_chefe_de_almoxarifado=False,
        setores_em_escopo=(),
        setor_chefiado_ativo_id=None,
        pode_ser_beneficiario=True,
    )
    with pytest.raises(FrozenInstanceError):
        papel.eh_almoxarifado = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Fixtures locais
# ---------------------------------------------------------------------------


@pytest.fixture
def setor_comum(db):
    from apps.accounts.models import Setor, SetorClassificacao

    return Setor.objects.create(
        codigo='SC', nome='Setor Comum', classificacao=SetorClassificacao.COMUM
    )


@pytest.fixture
def setor_almox(db):
    from apps.accounts.models import Setor, SetorClassificacao

    return Setor.objects.create(
        codigo='ALM', nome='Almoxarifado', classificacao=SetorClassificacao.ALMOXARIFADO
    )


@pytest.fixture
def usuario(db, setor_comum):
    from apps.accounts.models import User

    return User.objects.create_user(
        matricula='U99', nome='Usuário Teste', password='x', setor=setor_comum
    )


# ---------------------------------------------------------------------------
# Com banco — papel_efetivo()
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_sem_chefia_sem_vinculo(usuario):
    """Usuário sem chefia e sem vínculo de auxiliar tem papel vazio."""
    from apps.accounts.papeis import papel_efetivo

    papel = papel_efetivo(usuario)

    assert papel.eh_almoxarifado is False
    assert papel.eh_chefe_de_almoxarifado is False
    assert papel.setores_em_escopo == ()
    assert papel.setor_chefiado_ativo_id is None
    assert papel.pode_ser_beneficiario is True


@pytest.mark.django_db
def test_chefe_de_almoxarifado_ativo(usuario, setor_almox):
    """Chefe do almoxarifado ativo: eh_almoxarifado e eh_chefe_de_almoxarifado True."""
    from apps.accounts.papeis import papel_efetivo

    setor_almox.chefe = usuario
    setor_almox.ativo = True
    setor_almox.save()

    papel = papel_efetivo(usuario)

    assert papel.eh_almoxarifado is True
    assert papel.eh_chefe_de_almoxarifado is True
    assert papel.setores_em_escopo == ()
    assert papel.setor_chefiado_ativo_id == setor_almox.pk


@pytest.mark.django_db
def test_auxiliar_de_almoxarifado_sem_chefia(usuario, setor_almox):
    """Auxiliar de almoxarifado (sem chefia): eh_almoxarifado True, chefe False."""
    from apps.accounts.models import VinculoAuxiliar
    from apps.accounts.papeis import papel_efetivo

    VinculoAuxiliar.objects.create(usuario=usuario, setor=setor_almox, ativo=True)

    papel = papel_efetivo(usuario)

    assert papel.eh_almoxarifado is True
    assert papel.eh_chefe_de_almoxarifado is False
    assert papel.setores_em_escopo == ()
    assert papel.setor_chefiado_ativo_id is None


@pytest.mark.django_db
def test_chefe_de_setor_comum_ativo(usuario, setor_comum):
    """Chefe de setor comum: setores_em_escopo contém o pk do setor, não é almox."""
    from apps.accounts.papeis import papel_efetivo

    setor_comum.chefe = usuario
    setor_comum.ativo = True
    setor_comum.save()

    papel = papel_efetivo(usuario)

    assert papel.eh_almoxarifado is False
    assert papel.eh_chefe_de_almoxarifado is False
    assert setor_comum.pk in papel.setores_em_escopo
    assert papel.setor_chefiado_ativo_id == setor_comum.pk


@pytest.mark.django_db
def test_auxiliar_de_setor_comum_sem_chefia(db, usuario):
    """Auxiliar de setor comum (sem chefia): setores_em_escopo contém o pk."""
    from apps.accounts.models import Setor, SetorClassificacao, VinculoAuxiliar
    from apps.accounts.papeis import papel_efetivo

    outro_setor = Setor.objects.create(
        codigo='SC2', nome='Setor Comum 2', classificacao=SetorClassificacao.COMUM
    )
    VinculoAuxiliar.objects.create(usuario=usuario, setor=outro_setor, ativo=True)

    papel = papel_efetivo(usuario)

    assert papel.eh_almoxarifado is False
    assert papel.eh_chefe_de_almoxarifado is False
    assert outro_setor.pk in papel.setores_em_escopo
    assert papel.setor_chefiado_ativo_id is None


@pytest.mark.django_db
def test_setor_chefiado_inativo_nao_conta(usuario, setor_comum):
    """Setor chefiado inativo: setor_chefiado_ativo_id None, não entra no escopo."""
    from apps.accounts.papeis import papel_efetivo

    setor_comum.chefe = usuario
    setor_comum.ativo = False
    setor_comum.save()

    papel = papel_efetivo(usuario)

    assert papel.eh_almoxarifado is False
    assert papel.eh_chefe_de_almoxarifado is False
    assert papel.setores_em_escopo == ()
    assert papel.setor_chefiado_ativo_id is None


@pytest.mark.django_db
def test_setor_chefiado_inativo_auxiliar_almox(usuario, setor_almox, setor_comum):
    """Setor chefiado inativo + auxiliar de almox: eh_almoxarifado True, chefe False."""
    from apps.accounts.models import VinculoAuxiliar
    from apps.accounts.papeis import papel_efetivo

    setor_comum.chefe = usuario
    setor_comum.ativo = False
    setor_comum.save()
    VinculoAuxiliar.objects.create(usuario=usuario, setor=setor_almox, ativo=True)

    papel = papel_efetivo(usuario)

    assert papel.eh_almoxarifado is True
    assert papel.eh_chefe_de_almoxarifado is False
    assert papel.setores_em_escopo == ()
    assert papel.setor_chefiado_ativo_id is None


@pytest.mark.django_db
def test_usuario_inativo_nao_tem_papel_operacional(db, setor_almox):
    """Usuário inativo com chefia ativa: todos os flags operacionais False, sem hit no banco."""
    from apps.accounts.models import User
    from apps.accounts.papeis import papel_efetivo

    inativo = User.objects.create_user(
        matricula='U96', nome='Inativo Chefe', password='x', is_active=False
    )
    setor_almox.chefe = inativo
    setor_almox.ativo = True
    setor_almox.save()

    papel = papel_efetivo(inativo)

    assert papel.eh_almoxarifado is False
    assert papel.eh_chefe_de_almoxarifado is False
    assert papel.setores_em_escopo == ()
    assert papel.setor_chefiado_ativo_id is None
    assert papel.pode_ser_beneficiario is False


@pytest.mark.django_db
def test_pode_ser_beneficiario_inativo(db):
    """Usuário inativo: pode_ser_beneficiario False mesmo com setor."""
    from apps.accounts.models import Setor, SetorClassificacao, User
    from apps.accounts.papeis import papel_efetivo

    setor = Setor.objects.create(
        codigo='SX', nome='Setor X', classificacao=SetorClassificacao.COMUM
    )
    inativo = User.objects.create_user(
        matricula='U98', nome='Inativo', password='x', setor=setor, is_active=False
    )

    papel = papel_efetivo(inativo)

    assert papel.pode_ser_beneficiario is False


@pytest.mark.django_db
def test_pode_ser_beneficiario_sem_setor(db):
    """Usuário ativo sem setor: pode_ser_beneficiario False."""
    from apps.accounts.models import User
    from apps.accounts.papeis import papel_efetivo

    sem_setor = User.objects.create_user(
        matricula='U97', nome='Sem Setor', password='x'
    )

    papel = papel_efetivo(sem_setor)

    assert papel.pode_ser_beneficiario is False
