"""Testes de selector para estoque.saidas_excepcionais."""

from apps.estoque.models import SaidaExcepcional
from apps.estoque.selectors import listar_saidas_excepcionais


class TestListarSaidasExcepcionais:
    def test_retorna_queryset_vazio_quando_sem_registros(self, db, chefe_almoxarifado):
        qs = listar_saidas_excepcionais(chefe_almoxarifado.pk)
        assert list(qs) == []

    def test_retorna_saidas_existentes(self, db, chefe_almoxarifado, estoque_principal):
        saida = SaidaExcepcional.objects.create(
            motivo='Descarte por vencimento',
            registrado_por=chefe_almoxarifado,
            estoque=estoque_principal,
        )
        qs = listar_saidas_excepcionais(chefe_almoxarifado.pk)
        assert saida in qs

    def test_ordena_por_mais_recente_primeiro(
        self, db, chefe_almoxarifado, estoque_principal
    ):
        s1 = SaidaExcepcional.objects.create(
            motivo='Primeiro',
            registrado_por=chefe_almoxarifado,
            estoque=estoque_principal,
        )
        s2 = SaidaExcepcional.objects.create(
            motivo='Segundo',
            registrado_por=chefe_almoxarifado,
            estoque=estoque_principal,
        )
        qs = list(listar_saidas_excepcionais(chefe_almoxarifado.pk))
        assert qs[0] == s2
        assert qs[1] == s1

    def test_anota_quantidade_itens(
        self, db, chefe_almoxarifado, estoque_principal, material_disponivel
    ):
        from apps.estoque.models import ItemSaidaExcepcional

        saida = SaidaExcepcional.objects.create(
            motivo='Com itens',
            registrado_por=chefe_almoxarifado,
            estoque=estoque_principal,
        )
        ItemSaidaExcepcional.objects.create(
            saida=saida, material=material_disponivel, quantidade=5
        )
        qs = listar_saidas_excepcionais(chefe_almoxarifado.pk)
        saida_anotada = qs.get(pk=saida.pk)
        assert saida_anotada.quantidade_itens == 1


class TestBuscarDetalheSaidaExcepcional:
    def test_retorna_saida_com_itens(
        self,
        chefe_almoxarifado,
        estoque_principal,
        material_disponivel,
        saida_registrada,
    ):
        from apps.estoque.selectors import buscar_detalhe_saida_excepcional

        saida = buscar_detalhe_saida_excepcional(saida_id=saida_registrada.pk)
        assert saida is not None
        assert saida.pk == saida_registrada.pk
        assert len(saida.itens.all()) == 1

    def test_retorna_none_para_inexistente(self, db):
        from apps.estoque.selectors import buscar_detalhe_saida_excepcional

        assert buscar_detalhe_saida_excepcional(saida_id=999999) is None
