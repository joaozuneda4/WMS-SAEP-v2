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
