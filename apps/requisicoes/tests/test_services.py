"""Testes de services de requisições (ADR-0010).

3 casos por transição: caminho feliz, estado inválido, permissão negada.
"""

import pytest
from decimal import Decimal

from apps.core.exceptions import DadosInvalidos, EstadoInvalido, PermissaoNegada
from apps.requisicoes.models import EstadoRequisicao, EventoTimeline, Requisicao
from apps.requisicoes.services import criar_requisicao, editar_rascunho


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
