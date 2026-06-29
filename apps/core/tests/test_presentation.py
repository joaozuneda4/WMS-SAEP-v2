"""Testes unitários do tradutor de erro de domínio (sem request, sem DB)."""

import pytest

from apps.core.exceptions import (
    ConflitoDominio,
    DadosInvalidos,
    ErroDominio,
    EstadoInvalido,
    PermissaoNegada,
)
from apps.core.presentation import ErroPresentation, traduz_erro_dominio


def test_permissao_negada_mapeia_403_error():
    pres = traduz_erro_dominio(PermissaoNegada())
    assert pres.status == 403
    assert pres.severity == 'error'
    assert 'permissão' in pres.default_message


def test_dados_invalidos_mapeia_422_error():
    pres = traduz_erro_dominio(DadosInvalidos('campo ruim'))
    assert pres.status == 422
    assert pres.severity == 'error'
    assert 'inválidos' in pres.default_message


def test_estado_invalido_mapeia_409_warning():
    pres = traduz_erro_dominio(EstadoInvalido('transição inválida'))
    assert pres.status == 409
    assert pres.severity == 'warning'
    assert (
        'estado' in pres.default_message.lower()
        or 'transição' in pres.default_message.lower()
    )


def test_conflito_dominio_mapeia_409_warning():
    pres = traduz_erro_dominio(ConflitoDominio('saldo insuficiente'))
    assert pres.status == 409
    assert pres.severity == 'warning'
    assert (
        'conflito' in pres.default_message.lower()
        or 'domínio' in pres.default_message.lower()
    )


def test_erro_presentation_e_imutavel():
    pres = ErroPresentation(status=422, severity='error', default_message='x')
    with pytest.raises(Exception):
        pres.status = 999  # type: ignore[misc]


def test_subtipo_desconhecido_cai_no_fallback_error():
    class ErroDesconhecido(ErroDominio):
        pass

    pres = traduz_erro_dominio(ErroDesconhecido('ops'))
    assert pres.severity == 'error'
    assert pres.status == 500
