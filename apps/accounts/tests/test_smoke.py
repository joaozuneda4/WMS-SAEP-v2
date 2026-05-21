"""Teste de fumaça: valida o setup pytest-django contra PostgreSQL."""

import pytest

from apps.accounts.models import Setor


@pytest.mark.django_db
def test_cria_setor():
    setor = Setor.objects.create(codigo='SMK', nome='Setor de Fumaça')
    assert setor.pk is not None
