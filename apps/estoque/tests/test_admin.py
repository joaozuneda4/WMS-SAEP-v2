"""Testes do admin de estoque.

Guard de estoque único em `EstoqueAdmin` (issue #102, ADR-0017).
"""

import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory

from apps.estoque.admin import EstoqueAdmin
from apps.estoque.models import Estoque


@pytest.fixture
def estoque_admin():
    return EstoqueAdmin(Estoque, AdminSite())


@pytest.fixture
def request_de(rf: RequestFactory):
    """Devolve um request de admin já autenticado como o usuário dado."""

    def _request(usuario):
        req = rf.get('/admin/estoque/estoque/add/')
        req.user = usuario
        return req

    return _request


def test_nao_permite_adicionar_segundo_estoque(
    estoque_admin, request_de, superuser, estoque_principal
):
    assert estoque_admin.has_add_permission(request_de(superuser)) is False


def test_permite_adicionar_o_primeiro_estoque(estoque_admin, request_de, superuser):
    assert Estoque.objects.exists() is False

    assert estoque_admin.has_add_permission(request_de(superuser)) is True


def test_estoque_inativo_tambem_bloqueia_adicao(estoque_admin, request_de, superuser):
    """O guard não filtra por `ativo`.

    Os services localizam `SaldoEstoque` por `material_id` sem olhar
    `estoque.ativo`: um segundo estoque inativo com saldo quebraria a
    autorização do mesmo jeito.
    """
    Estoque.objects.create(codigo='EST99', nome='Estoque Desativado', ativo=False)

    assert estoque_admin.has_add_permission(request_de(superuser)) is False


def test_guard_nao_concede_permissao_a_quem_nao_tem(
    estoque_admin, request_de, chefe_almoxarifado
):
    """O guard compõe com a checagem padrão do Django, não a substitui."""
    assert Estoque.objects.exists() is False

    assert estoque_admin.has_add_permission(request_de(chefe_almoxarifado)) is False
