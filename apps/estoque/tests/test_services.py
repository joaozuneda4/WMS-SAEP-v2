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
