"""Testes de selector para estoque.saidas_excepcionais."""

import pytest

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
        cabecalho = 'CADPRO;DENOMINACAO;QUAN3'
        return '\n'.join([cabecalho] + linhas).encode('utf-8')

    def test_material_existente_saldo_igual_retorna_ok(
        self, db, estoque_principal, material_scpi
    ):
        from apps.estoque.selectors import gerar_preview_importacao_scpi

        # saldo_fisico do material_scpi = 100
        csv_bytes = self._csv([f'{material_scpi.codigo};Parafuso M6;100.000'])
        linhas = gerar_preview_importacao_scpi(
            conteudo_bytes=csv_bytes, estoque_id=estoque_principal.pk
        )
        assert len(linhas) == 1
        assert linhas[0].cadpro == material_scpi.codigo
        assert linhas[0].status == 'ok'


class TestGerarPreviewImportacaoScpiCasos:
    """Casos adicionais: divergências, novos, erros de formato."""

    def _csv(self, linhas: list[str]) -> bytes:
        return ('CADPRO;DENOMINACAO;QUAN3\n' + '\n'.join(linhas)).encode('utf-8')

    def test_divergencia_retorna_status_divergente(
        self, db, estoque_principal, material_scpi
    ):
        from apps.estoque.selectors import gerar_preview_importacao_scpi

        # saldo_fisico = 100, SCPI diz 80 → divergência
        csv_bytes = self._csv([f'{material_scpi.codigo};Parafuso M6;80.000'])
        linhas = gerar_preview_importacao_scpi(
            conteudo_bytes=csv_bytes, estoque_id=estoque_principal.pk
        )
        assert linhas[0].status == 'divergente'
        assert linhas[0].delta == -20

    def test_cadpro_inexistente_retorna_status_novo(self, db, estoque_principal):
        from apps.estoque.selectors import gerar_preview_importacao_scpi

        csv_bytes = self._csv(['000.999.999;Material Novo;50.000'])
        linhas = gerar_preview_importacao_scpi(
            conteudo_bytes=csv_bytes, estoque_id=estoque_principal.pk
        )
        assert linhas[0].status == 'novo'
        assert linhas[0].material_id is None
        assert linhas[0].saldo_wms == 0

    def test_csv_com_bom_parseia_corretamente(
        self, db, estoque_principal, material_scpi
    ):
        from apps.estoque.selectors import gerar_preview_importacao_scpi

        csv_com_bom = (
            f'﻿CADPRO;DENOMINACAO;QUAN3\n{material_scpi.codigo};Parafuso M6;100.000'
        ).encode('utf-8')
        linhas = gerar_preview_importacao_scpi(
            conteudo_bytes=csv_com_bom, estoque_id=estoque_principal.pk
        )
        assert len(linhas) == 1
        assert linhas[0].cadpro == material_scpi.codigo

    def test_csv_apenas_cabecalho_retorna_lista_vazia(self, db, estoque_principal):
        from apps.estoque.selectors import gerar_preview_importacao_scpi

        csv_bytes = 'CADPRO;DENOMINACAO;QUAN3\n'.encode('utf-8')
        linhas = gerar_preview_importacao_scpi(
            conteudo_bytes=csv_bytes, estoque_id=estoque_principal.pk
        )
        assert linhas == []

    def test_quantidade_invalida_lanca_dados_invalidos(self, db, estoque_principal):
        import pytest

        from apps.core.exceptions import DadosInvalidos
        from apps.estoque.selectors import gerar_preview_importacao_scpi

        csv_bytes = 'CADPRO;DENOMINACAO;QUAN3\n000.000.001;Teste;abc\n'.encode('utf-8')
        with pytest.raises(DadosInvalidos):
            gerar_preview_importacao_scpi(
                conteudo_bytes=csv_bytes, estoque_id=estoque_principal.pk
            )

    def test_csv_sem_coluna_cadpro_lanca_dados_invalidos(self, db, estoque_principal):
        import pytest

        from apps.core.exceptions import DadosInvalidos
        from apps.estoque.selectors import gerar_preview_importacao_scpi

        csv_bytes = 'COD;DENOMINACAO;QUANTIDADE\n000.000.001;X;10\n'.encode('utf-8')
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


class TestNormalizacaoCsvScpiMultilinha:
    """Registros SCPI que quebram em múltiplas linhas."""

    def test_registro_multilinha_e_juntado_em_uma_linha(self, db, estoque_principal):
        from apps.estoque.selectors import gerar_preview_importacao_scpi

        csv_bytes = (
            'CADPRO;DENOMINACAO;QUAN3\n'
            '000.000.001;PARAFUSO M6\n'
            'DESCRICAO CONTINUADA;10\n'
            '000.000.002;PORCA M6;20\n'
        ).encode('utf-8')
        linhas = gerar_preview_importacao_scpi(
            conteudo_bytes=csv_bytes, estoque_id=estoque_principal.pk
        )
        assert len(linhas) == 2
        assert linhas[0].cadpro == '000.000.001'
        assert linhas[1].cadpro == '000.000.002'

    def test_cadpro_formato_pontilhado_resolvido(self, db, estoque_principal):
        from apps.estoque.models import Material, SaldoEstoque, UnidadeMedida
        from apps.estoque.selectors import gerar_preview_importacao_scpi

        m = Material.objects.create(
            codigo='000.000.003',
            nome='Rebite',
            unidade=UnidadeMedida.UNIDADE,
            ativo=True,
        )
        SaldoEstoque.objects.create(
            estoque=estoque_principal, material=m, saldo_fisico=50, saldo_reservado=0
        )
        csv_bytes = 'CADPRO;DENOMINACAO;QUAN3\n000.000.003;REBITE;50\n'.encode('utf-8')
        linhas = gerar_preview_importacao_scpi(
            conteudo_bytes=csv_bytes, estoque_id=estoque_principal.pk
        )
        assert linhas[0].status == 'ok'
        assert linhas[0].material_id == m.pk


class TestDenominacaoScpiNoPreview:
    """denominacao_scpi deve ser propagada no LinhaPreviewSCPI."""

    def _csv(self, cadpro: str, denominacao: str, quantidade: str) -> bytes:
        return (
            f'CADPRO;DENOMINACAO;QUAN3\n{cadpro};{denominacao};{quantidade}\n'.encode(
                'utf-8'
            )
        )

    def test_material_novo_tem_denominacao_scpi(self, db, estoque_principal):
        from apps.estoque.selectors import gerar_preview_importacao_scpi

        csv_bytes = self._csv('000.999.001', 'Arruela Plana', '5.000')
        linhas = gerar_preview_importacao_scpi(
            conteudo_bytes=csv_bytes, estoque_id=estoque_principal.pk
        )
        assert linhas[0].status == 'novo'
        assert linhas[0].denominacao_scpi == 'Arruela Plana'

    def test_material_existente_tem_denominacao_scpi(
        self, db, estoque_principal, material_scpi
    ):
        from apps.estoque.selectors import gerar_preview_importacao_scpi

        csv_bytes = self._csv(material_scpi.codigo, 'Parafuso M6 Orig', '100.000')
        linhas = gerar_preview_importacao_scpi(
            conteudo_bytes=csv_bytes, estoque_id=estoque_principal.pk
        )
        assert linhas[0].denominacao_scpi == 'Parafuso M6 Orig'

    def test_denominacao_ausente_retorna_string_vazia(self, db, estoque_principal):
        from apps.estoque.selectors import gerar_preview_importacao_scpi

        csv_bytes = 'CADPRO;QUAN3\n000.999.002;10\n'.encode('utf-8')
        linhas = gerar_preview_importacao_scpi(
            conteudo_bytes=csv_bytes, estoque_id=estoque_principal.pk
        )
        assert linhas[0].denominacao_scpi == ''


class TestEntregaLiquidaPorItem:
    @pytest.mark.django_db
    def test_sem_consumo_retorna_zero(
        self,
        chefe_almoxarifado,
        estoque_principal,
        material_disponivel,
        requisicao_autorizada,
    ):
        from decimal import Decimal

        from apps.estoque.selectors import entregue_liquida_por_item

        req, item = requisicao_autorizada
        resultado = entregue_liquida_por_item(requisicao_id=req.pk, item_id=item.pk)
        assert resultado == Decimal('0')

    @pytest.mark.django_db
    def test_com_consumo_retorna_entregue(
        self,
        chefe_almoxarifado,
        estoque_principal,
        material_disponivel,
        requisicao_autorizada,
    ):
        from decimal import Decimal

        from apps.estoque.models import MovimentacaoEstoque, TipoMovimentacaoEstoque
        from apps.estoque.selectors import entregue_liquida_por_item

        req, item = requisicao_autorizada

        MovimentacaoEstoque.objects.create(
            tipo=TipoMovimentacaoEstoque.CONSUMO,
            material=material_disponivel,
            estoque=estoque_principal,
            delta_fisico=Decimal('-4'),
            delta_reservado=Decimal('-5'),
            requisicao=req,
            ator=chefe_almoxarifado,
        )

        resultado = entregue_liquida_por_item(requisicao_id=req.pk, item_id=item.pk)
        assert resultado == Decimal('4')

    @pytest.mark.django_db
    def test_com_multiplos_movimentos_soma_corretamente(
        self,
        chefe_almoxarifado,
        estoque_principal,
        material_disponivel,
        requisicao_autorizada,
    ):
        from decimal import Decimal

        from apps.estoque.models import MovimentacaoEstoque, TipoMovimentacaoEstoque
        from apps.estoque.selectors import entregue_liquida_por_item

        req, item = requisicao_autorizada

        MovimentacaoEstoque.objects.create(
            tipo=TipoMovimentacaoEstoque.CONSUMO,
            material=material_disponivel,
            estoque=estoque_principal,
            delta_fisico=Decimal('-5'),
            delta_reservado=Decimal('-5'),
            requisicao=req,
            ator=chefe_almoxarifado,
        )
        MovimentacaoEstoque.objects.create(
            tipo=TipoMovimentacaoEstoque.DEVOLUCAO,
            material=material_disponivel,
            estoque=estoque_principal,
            delta_fisico=Decimal('2'),
            delta_reservado=Decimal('0'),
            requisicao=req,
            ator=chefe_almoxarifado,
        )

        resultado = entregue_liquida_por_item(requisicao_id=req.pk, item_id=item.pk)
        assert resultado == Decimal('3')

    @pytest.mark.django_db
    def test_item_nao_pertence_requisicao_lanca_dados_invalidos(
        self,
        chefe_almoxarifado,
        estoque_principal,
        material_disponivel,
        requisicao_autorizada,
        setor_obras,
        solicitante,
    ):
        from apps.core.exceptions import DadosInvalidos
        from apps.estoque.selectors import entregue_liquida_por_item
        from apps.requisicoes.models import EstadoRequisicao, Requisicao

        req, item = requisicao_autorizada

        outra_req = Requisicao.objects.create(
            estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
            numero_publico='REQ-2025-999',
            criador=solicitante,
            beneficiario=solicitante,
            setor_beneficiario=setor_obras,
        )

        with pytest.raises(DadosInvalidos) as exc_info:
            entregue_liquida_por_item(requisicao_id=outra_req.pk, item_id=item.pk)

        assert exc_info.value.code == 'item_nao_pertence_requisicao'


class TestListarHistoricoImportacoesScpi:
    def test_retorna_queryset_vazio_quando_sem_registros(self, db):
        from apps.estoque.selectors import listar_historico_importacoes_scpi

        assert list(listar_historico_importacoes_scpi()) == []

    def test_retorna_importacoes_existentes(self, db, superuser, estoque_principal):
        from apps.estoque.models import ImportacaoSCPI, StatusImportacaoSCPI
        from apps.estoque.selectors import listar_historico_importacoes_scpi

        importacao = ImportacaoSCPI.objects.create(
            arquivo_nome='teste.csv',
            arquivo_hash='a' * 64,
            importado_por=superuser,
            estoque=estoque_principal,
            status=StatusImportacaoSCPI.CONCLUIDA,
            total_linhas=5,
            total_novos=1,
            total_divergentes=2,
        )
        qs = list(listar_historico_importacoes_scpi())
        assert importacao in qs

    def test_ordena_por_mais_recente_primeiro(self, db, superuser, estoque_principal):
        from apps.estoque.models import ImportacaoSCPI, StatusImportacaoSCPI
        from apps.estoque.selectors import listar_historico_importacoes_scpi

        i1 = ImportacaoSCPI.objects.create(
            arquivo_nome='primeiro.csv',
            arquivo_hash='b' * 64,
            importado_por=superuser,
            estoque=estoque_principal,
            status=StatusImportacaoSCPI.CONCLUIDA,
        )
        i2 = ImportacaoSCPI.objects.create(
            arquivo_nome='segundo.csv',
            arquivo_hash='c' * 64,
            importado_por=superuser,
            estoque=estoque_principal,
            status=StatusImportacaoSCPI.COM_ALERTAS,
        )
        qs = list(listar_historico_importacoes_scpi())
        assert qs[0] == i2
        assert qs[1] == i1

    def test_nao_expoe_csv_bruto(self, db, superuser, estoque_principal):
        from apps.estoque.models import ImportacaoSCPI, StatusImportacaoSCPI
        from apps.estoque.selectors import listar_historico_importacoes_scpi

        ImportacaoSCPI.objects.create(
            arquivo_nome='check.csv',
            arquivo_hash='d' * 64,
            importado_por=superuser,
            estoque=estoque_principal,
            status=StatusImportacaoSCPI.CONCLUIDA,
        )
        qs = listar_historico_importacoes_scpi()
        item = qs.first()
        assert not hasattr(item, 'conteudo_csv')


class TestListarMateriaisComSaldo:
    def test_retorna_saldos_do_estoque(
        self, chefe_almoxarifado, material_disponivel, estoque_principal
    ):
        from apps.estoque.selectors import listar_materiais_com_saldo

        resultado = listar_materiais_com_saldo()
        assert resultado.count() == 1
        saldo = resultado.first()
        assert saldo.material == material_disponivel

    def test_saldo_disponivel_e_fisico_menos_reservado(
        self, chefe_almoxarifado, material_disponivel, estoque_principal
    ):
        from apps.estoque.selectors import listar_materiais_com_saldo

        resultado = listar_materiais_com_saldo()
        saldo = resultado.get(material=material_disponivel)
        # material_disponivel: fisico=100, reservado=10 → disponivel=90
        assert saldo.saldo_disponivel_calculado == 90

    def test_divergente_true_quando_fisico_menor_que_reservado(
        self, chefe_almoxarifado, material_scpi_critico, estoque_principal
    ):
        from apps.estoque.selectors import listar_materiais_com_saldo

        resultado = listar_materiais_com_saldo()
        saldo = resultado.get(material=material_scpi_critico)
        assert saldo.divergente_calculado is True

    def test_divergente_false_quando_fisico_maior_que_reservado(
        self, chefe_almoxarifado, material_disponivel, estoque_principal
    ):
        from apps.estoque.selectors import listar_materiais_com_saldo

        resultado = listar_materiais_com_saldo()
        saldo = resultado.get(material=material_disponivel)
        assert saldo.divergente_calculado is False

    def test_busca_por_codigo_filtra_resultado(
        self,
        chefe_almoxarifado,
        material_disponivel,
        material_scpi_critico,
        estoque_principal,
    ):
        from apps.estoque.selectors import listar_materiais_com_saldo

        resultado = listar_materiais_com_saldo(busca='MAT001')
        assert set(resultado.values_list('material__pk', flat=True)) == {
            material_disponivel.pk
        }

    def test_busca_por_nome_filtra_resultado(
        self,
        chefe_almoxarifado,
        material_disponivel,
        material_scpi_critico,
        estoque_principal,
    ):
        from apps.estoque.selectors import listar_materiais_com_saldo

        resultado = listar_materiais_com_saldo(busca='Tinta')
        assert set(resultado.values_list('material__pk', flat=True)) == {
            material_scpi_critico.pk
        }

    def test_busca_vazia_retorna_todos(
        self,
        chefe_almoxarifado,
        material_disponivel,
        material_scpi_critico,
        estoque_principal,
    ):
        from apps.estoque.selectors import listar_materiais_com_saldo

        resultado = listar_materiais_com_saldo(busca='')
        assert set(resultado.values_list('material__pk', flat=True)) == {
            material_disponivel.pk,
            material_scpi_critico.pk,
        }
