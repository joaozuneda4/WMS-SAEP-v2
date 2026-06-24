"""Testes de policy para estoque.saidas_excepcionais."""

import pytest

from apps.estoque.policies import pode_consultar_saidas_excepcionais


class TestPodeConsultarSaidasExcepcionais:
    def test_chefe_almoxarifado_pode(self, chefe_almoxarifado):
        assert pode_consultar_saidas_excepcionais(chefe_almoxarifado) is True

    def test_aux_almoxarifado_pode(self, aux_almoxarifado):
        assert pode_consultar_saidas_excepcionais(aux_almoxarifado) is True

    def test_superuser_pode(self, superuser):
        assert pode_consultar_saidas_excepcionais(superuser) is True

    def test_solicitante_nao_pode(self, solicitante):
        assert pode_consultar_saidas_excepcionais(solicitante) is False

    def test_inativo_almox_nao_pode(self, usuario_inativo):
        assert pode_consultar_saidas_excepcionais(usuario_inativo) is False


class TestExigirPodeRegistrarSaidaExcepcional:
    def test_chefe_almoxarifado_nao_lanca(self, chefe_almoxarifado):
        from apps.estoque.policies import exigir_pode_registrar_saida_excepcional

        exigir_pode_registrar_saida_excepcional(chefe_almoxarifado)

    def test_superuser_nao_lanca(self, superuser):
        from apps.estoque.policies import exigir_pode_registrar_saida_excepcional

        exigir_pode_registrar_saida_excepcional(superuser)

    def test_aux_almox_lanca_permissao_negada(self, aux_almoxarifado):
        import pytest
        from apps.core.exceptions import PermissaoNegada
        from apps.estoque.policies import exigir_pode_registrar_saida_excepcional

        with pytest.raises(PermissaoNegada):
            exigir_pode_registrar_saida_excepcional(aux_almoxarifado)

    def test_solicitante_lanca_permissao_negada(self, solicitante):
        import pytest
        from apps.core.exceptions import PermissaoNegada
        from apps.estoque.policies import exigir_pode_registrar_saida_excepcional

        with pytest.raises(PermissaoNegada):
            exigir_pode_registrar_saida_excepcional(solicitante)

    def test_usuario_inativo_lanca_permissao_negada(self, usuario_inativo):
        import pytest

        from apps.core.exceptions import PermissaoNegada
        from apps.estoque.policies import exigir_pode_registrar_saida_excepcional

        with pytest.raises(PermissaoNegada):
            exigir_pode_registrar_saida_excepcional(usuario_inativo)


class TestPodeVisualizarPreviewScpi:
    def test_superuser_pode(self, superuser):
        from apps.estoque.policies import pode_visualizar_preview_scpi

        assert pode_visualizar_preview_scpi(superuser) is True

    def test_inativo_nao_pode(self, usuario_inativo):
        from apps.estoque.policies import pode_visualizar_preview_scpi

        assert pode_visualizar_preview_scpi(usuario_inativo) is False

    def test_chefe_almoxarifado_nao_pode(self, chefe_almoxarifado):
        from apps.estoque.policies import pode_visualizar_preview_scpi

        assert pode_visualizar_preview_scpi(chefe_almoxarifado) is False

    def test_aux_almoxarifado_nao_pode(self, aux_almoxarifado):
        from apps.estoque.policies import pode_visualizar_preview_scpi

        assert pode_visualizar_preview_scpi(aux_almoxarifado) is False

    def test_solicitante_nao_pode(self, solicitante):
        from apps.estoque.policies import pode_visualizar_preview_scpi

        assert pode_visualizar_preview_scpi(solicitante) is False


class TestExigirPodeVisualizarPreviewScpi:
    def test_superuser_nao_lanca(self, superuser):
        from apps.estoque.policies import exigir_pode_visualizar_preview_scpi

        exigir_pode_visualizar_preview_scpi(superuser)

    def test_chefe_almoxarifado_lanca_permissao_negada(self, chefe_almoxarifado):
        import pytest

        from apps.core.exceptions import PermissaoNegada
        from apps.estoque.policies import exigir_pode_visualizar_preview_scpi

        with pytest.raises(PermissaoNegada):
            exigir_pode_visualizar_preview_scpi(chefe_almoxarifado)


class TestPodeEstornarSaidaExcepcional:
    def test_chefe_almoxarifado_pode(self, chefe_almoxarifado):
        from apps.estoque.policies import pode_estornar_saida_excepcional

        assert pode_estornar_saida_excepcional(chefe_almoxarifado) is True

    def test_superuser_pode(self, superuser):
        from apps.estoque.policies import pode_estornar_saida_excepcional

        assert pode_estornar_saida_excepcional(superuser) is True

    def test_aux_almox_nao_pode(self, aux_almoxarifado):
        from apps.estoque.policies import pode_estornar_saida_excepcional

        assert pode_estornar_saida_excepcional(aux_almoxarifado) is False

    def test_solicitante_nao_pode(self, solicitante):
        from apps.estoque.policies import pode_estornar_saida_excepcional

        assert pode_estornar_saida_excepcional(solicitante) is False

    def test_inativo_nao_pode(self, usuario_inativo):
        from apps.estoque.policies import pode_estornar_saida_excepcional

        assert pode_estornar_saida_excepcional(usuario_inativo) is False


class TestExigirPodeEstornarSaidaExcepcional:
    def test_chefe_almox_nao_lanca(self, chefe_almoxarifado):
        from apps.estoque.policies import exigir_pode_estornar_saida_excepcional

        exigir_pode_estornar_saida_excepcional(chefe_almoxarifado)

    def test_superuser_nao_lanca(self, superuser):
        from apps.estoque.policies import exigir_pode_estornar_saida_excepcional

        exigir_pode_estornar_saida_excepcional(superuser)

    def test_aux_almox_lanca_permissao_negada(self, aux_almoxarifado):
        import pytest

        from apps.core.exceptions import PermissaoNegada
        from apps.estoque.policies import exigir_pode_estornar_saida_excepcional

        with pytest.raises(PermissaoNegada):
            exigir_pode_estornar_saida_excepcional(aux_almoxarifado)

    def test_inativo_lanca_permissao_negada(self, usuario_inativo):
        import pytest

        from apps.core.exceptions import PermissaoNegada
        from apps.estoque.policies import exigir_pode_estornar_saida_excepcional

        with pytest.raises(PermissaoNegada):
            exigir_pode_estornar_saida_excepcional(usuario_inativo)


class TestPodeConsultarHistoricoScpi:
    def test_superuser_pode(self, superuser):
        from apps.estoque.policies import pode_consultar_historico_scpi

        assert pode_consultar_historico_scpi(superuser) is True

    def test_chefe_almoxarifado_pode(self, chefe_almoxarifado):
        from apps.estoque.policies import pode_consultar_historico_scpi

        assert pode_consultar_historico_scpi(chefe_almoxarifado) is True

    def test_inativo_nao_pode(self, usuario_inativo):
        from apps.estoque.policies import pode_consultar_historico_scpi

        assert pode_consultar_historico_scpi(usuario_inativo) is False

    def test_aux_almoxarifado_nao_pode(self, aux_almoxarifado):
        from apps.estoque.policies import pode_consultar_historico_scpi

        assert pode_consultar_historico_scpi(aux_almoxarifado) is False

    def test_solicitante_nao_pode(self, solicitante):
        from apps.estoque.policies import pode_consultar_historico_scpi

        assert pode_consultar_historico_scpi(solicitante) is False


class TestExigirPodeConsultarHistoricoScpi:
    def test_levanta_quando_negada(self, solicitante):
        from apps.core.exceptions import PermissaoNegada
        from apps.estoque.policies import exigir_pode_consultar_historico_scpi

        with pytest.raises(PermissaoNegada):
            exigir_pode_consultar_historico_scpi(solicitante)

    def test_nao_levanta_quando_superuser(self, superuser):
        from apps.estoque.policies import exigir_pode_consultar_historico_scpi

        exigir_pode_consultar_historico_scpi(superuser)

    def test_nao_levanta_quando_chefe_almoxarifado(self, chefe_almoxarifado):
        from apps.estoque.policies import exigir_pode_consultar_historico_scpi

        exigir_pode_consultar_historico_scpi(chefe_almoxarifado)


class TestPodeConsultarCatalogoEstoque:
    def test_chefe_almoxarifado_pode(self, chefe_almoxarifado):
        from apps.estoque.policies import pode_consultar_catalogo_estoque

        assert pode_consultar_catalogo_estoque(chefe_almoxarifado) is True

    def test_aux_almoxarifado_pode(self, aux_almoxarifado):
        from apps.estoque.policies import pode_consultar_catalogo_estoque

        assert pode_consultar_catalogo_estoque(aux_almoxarifado) is True

    def test_superuser_pode(self, superuser):
        from apps.estoque.policies import pode_consultar_catalogo_estoque

        assert pode_consultar_catalogo_estoque(superuser) is True

    def test_solicitante_pode(self, solicitante):
        from apps.estoque.policies import pode_consultar_catalogo_estoque

        assert pode_consultar_catalogo_estoque(solicitante) is True

    def test_inativo_nao_pode(self, usuario_inativo):
        from apps.estoque.policies import pode_consultar_catalogo_estoque

        assert pode_consultar_catalogo_estoque(usuario_inativo) is False


class TestExigirPodeConsultarCatalogoEstoque:
    def test_chefe_almoxarifado_nao_lanca(self, chefe_almoxarifado):
        from apps.estoque.policies import exigir_pode_consultar_catalogo_estoque

        exigir_pode_consultar_catalogo_estoque(chefe_almoxarifado)

    def test_solicitante_nao_lanca(self, solicitante):
        from apps.estoque.policies import exigir_pode_consultar_catalogo_estoque

        exigir_pode_consultar_catalogo_estoque(solicitante)

    def test_superuser_nao_lanca(self, superuser):
        from apps.estoque.policies import exigir_pode_consultar_catalogo_estoque

        exigir_pode_consultar_catalogo_estoque(superuser)

    def test_usuario_inativo_lanca_permissao_negada(self, usuario_inativo):
        from apps.core.exceptions import PermissaoNegada
        from apps.estoque.policies import exigir_pode_consultar_catalogo_estoque

        with pytest.raises(PermissaoNegada):
            exigir_pode_consultar_catalogo_estoque(usuario_inativo)


class TestPodeConsultarMovimentacoesEstoque:
    def test_superuser_pode(self, superuser):
        from apps.estoque.policies import pode_consultar_movimentacoes_estoque

        assert pode_consultar_movimentacoes_estoque(superuser) is True

    def test_chefe_almoxarifado_pode(self, chefe_almoxarifado):
        from apps.estoque.policies import pode_consultar_movimentacoes_estoque

        assert pode_consultar_movimentacoes_estoque(chefe_almoxarifado) is True

    def test_aux_almoxarifado_pode(self, aux_almoxarifado):
        from apps.estoque.policies import pode_consultar_movimentacoes_estoque

        assert pode_consultar_movimentacoes_estoque(aux_almoxarifado) is True

    def test_chefe_setor_nao_almox_pode(self, chefe_obras):
        from apps.estoque.policies import pode_consultar_movimentacoes_estoque

        assert pode_consultar_movimentacoes_estoque(chefe_obras) is True

    def test_aux_setor_nao_almox_pode(self, aux_obras):
        from apps.estoque.policies import pode_consultar_movimentacoes_estoque

        assert pode_consultar_movimentacoes_estoque(aux_obras) is True

    def test_solicitante_puro_nao_pode(self, solicitante):
        from apps.estoque.policies import pode_consultar_movimentacoes_estoque

        assert pode_consultar_movimentacoes_estoque(solicitante) is False

    def test_inativo_nao_pode(self, usuario_inativo):
        from apps.estoque.policies import pode_consultar_movimentacoes_estoque

        assert pode_consultar_movimentacoes_estoque(usuario_inativo) is False
