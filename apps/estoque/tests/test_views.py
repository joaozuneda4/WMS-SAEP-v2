"""Testes de view para estoque.saidas_excepcionais."""

import re

from django.urls import reverse


URL = reverse('estoque:listar_saidas_excepcionais')


class TestListarSaidasExcepcionaisView:
    def test_chefe_almox_acessa_lista(self, client, chefe_almoxarifado):
        client.force_login(chefe_almoxarifado)
        response = client.get(URL)
        assert response.status_code == 200

    def test_aux_almox_acessa_lista(self, client, aux_almoxarifado):
        client.force_login(aux_almoxarifado)
        response = client.get(URL)
        assert response.status_code == 200

    def test_superuser_acessa_lista(self, client, superuser):
        client.force_login(superuser)
        response = client.get(URL)
        assert response.status_code == 200

    def test_solicitante_recebe_403(self, client, solicitante):
        client.force_login(solicitante)
        response = client.get(URL)
        assert response.status_code == 403

    def test_usuario_inativo_redirecionado_para_login(self, client, usuario_inativo):
        # Django ModelBackend trata is_active=False como não-autenticado;
        # @login_required redireciona para login (USR-01).
        client.force_login(usuario_inativo)
        response = client.get(URL)
        assert response.status_code == 302
        assert 'login' in response['Location']

    def test_anonimo_redirecionado_para_login(self, client):
        response = client.get(URL)
        assert response.status_code == 302
        assert (
            '/login' in response['Location'] or 'accounts/login' in response['Location']
        )

    def test_contexto_contem_saidas(self, client, chefe_almoxarifado):
        client.force_login(chefe_almoxarifado)
        response = client.get(URL)
        assert 'saidas' in response.context

    def test_botao_ver_detalhe_preserva_aria_label(
        self, client, chefe_almoxarifado, saida_registrada
    ):
        client.force_login(chefe_almoxarifado)
        response = client.get(URL)
        html = response.content.decode('utf-8')
        assert (
            f'aria-label="Ver detalhe da saída {saida_registrada.numero_publico}"'
            in html
        )

    def test_botao_ver_detalhe_fallback_pk_sem_numero_publico(
        self, client, chefe_almoxarifado, saida_registrada
    ):
        saida_registrada.numero_publico = ''
        saida_registrada.save(update_fields=['numero_publico'])
        client.force_login(chefe_almoxarifado)
        response = client.get(URL)
        html = response.content.decode('utf-8')
        assert f'aria-label="Ver detalhe da saída {saida_registrada.pk}"' in html

    def test_empty_state_cta_delega_para_componente_button(
        self, client, chefe_almoxarifado
    ):
        client.force_login(chefe_almoxarifado)
        response = client.get(URL)
        html = response.content.decode('utf-8')
        titulo_idx = html.index('Nenhuma saída excepcional registrada')
        match = re.search(r'<a\b[^>]*>', html[titulo_idx:])
        assert match is not None
        tag = match.group()
        assert 'min-h-11' in tag
        assert 'justify-center' in tag
        assert 'focus-visible:ring-offset-1' in tag
        assert 'ring-offset-2' not in tag

    def test_pode_registrar_verdadeiro_para_chefe(self, client, chefe_almoxarifado):
        client.force_login(chefe_almoxarifado)
        response = client.get(URL)
        assert response.context['pode_registrar'] is True

    def test_pode_registrar_falso_para_aux(self, client, aux_almoxarifado):
        client.force_login(aux_almoxarifado)
        response = client.get(URL)
        assert response.context['pode_registrar'] is False

    def test_pode_registrar_verdadeiro_para_superuser(self, client, superuser):
        # Superuser tem override técnico para registrar (matriz-permissoes.md linha 78)
        client.force_login(superuser)
        response = client.get(URL)
        assert response.context['pode_registrar'] is True

    def test_vazia_com_permissao_exibe_cta(self, client, chefe_almoxarifado):
        client.force_login(chefe_almoxarifado)
        response = client.get(URL)
        html = response.content.decode()
        assert 'border-dashed border-slate-300' in html
        assert 'Nenhuma saída excepcional registrada' in html
        assert 'Registre a primeira baixa administrativa direta de material.' in html
        assert reverse('estoque:nova_saida_excepcional') in html

    def test_vazia_sem_permissao_oculta_cta(self, client, aux_almoxarifado):
        client.force_login(aux_almoxarifado)
        response = client.get(URL)
        html = response.content.decode()
        assert 'Nenhuma saída excepcional registrada' in html
        assert 'Não há saídas excepcionais no sistema.' in html
        assert reverse('estoque:nova_saida_excepcional') not in html


URL_NOVA = reverse('estoque:nova_saida_excepcional')
URL_BUSCAR = reverse('estoque:buscar_materiais_saida_excepcional')


class TestNovaSaidaExcepcionalView:
    def test_chefe_acessa_formulario(
        self, client, chefe_almoxarifado, estoque_principal
    ):
        client.force_login(chefe_almoxarifado)
        response = client.get(URL_NOVA)
        assert response.status_code == 200

    def test_superuser_acessa_formulario(self, client, superuser, estoque_principal):
        client.force_login(superuser)
        response = client.get(URL_NOVA)
        assert response.status_code == 200

    def test_aux_recebe_403(self, client, aux_almoxarifado):
        client.force_login(aux_almoxarifado)
        response = client.get(URL_NOVA)
        assert response.status_code == 403

    def test_solicitante_recebe_403(self, client, solicitante):
        client.force_login(solicitante)
        response = client.get(URL_NOVA)
        assert response.status_code == 403

    def test_anonimo_redirecionado_para_login(self, client):
        response = client.get(URL_NOVA)
        assert response.status_code == 302
        assert 'login' in response['Location']

    def test_post_valido_cria_saida_e_redireciona(
        self, client, chefe_almoxarifado, estoque_principal, material_disponivel
    ):
        client.force_login(chefe_almoxarifado)
        response = client.post(
            URL_NOVA,
            data={
                'motivo': 'avaria',
                'observacao': 'Caixas molhadas',
                'itens-TOTAL_FORMS': '1',
                'itens-INITIAL_FORMS': '0',
                'itens-MIN_NUM_FORMS': '0',
                'itens-MAX_NUM_FORMS': '1000',
                'itens-0-material_id': str(material_disponivel.pk),
                'itens-0-quantidade': '5',
            },
        )
        assert response.status_code == 302
        from apps.estoque.models import SaidaExcepcional

        assert SaidaExcepcional.objects.count() == 1
        saida = SaidaExcepcional.objects.get()
        assert saida.numero_publico.startswith('SXP-')

    def test_post_sem_motivo_retorna_form_com_erro(
        self, client, chefe_almoxarifado, estoque_principal, material_disponivel
    ):
        client.force_login(chefe_almoxarifado)
        response = client.post(
            URL_NOVA,
            data={
                'motivo': '',
                'observacao': 'obs válida',
                'itens-TOTAL_FORMS': '1',
                'itens-INITIAL_FORMS': '0',
                'itens-MIN_NUM_FORMS': '0',
                'itens-MAX_NUM_FORMS': '1000',
                'itens-0-material_id': str(material_disponivel.pk),
                'itens-0-quantidade': '5',
            },
        )
        assert response.status_code == 200
        assert 'motivo' in response.context['erros']

    def test_post_sem_itens_retorna_form_com_erro(
        self, client, chefe_almoxarifado, estoque_principal
    ):
        client.force_login(chefe_almoxarifado)
        response = client.post(
            URL_NOVA,
            data={
                'motivo': 'avaria',
                'observacao': 'obs válida',
                'itens-TOTAL_FORMS': '0',
                'itens-INITIAL_FORMS': '0',
                'itens-MIN_NUM_FORMS': '0',
                'itens-MAX_NUM_FORMS': '1000',
            },
        )
        assert response.status_code == 200
        assert 'itens' in response.context['erros']

    def test_post_aux_recebe_403_sem_persistencia(
        self, client, aux_almoxarifado, estoque_principal, material_disponivel
    ):
        from apps.estoque.models import SaidaExcepcional

        client.force_login(aux_almoxarifado)
        response = client.post(
            URL_NOVA,
            data={
                'motivo': 'avaria',
                'observacao': 'Teste',
                'itens-TOTAL_FORMS': '1',
                'itens-INITIAL_FORMS': '0',
                'itens-MIN_NUM_FORMS': '0',
                'itens-MAX_NUM_FORMS': '1000',
                'itens-0-material_id': str(material_disponivel.pk),
                'itens-0-quantidade': '5',
            },
        )
        assert response.status_code == 403
        assert SaidaExcepcional.objects.count() == 0

    def test_post_solicitante_recebe_403_sem_persistencia(
        self, client, solicitante, estoque_principal, material_disponivel
    ):
        from apps.estoque.models import SaidaExcepcional

        client.force_login(solicitante)
        response = client.post(
            URL_NOVA,
            data={
                'motivo': 'avaria',
                'observacao': 'Teste',
                'itens-TOTAL_FORMS': '1',
                'itens-INITIAL_FORMS': '0',
                'itens-MIN_NUM_FORMS': '0',
                'itens-MAX_NUM_FORMS': '1000',
                'itens-0-material_id': str(material_disponivel.pk),
                'itens-0-quantidade': '5',
            },
        )
        assert response.status_code == 403
        assert SaidaExcepcional.objects.count() == 0

    def test_post_anonimo_redireciona_sem_persistencia(
        self, client, material_disponivel
    ):
        from apps.estoque.models import SaidaExcepcional

        response = client.post(
            URL_NOVA,
            data={
                'motivo': 'avaria',
                'observacao': 'Teste',
                'itens-TOTAL_FORMS': '1',
                'itens-INITIAL_FORMS': '0',
                'itens-MIN_NUM_FORMS': '0',
                'itens-MAX_NUM_FORMS': '1000',
                'itens-0-material_id': str(material_disponivel.pk),
                'itens-0-quantidade': '5',
            },
        )
        assert response.status_code == 302
        assert 'login' in response['Location']
        assert SaidaExcepcional.objects.count() == 0

    def test_dados_invalidos_do_service_rerendera_form_nao_redirect(
        self, client, chefe_almoxarifado, estoque_principal, material_disponivel
    ):
        """Opt-out: DadosInvalidos do service deve re-renderizar form com erro_geral,
        não redirect com messages (estado UI intermediário)."""
        from unittest.mock import patch

        from apps.core.exceptions import DadosInvalidos

        client.force_login(chefe_almoxarifado)
        with patch(
            'apps.estoque.views.registrar_saida_excepcional',
            side_effect=DadosInvalidos('material inativo'),
        ):
            response = client.post(
                URL_NOVA,
                data={
                    'motivo': 'avaria',
                    'observacao': 'Teste opt-out',
                    'itens-TOTAL_FORMS': '1',
                    'itens-INITIAL_FORMS': '0',
                    'itens-MIN_NUM_FORMS': '0',
                    'itens-MAX_NUM_FORMS': '1000',
                    'itens-0-material_id': str(material_disponivel.pk),
                    'itens-0-quantidade': '5',
                },
            )

        assert response.status_code == 200
        assert 'erro_geral' in response.context
        assert response.context['erro_geral'] == 'material inativo'
        assert not list(response.wsgi_request._messages)


class TestBuscarMateriasSaidaExcepcionalView:
    def test_chefe_recebe_json(self, client, chefe_almoxarifado, material_disponivel):
        client.force_login(chefe_almoxarifado)
        response = client.get(URL_BUSCAR, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        assert response.status_code == 200
        data = response.json()
        assert 'resultados' in data

    def test_filtra_por_q(self, client, chefe_almoxarifado, material_disponivel):
        client.force_login(chefe_almoxarifado)
        response = client.get(
            URL_BUSCAR + '?q=Parafuso', HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        assert response.status_code == 200
        data = response.json()
        assert any('Parafuso' in r['nome'] for r in data['resultados'])

    def test_aux_recebe_403(self, client, aux_almoxarifado):
        client.force_login(aux_almoxarifado)
        response = client.get(URL_BUSCAR, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        assert response.status_code == 403

    def test_anonimo_redirecionado(self, client):
        response = client.get(URL_BUSCAR)
        assert response.status_code == 302

    def test_aux_permissao_negada_retorna_json_403_nao_redirect(
        self, client, aux_almoxarifado
    ):
        """Opt-out: PermissaoNegada em buscar_materiais_saida_excepcional deve retornar
        JsonResponse 403 (não redirect com messages)."""
        client.force_login(aux_almoxarifado)
        response = client.get(URL_BUSCAR)
        assert response.status_code == 403
        assert response['Content-Type'].startswith('application/json')
        assert 'error' in response.json()


class TestDetalheSaidaExcepcionalView:
    def _url(self, pk):
        return reverse('estoque:detalhe_saida_excepcional', args=[pk])

    def test_chefe_almox_acessa_detalhe(
        self, client, chefe_almoxarifado, saida_registrada
    ):
        client.force_login(chefe_almoxarifado)
        response = client.get(self._url(saida_registrada.pk))
        assert response.status_code == 200

    def test_aux_almox_acessa_detalhe(self, client, aux_almoxarifado, saida_registrada):
        client.force_login(aux_almoxarifado)
        response = client.get(self._url(saida_registrada.pk))
        assert response.status_code == 200

    def test_superuser_acessa_detalhe(self, client, superuser, saida_registrada):
        client.force_login(superuser)
        response = client.get(self._url(saida_registrada.pk))
        assert response.status_code == 200

    def test_solicitante_recebe_403(self, client, solicitante, saida_registrada):
        client.force_login(solicitante)
        response = client.get(self._url(saida_registrada.pk))
        assert response.status_code == 403

    def test_anonimo_redirecionado_para_login(self, client, saida_registrada):
        response = client.get(self._url(saida_registrada.pk))
        assert response.status_code == 302
        assert 'login' in response['Location']

    def test_usuario_inativo_redirecionado_para_login(
        self, client, usuario_inativo, saida_registrada
    ):
        client.force_login(usuario_inativo)
        response = client.get(self._url(saida_registrada.pk))
        assert response.status_code == 302
        assert 'login' in response['Location']

    def test_pk_inexistente_retorna_404(self, client, chefe_almoxarifado):
        client.force_login(chefe_almoxarifado)
        response = client.get(self._url(999999))
        assert response.status_code == 404

    def test_contexto_contem_saida_e_pode_estornar(
        self, client, chefe_almoxarifado, saida_registrada
    ):
        client.force_login(chefe_almoxarifado)
        response = client.get(self._url(saida_registrada.pk))
        assert 'saida' in response.context
        assert 'pode_estornar' in response.context
        assert response.context['pode_estornar'] is True

    def test_aux_nao_pode_estornar_no_contexto(
        self, client, aux_almoxarifado, saida_registrada
    ):
        client.force_login(aux_almoxarifado)
        response = client.get(self._url(saida_registrada.pk))
        assert response.context['pode_estornar'] is False

    def test_post_retorna_405(self, client, chefe_almoxarifado, saida_registrada):
        client.force_login(chefe_almoxarifado)
        response = client.post(self._url(saida_registrada.pk), data={})
        assert response.status_code == 405


class TestEstornarSaidaExcepcionalView:
    def _url(self, pk):
        return reverse('estoque:estornar_saida_excepcional', args=[pk])

    def test_chefe_estorna_e_redireciona_para_detalhe(
        self, client, chefe_almoxarifado, saida_registrada
    ):
        client.force_login(chefe_almoxarifado)
        response = client.post(
            self._url(saida_registrada.pk),
            data={'justificativa': 'Registro equivocado.'},
        )
        assert response.status_code == 302
        assert str(saida_registrada.pk) in response['Location']

    def test_superuser_estorna_e_redireciona(self, client, superuser, saida_registrada):
        client.force_login(superuser)
        response = client.post(
            self._url(saida_registrada.pk),
            data={'justificativa': 'Override técnico.'},
        )
        assert response.status_code == 302
        assert str(saida_registrada.pk) in response['Location']

    def test_aux_recebe_403(self, client, aux_almoxarifado, saida_registrada):
        client.force_login(aux_almoxarifado)
        response = client.post(
            self._url(saida_registrada.pk),
            data={'justificativa': 'Tentativa.'},
        )
        assert response.status_code == 403

    def test_solicitante_recebe_403(self, client, solicitante, saida_registrada):
        client.force_login(solicitante)
        response = client.post(
            self._url(saida_registrada.pk),
            data={'justificativa': 'Tentativa.'},
        )
        assert response.status_code == 403

    def test_anonimo_redirecionado_para_login(self, client, saida_registrada):
        response = client.post(
            self._url(saida_registrada.pk),
            data={'justificativa': 'Tentativa.'},
        )
        assert response.status_code == 302
        assert 'login' in response['Location']

    def test_pk_inexistente_retorna_404(self, client, chefe_almoxarifado):
        client.force_login(chefe_almoxarifado)
        response = client.post(self._url(999999), data={'justificativa': 'x'})
        assert response.status_code == 404

    def test_get_retorna_405(self, client, chefe_almoxarifado, saida_registrada):
        client.force_login(chefe_almoxarifado)
        response = client.get(self._url(saida_registrada.pk))
        assert response.status_code == 405

    def test_justificativa_vazia_redireciona_com_mensagem_erro(
        self, client, chefe_almoxarifado, saida_registrada
    ):
        client.force_login(chefe_almoxarifado)
        response = client.post(
            self._url(saida_registrada.pk),
            data={'justificativa': ''},
        )
        assert response.status_code == 302
        assert str(saida_registrada.pk) in response['Location']
        messages_list = list(response.wsgi_request._messages)
        assert any(m.tags == 'error' for m in messages_list)

    def test_saida_ja_estornada_redireciona_com_mensagem_warning(
        self, client, chefe_almoxarifado, saida_registrada
    ):
        from apps.estoque.services import estornar_saida_excepcional

        estornar_saida_excepcional(
            ator_id=chefe_almoxarifado.pk,
            saida_id=saida_registrada.pk,
            justificativa='Primeiro.',
        )
        client.force_login(chefe_almoxarifado)
        response = client.post(
            self._url(saida_registrada.pk),
            data={'justificativa': 'Segundo.'},
        )
        assert response.status_code == 302
        assert str(saida_registrada.pk) in response['Location']
        messages_list = list(response.wsgi_request._messages)
        assert any(m.tags == 'warning' for m in messages_list)
        assert not any(m.tags == 'error' for m in messages_list)

    def test_estorno_nao_duplica_mensagem_no_detalhe(
        self, client, chefe_almoxarifado, saida_registrada
    ):
        client.force_login(chefe_almoxarifado)
        response = client.post(
            self._url(saida_registrada.pk),
            data={'justificativa': 'Registro equivocado.'},
        )
        assert response.status_code == 302
        assert str(saida_registrada.pk) in response['Location']

        detalhe_response = client.get(response['Location'])
        assert detalhe_response.status_code == 200
        conteudo = detalhe_response.content.decode()
        mensagem = f'Saída {saida_registrada.numero_publico} estornada com sucesso.'
        assert conteudo.count(mensagem) == 1

    def test_conflito_dominio_mostra_warning_nao_error(
        self, client, chefe_almoxarifado, saida_registrada
    ):
        """Drift 6 (canônico): ConflitoDominio em estornar_saida_excepcional deve
        gerar messages.warning, nunca messages.error."""
        from unittest.mock import patch

        from apps.core.exceptions import ConflitoDominio

        client.force_login(chefe_almoxarifado)
        with patch(
            'apps.estoque.services.estornar_saida_excepcional',
            side_effect=ConflitoDominio('Já estornada'),
        ):
            response = client.post(
                self._url(saida_registrada.pk),
                data={'justificativa': 'Motivo'},
            )

        messages_list = list(response.wsgi_request._messages)
        assert any(m.tags == 'warning' for m in messages_list)
        assert not any(m.tags == 'error' for m in messages_list)


class TestPreviewImportacaoScpiView:
    """Contrato HTTP de preview_importacao_scpi_view."""

    URL = '/estoque/importacao-scpi/pre-visualizacao/'

    def _csv_valido(
        self, codigo: str = '000.000.001', quantidade: str = '10.000'
    ) -> bytes:
        return f'CADPRO;DENOMINACAO;QUAN3\n{codigo};Teste;{quantidade}\n'.encode(
            'utf-8'
        )

    def test_nao_autenticado_redireciona_para_login(self, client):
        resp = client.get(self.URL)
        assert resp.status_code == 302
        assert '/login/' in resp['Location']

    def test_sem_permissao_retorna_403(self, client, chefe_almoxarifado):
        client.force_login(chefe_almoxarifado)
        resp = client.get(self.URL)
        assert resp.status_code == 403

    def test_superuser_get_retorna_200(self, client, superuser):
        client.force_login(superuser)
        resp = client.get(self.URL)
        assert resp.status_code == 200

    def test_post_csv_valido_retorna_200_com_preview(
        self, client, superuser, estoque_principal, material_scpi
    ):
        from django.core.files.uploadedfile import SimpleUploadedFile

        client.force_login(superuser)
        csv_bytes = self._csv_valido(material_scpi.codigo, '100.000')
        arquivo = SimpleUploadedFile('teste.csv', csv_bytes, content_type='text/csv')
        resp = client.post(self.URL, {'arquivo': arquivo})
        assert resp.status_code == 200
        assert (
            b'CADPRO' in resp.content or material_scpi.codigo.encode() in resp.content
        )

    def test_post_sem_arquivo_retorna_200_com_erro(self, client, superuser):
        client.force_login(superuser)
        resp = client.post(self.URL, {})
        assert resp.status_code == 200
        assert b'arquivo' in resp.content.lower() or b'obrigat' in resp.content.lower()

    def test_post_csv_invalido_retorna_200_com_mensagem_erro(
        self, client, superuser, estoque_principal
    ):
        from django.core.files.uploadedfile import SimpleUploadedFile

        client.force_login(superuser)
        csv_ruim = b'COLUNA_ERRADA;OUTRA\nX;Y\n'
        arquivo = SimpleUploadedFile('ruim.csv', csv_ruim, content_type='text/csv')
        resp = client.post(self.URL, {'arquivo': arquivo})
        assert resp.status_code == 200
        assert b'CADPRO' in resp.content or b'inv' in resp.content.lower()


class TestConfirmarImportacaoScpiView:
    """Contrato HTTP de confirmar_importacao_scpi_view (POST) + sucesso_importacao_scpi_view (GET)."""

    URL_PREVIEW = '/estoque/importacao-scpi/pre-visualizacao/'
    URL = '/requisicoes/importacao-scpi/confirmar/'

    def _csv(self, cadpro: str = '000.888.001', quantidade: str = '10.000') -> bytes:
        return f'CADPRO;DENOMINACAO;QUAN3\n{cadpro};Teste;{quantidade}\n'.encode(
            'utf-8'
        )

    def _seed_session(self, client, superuser, csv_bytes: bytes) -> None:
        from django.core.files.uploadedfile import SimpleUploadedFile

        client.force_login(superuser)
        arquivo = SimpleUploadedFile('seed.csv', csv_bytes, content_type='text/csv')
        client.post(self.URL_PREVIEW, {'arquivo': arquivo})

    def test_nao_autenticado_redireciona_para_login(self, client):
        resp = client.post(self.URL, {})
        assert resp.status_code == 302
        assert '/login/' in resp['Location']

    def test_sem_permissao_retorna_403(self, client, chefe_almoxarifado):
        client.force_login(chefe_almoxarifado)
        resp = client.post(self.URL, {})
        assert resp.status_code == 403

    def test_sem_session_retorna_200_com_erro(self, client, superuser):
        client.force_login(superuser)
        resp = client.post(self.URL, {})
        assert resp.status_code == 200
        assert (
            b'pr\xc3\xa9' in resp.content.lower()
            or b'upload' in resp.content.lower()
            or b'visualiza' in resp.content.lower()
            or b'novamente' in resp.content.lower()
        )

    def test_post_com_session_valida_redireciona_para_sucesso(
        self, client, superuser, estoque_principal
    ):
        csv_bytes = self._csv('000.888.010')
        self._seed_session(client, superuser, csv_bytes)
        resp = client.post(self.URL, {})
        assert resp.status_code == 302
        assert '/confirmada/' in resp['Location']

    def test_get_sucesso_retorna_200_com_metadados(
        self, client, superuser, estoque_principal
    ):
        csv_bytes = self._csv('000.888.011')
        self._seed_session(client, superuser, csv_bytes)
        redirect = client.post(self.URL, {})
        assert redirect.status_code == 302
        resp = client.get(redirect['Location'])
        assert resp.status_code == 200
        assert (
            b'sucesso' in resp.content.lower() or b'confirmad' in resp.content.lower()
        )

    def test_hash_duplicado_retorna_200_com_mensagem_erro(
        self, client, superuser, estoque_principal
    ):
        csv_bytes = self._csv('000.888.020')
        self._seed_session(client, superuser, csv_bytes)
        client.post(self.URL, {})

        self._seed_session(client, superuser, csv_bytes)
        resp = client.post(self.URL, {})
        assert resp.status_code == 200
        assert (
            b'duplicad' in resp.content.lower()
            or b'reimporta' in resp.content.lower()
            or b'j\xc3\xa1' in resp.content.lower()
        )

    def test_get_nao_permitido_retorna_405(self, client, superuser):
        client.force_login(superuser)
        resp = client.get(self.URL)
        assert resp.status_code == 405


class TestHistoricoImportacoesScpiView:
    """Contrato HTTP de historico_importacoes_scpi_view."""

    URL = '/estoque/importacao-scpi/historico/'

    def test_nao_autenticado_redireciona_para_login(self, client):
        resp = client.get(self.URL)
        assert resp.status_code == 302
        assert '/login/' in resp['Location']

    def test_sem_permissao_retorna_403(self, client, solicitante):
        client.force_login(solicitante)
        resp = client.get(self.URL)
        assert resp.status_code == 403

    def test_superuser_get_retorna_200(self, client, superuser):
        client.force_login(superuser)
        resp = client.get(self.URL)
        assert resp.status_code == 200

    def test_chefe_almoxarifado_get_retorna_200(self, client, chefe_almoxarifado):
        client.force_login(chefe_almoxarifado)
        resp = client.get(self.URL)
        assert resp.status_code == 200

    def test_post_retorna_405(self, client, superuser):
        client.force_login(superuser)
        resp = client.post(self.URL, {})
        assert resp.status_code == 405

    def test_lista_vazia_retorna_200(self, client, superuser):
        client.force_login(superuser)
        resp = client.get(self.URL)
        assert resp.status_code == 200

    def test_exibe_metadados_da_importacao(self, client, superuser, estoque_principal):
        from apps.estoque.models import ImportacaoSCPI, StatusImportacaoSCPI

        ImportacaoSCPI.objects.create(
            arquivo_nome='relatorio.csv',
            arquivo_hash='e' * 64,
            importado_por=superuser,
            estoque=estoque_principal,
            status=StatusImportacaoSCPI.CONCLUIDA,
            total_linhas=10,
            total_novos=2,
            total_divergentes=3,
        )
        client.force_login(superuser)
        resp = client.get(self.URL)
        assert resp.status_code == 200
        assert b'relatorio.csv' in resp.content

    def test_nao_expoe_csv_bruto(self, client, superuser, estoque_principal):
        from apps.estoque.models import ImportacaoSCPI, StatusImportacaoSCPI

        ImportacaoSCPI.objects.create(
            arquivo_nome='bruto.csv',
            arquivo_hash='f' * 64,
            importado_por=superuser,
            estoque=estoque_principal,
            status=StatusImportacaoSCPI.CONCLUIDA,
        )
        client.force_login(superuser)
        resp = client.get(self.URL)
        assert b'conteudo_csv' not in resp.content


URL_MATERIAIS = reverse('estoque:lista_materiais')


class TestListaMateriaisView:
    def test_chefe_almox_acessa_lista(self, client, chefe_almoxarifado):
        client.force_login(chefe_almoxarifado)
        response = client.get(URL_MATERIAIS)
        assert response.status_code == 200

    def test_aux_almox_acessa_lista(self, client, aux_almoxarifado):
        client.force_login(aux_almoxarifado)
        response = client.get(URL_MATERIAIS)
        assert response.status_code == 200

    def test_superuser_acessa_lista(self, client, superuser):
        client.force_login(superuser)
        response = client.get(URL_MATERIAIS)
        assert response.status_code == 200

    def test_solicitante_acessa_lista(self, client, solicitante):
        # Consultar materiais é permitido para todos os papéis ativos (matriz-permissoes.md).
        client.force_login(solicitante)
        response = client.get(URL_MATERIAIS)
        assert response.status_code == 200

    def test_usuario_inativo_redirecionado_para_login(self, client, usuario_inativo):
        # Django ModelBackend trata is_active=False como não-autenticado;
        # @login_required redireciona para login (USR-01).
        client.force_login(usuario_inativo)
        response = client.get(URL_MATERIAIS)
        assert response.status_code == 302
        assert 'login' in response['Location']

    def test_anonimo_redirecionado_para_login(self, client):
        response = client.get(URL_MATERIAIS)
        assert response.status_code == 302
        assert 'login' in response['Location']

    def test_contexto_contem_saldos(
        self, client, chefe_almoxarifado, material_disponivel, estoque_principal
    ):
        client.force_login(chefe_almoxarifado)
        response = client.get(URL_MATERIAIS)
        assert 'saldos' in response.context

    def test_contexto_contem_busca_vazia_por_padrao(self, client, chefe_almoxarifado):
        client.force_login(chefe_almoxarifado)
        response = client.get(URL_MATERIAIS)
        assert response.context['busca'] == ''

    def test_nenhum_material_cadastrado_exibe_empty_state_dashed(
        self, client, chefe_almoxarifado
    ):
        client.force_login(chefe_almoxarifado)
        response = client.get(URL_MATERIAIS)
        html = response.content.decode()
        assert 'border-dashed border-slate-300' in html
        assert 'border-slate-200 bg-white p-8' not in html
        assert 'Nenhum material cadastrado no estoque.' in html

    def test_busca_sem_resultado_exibe_cta_secundario_link(
        self, client, chefe_almoxarifado
    ):
        client.force_login(chefe_almoxarifado)
        response = client.get(URL_MATERIAIS, {'busca': 'inexistente-xyz'})
        html = response.content.decode()
        assert 'border-dashed border-slate-300' in html
        titulo_idx = html.index('Nenhum material encontrado para')
        match = re.search(r'<a\b[^>]*>', html[titulo_idx:])
        assert match is not None
        tag = match.group()
        assert re.search(r'href="[^"]*"', tag)
        assert 'underline' in tag
        assert 'bg-blue-600' not in tag

    def test_busca_filtra_por_codigo(
        self,
        client,
        chefe_almoxarifado,
        material_disponivel,
        material_scpi_critico,
        estoque_principal,
    ):
        client.force_login(chefe_almoxarifado)
        response = client.get(URL_MATERIAIS, {'busca': 'MAT001'})
        assert response.status_code == 200
        saldos = list(response.context['saldos'])
        assert len(saldos) == 1
        assert saldos[0].material.codigo == 'MAT001'

    def test_flag_divergente_visivel_no_contexto(
        self, client, chefe_almoxarifado, material_scpi_critico, estoque_principal
    ):
        client.force_login(chefe_almoxarifado)
        response = client.get(URL_MATERIAIS)
        saldos = list(response.context['saldos'])
        critico = next(s for s in saldos if s.material == material_scpi_critico)
        assert critico.divergente_calculado is True


URL_MOVIMENTACOES = reverse('estoque:historico_movimentacoes')


class TestHistoricoMovimentacoesView:
    def test_chefe_almox_acessa(self, client, chefe_almoxarifado):
        client.force_login(chefe_almoxarifado)
        response = client.get(URL_MOVIMENTACOES)
        assert response.status_code == 200

    def test_superuser_acessa(self, client, superuser):
        client.force_login(superuser)
        response = client.get(URL_MOVIMENTACOES)
        assert response.status_code == 200

    def test_solicitante_recebe_403(self, client, solicitante):
        client.force_login(solicitante)
        response = client.get(URL_MOVIMENTACOES)
        assert response.status_code == 403

    def test_anonimo_redirecionado_para_login(self, client):
        response = client.get(URL_MOVIMENTACOES)
        assert response.status_code == 302
        assert 'login' in response['Location']

    def test_contexto_tem_page_obj(self, client, chefe_almoxarifado):
        client.force_login(chefe_almoxarifado)
        response = client.get(URL_MOVIMENTACOES)
        assert 'page_obj' in response.context

    def test_view_alimenta_page_obj_com_selector_escopado(
        self,
        client,
        chefe_obras,
        requisicao_autorizada,
        saida_registrada,
        movimentacao_outro_setor,
    ):
        # Contrato HTTP/render: a view delega o escopo ao selector e pagina o
        # resultado. A matriz de visibilidade em si é coberta em test_selectors.
        from apps.estoque.selectors import movimentacoes_visiveis_para

        client.force_login(chefe_obras)
        response = client.get(URL_MOVIMENTACOES)
        assert response.status_code == 200
        assert 'estoque/historico_movimentacoes.html' in {
            t.name for t in response.templates
        }
        esperado = movimentacoes_visiveis_para(chefe_obras.pk).count()
        assert response.context['page_obj'].paginator.count == esperado

    def test_paginacao_server_side(
        self,
        client,
        superuser,
        requisicao_autorizada,
        material_disponivel,
        estoque_principal,
    ):
        from decimal import Decimal

        from apps.estoque.models import MovimentacaoEstoque, TipoMovimentacaoEstoque

        req, _ = requisicao_autorizada
        for _ in range(30):
            MovimentacaoEstoque.objects.create(
                tipo=TipoMovimentacaoEstoque.CONSUMO,
                material=material_disponivel,
                estoque=estoque_principal,
                delta_fisico=Decimal('-1'),
                delta_reservado=Decimal('-1'),
                requisicao=req,
                ator=superuser,
            )
        client.force_login(superuser)
        page1 = client.get(URL_MOVIMENTACOES)
        assert len(page1.context['page_obj'].object_list) == 25
        assert page1.context['page_obj'].has_next() is True
        page2 = client.get(URL_MOVIMENTACOES, {'page': 2})
        assert page2.status_code == 200
        assert len(page2.context['page_obj'].object_list) >= 1

    def test_empty_state_quando_ledger_vazio(self, client, chefe_almoxarifado):
        client.force_login(chefe_almoxarifado)
        response = client.get(URL_MOVIMENTACOES)
        assert response.context['page_obj'].paginator.count == 0
        assert b'Nenhuma movimenta' in response.content

    def test_paginacao_usa_componente_com_rotulo_e_aria_label_proprios(
        self,
        client,
        superuser,
        requisicao_autorizada,
        material_disponivel,
        estoque_principal,
    ):
        from decimal import Decimal

        from apps.estoque.models import MovimentacaoEstoque, TipoMovimentacaoEstoque

        req, _ = requisicao_autorizada
        for _ in range(30):
            MovimentacaoEstoque.objects.create(
                tipo=TipoMovimentacaoEstoque.CONSUMO,
                material=material_disponivel,
                estoque=estoque_principal,
                delta_fisico=Decimal('-1'),
                delta_reservado=Decimal('-1'),
                requisicao=req,
                ator=superuser,
            )
        client.force_login(superuser)
        response = client.get(URL_MOVIMENTACOES)
        total = response.context['page_obj'].paginator.count
        assert 'aria-label="Paginação das movimentações"'.encode() in response.content
        esperado = f'<span class="tabular-nums">{total}</span> movimentações'
        assert esperado.encode() in response.content

    def test_menu_mostra_link_para_almox(self, client, chefe_almoxarifado):
        client.force_login(chefe_almoxarifado)
        response = client.get(URL_MOVIMENTACOES)
        assert URL_MOVIMENTACOES.encode() in response.content

    def test_comentarios_dos_partials_nao_vazam_para_a_tela(
        self, client, superuser, requisicao_autorizada
    ):
        # Comentário multilinha precisa ser {% comment %}, não {# #} (que é
        # single-line) — senão o texto do comentário renderiza como conteúdo.
        client.force_login(superuser)
        response = client.get(URL_MOVIMENTACOES)
        assert 'Badge semântico'.encode() not in response.content
        assert 'Célula de delta'.encode() not in response.content
        assert 'Paginação server-side'.encode() not in response.content


class TestHistoricoMovimentacoesFiltros:
    """Camada de filtros HTMX sobre o ledger (issue #7)."""

    def test_filtro_material_reduz_resultado(
        self, client, superuser, requisicao_autorizada
    ):
        client.force_login(superuser)
        com = client.get(URL_MOVIMENTACOES, {'material': 'MAT001'})
        sem = client.get(URL_MOVIMENTACOES, {'material': 'inexistente'})
        assert com.context['page_obj'].paginator.count >= 1
        assert sem.context['page_obj'].paginator.count == 0

    def test_requisicao_htmx_devolve_so_partial(
        self, client, superuser, requisicao_autorizada
    ):
        client.force_login(superuser)
        response = client.get(URL_MOVIMENTACOES, HTTP_HX_REQUEST='true')
        assert response.status_code == 200
        nomes = {t.name for t in response.templates}
        assert 'estoque/partials/_tabela_movimentacoes.html' in nomes
        # Não renderiza o template completo (app-bar) num swap parcial.
        assert 'estoque/historico_movimentacoes.html' not in nomes

    def test_requisicao_normal_devolve_template_completo(
        self, client, superuser, requisicao_autorizada
    ):
        client.force_login(superuser)
        response = client.get(URL_MOVIMENTACOES)
        nomes = {t.name for t in response.templates}
        assert 'estoque/historico_movimentacoes.html' in nomes

    def test_ordenacao_asc_inverte_cronologia(
        self,
        client,
        superuser,
        requisicao_autorizada,
        material_disponivel,
        estoque_principal,
    ):
        from decimal import Decimal

        from apps.estoque.models import MovimentacaoEstoque, TipoMovimentacaoEstoque

        req, _ = requisicao_autorizada
        for _ in range(2):
            MovimentacaoEstoque.objects.create(
                tipo=TipoMovimentacaoEstoque.CONSUMO,
                material=material_disponivel,
                estoque=estoque_principal,
                delta_fisico=Decimal('-1'),
                delta_reservado=Decimal('-1'),
                requisicao=req,
                ator=superuser,
            )
        client.force_login(superuser)
        desc = client.get(URL_MOVIMENTACOES).context['page_obj'].object_list
        asc = (
            client.get(URL_MOVIMENTACOES, {'ordem': 'asc'})
            .context['page_obj']
            .object_list
        )
        assert [m.pk for m in asc] == [m.pk for m in reversed(list(desc))]
        assert client.get(URL_MOVIMENTACOES, {'ordem': 'asc'}).context['ordem'] == 'asc'

    def test_filtro_setor_visivel_so_para_almox(
        self, client, chefe_almoxarifado, chefe_obras
    ):
        client.force_login(chefe_almoxarifado)
        assert client.get(URL_MOVIMENTACOES).context['mostrar_filtro_setor'] is True
        client.force_login(chefe_obras)
        assert client.get(URL_MOVIMENTACOES).context['mostrar_filtro_setor'] is False

    def test_chefe_setor_nao_filtra_por_setor_via_querystring(
        self, client, chefe_obras, requisicao_autorizada, movimentacao_outro_setor
    ):
        # Mesmo forçando ?setor=<outro> na URL, chefe de setor não vaza dado.
        setor_ti = movimentacao_outro_setor.requisicao.setor_beneficiario_id
        client.force_login(chefe_obras)
        response = client.get(URL_MOVIMENTACOES, {'setor': setor_ti})
        assert response.status_code == 200
        pks = {m.pk for m in response.context['page_obj'].object_list}
        assert movimentacao_outro_setor.pk not in pks

    def test_querystring_invalida_nao_quebra(
        self, client, superuser, requisicao_autorizada
    ):
        client.force_login(superuser)
        response = client.get(
            URL_MOVIMENTACOES,
            {
                'data_ini': 'abc',
                'data_fim': '2026-13-99',
                'setor': 'xyz',
                'ordem': 'lixo',
                'tipos': 'nao_existe',
                'page': 'foo',
            },
        )
        assert response.status_code == 200

    def test_chip_so_saidas_marca_estado_ativo(
        self, client, superuser, requisicao_autorizada
    ):
        client.force_login(superuser)
        ativo = client.get(
            URL_MOVIMENTACOES,
            {'tipos': ['consumo', 'saida_excepcional']},
        )
        inativo = client.get(URL_MOVIMENTACOES)
        assert ativo.context['so_saidas_ativo'] is True
        assert inativo.context['so_saidas_ativo'] is False

    def test_chip_so_saidas_reemitido_via_oob_no_swap_htmx(
        self, client, superuser, requisicao_autorizada
    ):
        # Bug-regressão: o chip vive fora de #resultados-movimentacoes, então
        # numa resposta HTMX precisa ser reemitido como out-of-band para o
        # estado ativo e a URL de alternância refletirem o novo recorte.
        client.force_login(superuser)
        parcial = client.get(
            URL_MOVIMENTACOES,
            {'tipos': ['consumo', 'saida_excepcional']},
            HTTP_HX_REQUEST='true',
        ).content
        assert b'id="chip-so-saidas"' in parcial
        assert b'hx-swap-oob="true"' in parcial
        assert b'aria-current="true"' in parcial

    def test_chip_so_saidas_sem_oob_na_pagina_completa(
        self, client, superuser, requisicao_autorizada
    ):
        # Render completo: chip único, sem atributo OOB (evita id duplicado).
        client.force_login(superuser)
        conteudo = client.get(URL_MOVIMENTACOES).content
        assert conteudo.count(b'id="chip-so-saidas"') == 1
        assert b'hx-swap-oob' not in conteudo

    def test_flag_tem_filtro_ativo(self, client, superuser, requisicao_autorizada):
        client.force_login(superuser)
        com = client.get(URL_MOVIMENTACOES, {'material': 'x'})
        sem = client.get(URL_MOVIMENTACOES)
        assert com.context['tem_filtro_ativo'] is True
        assert sem.context['tem_filtro_ativo'] is False

    def test_empty_state_contextual_distingue_filtro_de_ledger_vazio(
        self, client, superuser, requisicao_autorizada
    ):
        client.force_login(superuser)
        # Filtro sem resultado → mensagem específica de filtro, e NÃO a de
        # ledger vazio.
        filtrado = client.get(URL_MOVIMENTACOES, {'material': 'inexistente'}).content
        assert 'Nenhum resultado para este filtro'.encode() in filtrado
        assert 'Nenhuma movimentação encontrada'.encode() not in filtrado

    def test_chip_so_saidas_preserva_filtros_atuais(
        self, client, chefe_almoxarifado, setor_obras
    ):
        # Bug-regressão: alternar o chip não pode descartar o recorte atual.
        client.force_login(chefe_almoxarifado)
        response = client.get(
            URL_MOVIMENTACOES,
            {'material': 'parafuso', 'ordem': 'asc', 'setor': setor_obras.pk},
        )
        url_chip = response.context['url_chip_so_saidas']
        assert 'material=parafuso' in url_chip
        assert 'ordem=asc' in url_chip
        assert f'setor={setor_obras.pk}' in url_chip
        assert 'tipos=consumo' in url_chip
        assert 'tipos=saida_excepcional' in url_chip


class TestHistoricoMovimentacoesResponsivo:
    """Testes de estrutura HTML responsiva e atributos de acessibilidade."""

    def test_disclosure_nativo_presente_na_pagina(self, client, chefe_almoxarifado):
        # A barra de filtros usa <details>/<summary> nativo para disclosure mobile
        # — funciona sem JavaScript (progressive enhancement).
        client.force_login(chefe_almoxarifado)
        response = client.get(URL_MOVIMENTACOES)
        assert response.status_code == 200
        assert b'<details' in response.content
        assert b'<summary' in response.content

    def test_chip_so_saidas_visivel_fora_do_disclosure(
        self, client, chefe_almoxarifado
    ):
        # O chip "só saídas" deve aparecer ANTES do <details> no HTML para
        # garantir visibilidade permanente no mobile sem abrir o disclosure.
        client.force_login(chefe_almoxarifado)
        response = client.get(URL_MOVIMENTACOES)
        assert response.status_code == 200
        content = response.content.decode()
        pos_chip = content.find('id="chip-so-saidas"')
        pos_details = content.find('<details')
        assert pos_chip != -1, 'chip-so-saidas não encontrado'
        assert pos_details != -1, '<details não encontrado'
        assert pos_chip < pos_details, 'chip deve aparecer antes do <details>'

    def test_aria_live_polite_no_conteiner_de_resultados(
        self, client, chefe_almoxarifado
    ):
        # O wrapper #resultados-movimentacoes deve ter aria-live="polite" e
        # aria-atomic="true" para anunciar swaps HTMX a tecnologias assistivas.
        client.force_login(chefe_almoxarifado)
        response = client.get(URL_MOVIMENTACOES)
        assert response.status_code == 200
        assert b'aria-live="polite"' in response.content
        assert b'aria-atomic="true"' in response.content
