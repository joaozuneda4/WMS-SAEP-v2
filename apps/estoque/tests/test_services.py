"""Testes de serviço para estoque.registrar_saida_excepcional."""

import pytest

from apps.estoque.models import EstadoSaidaExcepcional, SaidaExcepcional, SaldoEstoque


class TestRegistrarSaidaExcepcional:
    def test_happy_path_cria_saida_e_baixa_saldo(
        self, chefe_almoxarifado, estoque_principal, material_disponivel
    ):
        from apps.estoque.services import registrar_saida_excepcional

        saida = registrar_saida_excepcional(
            ator_id=chefe_almoxarifado.pk,
            estoque_id=estoque_principal.pk,
            motivo='Descarte por avaria',
            observacao='Caixas molhadas',
            itens=[{'material_id': material_disponivel.pk, 'quantidade': '5'}],
        )

        assert saida.pk is not None
        assert saida.numero_publico is not None
        assert saida.numero_publico.startswith('SXP-')
        assert saida.estado == EstadoSaidaExcepcional.REGISTRADA
        assert saida.registrado_por_id == chefe_almoxarifado.pk
        assert saida.estoque_id == estoque_principal.pk
        assert saida.itens.count() == 1

        saldo = SaldoEstoque.objects.get(
            estoque=estoque_principal, material=material_disponivel
        )
        assert saldo.saldo_fisico == 95  # 100 - 5

    def test_numero_publico_formato_sxp(
        self, chefe_almoxarifado, estoque_principal, material_disponivel
    ):
        from apps.estoque.services import registrar_saida_excepcional
        from django.utils import timezone

        saida = registrar_saida_excepcional(
            ator_id=chefe_almoxarifado.pk,
            estoque_id=estoque_principal.pk,
            motivo='Teste formato',
            observacao='obs',
            itens=[{'material_id': material_disponivel.pk, 'quantidade': '1'}],
        )

        ano = timezone.localdate().year
        assert saida.numero_publico == f'SXP-{ano}-000001'

    def test_sequencia_incrementa(
        self, chefe_almoxarifado, estoque_principal, material_disponivel
    ):
        from apps.estoque.models import Material, SaldoEstoque, UnidadeMedida
        from apps.estoque.services import registrar_saida_excepcional
        from django.utils import timezone

        m2 = Material.objects.create(
            codigo='MAT002',
            nome='Parafuso M8',
            unidade=UnidadeMedida.UNIDADE,
            ativo=True,
        )
        SaldoEstoque.objects.create(
            estoque=estoque_principal, material=m2, saldo_fisico=50, saldo_reservado=0
        )

        saida1 = registrar_saida_excepcional(
            ator_id=chefe_almoxarifado.pk,
            estoque_id=estoque_principal.pk,
            motivo='A',
            observacao='',
            itens=[{'material_id': material_disponivel.pk, 'quantidade': '1'}],
        )
        saida2 = registrar_saida_excepcional(
            ator_id=chefe_almoxarifado.pk,
            estoque_id=estoque_principal.pk,
            motivo='B',
            observacao='',
            itens=[{'material_id': m2.pk, 'quantidade': '1'}],
        )

        ano = timezone.localdate().year
        assert saida1.numero_publico == f'SXP-{ano}-000001'
        assert saida2.numero_publico == f'SXP-{ano}-000002'

    def test_sem_itens_lanca_dados_invalidos(
        self, chefe_almoxarifado, estoque_principal
    ):
        from apps.core.exceptions import DadosInvalidos
        from apps.estoque.services import registrar_saida_excepcional

        with pytest.raises(DadosInvalidos, match='ao menos um item'):
            registrar_saida_excepcional(
                ator_id=chefe_almoxarifado.pk,
                estoque_id=estoque_principal.pk,
                motivo='Teste',
                observacao='Teste válido',
                itens=[],
            )

    def test_material_duplicado_lanca_dados_invalidos(
        self, chefe_almoxarifado, estoque_principal, material_disponivel
    ):
        from apps.core.exceptions import DadosInvalidos
        from apps.estoque.services import registrar_saida_excepcional

        with pytest.raises(DadosInvalidos, match='duplicado'):
            registrar_saida_excepcional(
                ator_id=chefe_almoxarifado.pk,
                estoque_id=estoque_principal.pk,
                motivo='Duplicado',
                observacao='Teste válido',
                itens=[
                    {'material_id': material_disponivel.pk, 'quantidade': '5'},
                    {'material_id': material_disponivel.pk, 'quantidade': '3'},
                ],
            )

    def test_saldo_inexistente_lanca_conflito(
        self, chefe_almoxarifado, estoque_principal
    ):
        from apps.core.exceptions import ConflitoDominio
        from apps.estoque.models import Material, UnidadeMedida
        from apps.estoque.services import registrar_saida_excepcional

        m = Material.objects.create(
            codigo='MAT999', nome='Sem Saldo', unidade=UnidadeMedida.UNIDADE, ativo=True
        )

        with pytest.raises(ConflitoDominio, match='Saldo não encontrado'):
            registrar_saida_excepcional(
                ator_id=chefe_almoxarifado.pk,
                estoque_id=estoque_principal.pk,
                motivo='Sem saldo',
                observacao='Teste válido',
                itens=[{'material_id': m.pk, 'quantidade': '1'}],
            )

    def test_quantidade_invalida_lanca_dados_invalidos(
        self, chefe_almoxarifado, estoque_principal, material_disponivel
    ):
        from apps.core.exceptions import DadosInvalidos
        from apps.estoque.services import registrar_saida_excepcional

        with pytest.raises(DadosInvalidos, match='maior que zero'):
            registrar_saida_excepcional(
                ator_id=chefe_almoxarifado.pk,
                estoque_id=estoque_principal.pk,
                motivo='Qtd zero',
                observacao='Teste válido',
                itens=[{'material_id': material_disponivel.pk, 'quantidade': '0'}],
            )

    def test_nao_persiste_se_saldo_insuficiente(
        self, chefe_almoxarifado, estoque_principal, material_disponivel
    ):
        """Transação atomic: nenhum objeto persistido se saldo_fisico insuficiente."""
        from apps.core.exceptions import ConflitoDominio
        from apps.estoque.services import registrar_saida_excepcional

        with pytest.raises(ConflitoDominio):
            registrar_saida_excepcional(
                ator_id=chefe_almoxarifado.pk,
                estoque_id=estoque_principal.pk,
                motivo='Muito',
                observacao='Teste válido',
                itens=[{'material_id': material_disponivel.pk, 'quantidade': '9999'}],
            )

        assert not SaidaExcepcional.objects.exists()


class TestRegistrarSaidaExcepcionalAuth:
    def test_ator_nao_autorizado_lanca_permissao_negada(
        self, aux_almoxarifado, estoque_principal, material_disponivel
    ):
        import pytest

        from apps.core.exceptions import PermissaoNegada
        from apps.estoque.services import registrar_saida_excepcional

        with pytest.raises(PermissaoNegada):
            registrar_saida_excepcional(
                ator_id=aux_almoxarifado.pk,
                estoque_id=estoque_principal.pk,
                motivo='Avaria',
                observacao='Teste válido',
                itens=[{'material_id': material_disponivel.pk, 'quantidade': '1'}],
            )


class TestEstornarSaidaExcepcional:
    def test_happy_path_estorna_e_restaura_saldo(
        self,
        chefe_almoxarifado,
        estoque_principal,
        material_disponivel,
        saida_registrada,
    ):
        from apps.estoque.services import estornar_saida_excepcional

        saldo_obj_antes = SaldoEstoque.objects.get(
            estoque=estoque_principal, material=material_disponivel
        )
        saldo_fisico_antes = saldo_obj_antes.saldo_fisico
        saldo_reservado_antes = saldo_obj_antes.saldo_reservado

        quantidade_estornada = saida_registrada.itens.first().quantidade

        saida = estornar_saida_excepcional(
            ator_id=chefe_almoxarifado.pk,
            saida_id=saida_registrada.pk,
            justificativa='Registro equivocado.',
        )

        assert saida.estado == EstadoSaidaExcepcional.ESTORNADA
        assert saida.estornado_por_id == chefe_almoxarifado.pk
        assert saida.estornado_em is not None
        assert saida.justificativa_estorno == 'Registro equivocado.'

        saldo_obj_depois = SaldoEstoque.objects.get(
            estoque=estoque_principal, material=material_disponivel
        )
        assert (
            saldo_obj_depois.saldo_fisico == saldo_fisico_antes + quantidade_estornada
        )
        assert saldo_obj_depois.saldo_reservado == saldo_reservado_antes
        assert (
            saldo_obj_depois.saldo_fisico - saldo_obj_depois.saldo_reservado
            == saldo_obj_depois.saldo_disponivel
        )

    def test_estorno_duplo_lanca_conflito(self, chefe_almoxarifado, saida_registrada):
        import pytest

        from apps.core.exceptions import ConflitoDominio
        from apps.estoque.services import estornar_saida_excepcional

        estornar_saida_excepcional(
            ator_id=chefe_almoxarifado.pk,
            saida_id=saida_registrada.pk,
            justificativa='Primeiro estorno.',
        )

        with pytest.raises(ConflitoDominio, match='já estornada'):
            estornar_saida_excepcional(
                ator_id=chefe_almoxarifado.pk,
                saida_id=saida_registrada.pk,
                justificativa='Segundo estorno.',
            )

    def test_ator_sem_permissao_lanca_permissao_negada(
        self, aux_almoxarifado, saida_registrada
    ):
        import pytest

        from apps.core.exceptions import PermissaoNegada
        from apps.estoque.services import estornar_saida_excepcional

        with pytest.raises(PermissaoNegada):
            estornar_saida_excepcional(
                ator_id=aux_almoxarifado.pk,
                saida_id=saida_registrada.pk,
                justificativa='Tentativa indevida.',
            )

    def test_justificativa_vazia_lanca_dados_invalidos(
        self, chefe_almoxarifado, saida_registrada
    ):
        import pytest

        from apps.core.exceptions import DadosInvalidos
        from apps.estoque.services import estornar_saida_excepcional

        with pytest.raises(DadosInvalidos, match='justificativa'):
            estornar_saida_excepcional(
                ator_id=chefe_almoxarifado.pk,
                saida_id=saida_registrada.pk,
                justificativa='',
            )

    def test_saida_inexistente_lanca_dados_invalidos(self, chefe_almoxarifado):
        import pytest

        from apps.core.exceptions import DadosInvalidos
        from apps.estoque.services import estornar_saida_excepcional

        with pytest.raises(DadosInvalidos):
            estornar_saida_excepcional(
                ator_id=chefe_almoxarifado.pk,
                saida_id=999999,
                justificativa='Inexistente.',
            )


class TestConfirmarImportacaoScpi:
    """Contrato de confirmar_importacao_scpi."""

    def _csv(self, cadpro: str, denominacao: str, quantidade: str) -> bytes:
        return (
            f'CADPRO;DENOMINACAO;QUAN3\n{cadpro};{denominacao};{quantidade}\n'.encode(
                'utf-8'
            )
        )

    def test_cria_importacao_scpi_com_metadados(self, db, superuser, estoque_principal):
        from apps.estoque.models import ImportacaoSCPI
        from apps.estoque.services import confirmar_importacao_scpi

        csv_bytes = self._csv('000.999.100', 'Material Qualquer', '10.000')
        importacao = confirmar_importacao_scpi(
            ator_id=superuser.pk,
            conteudo_bytes=csv_bytes,
            arquivo_nome='teste.csv',
            estoque_id=estoque_principal.pk,
        )
        assert importacao.pk is not None
        assert importacao.arquivo_nome == 'teste.csv'
        assert importacao.importado_por_id == superuser.pk
        assert importacao.total_linhas == 1
        assert ImportacaoSCPI.objects.filter(pk=importacao.pk).exists()

    def test_cria_material_novo_com_saldo_inicial(
        self, db, superuser, estoque_principal
    ):
        from decimal import Decimal

        from apps.estoque.models import Material, SaldoEstoque
        from apps.estoque.services import confirmar_importacao_scpi

        csv_bytes = self._csv('000.999.200', 'Rebite 3mm', '42.000')
        confirmar_importacao_scpi(
            ator_id=superuser.pk,
            conteudo_bytes=csv_bytes,
            arquivo_nome='novo.csv',
            estoque_id=estoque_principal.pk,
        )
        material = Material.objects.get(codigo='000.999.200')
        assert material.nome == 'Rebite 3mm'
        saldo = SaldoEstoque.objects.get(material=material, estoque=estoque_principal)
        assert saldo.saldo_fisico == Decimal('42')
        assert saldo.saldo_reservado == Decimal('0')

    def test_material_existente_nao_tem_saldo_alterado(
        self, db, superuser, estoque_principal, material_scpi
    ):

        from apps.estoque.models import SaldoEstoque
        from apps.estoque.services import confirmar_importacao_scpi

        saldo_antes = SaldoEstoque.objects.get(
            material=material_scpi, estoque=estoque_principal
        ).saldo_fisico

        csv_bytes = self._csv(material_scpi.codigo, 'Parafuso M6', '999.000')
        confirmar_importacao_scpi(
            ator_id=superuser.pk,
            conteudo_bytes=csv_bytes,
            arquivo_nome='existente.csv',
            estoque_id=estoque_principal.pk,
        )
        saldo_depois = SaldoEstoque.objects.get(
            material=material_scpi, estoque=estoque_principal
        ).saldo_fisico
        assert saldo_depois == saldo_antes

    def test_hash_duplicado_lanca_conflito_dominio(
        self, db, superuser, estoque_principal
    ):
        import pytest

        from apps.core.exceptions import ConflitoDominio
        from apps.estoque.services import confirmar_importacao_scpi

        csv_bytes = self._csv('000.999.300', 'Porca M4', '5.000')
        confirmar_importacao_scpi(
            ator_id=superuser.pk,
            conteudo_bytes=csv_bytes,
            arquivo_nome='dup.csv',
            estoque_id=estoque_principal.pk,
        )
        with pytest.raises(ConflitoDominio):
            confirmar_importacao_scpi(
                ator_id=superuser.pk,
                conteudo_bytes=csv_bytes,
                arquivo_nome='dup.csv',
                estoque_id=estoque_principal.pk,
            )

    def test_sem_permissao_lanca_permissao_negada(
        self, db, chefe_almoxarifado, estoque_principal
    ):
        import pytest

        from apps.core.exceptions import PermissaoNegada
        from apps.estoque.services import confirmar_importacao_scpi

        csv_bytes = self._csv('000.999.400', 'Parafuso', '1.000')
        with pytest.raises(PermissaoNegada):
            confirmar_importacao_scpi(
                ator_id=chefe_almoxarifado.pk,
                conteudo_bytes=csv_bytes,
                arquivo_nome='negado.csv',
                estoque_id=estoque_principal.pk,
            )

    def test_total_novos_e_divergentes_gravados(
        self, db, superuser, estoque_principal, material_scpi
    ):
        from apps.estoque.services import confirmar_importacao_scpi

        csv_bytes = (
            'CADPRO;DENOMINACAO;QUAN3\n'
            f'{material_scpi.codigo};Parafuso M6;999.000\n'
            '000.999.500;Material Nv;5.000\n'
        ).encode('utf-8')
        importacao = confirmar_importacao_scpi(
            ator_id=superuser.pk,
            conteudo_bytes=csv_bytes,
            arquivo_nome='mix.csv',
            estoque_id=estoque_principal.pk,
        )
        assert importacao.total_linhas == 2
        assert importacao.total_novos == 1
        assert importacao.total_divergentes == 1


class TestConfirmarImportacaoScpiTimelineRequisicoes:
    """atualizacao_estoque_relevante registrado em requisições autorizadas afetadas."""

    def _csv(self, cadpro: str, denominacao: str, quantidade: str) -> bytes:
        """Monta CSV SCPI mínimo com uma linha."""
        return (
            f'CADPRO;DENOMINACAO;QUAN3\n{cadpro};{denominacao};{quantidade}\n'.encode(
                'utf-8'
            )
        )

    def test_cria_evento_quando_divergencia_critica_e_requisicao_autorizada(
        self,
        db,
        superuser,
        estoque_principal,
        material_scpi_critico,
        requisicao_autorizada_critico,
    ):
        """Happy path: material crítico + requisição autorizada → evento criado com metadata correto."""
        from apps.estoque.services import confirmar_importacao_scpi
        from apps.requisicoes.models import EventoTimeline, TimelineRequisicao

        csv_bytes = self._csv(material_scpi_critico.codigo, 'Tinta Branca 18L', '1.000')
        importacao = confirmar_importacao_scpi(
            ator_id=superuser.pk,
            conteudo_bytes=csv_bytes,
            arquivo_nome='crit.csv',
            estoque_id=estoque_principal.pk,
        )

        eventos = TimelineRequisicao.objects.filter(
            requisicao=requisicao_autorizada_critico,
            evento=EventoTimeline.ATUALIZACAO_ESTOQUE_RELEVANTE,
        )
        assert eventos.count() == 1
        evento = eventos.first()
        assert evento.metadata['importacao_id'] == importacao.pk
        assert any(
            m['codigo'] == material_scpi_critico.codigo
            for m in evento.metadata['materiais']
        )
        assert any(
            m['nome'] == material_scpi_critico.nome
            for m in evento.metadata['materiais']
        )

    def test_nao_cria_evento_quando_saldo_nao_critico(
        self, db, superuser, estoque_principal, solicitante, setor_obras
    ):
        """Material divergente (SCPI != WMS) mas não crítico: sem evento."""
        from decimal import Decimal

        from apps.estoque.models import Material, SaldoEstoque, UnidadeMedida
        from apps.estoque.services import confirmar_importacao_scpi
        from apps.requisicoes.models import (
            EstadoRequisicao,
            EventoTimeline,
            ItemRequisicao,
            Requisicao,
            TimelineRequisicao,
        )

        m = Material.objects.create(
            codigo='000.000.010',
            nome='Parafuso M8',
            unidade=UnidadeMedida.UNIDADE,
            ativo=True,
        )
        SaldoEstoque.objects.create(
            estoque=estoque_principal, material=m, saldo_fisico=10, saldo_reservado=5
        )
        req = Requisicao.objects.create(
            estado=EstadoRequisicao.AUTORIZADA,
            numero_publico='REQ-2025-000010',
            criador=solicitante,
            beneficiario=solicitante,
            setor_beneficiario=setor_obras,
        )
        ItemRequisicao.objects.create(
            requisicao=req,
            material=m,
            quantidade_solicitada=Decimal('5'),
            quantidade_autorizada=Decimal('5'),
        )

        # SCPI diz 8 (divergente de WMS=10), mas saldo_fisico=10 >= saldo_reservado=5
        csv_bytes = self._csv(m.codigo, 'Parafuso M8', '8.000')
        confirmar_importacao_scpi(
            ator_id=superuser.pk,
            conteudo_bytes=csv_bytes,
            arquivo_nome='nao_crit.csv',
            estoque_id=estoque_principal.pk,
        )

        assert not TimelineRequisicao.objects.filter(
            requisicao=req,
            evento=EventoTimeline.ATUALIZACAO_ESTOQUE_RELEVANTE,
        ).exists()

    def test_nao_cria_evento_sem_requisicao_autorizada(
        self, db, superuser, estoque_principal, material_scpi_critico
    ):
        """Material crítico mas sem requisição autorizada: sem evento."""
        from apps.estoque.services import confirmar_importacao_scpi
        from apps.requisicoes.models import EventoTimeline, TimelineRequisicao

        csv_bytes = self._csv(material_scpi_critico.codigo, 'Tinta Branca 18L', '1.000')
        confirmar_importacao_scpi(
            ator_id=superuser.pk,
            conteudo_bytes=csv_bytes,
            arquivo_nome='sem_req.csv',
            estoque_id=estoque_principal.pk,
        )

        assert not TimelineRequisicao.objects.filter(
            evento=EventoTimeline.ATUALIZACAO_ESTOQUE_RELEVANTE,
        ).exists()

    def test_evento_agregado_com_multiplos_materiais_criticos(
        self, db, superuser, estoque_principal, solicitante, setor_obras
    ):
        """Dois materiais críticos na mesma requisição: um evento com lista agregada."""
        from decimal import Decimal

        from apps.estoque.models import Material, SaldoEstoque, UnidadeMedida
        from apps.estoque.services import confirmar_importacao_scpi
        from apps.requisicoes.models import (
            EstadoRequisicao,
            EventoTimeline,
            ItemRequisicao,
            Requisicao,
            TimelineRequisicao,
        )

        m1 = Material.objects.create(
            codigo='000.000.011',
            nome='Material A',
            unidade=UnidadeMedida.UNIDADE,
            ativo=True,
        )
        m2 = Material.objects.create(
            codigo='000.000.012',
            nome='Material B',
            unidade=UnidadeMedida.UNIDADE,
            ativo=True,
        )
        SaldoEstoque.objects.create(
            estoque=estoque_principal, material=m1, saldo_fisico=2, saldo_reservado=5
        )
        SaldoEstoque.objects.create(
            estoque=estoque_principal, material=m2, saldo_fisico=1, saldo_reservado=3
        )

        req = Requisicao.objects.create(
            estado=EstadoRequisicao.AUTORIZADA,
            numero_publico='REQ-2025-000011',
            criador=solicitante,
            beneficiario=solicitante,
            setor_beneficiario=setor_obras,
        )
        ItemRequisicao.objects.create(
            requisicao=req,
            material=m1,
            quantidade_solicitada=Decimal('3'),
            quantidade_autorizada=Decimal('3'),
        )
        ItemRequisicao.objects.create(
            requisicao=req,
            material=m2,
            quantidade_solicitada=Decimal('2'),
            quantidade_autorizada=Decimal('2'),
        )

        csv_bytes = (
            'CADPRO;DENOMINACAO;QUAN3\n'
            f'{m1.codigo};Material A;1.000\n'
            f'{m2.codigo};Material B;1.000\n'
        ).encode('utf-8')
        importacao = confirmar_importacao_scpi(
            ator_id=superuser.pk,
            conteudo_bytes=csv_bytes,
            arquivo_nome='multi.csv',
            estoque_id=estoque_principal.pk,
        )

        eventos = TimelineRequisicao.objects.filter(
            requisicao=req,
            evento=EventoTimeline.ATUALIZACAO_ESTOQUE_RELEVANTE,
        )
        assert eventos.count() == 1
        codigos = {m['codigo'] for m in eventos.first().metadata['materiais']}
        assert codigos == {m1.codigo, m2.codigo}
        assert eventos.first().metadata['importacao_id'] == importacao.pk


class TestMovimentacaoEstoqueImutavel:
    @pytest.mark.django_db
    def test_save_apos_criacao_levanta_excecao(
        self,
        chefe_almoxarifado,
        estoque_principal,
        material_disponivel,
        saida_registrada,
    ):
        from apps.estoque.models import MovimentacaoEstoque, MovimentacaoEstoqueImutavel

        mov = MovimentacaoEstoque.objects.filter(
            saida_excepcional=saida_registrada
        ).first()
        assert mov is not None
        with pytest.raises(MovimentacaoEstoqueImutavel):
            mov.delta_fisico = mov.delta_fisico + 1
            mov.save()

    @pytest.mark.django_db
    def test_delete_levanta_excecao(
        self,
        chefe_almoxarifado,
        estoque_principal,
        material_disponivel,
        saida_registrada,
    ):
        from apps.estoque.models import MovimentacaoEstoque, MovimentacaoEstoqueImutavel

        mov = MovimentacaoEstoque.objects.filter(
            saida_excepcional=saida_registrada
        ).first()
        assert mov is not None
        with pytest.raises(MovimentacaoEstoqueImutavel):
            mov.delete()


class TestLedgerRegistrarSaidaExcepcional:
    @pytest.mark.django_db
    def test_emite_movimentacao_saida_excepcional(
        self,
        chefe_almoxarifado,
        estoque_principal,
        material_disponivel,
        saida_registrada,
    ):
        from decimal import Decimal

        from apps.estoque.models import MovimentacaoEstoque, TipoMovimentacaoEstoque

        movs = MovimentacaoEstoque.objects.filter(saida_excepcional=saida_registrada)
        assert movs.count() == 1
        mov = movs.first()
        assert mov.tipo == TipoMovimentacaoEstoque.SAIDA_EXCEPCIONAL
        assert mov.material == material_disponivel
        assert mov.estoque == estoque_principal
        assert mov.delta_fisico == Decimal('-5')
        assert mov.delta_reservado == Decimal('0')
        assert mov.ator == chefe_almoxarifado


class TestLedgerEstornarSaidaExcepcional:
    @pytest.mark.django_db
    def test_emite_movimentacao_estorno_saida(
        self,
        chefe_almoxarifado,
        estoque_principal,
        material_disponivel,
        saida_registrada,
    ):
        from decimal import Decimal

        from apps.estoque.models import MovimentacaoEstoque, TipoMovimentacaoEstoque
        from apps.estoque.services import estornar_saida_excepcional

        estornar_saida_excepcional(
            ator_id=chefe_almoxarifado.pk,
            saida_id=saida_registrada.pk,
            justificativa='Estorno de teste',
        )

        movs = MovimentacaoEstoque.objects.filter(saida_excepcional=saida_registrada)
        tipos = list(movs.values_list('tipo', flat=True))
        assert TipoMovimentacaoEstoque.ESTORNO_SAIDA in tipos

        mov_estorno = movs.get(tipo=TipoMovimentacaoEstoque.ESTORNO_SAIDA)
        assert mov_estorno.delta_fisico == Decimal('5')
        assert mov_estorno.delta_reservado == Decimal('0')
        assert mov_estorno.ator == chefe_almoxarifado


class TestLedgerReservarSaldos:
    @pytest.mark.django_db
    def test_emite_movimentacao_reserva(
        self,
        chefe_almoxarifado,
        estoque_principal,
        material_disponivel,
        requisicao_autorizavel,
    ):
        from decimal import Decimal

        from apps.estoque.models import MovimentacaoEstoque, TipoMovimentacaoEstoque
        from apps.estoque.services import (
            OrigemMovimentacaoEstoque,
            reservar_saldos_para_autorizacao,
        )

        reservar_saldos_para_autorizacao(
            itens=[
                {
                    'material_id': material_disponivel.pk,
                    'quantidade_solicitada': Decimal('3'),
                }
            ],
            ator_id=chefe_almoxarifado.pk,
            origem=OrigemMovimentacaoEstoque.de_requisicao(requisicao_autorizavel),
        )

        movs = MovimentacaoEstoque.objects.filter(requisicao=requisicao_autorizavel)
        assert movs.count() == 1
        mov = movs.first()
        assert mov.tipo == TipoMovimentacaoEstoque.RESERVA
        assert mov.delta_fisico == Decimal('0')
        assert mov.delta_reservado == Decimal('3')
        assert mov.ator == chefe_almoxarifado


class TestLedgerLiberarReservas:
    @pytest.mark.django_db
    def test_emite_movimentacao_liberacao(
        self,
        chefe_almoxarifado,
        estoque_principal,
        material_disponivel,
        requisicao_autorizada,
    ):
        from decimal import Decimal

        from apps.estoque.models import MovimentacaoEstoque, TipoMovimentacaoEstoque
        from apps.estoque.services import (
            OrigemMovimentacaoEstoque,
            liberar_reservas_para_cancelamento,
        )

        req, item = requisicao_autorizada

        liberar_reservas_para_cancelamento(
            itens=[
                {
                    'material_id': material_disponivel.pk,
                    'quantidade_reservada': Decimal('5'),
                }
            ],
            ator_id=chefe_almoxarifado.pk,
            origem=OrigemMovimentacaoEstoque.de_requisicao(req),
        )

        movs = MovimentacaoEstoque.objects.filter(
            requisicao=req, tipo=TipoMovimentacaoEstoque.LIBERACAO
        )
        assert movs.count() == 1
        mov = movs.first()
        assert mov.delta_fisico == Decimal('0')
        assert mov.delta_reservado == Decimal('-5')


class TestLedgerConsumirReservas:
    @pytest.mark.django_db
    def test_emite_movimentacao_consumo(
        self,
        chefe_almoxarifado,
        estoque_principal,
        material_disponivel,
        requisicao_autorizada,
    ):
        from decimal import Decimal

        from apps.estoque.models import MovimentacaoEstoque, TipoMovimentacaoEstoque
        from apps.estoque.services import (
            OrigemMovimentacaoEstoque,
            consumir_e_liberar_reservas_para_atendimento,
        )

        req, item = requisicao_autorizada

        consumir_e_liberar_reservas_para_atendimento(
            itens=[
                {
                    'material_id': material_disponivel.pk,
                    'quantidade_autorizada': Decimal('5'),
                    'quantidade_entregue': Decimal('4'),
                }
            ],
            ator_id=chefe_almoxarifado.pk,
            origem=OrigemMovimentacaoEstoque.de_requisicao(req),
        )

        movs = MovimentacaoEstoque.objects.filter(
            requisicao=req, tipo=TipoMovimentacaoEstoque.CONSUMO
        )
        assert movs.count() == 1
        mov = movs.first()
        assert mov.delta_fisico == Decimal('-4')
        assert mov.delta_reservado == Decimal('-5')


class TestLedgerReconciliacao:
    @pytest.mark.django_db
    def test_soma_delta_fisico_reconcilia_com_saldo(
        self,
        chefe_almoxarifado,
        estoque_principal,
        material_disponivel,
        saida_registrada,
    ):
        from decimal import Decimal

        from django.db.models import Sum

        from apps.estoque.models import MovimentacaoEstoque, SaldoEstoque
        from apps.estoque.services import estornar_saida_excepcional

        saldo_inicial = Decimal('100')

        estornar_saida_excepcional(
            ator_id=chefe_almoxarifado.pk,
            saida_id=saida_registrada.pk,
            justificativa='Reconciliação de teste',
        )

        total_delta = MovimentacaoEstoque.objects.filter(
            estoque=estoque_principal,
            material=material_disponivel,
        ).aggregate(total=Sum('delta_fisico'))['total'] or Decimal('0')

        saldo_atual = SaldoEstoque.objects.get(
            estoque=estoque_principal, material=material_disponivel
        ).saldo_fisico

        assert saldo_atual == saldo_inicial + total_delta


@pytest.mark.django_db(transaction=True)
class TestLedgerConcorrenciaEST06:
    def test_locks_preservados_com_ledger(
        self,
        chefe_almoxarifado,
        estoque_principal,
        material_disponivel,
        requisicao_autorizavel,
    ):
        """EST-06: lock determinístico preservado após retrofit do ledger."""
        import threading
        from decimal import Decimal

        from apps.estoque.models import (
            MovimentacaoEstoque,
            SaldoEstoque,
            TipoMovimentacaoEstoque,
        )
        from apps.estoque.services import (
            OrigemMovimentacaoEstoque,
            reservar_saldos_para_autorizacao,
        )

        erros = []

        def reservar():
            try:
                reservar_saldos_para_autorizacao(
                    itens=[
                        {
                            'material_id': material_disponivel.pk,
                            'quantidade_solicitada': Decimal('1'),
                        }
                    ],
                    ator_id=chefe_almoxarifado.pk,
                    origem=OrigemMovimentacaoEstoque.de_requisicao(
                        requisicao_autorizavel
                    ),
                )
            except Exception as e:
                erros.append(e)

        t1 = threading.Thread(target=reservar)
        t2 = threading.Thread(target=reservar)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        saldo = SaldoEstoque.objects.get(
            estoque=estoque_principal, material=material_disponivel
        )
        movs = MovimentacaoEstoque.objects.filter(
            requisicao=requisicao_autorizavel,
            tipo=TipoMovimentacaoEstoque.RESERVA,
        )
        # Ambas as threads devem ter completado sem erro
        assert not erros
        # saldo_reservado aumentou 2 (1 por thread)
        assert saldo.saldo_reservado == Decimal('10') + Decimal('2')
        # 2 movimentações criadas
        assert movs.count() == 2
