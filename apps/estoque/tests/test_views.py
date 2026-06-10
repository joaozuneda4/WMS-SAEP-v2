"""Testes de view para estoque.saidas_excepcionais."""

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

    def test_saida_ja_estornada_redireciona_com_mensagem_erro(
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
        assert any(m.tags == 'error' for m in messages_list)


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
    URL = '/estoque/importacao-scpi/confirmar/'

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
