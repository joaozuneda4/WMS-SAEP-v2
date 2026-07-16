import pytest
from django.test import RequestFactory

from apps.accounts.models import VinculoAuxiliar
from apps.core.listagem import paginar_com_filtros

pytestmark = pytest.mark.django_db


def _request(factory, params='', htmx=False):
    request = factory.get(f'/qualquer/?{params}')
    request.htmx = htmx
    return request


class TestPaginarComFiltrosOrdenacao:
    def test_ordem_default_desc_quando_ausente(self, setor_comum, solicitante):
        primeiro = VinculoAuxiliar.objects.create(
            usuario=solicitante, setor=setor_comum
        )
        segundo = VinculoAuxiliar.objects.create(
            usuario=solicitante, setor=setor_comum, ativo=False
        )

        request = _request(RequestFactory())
        resultado = paginar_com_filtros(
            request, VinculoAuxiliar.objects.all(), per_page=25
        )

        assert resultado.ordem == 'desc'
        assert list(resultado.page_obj.object_list) == [segundo, primeiro]

    def test_ordem_asc_inverte_cronologia(self, setor_comum, solicitante):
        primeiro = VinculoAuxiliar.objects.create(
            usuario=solicitante, setor=setor_comum
        )
        segundo = VinculoAuxiliar.objects.create(
            usuario=solicitante, setor=setor_comum, ativo=False
        )

        request = _request(RequestFactory(), params='ordem=asc')
        resultado = paginar_com_filtros(
            request, VinculoAuxiliar.objects.all(), per_page=25
        )

        assert resultado.ordem == 'asc'
        assert list(resultado.page_obj.object_list) == [primeiro, segundo]

    def test_ordem_invalida_cai_no_default_desc(self, setor_comum, solicitante):
        primeiro = VinculoAuxiliar.objects.create(
            usuario=solicitante, setor=setor_comum
        )
        segundo = VinculoAuxiliar.objects.create(
            usuario=solicitante, setor=setor_comum, ativo=False
        )

        request = _request(RequestFactory(), params='ordem=lixo')
        resultado = paginar_com_filtros(
            request, VinculoAuxiliar.objects.all(), per_page=25
        )

        assert resultado.ordem == 'desc'
        assert list(resultado.page_obj.object_list) == [segundo, primeiro]


class TestPaginarComFiltrosMetadados:
    def test_url_ordenacao_inverte_ordem_e_preserva_outros_params_removendo_page(
        self, setor_comum, solicitante
    ):
        VinculoAuxiliar.objects.create(usuario=solicitante, setor=setor_comum)

        request = _request(RequestFactory(), params='material=parafuso&page=2')
        resultado = paginar_com_filtros(
            request, VinculoAuxiliar.objects.all(), per_page=25
        )

        assert 'page' not in resultado.url_ordenacao
        assert 'material=parafuso' in resultado.url_ordenacao
        assert 'ordem=asc' in resultado.url_ordenacao

    def test_aria_sort_corresponde_a_ordem(self, setor_comum, solicitante):
        VinculoAuxiliar.objects.create(usuario=solicitante, setor=setor_comum)

        request_desc = _request(RequestFactory())
        request_asc = _request(RequestFactory(), params='ordem=asc')

        resultado_desc = paginar_com_filtros(
            request_desc, VinculoAuxiliar.objects.all(), per_page=25
        )
        resultado_asc = paginar_com_filtros(
            request_asc, VinculoAuxiliar.objects.all(), per_page=25
        )

        assert resultado_desc.aria_sort == 'descending'
        assert resultado_asc.aria_sort == 'ascending'

    def test_is_htmx_reflete_request_htmx(self, setor_comum, solicitante):
        VinculoAuxiliar.objects.create(usuario=solicitante, setor=setor_comum)

        request_htmx = _request(RequestFactory(), htmx=True)
        request_normal = _request(RequestFactory(), htmx=False)

        resultado_htmx = paginar_com_filtros(
            request_htmx, VinculoAuxiliar.objects.all(), per_page=25
        )
        resultado_normal = paginar_com_filtros(
            request_normal, VinculoAuxiliar.objects.all(), per_page=25
        )

        assert resultado_htmx.is_htmx is True
        assert resultado_normal.is_htmx is False

    def test_querystring_filtros_remove_page(self, setor_comum, solicitante):
        VinculoAuxiliar.objects.create(usuario=solicitante, setor=setor_comum)

        request = _request(RequestFactory(), params='material=parafuso&page=2')
        resultado = paginar_com_filtros(
            request, VinculoAuxiliar.objects.all(), per_page=25
        )

        assert 'page' not in resultado.querystring_filtros
        assert 'material=parafuso' in resultado.querystring_filtros

    def test_page_obj_pagina_com_per_page_customizado(self, setor_comum, solicitante):
        for _ in range(3):
            VinculoAuxiliar.objects.create(
                usuario=solicitante, setor=setor_comum, ativo=False
            )

        request = _request(RequestFactory())
        resultado = paginar_com_filtros(
            request, VinculoAuxiliar.objects.all(), per_page=2
        )

        assert resultado.page_obj.paginator.count == 3
        assert len(resultado.page_obj.object_list) == 2
        assert resultado.page_obj.has_next() is True
