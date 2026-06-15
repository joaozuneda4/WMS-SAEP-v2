"""Testes de services de requisições (ADR-0010).

3 casos por transição: caminho feliz, estado inválido, permissão negada.
"""

from decimal import Decimal

import pytest

from apps.core.exceptions import (
    ConflitoDominio,
    DadosInvalidos,
    EstadoInvalido,
    PermissaoNegada,
)
from apps.requisicoes.models import (
    EstadoRequisicao,
    EventoTimeline,
    ItemRequisicao,
    Requisicao,
)
from apps.requisicoes.services import (
    autorizar_requisicao,
    criar_requisicao,
    cancelar_ou_descartar_requisicao,
    cancelar_requisicao,
    descartar_rascunho,
    editar_rascunho,
    recusar_requisicao,
    registrar_atendimento,
    retornar_para_rascunho,
    separar_para_retirada,
)
from apps.estoque.services import (
    liberar_reservas_para_cancelamento,
    reservar_saldos_para_autorizacao,
)


# ---------------------------------------------------------------------------
# TR-001: criar_requisicao — caminho feliz
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_criar_requisicao_estado_rascunho(solicitante, material_disponivel):
    req = criar_requisicao(
        ator_id=solicitante.pk,
        beneficiario_id=solicitante.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('5'),
            }
        ],
    )
    assert req.pk is not None
    assert req.estado == EstadoRequisicao.RASCUNHO


@pytest.mark.django_db
def test_criar_requisicao_sem_numero_publico(solicitante, material_disponivel):
    req = criar_requisicao(
        ator_id=solicitante.pk,
        beneficiario_id=solicitante.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('1'),
            }
        ],
    )
    assert req.numero_publico is None


@pytest.mark.django_db
def test_criar_requisicao_snapshot_setor_beneficiario(
    chefe_obras, outro_usuario_obras, setor_obras, material_disponivel
):
    """setor_beneficiario é snapshot do setor do beneficiário no momento da criação."""
    req = criar_requisicao(
        ator_id=chefe_obras.pk,
        beneficiario_id=outro_usuario_obras.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('2'),
            }
        ],
    )
    assert req.setor_beneficiario_id == setor_obras.pk
    assert req.criador_id == chefe_obras.pk
    assert req.beneficiario_id == outro_usuario_obras.pk


@pytest.mark.django_db
def test_criar_requisicao_registra_evento_criacao(solicitante, material_disponivel):
    req = criar_requisicao(
        ator_id=solicitante.pk,
        beneficiario_id=solicitante.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('3'),
            }
        ],
    )
    evento = req.eventos.get()
    assert evento.evento == EventoTimeline.CRIACAO
    assert evento.ator_id == solicitante.pk
    assert evento.estado_resultante == EstadoRequisicao.RASCUNHO


@pytest.mark.django_db
def test_criar_requisicao_cria_itens(
    solicitante, material_disponivel, material_disponivel_2
):
    req = criar_requisicao(
        ator_id=solicitante.pk,
        beneficiario_id=solicitante.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('5'),
            },
            {
                'material_id': material_disponivel_2.pk,
                'quantidade_solicitada': Decimal('2'),
            },
        ],
    )
    assert req.itens.count() == 2


# ---------------------------------------------------------------------------
# TR-001: criar_requisicao — permissão negada
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_criar_requisicao_solicitante_nao_pode_criar_para_terceiro(
    solicitante, outro_usuario_obras, material_disponivel
):
    with pytest.raises(PermissaoNegada):
        criar_requisicao(
            ator_id=solicitante.pk,
            beneficiario_id=outro_usuario_obras.pk,
            itens=[
                {
                    'material_id': material_disponivel.pk,
                    'quantidade_solicitada': Decimal('1'),
                }
            ],
        )


# ---------------------------------------------------------------------------
# TR-001: criar_requisicao — dados inválidos
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_criar_requisicao_sem_itens(solicitante):
    with pytest.raises(DadosInvalidos, match='ao menos um item'):
        criar_requisicao(
            ator_id=solicitante.pk,
            beneficiario_id=solicitante.pk,
            itens=[],
        )


@pytest.mark.django_db
def test_criar_requisicao_material_inativo(solicitante, material_inativo):
    with pytest.raises(DadosInvalidos):
        criar_requisicao(
            ator_id=solicitante.pk,
            beneficiario_id=solicitante.pk,
            itens=[
                {
                    'material_id': material_inativo.pk,
                    'quantidade_solicitada': Decimal('1'),
                }
            ],
        )


@pytest.mark.django_db
def test_criar_requisicao_material_sem_saldo(solicitante, material_sem_saldo):
    with pytest.raises(DadosInvalidos):
        criar_requisicao(
            ator_id=solicitante.pk,
            beneficiario_id=solicitante.pk,
            itens=[
                {
                    'material_id': material_sem_saldo.pk,
                    'quantidade_solicitada': Decimal('1'),
                }
            ],
        )


@pytest.mark.django_db
def test_criar_requisicao_material_divergente(solicitante, material_divergente):
    with pytest.raises(DadosInvalidos):
        criar_requisicao(
            ator_id=solicitante.pk,
            beneficiario_id=solicitante.pk,
            itens=[
                {
                    'material_id': material_divergente.pk,
                    'quantidade_solicitada': Decimal('1'),
                }
            ],
        )


@pytest.mark.django_db
def test_criar_requisicao_quantidade_zero(solicitante, material_disponivel):
    with pytest.raises(DadosInvalidos, match='Quantidade'):
        criar_requisicao(
            ator_id=solicitante.pk,
            beneficiario_id=solicitante.pk,
            itens=[
                {
                    'material_id': material_disponivel.pk,
                    'quantidade_solicitada': Decimal('0'),
                }
            ],
        )


@pytest.mark.django_db
def test_criar_requisicao_material_duplicado(solicitante, material_disponivel):
    with pytest.raises(DadosInvalidos, match='mesmo material'):
        criar_requisicao(
            ator_id=solicitante.pk,
            beneficiario_id=solicitante.pk,
            itens=[
                {
                    'material_id': material_disponivel.pk,
                    'quantidade_solicitada': Decimal('1'),
                },
                {
                    'material_id': material_disponivel.pk,
                    'quantidade_solicitada': Decimal('2'),
                },
            ],
        )


# ---------------------------------------------------------------------------
# TR-002: editar_rascunho — caminho feliz
# ---------------------------------------------------------------------------


@pytest.fixture
def rascunho(db, solicitante, setor_obras, material_disponivel):
    req = criar_requisicao(
        ator_id=solicitante.pk,
        beneficiario_id=solicitante.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('3'),
            }
        ],
    )
    return req


@pytest.mark.django_db
def test_editar_rascunho_atualiza_itens(
    rascunho, solicitante, material_disponivel, material_disponivel_2
):
    editar_rascunho(
        ator_id=solicitante.pk,
        requisicao_id=rascunho.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('10'),
            },
            {
                'material_id': material_disponivel_2.pk,
                'quantidade_solicitada': Decimal('5'),
            },
        ],
    )
    rascunho.refresh_from_db()
    assert rascunho.itens.count() == 2
    item = rascunho.itens.get(material_id=material_disponivel.pk)
    assert item.quantidade_solicitada == Decimal('10')


@pytest.mark.django_db
def test_editar_rascunho_atualiza_observacao(
    rascunho, solicitante, material_disponivel
):
    editar_rascunho(
        ator_id=solicitante.pk,
        requisicao_id=rascunho.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('1'),
            }
        ],
        observacao_geral='Nova observação.',
    )
    rascunho.refresh_from_db()
    assert rascunho.observacao_geral == 'Nova observação.'


@pytest.mark.django_db
def test_editar_rascunho_nao_altera_beneficiario(
    rascunho, solicitante, material_disponivel, setor_obras
):
    beneficiario_original = rascunho.beneficiario_id
    setor_original = rascunho.setor_beneficiario_id
    editar_rascunho(
        ator_id=solicitante.pk,
        requisicao_id=rascunho.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('2'),
            }
        ],
    )
    rascunho.refresh_from_db()
    assert rascunho.beneficiario_id == beneficiario_original
    assert rascunho.setor_beneficiario_id == setor_original


# ---------------------------------------------------------------------------
# TR-002: editar_rascunho — permissão negada
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_editar_rascunho_nao_criador_levanta_permissao_negada(
    rascunho, outro_usuario_obras, material_disponivel
):
    with pytest.raises(PermissaoNegada):
        editar_rascunho(
            ator_id=outro_usuario_obras.pk,
            requisicao_id=rascunho.pk,
            itens=[
                {
                    'material_id': material_disponivel.pk,
                    'quantidade_solicitada': Decimal('1'),
                }
            ],
        )


# ---------------------------------------------------------------------------
# TR-002: editar_rascunho — estado inválido
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_editar_rascunho_estado_invalido(solicitante, setor_obras, material_disponivel):
    req = Requisicao.objects.create(
        estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        numero_publico='REQ-2026-000099',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    # Policy passa (ator é o criador), mas transitions lança EstadoInvalido
    with pytest.raises(EstadoInvalido):
        editar_rascunho(
            ator_id=solicitante.pk,
            requisicao_id=req.pk,
            itens=[
                {
                    'material_id': material_disponivel.pk,
                    'quantidade_solicitada': Decimal('1'),
                }
            ],
        )


# ---------------------------------------------------------------------------
# TR-005: enviar_para_autorizacao
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_enviar_para_autorizacao_emite_numero_publico(rascunho, solicitante):
    from apps.requisicoes.services import enviar_para_autorizacao

    req = enviar_para_autorizacao(ator_id=solicitante.pk, requisicao_id=rascunho.pk)
    assert req.estado == EstadoRequisicao.AGUARDANDO_AUTORIZACAO
    assert req.numero_publico is not None
    from django.utils import timezone

    ano = timezone.now().year
    assert req.numero_publico.startswith(f'REQ-{ano}-')
    assert req.numero_publico == f'REQ-{ano}-{1:06d}'


@pytest.mark.django_db
def test_enviar_sequencia_anual_incrementa(
    solicitante, material_disponivel, material_disponivel_2
):
    from apps.requisicoes.services import enviar_para_autorizacao

    r1 = criar_requisicao(
        ator_id=solicitante.pk,
        beneficiario_id=solicitante.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('1'),
            }
        ],
    )
    r2 = criar_requisicao(
        ator_id=solicitante.pk,
        beneficiario_id=solicitante.pk,
        itens=[
            {
                'material_id': material_disponivel_2.pk,
                'quantidade_solicitada': Decimal('1'),
            }
        ],
    )
    n1 = enviar_para_autorizacao(
        ator_id=solicitante.pk, requisicao_id=r1.pk
    ).numero_publico
    n2 = enviar_para_autorizacao(
        ator_id=solicitante.pk, requisicao_id=r2.pk
    ).numero_publico
    assert int(n1.rsplit('-', 1)[1]) + 1 == int(n2.rsplit('-', 1)[1])


@pytest.mark.django_db
def test_enviar_reenvio_preserva_numero_publico(rascunho, solicitante):
    """Rascunho retornado mantém número público no reenvio (REQ-04)."""
    from apps.requisicoes.services import enviar_para_autorizacao

    req = enviar_para_autorizacao(ator_id=solicitante.pk, requisicao_id=rascunho.pk)
    numero_original = req.numero_publico

    # Simula retorno para rascunho preservando o número
    req.estado = EstadoRequisicao.RASCUNHO
    req.save(update_fields=['estado'])

    req2 = enviar_para_autorizacao(ator_id=solicitante.pk, requisicao_id=req.pk)
    assert req2.numero_publico == numero_original
    assert req2.estado == EstadoRequisicao.AGUARDANDO_AUTORIZACAO


@pytest.mark.django_db
def test_enviar_registra_timeline_envio_autorizacao(rascunho, solicitante):
    from apps.requisicoes.services import enviar_para_autorizacao

    enviar_para_autorizacao(ator_id=solicitante.pk, requisicao_id=rascunho.pk)
    evento = rascunho.eventos.filter(evento=EventoTimeline.ENVIO_AUTORIZACAO).get()
    assert evento.ator_id == solicitante.pk
    assert evento.estado_resultante == EstadoRequisicao.AGUARDANDO_AUTORIZACAO


@pytest.mark.django_db
def test_enviar_sem_itens_levanta_dados_invalidos(solicitante, setor_obras):
    from apps.requisicoes.services import enviar_para_autorizacao

    req = Requisicao.objects.create(
        estado=EstadoRequisicao.RASCUNHO,
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    with pytest.raises(DadosInvalidos, match='ao menos um item'):
        enviar_para_autorizacao(ator_id=solicitante.pk, requisicao_id=req.pk)


@pytest.mark.django_db
def test_enviar_em_estado_invalido_levanta_estado_invalido(rascunho, solicitante):
    from apps.requisicoes.services import enviar_para_autorizacao

    rascunho.estado = EstadoRequisicao.AGUARDANDO_AUTORIZACAO
    rascunho.numero_publico = 'REQ-2026-000999'
    rascunho.save(update_fields=['estado', 'numero_publico'])

    with pytest.raises(EstadoInvalido):
        enviar_para_autorizacao(ator_id=solicitante.pk, requisicao_id=rascunho.pk)


@pytest.mark.django_db
def test_enviar_por_terceiro_levanta_permissao_negada(rascunho, outro_usuario_obras):
    from apps.requisicoes.services import enviar_para_autorizacao

    with pytest.raises(PermissaoNegada):
        enviar_para_autorizacao(
            ator_id=outro_usuario_obras.pk, requisicao_id=rascunho.pk
        )


@pytest.mark.django_db
def test_enviar_por_criador_inativo_levanta_permissao_negada(rascunho, solicitante):
    from apps.requisicoes.services import enviar_para_autorizacao

    solicitante.is_active = False
    solicitante.save(update_fields=['is_active'])
    with pytest.raises(PermissaoNegada):
        enviar_para_autorizacao(ator_id=solicitante.pk, requisicao_id=rascunho.pk)


@pytest.mark.django_db
def test_enviar_nao_reserva_estoque(rascunho, solicitante, material_disponivel):
    from apps.estoque.models import SaldoEstoque
    from apps.requisicoes.services import enviar_para_autorizacao

    saldo_antes = SaldoEstoque.objects.get(material=material_disponivel)
    reservado_antes = saldo_antes.saldo_reservado
    fisico_antes = saldo_antes.saldo_fisico

    enviar_para_autorizacao(ator_id=solicitante.pk, requisicao_id=rascunho.pk)

    saldo_depois = SaldoEstoque.objects.get(material=material_disponivel)
    assert saldo_depois.saldo_reservado == reservado_antes
    assert saldo_depois.saldo_fisico == fisico_antes


# ---------------------------------------------------------------------------
# TR-003 / TR-004 / TR-012 / TR-013 / TR-014: cancelamento e descarte
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_descartar_rascunho_nunca_enviado_remove_requisicao_e_nao_consumo_numero(
    solicitante, material_disponivel
):
    from apps.requisicoes.models import SequenciaRequisicao, TimelineRequisicao

    req = criar_requisicao(
        ator_id=solicitante.pk,
        beneficiario_id=solicitante.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('2'),
            }
        ],
    )

    descartar_rascunho(ator_id=solicitante.pk, requisicao_id=req.pk)

    assert not Requisicao.objects.filter(pk=req.pk).exists()
    assert not ItemRequisicao.objects.filter(requisicao_id=req.pk).exists()
    assert not TimelineRequisicao.objects.filter(requisicao_id=req.pk).exists()
    assert not SequenciaRequisicao.objects.exists()


@pytest.mark.django_db
def test_cancelar_rascunho_numerado_preserva_numero_publico_e_registra_timeline(
    solicitante, setor_obras, material_disponivel
):
    req = Requisicao.objects.create(
        estado=EstadoRequisicao.RASCUNHO,
        numero_publico='REQ-2026-000301',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    ItemRequisicao.objects.create(
        requisicao=req,
        material=material_disponivel,
        quantidade_solicitada=Decimal('2'),
    )

    req = cancelar_requisicao(
        ator_id=solicitante.pk,
        requisicao_id=req.pk,
    )

    assert req.estado == EstadoRequisicao.CANCELADA
    assert req.numero_publico == 'REQ-2026-000301'
    evento = req.eventos.filter(evento=EventoTimeline.CANCELAMENTO).get()
    assert evento.ator_id == solicitante.pk
    assert evento.estado_resultante == EstadoRequisicao.CANCELADA
    assert evento.justificativa == ''
    assert not req.eventos.filter(evento=EventoTimeline.LIBERACAO_RESERVA).exists()


@pytest.mark.django_db
def test_cancelar_requisicao_aguardando_autorizacao_sem_justificativa(
    requisicao_aguardando, solicitante, material_disponivel
):
    from apps.estoque.models import SaldoEstoque

    saldo_antes = SaldoEstoque.objects.get(material=material_disponivel)
    reservado_antes = saldo_antes.saldo_reservado
    fisico_antes = saldo_antes.saldo_fisico

    req = cancelar_requisicao(
        ator_id=solicitante.pk,
        requisicao_id=requisicao_aguardando.pk,
    )

    saldo_depois = SaldoEstoque.objects.get(material=material_disponivel)
    assert req.estado == EstadoRequisicao.CANCELADA
    assert req.numero_publico is not None
    assert saldo_depois.saldo_reservado == reservado_antes
    assert saldo_depois.saldo_fisico == fisico_antes
    evento = req.eventos.filter(evento=EventoTimeline.CANCELAMENTO).get()
    assert evento.justificativa == ''
    assert not req.eventos.filter(evento=EventoTimeline.LIBERACAO_RESERVA).exists()


@pytest.mark.django_db
def test_cancelar_requisicao_aguardando_autorizacao_ignora_justificativa(
    requisicao_aguardando, solicitante
):
    req = cancelar_requisicao(
        ator_id=solicitante.pk,
        requisicao_id=requisicao_aguardando.pk,
        justificativa='Cancelamento solicitado pelo usuário.',
    )

    assert req.estado == EstadoRequisicao.CANCELADA
    evento = req.eventos.filter(evento=EventoTimeline.CANCELAMENTO).get()
    assert evento.justificativa == ''
    assert not req.eventos.filter(evento=EventoTimeline.LIBERACAO_RESERVA).exists()


@pytest.mark.django_db
def test_cancelar_ou_descartar_requisicao_aguardando_autorizacao_ignora_justificativa(
    requisicao_aguardando, solicitante
):
    req = cancelar_ou_descartar_requisicao(
        ator_id=solicitante.pk,
        requisicao_id=requisicao_aguardando.pk,
        justificativa='Cancelamento solicitado pelo usuário.',
    )

    assert req is not None
    assert req.estado == EstadoRequisicao.CANCELADA
    evento = req.eventos.filter(evento=EventoTimeline.CANCELAMENTO).get()
    assert evento.justificativa == ''
    assert not req.eventos.filter(evento=EventoTimeline.LIBERACAO_RESERVA).exists()


@pytest.mark.django_db
def test_cancelar_requisicao_autorizada_libera_reserva_e_registra_timeline(
    requisicao_aguardando, chefe_obras, material_disponivel
):
    from apps.estoque.models import SaldoEstoque

    req = autorizar_requisicao(
        ator_id=chefe_obras.pk,
        requisicao_id=requisicao_aguardando.pk,
    )
    saldo_antes = SaldoEstoque.objects.get(material=material_disponivel)
    reservado_antes = saldo_antes.saldo_reservado
    fisico_antes = saldo_antes.saldo_fisico

    req = cancelar_requisicao(
        ator_id=requisicao_aguardando.criador_id,
        requisicao_id=req.pk,
        justificativa='Revisão interna do pedido.',
    )

    saldo_depois = SaldoEstoque.objects.get(material=material_disponivel)
    assert req.estado == EstadoRequisicao.CANCELADA
    assert saldo_depois.saldo_reservado == reservado_antes - Decimal('2')
    assert saldo_depois.saldo_fisico == fisico_antes
    cancelamento = req.eventos.filter(evento=EventoTimeline.CANCELAMENTO).get()
    assert cancelamento.justificativa == 'Revisão interna do pedido.'
    assert cancelamento.estado_resultante == EstadoRequisicao.CANCELADA
    assert cancelamento.metadata == {'liberou_reserva': True}
    assert not req.eventos.filter(evento=EventoTimeline.LIBERACAO_RESERVA).exists()


@pytest.mark.django_db
def test_cancelar_requisicao_pronta_para_retirada_libera_reserva_sem_baixa_fisica(
    requisicao_aguardando, chefe_obras, aux_almoxarifado, material_disponivel
):
    from apps.estoque.models import SaldoEstoque

    req = autorizar_requisicao(
        ator_id=chefe_obras.pk,
        requisicao_id=requisicao_aguardando.pk,
    )
    req = separar_para_retirada(
        ator_id=aux_almoxarifado.pk,
        requisicao_id=req.pk,
    )
    item = req.itens.get()
    saldo_antes = SaldoEstoque.objects.get(material=material_disponivel)
    reservado_antes = saldo_antes.saldo_reservado
    fisico_antes = saldo_antes.saldo_fisico

    req = cancelar_requisicao(
        ator_id=req.criador_id,
        requisicao_id=req.pk,
        justificativa='Cancelamento antes da retirada.',
    )

    saldo_depois = SaldoEstoque.objects.get(material=material_disponivel)
    assert req.estado == EstadoRequisicao.CANCELADA
    assert saldo_depois.saldo_reservado == (
        reservado_antes - item.quantidade_autorizada
    )
    assert saldo_depois.saldo_fisico == fisico_antes
    cancelamento = req.eventos.filter(evento=EventoTimeline.CANCELAMENTO).get()
    assert cancelamento.justificativa == 'Cancelamento antes da retirada.'
    assert cancelamento.estado_resultante == EstadoRequisicao.CANCELADA
    assert cancelamento.metadata == {'liberou_reserva': True}
    assert not req.eventos.filter(evento=EventoTimeline.LIBERACAO_RESERVA).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    'quantidade_reservada',
    [Decimal('NaN'), Decimal('Infinity'), Decimal('-Infinity')],
)
def test_liberar_reservas_para_cancelamento_rejeita_quantidade_nao_finita(
    material_disponivel, quantidade_reservada, chefe_almoxarifado
):
    from apps.estoque.models import SaldoEstoque
    from apps.estoque.services import OrigemMovimentacaoEstoque

    saldo_antes = SaldoEstoque.objects.get(material=material_disponivel)
    reservado_antes = saldo_antes.saldo_reservado
    fisico_antes = saldo_antes.saldo_fisico

    with pytest.raises(DadosInvalidos) as excinfo:
        liberar_reservas_para_cancelamento(
            itens=[
                {
                    'material_id': material_disponivel.pk,
                    'quantidade_reservada': quantidade_reservada,
                }
            ],
            ator_id=chefe_almoxarifado.pk,
            origem=OrigemMovimentacaoEstoque(requisicao_id=999),
        )

    saldo_antes.refresh_from_db()
    assert excinfo.value.code == 'quantidade_reservada_invalida'
    assert saldo_antes.saldo_reservado == reservado_antes
    assert saldo_antes.saldo_fisico == fisico_antes


@pytest.mark.django_db
def test_descartar_rascunho_permissao_negada_nao_altera_estado_ou_estoque(
    usuario_ti, solicitante, material_disponivel
):
    from apps.estoque.models import SaldoEstoque
    from apps.requisicoes.models import SequenciaRequisicao, TimelineRequisicao

    req = criar_requisicao(
        ator_id=solicitante.pk,
        beneficiario_id=solicitante.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('2'),
            }
        ],
    )
    saldo_antes = SaldoEstoque.objects.get(material=material_disponivel)
    timeline_antes = TimelineRequisicao.objects.filter(requisicao=req).count()

    with pytest.raises(PermissaoNegada):
        descartar_rascunho(ator_id=usuario_ti.pk, requisicao_id=req.pk)

    req.refresh_from_db()
    saldo_depois = SaldoEstoque.objects.get(material=material_disponivel)
    assert req.estado == EstadoRequisicao.RASCUNHO
    assert TimelineRequisicao.objects.filter(requisicao=req).count() == timeline_antes
    assert saldo_depois.saldo_reservado == saldo_antes.saldo_reservado
    assert saldo_depois.saldo_fisico == saldo_antes.saldo_fisico
    assert not SequenciaRequisicao.objects.exists()


@pytest.mark.django_db
def test_cancelar_requisicao_permissao_negada_nao_altera_estado_ou_estoque(
    usuario_ti, chefe_obras, requisicao_aguardando, material_disponivel
):
    from apps.estoque.models import SaldoEstoque

    req = autorizar_requisicao(
        ator_id=chefe_obras.pk,
        requisicao_id=requisicao_aguardando.pk,
    )
    saldo_antes = SaldoEstoque.objects.get(material=material_disponivel)
    timeline_antes = req.eventos.count()

    with pytest.raises(PermissaoNegada):
        cancelar_requisicao(
            ator_id=usuario_ti.pk,
            requisicao_id=req.pk,
            justificativa='Revisão do pedido.',
        )

    req.refresh_from_db()
    saldo_depois = SaldoEstoque.objects.get(material=material_disponivel)
    assert req.estado == EstadoRequisicao.AUTORIZADA
    assert req.numero_publico is not None
    assert req.eventos.count() == timeline_antes
    assert saldo_depois.saldo_reservado == saldo_antes.saldo_reservado
    assert saldo_depois.saldo_fisico == saldo_antes.saldo_fisico


@pytest.mark.django_db
def test_cancelar_requisicao_estado_invalido_nao_altera_ou_cria_timeline(
    solicitante, material_disponivel
):
    from apps.estoque.models import SaldoEstoque
    from apps.requisicoes.models import TimelineRequisicao

    req = Requisicao.objects.create(
        estado=EstadoRequisicao.CANCELADA,
        numero_publico='REQ-2026-000302',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=solicitante.setor,
    )
    ItemRequisicao.objects.create(
        requisicao=req,
        material=material_disponivel,
        quantidade_solicitada=Decimal('2'),
    )
    saldo_antes = SaldoEstoque.objects.get(material=material_disponivel)
    timeline_antes = TimelineRequisicao.objects.filter(requisicao=req).count()

    with pytest.raises(EstadoInvalido):
        cancelar_requisicao(
            ator_id=solicitante.pk,
            requisicao_id=req.pk,
            justificativa='Não aplica.',
        )

    req.refresh_from_db()
    saldo_depois = SaldoEstoque.objects.get(material=material_disponivel)
    assert req.estado == EstadoRequisicao.CANCELADA
    assert TimelineRequisicao.objects.filter(requisicao=req).count() == timeline_antes
    assert saldo_depois.saldo_reservado == saldo_antes.saldo_reservado
    assert saldo_depois.saldo_fisico == saldo_antes.saldo_fisico


@pytest.mark.django_db
def test_cancelar_requisicao_sem_justificativa_obrigatoria_nao_altera_estado_ou_estoque(
    solicitante, chefe_obras, requisicao_aguardando, material_disponivel
):
    from apps.estoque.models import SaldoEstoque
    from apps.requisicoes.models import TimelineRequisicao

    req = autorizar_requisicao(
        ator_id=chefe_obras.pk,
        requisicao_id=requisicao_aguardando.pk,
    )
    saldo_antes = SaldoEstoque.objects.get(material=material_disponivel)
    timeline_antes = TimelineRequisicao.objects.filter(requisicao=req).count()

    with pytest.raises(DadosInvalidos) as excinfo:
        cancelar_requisicao(
            ator_id=solicitante.pk,
            requisicao_id=req.pk,
            justificativa='',
        )

    assert excinfo.value.code == 'justificativa_cancelamento_obrigatoria'
    req.refresh_from_db()
    saldo_depois = SaldoEstoque.objects.get(material=material_disponivel)
    assert req.estado == EstadoRequisicao.AUTORIZADA
    assert req.numero_publico is not None
    assert TimelineRequisicao.objects.filter(requisicao=req).count() == timeline_antes
    assert saldo_depois.saldo_reservado == saldo_antes.saldo_reservado
    assert saldo_depois.saldo_fisico == saldo_antes.saldo_fisico


# ---------------------------------------------------------------------------
# TR-006 / TR-011: retorno para rascunho e recusa
# ---------------------------------------------------------------------------


@pytest.fixture
def requisicao_aguardando(solicitante, material_disponivel):
    from apps.requisicoes.services import enviar_para_autorizacao

    req = criar_requisicao(
        ator_id=solicitante.pk,
        beneficiario_id=solicitante.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('2'),
            }
        ],
    )
    return enviar_para_autorizacao(ator_id=solicitante.pk, requisicao_id=req.pk)


@pytest.mark.django_db
def test_retornar_para_rascunho_preserva_numero_publico_e_registra_timeline(
    requisicao_aguardando, solicitante
):
    numero_original = requisicao_aguardando.numero_publico

    req = retornar_para_rascunho(
        ator_id=solicitante.pk,
        requisicao_id=requisicao_aguardando.pk,
        observacao='Corrigir quantidade.',
    )

    assert req.estado == EstadoRequisicao.RASCUNHO
    assert req.numero_publico == numero_original
    evento = req.eventos.filter(evento=EventoTimeline.RETORNO_RASCUNHO).get()
    assert evento.ator_id == solicitante.pk
    assert evento.estado_resultante == EstadoRequisicao.RASCUNHO
    assert evento.justificativa == 'Corrigir quantidade.'


@pytest.mark.django_db
def test_retornar_para_rascunho_restaura_visibilidade_creator_only(
    aux_obras, solicitante, material_disponivel
):
    from apps.requisicoes.selectors import requisicoes_visiveis_para
    from apps.requisicoes.services import enviar_para_autorizacao

    req = criar_requisicao(
        ator_id=aux_obras.pk,
        beneficiario_id=solicitante.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('2'),
            }
        ],
    )
    req = enviar_para_autorizacao(ator_id=aux_obras.pk, requisicao_id=req.pk)

    retornar_para_rascunho(ator_id=solicitante.pk, requisicao_id=req.pk)

    assert req not in list(requisicoes_visiveis_para(solicitante.pk))
    assert req in list(requisicoes_visiveis_para(aux_obras.pk))


@pytest.mark.django_db
def test_retornar_para_rascunho_estado_invalido(solicitante, material_disponivel):
    req = criar_requisicao(
        ator_id=solicitante.pk,
        beneficiario_id=solicitante.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('2'),
            }
        ],
    )

    with pytest.raises(EstadoInvalido):
        retornar_para_rascunho(ator_id=solicitante.pk, requisicao_id=req.pk)


@pytest.mark.django_db
def test_retornar_para_rascunho_terceiro_sem_permissao(
    requisicao_aguardando, usuario_ti
):
    with pytest.raises(PermissaoNegada):
        retornar_para_rascunho(
            ator_id=usuario_ti.pk,
            requisicao_id=requisicao_aguardando.pk,
        )


@pytest.mark.django_db
def test_recusar_requisicao_aplica_estado_e_registra_timeline(
    requisicao_aguardando, chefe_obras
):
    req = recusar_requisicao(
        ator_id=chefe_obras.pk,
        requisicao_id=requisicao_aguardando.pk,
        motivo='Material solicitado precisa de revisão.',
    )

    assert req.estado == EstadoRequisicao.RECUSADA
    evento = req.eventos.filter(evento=EventoTimeline.RECUSA).get()
    assert evento.ator_id == chefe_obras.pk
    assert evento.estado_resultante == EstadoRequisicao.RECUSADA
    assert evento.justificativa == 'Material solicitado precisa de revisão.'


@pytest.mark.django_db
def test_recusar_requisicao_exige_motivo(requisicao_aguardando, chefe_obras):
    with pytest.raises(DadosInvalidos, match='motivo'):
        recusar_requisicao(
            ator_id=chefe_obras.pk,
            requisicao_id=requisicao_aguardando.pk,
            motivo='  ',
        )
    requisicao_aguardando.refresh_from_db()
    assert requisicao_aguardando.estado == EstadoRequisicao.AGUARDANDO_AUTORIZACAO


@pytest.mark.django_db
def test_recusar_requisicao_estado_invalido(requisicao_aguardando, chefe_obras):
    retornar_para_rascunho(
        ator_id=requisicao_aguardando.criador_id,
        requisicao_id=requisicao_aguardando.pk,
    )

    with pytest.raises(EstadoInvalido):
        recusar_requisicao(
            ator_id=chefe_obras.pk,
            requisicao_id=requisicao_aguardando.pk,
            motivo='Não aprovado.',
        )


@pytest.mark.django_db
def test_recusar_requisicao_outro_setor_sem_permissao(
    requisicao_aguardando, chefe_almoxarifado
):
    with pytest.raises(PermissaoNegada):
        recusar_requisicao(
            ator_id=chefe_almoxarifado.pk,
            requisicao_id=requisicao_aguardando.pk,
            motivo='Não aprovado.',
        )


@pytest.mark.django_db
def test_recusar_requisicao_nao_altera_estoque(
    requisicao_aguardando, chefe_obras, material_disponivel
):
    from apps.estoque.models import SaldoEstoque

    saldo_antes = SaldoEstoque.objects.get(material=material_disponivel)
    reservado_antes = saldo_antes.saldo_reservado
    fisico_antes = saldo_antes.saldo_fisico

    recusar_requisicao(
        ator_id=chefe_obras.pk,
        requisicao_id=requisicao_aguardando.pk,
        motivo='Não aprovado.',
    )

    saldo_depois = SaldoEstoque.objects.get(material=material_disponivel)
    assert saldo_depois.saldo_reservado == reservado_antes
    assert saldo_depois.saldo_fisico == fisico_antes


# ---------------------------------------------------------------------------
# TR-008: autorizar_requisicao — reserva integral
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_autorizar_requisicao_aplica_estado_reserva_e_registra_timeline(
    requisicao_aguardando, chefe_obras, material_disponivel
):
    from apps.estoque.models import SaldoEstoque

    saldo_antes = SaldoEstoque.objects.get(material=material_disponivel)
    reservado_antes = saldo_antes.saldo_reservado
    fisico_antes = saldo_antes.saldo_fisico

    req = autorizar_requisicao(
        ator_id=chefe_obras.pk,
        requisicao_id=requisicao_aguardando.pk,
    )

    req.refresh_from_db()
    item = req.itens.get()
    saldo_depois = SaldoEstoque.objects.get(material=material_disponivel)
    evento = req.eventos.filter(evento=EventoTimeline.AUTORIZACAO_TOTAL).get()

    assert req.estado == EstadoRequisicao.AUTORIZADA
    assert item.quantidade_autorizada == item.quantidade_solicitada
    assert saldo_depois.saldo_reservado == reservado_antes + item.quantidade_solicitada
    assert saldo_depois.saldo_fisico == fisico_antes
    assert evento.evento == EventoTimeline.AUTORIZACAO_TOTAL
    assert evento.ator_id == chefe_obras.pk
    assert evento.estado_resultante == EstadoRequisicao.AUTORIZADA
    assert evento.metadata == {}
    assert req.pk == requisicao_aguardando.pk


@pytest.mark.django_db
def test_autorizar_requisicao_auto_autorizacao_registra_metadata(
    chefe_obras, material_disponivel
):
    req = criar_requisicao(
        ator_id=chefe_obras.pk,
        beneficiario_id=chefe_obras.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('2'),
            }
        ],
    )
    from apps.requisicoes.services import enviar_para_autorizacao

    req = enviar_para_autorizacao(ator_id=chefe_obras.pk, requisicao_id=req.pk)
    req = autorizar_requisicao(ator_id=chefe_obras.pk, requisicao_id=req.pk)

    evento = req.eventos.filter(evento=EventoTimeline.AUTORIZACAO_TOTAL).get()

    assert req.estado == EstadoRequisicao.AUTORIZADA
    assert req.beneficiario_id == chefe_obras.pk
    assert evento.metadata == {'auto_autorizacao': True}


@pytest.mark.django_db
def test_autorizar_requisicao_permissao_negada(
    requisicao_aguardando, chefe_almoxarifado
):
    with pytest.raises(PermissaoNegada):
        autorizar_requisicao(
            ator_id=chefe_almoxarifado.pk,
            requisicao_id=requisicao_aguardando.pk,
        )


@pytest.mark.django_db
def test_autorizar_requisicao_estado_invalido(chefe_obras, material_disponivel):
    req = criar_requisicao(
        ator_id=chefe_obras.pk,
        beneficiario_id=chefe_obras.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('2'),
            }
        ],
    )

    with pytest.raises(EstadoInvalido):
        autorizar_requisicao(ator_id=chefe_obras.pk, requisicao_id=req.pk)


@pytest.mark.django_db
@pytest.mark.parametrize('modo', ['inativo', 'divergente', 'insuficiente'])
def test_autorizar_requisicao_bloqueia_estoque_sem_efeitos_parciais(
    requisicao_aguardando, chefe_obras, material_disponivel, modo
):
    from apps.estoque.models import SaldoEstoque

    saldo = SaldoEstoque.objects.get(material=material_disponivel)
    if modo == 'inativo':
        material_disponivel.ativo = False
        material_disponivel.save(update_fields=['ativo'])
    elif modo == 'divergente':
        saldo.saldo_fisico = Decimal('1')
        saldo.saldo_reservado = Decimal('2')
        saldo.save(update_fields=['saldo_fisico', 'saldo_reservado'])
    else:
        saldo.saldo_fisico = saldo.saldo_reservado + Decimal('1')
        saldo.save(update_fields=['saldo_fisico'])

    reservado_antes = saldo.saldo_reservado
    fisico_antes = saldo.saldo_fisico

    with pytest.raises(ConflitoDominio):
        autorizar_requisicao(
            ator_id=chefe_obras.pk,
            requisicao_id=requisicao_aguardando.pk,
        )

    requisicao_aguardando.refresh_from_db()
    item = requisicao_aguardando.itens.get()
    saldo.refresh_from_db()

    assert requisicao_aguardando.estado == EstadoRequisicao.AGUARDANDO_AUTORIZACAO
    assert item.quantidade_autorizada is None
    assert not requisicao_aguardando.eventos.filter(
        evento=EventoTimeline.AUTORIZACAO_TOTAL
    ).exists()
    assert saldo.saldo_reservado == reservado_antes
    assert saldo.saldo_fisico == fisico_antes


@pytest.mark.django_db
def test_autorizar_requisicao_bloqueia_multiplos_itens_sem_efeitos_parciais(
    chefe_obras, material_disponivel, material_disponivel_2
):
    from apps.estoque.models import SaldoEstoque
    from apps.requisicoes.services import enviar_para_autorizacao

    req = criar_requisicao(
        ator_id=chefe_obras.pk,
        beneficiario_id=chefe_obras.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('2'),
            },
            {
                'material_id': material_disponivel_2.pk,
                'quantidade_solicitada': Decimal('3'),
            },
        ],
    )
    req = enviar_para_autorizacao(ator_id=chefe_obras.pk, requisicao_id=req.pk)

    saldo_disponivel = SaldoEstoque.objects.get(material=material_disponivel)
    saldo_insuficiente = SaldoEstoque.objects.get(material=material_disponivel_2)
    saldo_disponivel_antes = (
        saldo_disponivel.saldo_fisico,
        saldo_disponivel.saldo_reservado,
    )

    saldo_insuficiente.saldo_fisico = saldo_insuficiente.saldo_reservado + Decimal('1')
    saldo_insuficiente.save(update_fields=['saldo_fisico'])
    saldo_insuficiente.refresh_from_db()
    saldo_insuficiente_antes = (
        saldo_insuficiente.saldo_fisico,
        saldo_insuficiente.saldo_reservado,
    )

    with pytest.raises(ConflitoDominio):
        autorizar_requisicao(ator_id=chefe_obras.pk, requisicao_id=req.pk)

    req.refresh_from_db()
    itens = list(req.itens.order_by('id'))
    saldo_disponivel.refresh_from_db()
    saldo_insuficiente.refresh_from_db()

    assert req.estado == EstadoRequisicao.AGUARDANDO_AUTORIZACAO
    assert all(item.quantidade_autorizada is None for item in itens)
    assert not req.eventos.filter(evento=EventoTimeline.AUTORIZACAO_TOTAL).exists()
    assert (
        saldo_disponivel.saldo_fisico,
        saldo_disponivel.saldo_reservado,
    ) == saldo_disponivel_antes
    assert (
        saldo_insuficiente.saldo_fisico,
        saldo_insuficiente.saldo_reservado,
    ) == saldo_insuficiente_antes


@pytest.mark.django_db
def test_reservar_saldos_para_autorizacao_acumula_itens_do_mesmo_material(
    material_disponivel, chefe_almoxarifado, solicitante, setor_obras
):
    from apps.estoque.models import SaldoEstoque
    from apps.estoque.services import OrigemMovimentacaoEstoque
    from apps.requisicoes.models import EstadoRequisicao, Requisicao

    req = Requisicao.objects.create(
        estado=EstadoRequisicao.AGUARDANDO_AUTORIZACAO,
        numero_publico='REQ-2025-TEST01',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )

    saldo = SaldoEstoque.objects.get(material=material_disponivel)
    reservado_antes = saldo.saldo_reservado
    fisico_antes = saldo.saldo_fisico

    reservar_saldos_para_autorizacao(
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('2'),
            },
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('3'),
            },
        ],
        ator_id=chefe_almoxarifado.pk,
        origem=OrigemMovimentacaoEstoque.de_requisicao(req),
    )

    saldo.refresh_from_db()

    assert saldo.saldo_reservado == reservado_antes + Decimal('5')
    assert saldo.saldo_fisico == fisico_antes


@pytest.mark.django_db
def test_reservar_saldos_para_autorizacao_rejeita_saldo_ambiguo(
    material_disponivel, estoque_principal, chefe_almoxarifado
):
    from apps.estoque.models import Estoque, SaldoEstoque
    from apps.estoque.services import OrigemMovimentacaoEstoque

    estoque_secundario = Estoque.objects.create(
        codigo='EST02',
        nome='Estoque Secundario',
    )
    saldo_principal = SaldoEstoque.objects.get(
        material=material_disponivel, estoque=estoque_principal
    )
    saldo_secundario = SaldoEstoque.objects.create(
        estoque=estoque_secundario,
        material=material_disponivel,
        saldo_fisico=20,
        saldo_reservado=0,
    )
    saldo_principal_antes = (
        saldo_principal.saldo_fisico,
        saldo_principal.saldo_reservado,
    )
    saldo_secundario_antes = (
        saldo_secundario.saldo_fisico,
        saldo_secundario.saldo_reservado,
    )

    with pytest.raises(ConflitoDominio):
        reservar_saldos_para_autorizacao(
            itens=[
                {
                    'material_id': material_disponivel.pk,
                    'quantidade_solicitada': Decimal('2'),
                }
            ],
            ator_id=chefe_almoxarifado.pk,
            origem=OrigemMovimentacaoEstoque(requisicao_id=999),
        )

    saldo_principal.refresh_from_db()
    saldo_secundario.refresh_from_db()

    assert (
        saldo_principal.saldo_fisico,
        saldo_principal.saldo_reservado,
    ) == saldo_principal_antes
    assert (
        saldo_secundario.saldo_fisico,
        saldo_secundario.saldo_reservado,
    ) == saldo_secundario_antes


# ---------------------------------------------------------------------------
# TR-009: separar_para_retirada — autorizada -> pronta_para_retirada
# ---------------------------------------------------------------------------


@pytest.fixture
def requisicao_autorizada(requisicao_aguardando, chefe_obras):
    return autorizar_requisicao(
        ator_id=chefe_obras.pk,
        requisicao_id=requisicao_aguardando.pk,
    )


@pytest.mark.django_db
def test_separar_para_retirada_aplica_estado_e_registra_timeline(
    requisicao_autorizada, aux_almoxarifado, material_disponivel
):
    from apps.estoque.models import SaldoEstoque

    saldo_antes = SaldoEstoque.objects.get(material=material_disponivel)
    reservado_antes = saldo_antes.saldo_reservado
    fisico_antes = saldo_antes.saldo_fisico

    req = separar_para_retirada(
        ator_id=aux_almoxarifado.pk,
        requisicao_id=requisicao_autorizada.pk,
    )

    req.refresh_from_db()
    saldo_depois = SaldoEstoque.objects.get(material=material_disponivel)
    evento = req.eventos.filter(evento=EventoTimeline.SEPARACAO_RETIRADA).get()

    assert req.estado == EstadoRequisicao.PRONTA_PARA_RETIRADA
    assert saldo_depois.saldo_reservado == reservado_antes
    assert saldo_depois.saldo_fisico == fisico_antes
    assert evento.ator_id == aux_almoxarifado.pk
    assert evento.estado_resultante == EstadoRequisicao.PRONTA_PARA_RETIRADA
    assert evento.metadata == {}


@pytest.mark.django_db
def test_separar_para_retirada_aceita_chefe_almox(
    requisicao_autorizada, chefe_almoxarifado
):
    req = separar_para_retirada(
        ator_id=chefe_almoxarifado.pk,
        requisicao_id=requisicao_autorizada.pk,
    )
    assert req.estado == EstadoRequisicao.PRONTA_PARA_RETIRADA


@pytest.mark.django_db
def test_separar_para_retirada_aceita_superuser(requisicao_autorizada, superuser):
    req = separar_para_retirada(
        ator_id=superuser.pk,
        requisicao_id=requisicao_autorizada.pk,
    )
    assert req.estado == EstadoRequisicao.PRONTA_PARA_RETIRADA


@pytest.mark.django_db
def test_separar_para_retirada_permissao_negada_chefe_setor(
    requisicao_autorizada, chefe_obras
):
    with pytest.raises(PermissaoNegada):
        separar_para_retirada(
            ator_id=chefe_obras.pk,
            requisicao_id=requisicao_autorizada.pk,
        )


@pytest.mark.django_db
def test_separar_para_retirada_permissao_negada_solicitante(
    requisicao_autorizada, solicitante
):
    with pytest.raises(PermissaoNegada):
        separar_para_retirada(
            ator_id=solicitante.pk,
            requisicao_id=requisicao_autorizada.pk,
        )


@pytest.mark.django_db
def test_separar_para_retirada_estado_invalido(requisicao_aguardando, aux_almoxarifado):
    with pytest.raises(EstadoInvalido):
        separar_para_retirada(
            ator_id=aux_almoxarifado.pk,
            requisicao_id=requisicao_aguardando.pk,
        )


@pytest.mark.django_db
def test_separar_para_retirada_sem_itens_autorizados(
    aux_almoxarifado, solicitante, setor_obras
):
    req = Requisicao.objects.create(
        estado=EstadoRequisicao.AUTORIZADA,
        numero_publico='REQ-2026-TST-001',
        criador=solicitante,
        beneficiario=solicitante,
        setor_beneficiario=setor_obras,
    )
    with pytest.raises(EstadoInvalido):
        separar_para_retirada(
            ator_id=aux_almoxarifado.pk,
            requisicao_id=req.pk,
        )


@pytest.mark.django_db
def test_separar_para_retirada_ator_inexistente(requisicao_autorizada):
    with pytest.raises(DadosInvalidos) as excinfo:
        separar_para_retirada(
            ator_id=999_999,
            requisicao_id=requisicao_autorizada.pk,
        )
    assert excinfo.value.code == 'ator_nao_encontrado'


@pytest.mark.django_db
def test_separar_para_retirada_requisicao_inexistente(aux_almoxarifado):
    with pytest.raises(DadosInvalidos) as excinfo:
        separar_para_retirada(
            ator_id=aux_almoxarifado.pk,
            requisicao_id=999_999,
        )
    assert excinfo.value.code == 'requisicao_nao_encontrada'


@pytest.mark.django_db
def test_separar_para_retirada_idempotencia_bloqueia_segunda_execucao(
    requisicao_autorizada, aux_almoxarifado
):
    """Após separar, repetir falha com EstadoInvalido (estado origem inválido)."""
    separar_para_retirada(
        ator_id=aux_almoxarifado.pk,
        requisicao_id=requisicao_autorizada.pk,
    )
    with pytest.raises(EstadoInvalido):
        separar_para_retirada(
            ator_id=aux_almoxarifado.pk,
            requisicao_id=requisicao_autorizada.pk,
        )


# ---------------------------------------------------------------------------
# TR-015B: separar_para_retirada — bloqueio por divergência/físico insuficiente
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_tr015b_bloqueia_por_divergencia_critica(
    requisicao_autorizada, aux_almoxarifado, material_disponivel
):
    """TR-015B: divergência crítica pós-autorização bloqueia separação sem efeitos colaterais."""
    from apps.estoque.models import SaldoEstoque

    saldo = SaldoEstoque.objects.get(material=material_disponivel)
    saldo.saldo_fisico = saldo.saldo_reservado - 1
    saldo.save(update_fields=['saldo_fisico'])

    fisico_antes = saldo.saldo_fisico
    reservado_antes = saldo.saldo_reservado
    timeline_count_antes = requisicao_autorizada.eventos.count()

    with pytest.raises(DadosInvalidos) as excinfo:
        separar_para_retirada(
            ator_id=aux_almoxarifado.pk,
            requisicao_id=requisicao_autorizada.pk,
        )
    assert excinfo.value.code == 'separacao_bloqueada'

    requisicao_autorizada.refresh_from_db()
    saldo.refresh_from_db()
    assert requisicao_autorizada.estado == EstadoRequisicao.AUTORIZADA
    assert saldo.saldo_fisico == fisico_antes
    assert saldo.saldo_reservado == reservado_antes
    assert requisicao_autorizada.eventos.count() == timeline_count_antes


@pytest.mark.django_db
def test_tr015b_bloqueia_quando_um_item_diverge_em_req_multi_item(
    aux_almoxarifado,
    solicitante,
    chefe_obras,
    material_disponivel,
    material_disponivel_2,
):
    """TR-015B: req com dois itens bloqueia quando um material tem divergência pós-auth."""
    from apps.estoque.models import SaldoEstoque
    from apps.requisicoes.services import enviar_para_autorizacao

    req = criar_requisicao(
        ator_id=solicitante.pk,
        beneficiario_id=solicitante.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('2'),
            },
            {
                'material_id': material_disponivel_2.pk,
                'quantidade_solicitada': Decimal('5'),
            },
        ],
    )
    req = enviar_para_autorizacao(ator_id=solicitante.pk, requisicao_id=req.pk)
    req = autorizar_requisicao(ator_id=chefe_obras.pk, requisicao_id=req.pk)

    saldo2 = SaldoEstoque.objects.get(material=material_disponivel_2)
    saldo2.saldo_fisico = saldo2.saldo_reservado - 1
    saldo2.save(update_fields=['saldo_fisico'])

    saldo1 = SaldoEstoque.objects.get(material=material_disponivel)
    fisico1_antes = saldo1.saldo_fisico
    reservado1_antes = saldo1.saldo_reservado
    fisico2_antes = saldo2.saldo_fisico
    reservado2_antes = saldo2.saldo_reservado
    timeline_count_antes = req.eventos.count()

    with pytest.raises(DadosInvalidos) as excinfo:
        separar_para_retirada(
            ator_id=aux_almoxarifado.pk,
            requisicao_id=req.pk,
        )
    assert excinfo.value.code == 'separacao_bloqueada'

    req.refresh_from_db()
    saldo1.refresh_from_db()
    saldo2.refresh_from_db()
    assert req.estado == EstadoRequisicao.AUTORIZADA
    assert saldo1.saldo_fisico == fisico1_antes
    assert saldo1.saldo_reservado == reservado1_antes
    assert saldo2.saldo_fisico == fisico2_antes
    assert saldo2.saldo_reservado == reservado2_antes
    assert req.eventos.count() == timeline_count_antes


# ---------------------------------------------------------------------------
# TR-016 / TR-017 / TR-018: registrar_atendimento
# ---------------------------------------------------------------------------


@pytest.fixture
def requisicao_pronta_retirada(requisicao_autorizada, aux_almoxarifado):
    return separar_para_retirada(
        ator_id=aux_almoxarifado.pk,
        requisicao_id=requisicao_autorizada.pk,
    )


@pytest.fixture
def requisicao_pronta_retirada_multi(
    solicitante,
    chefe_obras,
    aux_almoxarifado,
    material_disponivel,
    material_disponivel_2,
):
    from apps.requisicoes.services import enviar_para_autorizacao

    req = criar_requisicao(
        ator_id=solicitante.pk,
        beneficiario_id=solicitante.pk,
        itens=[
            {
                'material_id': material_disponivel.pk,
                'quantidade_solicitada': Decimal('2'),
            },
            {
                'material_id': material_disponivel_2.pk,
                'quantidade_solicitada': Decimal('3'),
            },
        ],
    )
    enviar_para_autorizacao(ator_id=solicitante.pk, requisicao_id=req.pk)
    autorizar_requisicao(ator_id=chefe_obras.pk, requisicao_id=req.pk)
    return separar_para_retirada(ator_id=aux_almoxarifado.pk, requisicao_id=req.pk)


def _payload_total(requisicao):
    return [
        {
            'item_id': item.id,
            'quantidade_entregue': item.quantidade_autorizada,
            'justificativa': '',
        }
        for item in requisicao.itens.filter(quantidade_autorizada__gt=0).order_by('id')
    ]


@pytest.mark.django_db
def test_registrar_atendimento_total_baixa_fisico_e_zera_reserva(
    requisicao_pronta_retirada, aux_almoxarifado, material_disponivel
):
    from apps.estoque.models import SaldoEstoque

    saldo_antes = SaldoEstoque.objects.get(material=material_disponivel)
    fisico_antes = saldo_antes.saldo_fisico
    reservado_antes = saldo_antes.saldo_reservado
    autorizada = requisicao_pronta_retirada.itens.first().quantidade_autorizada

    req = registrar_atendimento(
        ator_id=aux_almoxarifado.pk,
        requisicao_id=requisicao_pronta_retirada.pk,
        itens=_payload_total(requisicao_pronta_retirada),
        retirante_nome='Beneficiário',
    )

    req.refresh_from_db()
    saldo_depois = SaldoEstoque.objects.get(material=material_disponivel)
    assert req.estado == EstadoRequisicao.ATENDIDA
    assert saldo_depois.saldo_fisico == fisico_antes - autorizada
    assert saldo_depois.saldo_reservado == reservado_antes - autorizada
    item = req.itens.first()
    assert item.quantidade_entregue == autorizada
    evento = req.eventos.filter(evento=EventoTimeline.ATENDIMENTO_TOTAL).get()
    assert evento.ator_id == aux_almoxarifado.pk
    assert evento.metadata == {'retirante': 'Beneficiário'}
    assert not req.eventos.filter(evento=EventoTimeline.LIBERACAO_RESERVA).exists()


@pytest.mark.django_db
def test_registrar_atendimento_parcial_libera_reserva_e_registra_evento(
    requisicao_pronta_retirada, aux_almoxarifado, material_disponivel
):
    from apps.estoque.models import SaldoEstoque

    saldo_antes = SaldoEstoque.objects.get(material=material_disponivel)
    fisico_antes = saldo_antes.saldo_fisico
    reservado_antes = saldo_antes.saldo_reservado
    item_unico = requisicao_pronta_retirada.itens.first()
    autorizada = item_unico.quantidade_autorizada  # 2 (fixture)
    entregue = autorizada - Decimal('1')

    req = registrar_atendimento(
        ator_id=aux_almoxarifado.pk,
        requisicao_id=requisicao_pronta_retirada.pk,
        itens=[
            {
                'item_id': item_unico.id,
                'quantidade_entregue': entregue,
                'justificativa': 'Solicitante levou menos do que pediu.',
            }
        ],
        retirante_nome='Carlos',
        observacao='Retirada parcial.',
    )

    req.refresh_from_db()
    saldo_depois = SaldoEstoque.objects.get(material=material_disponivel)
    assert req.estado == EstadoRequisicao.ATENDIDA
    assert saldo_depois.saldo_fisico == fisico_antes - entregue
    assert saldo_depois.saldo_reservado == reservado_antes - autorizada
    item_unico.refresh_from_db()
    assert item_unico.quantidade_entregue == entregue
    assert item_unico.justificativa_entrega == 'Solicitante levou menos do que pediu.'
    parcial = req.eventos.filter(evento=EventoTimeline.ATENDIMENTO_PARCIAL).get()
    assert parcial.metadata == {
        'retirante': 'Carlos',
        'observacao': 'Retirada parcial.',
        'liberou_reserva': True,
    }
    assert not req.eventos.filter(evento=EventoTimeline.LIBERACAO_RESERVA).exists()


@pytest.mark.django_db
def test_registrar_atendimento_sem_entrega_bloqueia(
    requisicao_pronta_retirada, aux_almoxarifado
):
    item = requisicao_pronta_retirada.itens.first()
    with pytest.raises(EstadoInvalido) as excinfo:
        registrar_atendimento(
            ator_id=aux_almoxarifado.pk,
            requisicao_id=requisicao_pronta_retirada.pk,
            itens=[
                {
                    'item_id': item.id,
                    'quantidade_entregue': Decimal('0'),
                    'justificativa': 'Não compareceu',
                }
            ],
            retirante_nome='X',
        )
    assert excinfo.value.code == 'atendimento_sem_entrega'
    requisicao_pronta_retirada.refresh_from_db()
    assert requisicao_pronta_retirada.estado == EstadoRequisicao.PRONTA_PARA_RETIRADA


@pytest.mark.django_db
def test_registrar_atendimento_parcial_sem_justificativa_falha(
    requisicao_pronta_retirada, aux_almoxarifado
):
    item = requisicao_pronta_retirada.itens.first()
    with pytest.raises(DadosInvalidos) as excinfo:
        registrar_atendimento(
            ator_id=aux_almoxarifado.pk,
            requisicao_id=requisicao_pronta_retirada.pk,
            itens=[
                {
                    'item_id': item.id,
                    'quantidade_entregue': item.quantidade_autorizada - Decimal('1'),
                    'justificativa': '',
                }
            ],
            retirante_nome='X',
        )
    assert excinfo.value.code == 'justificativa_obrigatoria'


@pytest.mark.django_db
def test_registrar_atendimento_entregue_acima_da_autorizada_falha(
    requisicao_pronta_retirada, aux_almoxarifado
):
    item = requisicao_pronta_retirada.itens.first()
    with pytest.raises(DadosInvalidos) as excinfo:
        registrar_atendimento(
            ator_id=aux_almoxarifado.pk,
            requisicao_id=requisicao_pronta_retirada.pk,
            itens=[
                {
                    'item_id': item.id,
                    'quantidade_entregue': item.quantidade_autorizada + Decimal('1'),
                    'justificativa': '',
                }
            ],
            retirante_nome='X',
        )
    assert excinfo.value.code == 'quantidade_entregue_invalida'


@pytest.mark.django_db
def test_registrar_atendimento_estado_origem_invalido(
    requisicao_autorizada, aux_almoxarifado
):
    item = requisicao_autorizada.itens.first()
    with pytest.raises(EstadoInvalido) as excinfo:
        registrar_atendimento(
            ator_id=aux_almoxarifado.pk,
            requisicao_id=requisicao_autorizada.pk,
            itens=[
                {
                    'item_id': item.id,
                    'quantidade_entregue': item.quantidade_autorizada,
                    'justificativa': '',
                }
            ],
            retirante_nome='X',
        )
    assert excinfo.value.code == 'estado_origem_invalido'


@pytest.mark.django_db
def test_registrar_atendimento_permissao_negada_solicitante(
    requisicao_pronta_retirada, solicitante
):
    with pytest.raises(PermissaoNegada):
        registrar_atendimento(
            ator_id=solicitante.pk,
            requisicao_id=requisicao_pronta_retirada.pk,
            itens=_payload_total(requisicao_pronta_retirada),
            retirante_nome='X',
        )


@pytest.mark.django_db
def test_registrar_atendimento_aceita_chefe_almox(
    requisicao_pronta_retirada, chefe_almoxarifado
):
    req = registrar_atendimento(
        ator_id=chefe_almoxarifado.pk,
        requisicao_id=requisicao_pronta_retirada.pk,
        itens=_payload_total(requisicao_pronta_retirada),
        retirante_nome='X',
    )
    assert req.estado == EstadoRequisicao.ATENDIDA


@pytest.mark.django_db
def test_registrar_atendimento_aceita_superuser(requisicao_pronta_retirada, superuser):
    req = registrar_atendimento(
        ator_id=superuser.pk,
        requisicao_id=requisicao_pronta_retirada.pk,
        itens=_payload_total(requisicao_pronta_retirada),
        retirante_nome='X',
    )
    assert req.estado == EstadoRequisicao.ATENDIDA


@pytest.mark.django_db
def test_registrar_atendimento_retirante_obrigatorio(
    requisicao_pronta_retirada, aux_almoxarifado
):
    with pytest.raises(DadosInvalidos) as excinfo:
        registrar_atendimento(
            ator_id=aux_almoxarifado.pk,
            requisicao_id=requisicao_pronta_retirada.pk,
            itens=_payload_total(requisicao_pronta_retirada),
            retirante_nome='   ',
        )
    assert excinfo.value.code == 'retirante_obrigatorio'


@pytest.mark.django_db
def test_registrar_atendimento_payload_incompleto(
    requisicao_pronta_retirada, aux_almoxarifado
):
    with pytest.raises(DadosInvalidos) as excinfo:
        registrar_atendimento(
            ator_id=aux_almoxarifado.pk,
            requisicao_id=requisicao_pronta_retirada.pk,
            itens=[],
            retirante_nome='X',
        )
    assert excinfo.value.code == 'itens_atendimento_incompletos'


@pytest.mark.django_db
def test_registrar_atendimento_idempotencia_bloqueia_segunda_execucao(
    requisicao_pronta_retirada, aux_almoxarifado
):
    registrar_atendimento(
        ator_id=aux_almoxarifado.pk,
        requisicao_id=requisicao_pronta_retirada.pk,
        itens=_payload_total(requisicao_pronta_retirada),
        retirante_nome='X',
    )
    with pytest.raises(EstadoInvalido):
        registrar_atendimento(
            ator_id=aux_almoxarifado.pk,
            requisicao_id=requisicao_pronta_retirada.pk,
            itens=_payload_total(requisicao_pronta_retirada),
            retirante_nome='X',
        )


@pytest.mark.django_db
def test_registrar_atendimento_ator_inexistente(requisicao_pronta_retirada):
    with pytest.raises(DadosInvalidos) as excinfo:
        registrar_atendimento(
            ator_id=999_999,
            requisicao_id=requisicao_pronta_retirada.pk,
            itens=_payload_total(requisicao_pronta_retirada),
            retirante_nome='X',
        )
    assert excinfo.value.code == 'ator_nao_encontrado'


@pytest.mark.django_db
def test_registrar_atendimento_item_zero_sem_justificativa_falha_no_parcial_multi_item(
    requisicao_pronta_retirada_multi, aux_almoxarifado
):
    itens = list(requisicao_pronta_retirada_multi.itens.order_by('id'))
    primeiro, segundo = itens[0], itens[1]
    with pytest.raises(DadosInvalidos) as excinfo:
        registrar_atendimento(
            ator_id=aux_almoxarifado.pk,
            requisicao_id=requisicao_pronta_retirada_multi.pk,
            itens=[
                {
                    'item_id': primeiro.id,
                    'quantidade_entregue': primeiro.quantidade_autorizada,
                    'justificativa': '',
                },
                {
                    'item_id': segundo.id,
                    'quantidade_entregue': Decimal('0'),
                    'justificativa': '',
                },
            ],
            retirante_nome='Carlos',
        )
    assert excinfo.value.code == 'justificativa_obrigatoria'


@pytest.mark.django_db
def test_registrar_atendimento_rejeita_nan_em_quantidade_entregue(
    requisicao_pronta_retirada, aux_almoxarifado
):
    item = requisicao_pronta_retirada.itens.first()
    with pytest.raises(DadosInvalidos) as excinfo:
        registrar_atendimento(
            ator_id=aux_almoxarifado.pk,
            requisicao_id=requisicao_pronta_retirada.pk,
            itens=[
                {
                    'item_id': item.id,
                    'quantidade_entregue': Decimal('NaN'),
                    'justificativa': '',
                }
            ],
            retirante_nome='X',
        )
    assert excinfo.value.code == 'quantidade_entregue_invalida'


@pytest.mark.django_db
def test_registrar_atendimento_total_zera_justificativa_existente(
    requisicao_pronta_retirada, aux_almoxarifado
):
    """Atendimento total sobrescreve justificativa eventual com string vazia."""
    item = requisicao_pronta_retirada.itens.first()
    item.justificativa_entrega = 'antiga'
    item.save(update_fields=['justificativa_entrega'])

    registrar_atendimento(
        ator_id=aux_almoxarifado.pk,
        requisicao_id=requisicao_pronta_retirada.pk,
        itens=[
            {
                'item_id': item.id,
                'quantidade_entregue': item.quantidade_autorizada,
                'justificativa': 'ignorada por ser total',
            }
        ],
        retirante_nome='Carlos',
    )

    item.refresh_from_db()
    assert item.justificativa_entrega == ''


@pytest.mark.django_db
def test_registrar_atendimento_bloqueia_material_inativo(
    requisicao_pronta_retirada, aux_almoxarifado, material_disponivel
):
    """Material desativado entre autorização e atendimento bloqueia retirada."""
    material_disponivel.ativo = False
    material_disponivel.save(update_fields=['ativo'])

    with pytest.raises(ConflitoDominio) as excinfo:
        registrar_atendimento(
            ator_id=aux_almoxarifado.pk,
            requisicao_id=requisicao_pronta_retirada.pk,
            itens=_payload_total(requisicao_pronta_retirada),
            retirante_nome='Carlos',
        )
    assert excinfo.value.code == 'material_inativo'
    requisicao_pronta_retirada.refresh_from_db()
    assert requisicao_pronta_retirada.estado == EstadoRequisicao.PRONTA_PARA_RETIRADA


@pytest.mark.django_db
def test_registrar_atendimento_requisicao_inexistente(aux_almoxarifado):
    with pytest.raises(DadosInvalidos) as excinfo:
        registrar_atendimento(
            ator_id=aux_almoxarifado.pk,
            requisicao_id=999_999,
            itens=[],
            retirante_nome='X',
        )
    assert excinfo.value.code == 'requisicao_nao_encontrada'


# ---------------------------------------------------------------------------
# REQ-09 / TR-001 variant: copiar_requisicao
# ---------------------------------------------------------------------------


@pytest.fixture
def requisicao_recusada(requisicao_aguardando, chefe_obras):
    return recusar_requisicao(
        ator_id=chefe_obras.pk,
        requisicao_id=requisicao_aguardando.pk,
        motivo='Orçamento insuficiente.',
    )


@pytest.fixture
def requisicao_atendida(requisicao_pronta_retirada, aux_almoxarifado):
    item = requisicao_pronta_retirada.itens.first()
    return registrar_atendimento(
        ator_id=aux_almoxarifado.pk,
        requisicao_id=requisicao_pronta_retirada.pk,
        itens=[
            {
                'item_id': item.pk,
                'quantidade_entregue': item.quantidade_autorizada,
                'justificativa': '',
            }
        ],
        retirante_nome='Carlos',
    )


@pytest.mark.django_db
def test_copiar_requisicao_recusada_cria_rascunho(requisicao_recusada, solicitante):
    from apps.requisicoes.services import copiar_requisicao

    novo = copiar_requisicao(
        ator_id=solicitante.pk,
        requisicao_id=requisicao_recusada.pk,
    )

    assert novo.pk is not None
    assert novo.estado == EstadoRequisicao.RASCUNHO
    assert novo.numero_publico is None


@pytest.mark.django_db
def test_copiar_requisicao_atendida_cria_rascunho(requisicao_atendida, solicitante):
    from apps.requisicoes.services import copiar_requisicao

    novo = copiar_requisicao(
        ator_id=solicitante.pk,
        requisicao_id=requisicao_atendida.pk,
    )

    assert novo.estado == EstadoRequisicao.RASCUNHO


@pytest.mark.django_db
def test_copiar_requisicao_preserva_itens_solicitados(requisicao_recusada, solicitante):
    from apps.requisicoes.services import copiar_requisicao

    novo = copiar_requisicao(
        ator_id=solicitante.pk,
        requisicao_id=requisicao_recusada.pk,
    )

    itens_origem = list(
        requisicao_recusada.itens.values_list('material_id', 'quantidade_solicitada')
    )
    itens_novo = list(novo.itens.values_list('material_id', 'quantidade_solicitada'))
    assert itens_novo == itens_origem


@pytest.mark.django_db
def test_copiar_requisicao_nao_copia_autorizada_entregue(
    requisicao_atendida, solicitante
):
    from apps.requisicoes.services import copiar_requisicao

    novo = copiar_requisicao(
        ator_id=solicitante.pk,
        requisicao_id=requisicao_atendida.pk,
    )

    for item in novo.itens.all():
        assert item.quantidade_autorizada is None
        assert item.quantidade_entregue is None


@pytest.mark.django_db
def test_copiar_requisicao_registra_timeline_criacao(requisicao_recusada, solicitante):
    from apps.requisicoes.services import copiar_requisicao

    novo = copiar_requisicao(
        ator_id=solicitante.pk,
        requisicao_id=requisicao_recusada.pk,
    )

    assert novo.eventos.filter(evento=EventoTimeline.CRIACAO).exists()


@pytest.mark.django_db
def test_copiar_requisicao_preserva_beneficiario_setor_e_observacao(
    requisicao_recusada, solicitante, setor_obras
):
    from apps.requisicoes.services import copiar_requisicao

    requisicao_recusada.observacao_geral = 'Urgente'
    requisicao_recusada.save(update_fields=['observacao_geral'])

    novo = copiar_requisicao(
        ator_id=solicitante.pk,
        requisicao_id=requisicao_recusada.pk,
    )

    assert novo.beneficiario_id == requisicao_recusada.beneficiario_id
    assert novo.setor_beneficiario_id == requisicao_recusada.setor_beneficiario_id
    assert novo.criador_id == solicitante.pk
    assert novo.observacao_geral == 'Urgente'


@pytest.mark.django_db
def test_copiar_requisicao_estado_invalido_lanca_estado_invalido(
    requisicao_aguardando, solicitante
):
    from apps.core.exceptions import EstadoInvalido
    from apps.requisicoes.services import copiar_requisicao

    with pytest.raises(EstadoInvalido) as excinfo:
        copiar_requisicao(
            ator_id=solicitante.pk,
            requisicao_id=requisicao_aguardando.pk,
        )
    assert excinfo.value.code == 'estado_invalido'


@pytest.mark.django_db
def test_copiar_requisicao_ator_sem_permissao_lanca_permissao_negada(
    requisicao_recusada, usuario_ti
):
    from apps.core.exceptions import PermissaoNegada
    from apps.requisicoes.services import copiar_requisicao

    with pytest.raises(PermissaoNegada):
        copiar_requisicao(
            ator_id=usuario_ti.pk,
            requisicao_id=requisicao_recusada.pk,
        )


@pytest.mark.django_db
def test_copiar_requisicao_inclui_item_inelegivel_sem_erro(
    solicitante, requisicao_aguardando, chefe_obras, material_sem_saldo
):
    """Itens inelegíveis no momento da cópia são incluídos no rascunho."""
    from apps.requisicoes.services import copiar_requisicao

    recusada = recusar_requisicao(
        ator_id=chefe_obras.pk,
        requisicao_id=requisicao_aguardando.pk,
        motivo='Sem estoque.',
    )
    from apps.estoque.models import SaldoEstoque

    SaldoEstoque.objects.filter(material=recusada.itens.first().material).update(
        saldo_fisico=0, saldo_reservado=0
    )

    novo = copiar_requisicao(
        ator_id=solicitante.pk,
        requisicao_id=recusada.pk,
    )

    assert novo.itens.count() == recusada.itens.count()
