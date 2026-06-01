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


class TestGerarPreviewImportacaoScpi:
    """Testes de comportamento de gerar_preview_importacao_scpi."""

    def _csv(self, linhas: list[str]) -> bytes:
        cabecalho = 'CADPRO;QUANTIDADE'
        return '\n'.join([cabecalho] + linhas).encode('utf-8')

    def test_material_existente_saldo_igual_retorna_ok(
        self, db, estoque_principal, material_disponivel
    ):
        from apps.estoque.selectors import gerar_preview_importacao_scpi

        # saldo_fisico do material_disponivel = 100
        csv_bytes = self._csv([f'{material_disponivel.codigo};100.000'])
        linhas = gerar_preview_importacao_scpi(
            conteudo_bytes=csv_bytes, estoque_id=estoque_principal.pk
        )
        assert len(linhas) == 1
        assert linhas[0].cadpro == material_disponivel.codigo
        assert linhas[0].status == 'ok'


class TestGerarPreviewImportacaoScpiCasos:
    """Casos adicionais: divergências, novos, erros de formato."""

    def _csv(self, linhas: list[str]) -> bytes:
        return ('CADPRO;QUANTIDADE\n' + '\n'.join(linhas)).encode('utf-8')

    def test_divergencia_retorna_status_divergente(
        self, db, estoque_principal, material_disponivel
    ):
        from apps.estoque.selectors import gerar_preview_importacao_scpi

        # saldo_fisico = 100, SCPI diz 80 → divergência
        csv_bytes = self._csv([f'{material_disponivel.codigo};80.000'])
        linhas = gerar_preview_importacao_scpi(
            conteudo_bytes=csv_bytes, estoque_id=estoque_principal.pk
        )
        assert linhas[0].status == 'divergente'
        assert linhas[0].delta == -20

    def test_cadpro_inexistente_retorna_status_novo(self, db, estoque_principal):
        from apps.estoque.selectors import gerar_preview_importacao_scpi

        csv_bytes = self._csv(['CODNOVO999;50.000'])
        linhas = gerar_preview_importacao_scpi(
            conteudo_bytes=csv_bytes, estoque_id=estoque_principal.pk
        )
        assert linhas[0].status == 'novo'
        assert linhas[0].material_id is None
        assert linhas[0].saldo_wms == 0

    def test_csv_com_bom_parseia_corretamente(
        self, db, estoque_principal, material_disponivel
    ):
        from apps.estoque.selectors import gerar_preview_importacao_scpi

        csv_com_bom = (
            f'﻿CADPRO;QUANTIDADE\n{material_disponivel.codigo};100.000'
        ).encode('utf-8')
        linhas = gerar_preview_importacao_scpi(
            conteudo_bytes=csv_com_bom, estoque_id=estoque_principal.pk
        )
        assert len(linhas) == 1
        assert linhas[0].cadpro == material_disponivel.codigo

    def test_csv_apenas_cabecalho_retorna_lista_vazia(self, db, estoque_principal):
        from apps.estoque.selectors import gerar_preview_importacao_scpi

        csv_bytes = 'CADPRO;QUANTIDADE\n'.encode('utf-8')
        linhas = gerar_preview_importacao_scpi(
            conteudo_bytes=csv_bytes, estoque_id=estoque_principal.pk
        )
        assert linhas == []

    def test_quantidade_invalida_lanca_dados_invalidos(self, db, estoque_principal):
        import pytest

        from apps.core.exceptions import DadosInvalidos
        from apps.estoque.selectors import gerar_preview_importacao_scpi

        csv_bytes = 'CADPRO;QUANTIDADE\nMAT001;abc\n'.encode('utf-8')
        with pytest.raises(DadosInvalidos):
            gerar_preview_importacao_scpi(
                conteudo_bytes=csv_bytes, estoque_id=estoque_principal.pk
            )

    def test_csv_sem_coluna_cadpro_lanca_dados_invalidos(self, db, estoque_principal):
        import pytest

        from apps.core.exceptions import DadosInvalidos
        from apps.estoque.selectors import gerar_preview_importacao_scpi

        csv_bytes = 'COD;QUANTIDADE\nMAT001;10\n'.encode('utf-8')
        with pytest.raises(DadosInvalidos):
            gerar_preview_importacao_scpi(
                conteudo_bytes=csv_bytes, estoque_id=estoque_principal.pk
            )


class TestNormalizacaoCsvScpi:
    """Testes de normalização e erros de codificação."""

    def test_codificacao_invalida_lanca_dados_invalidos(self, db, estoque_principal):
        import pytest

        from apps.core.exceptions import DadosInvalidos
        from apps.estoque.selectors import gerar_preview_importacao_scpi

        bytes_invalidos = b'\xff\xfe' + b'\x80\x81' * 20
        with pytest.raises(DadosInvalidos, match='UTF-8'):
            gerar_preview_importacao_scpi(
                conteudo_bytes=bytes_invalidos, estoque_id=estoque_principal.pk
            )
