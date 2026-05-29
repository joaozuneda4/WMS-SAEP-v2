"""Testes de policy para estoque.saidas_excepcionais."""

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
