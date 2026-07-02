"""Modelos de requisições: cabeçalho da requisição e sequência de numeração.

A máquina de estados é declarativa em ``requisicoes.services``/transitions;
o model ``Requisicao`` guarda apenas o estado atual. Justificativas de
transição (recusa, cancelamento, estorno) pertencem à futura
``TimelineRequisicao`` (ADR-0002), nunca a campos ``motivo_*`` aqui.
"""

from django.conf import settings
from django.db import models


class EstadoRequisicao(models.TextChoices):
    """Os 8 estados canônicos do ciclo de vida da requisição."""

    RASCUNHO = 'rascunho', 'Rascunho'
    AGUARDANDO_AUTORIZACAO = 'aguardando_autorizacao', 'Aguardando autorização'
    RECUSADA = 'recusada', 'Recusada'
    AUTORIZADA = 'autorizada', 'Autorizada'
    PRONTA_PARA_RETIRADA = 'pronta_para_retirada', 'Pronta para retirada'
    ATENDIDA = 'atendida', 'Atendida'
    CANCELADA = 'cancelada', 'Cancelada'
    ESTORNADA = 'estornada', 'Estornada'


class SequenciaRequisicao(models.Model):
    """Contador anual para emissão do número público da requisição.

    O número público é gerado por ``requisicoes.services`` dentro de
    ``transaction.atomic``, com ``select_for_update`` na linha do ano
    (ADR-0003). Não emitir número fora desse caminho.
    """

    ano = models.PositiveIntegerField('ano', unique=True)
    ultimo_numero = models.PositiveIntegerField('último número', default=0)

    class Meta:
        verbose_name = 'sequência de requisição'
        verbose_name_plural = 'sequências de requisição'
        ordering = ('-ano',)

    def __str__(self):
        return f'{self.ano}: {self.ultimo_numero}'


class Requisicao(models.Model):
    """Cabeçalho de uma requisição de material.

    ``setor_beneficiario`` é snapshot do setor do beneficiário no momento da
    criação; nunca é recalculado a partir de ``beneficiario.setor``.
    """

    estado = models.CharField(
        'estado',
        max_length=30,
        choices=EstadoRequisicao.choices,
        default=EstadoRequisicao.RASCUNHO,
    )
    numero_publico = models.CharField(
        'número público',
        max_length=20,
        null=True,
        blank=True,
        unique=True,
    )
    criador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='requisicoes_criadas',
        verbose_name='criador',
    )
    beneficiario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='requisicoes_beneficiadas',
        verbose_name='beneficiário',
    )
    setor_beneficiario = models.ForeignKey(
        'accounts.Setor',
        on_delete=models.PROTECT,
        related_name='requisicoes',
        verbose_name='setor do beneficiário',
    )
    observacao_geral = models.TextField('observação geral', blank=True)
    criado_em = models.DateTimeField('criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'requisição'
        verbose_name_plural = 'requisições'
        ordering = ('-criado_em',)
        indexes = [
            models.Index(
                fields=['estado', 'criado_em'],
                name='idx_requisicao_estado_data',
            ),
            models.Index(
                fields=['setor_beneficiario', 'criado_em'],
                name='idx_requisicao_setor_data',
            ),
        ]

    def __str__(self):
        return self.numero_publico or f'Rascunho #{self.pk}'


class ItemRequisicao(models.Model):
    """Linha de material de uma requisição.

    As três quantidades são distintas: ``solicitada`` é fixada na criação;
    ``autorizada`` nasce ``NULL`` e é preenchida na autorização; ``entregue``
    nasce ``NULL`` e é preenchida no atendimento, podendo ser 0. A igualdade
    ``autorizada == solicitada`` é regra do service de autorização (integral),
    não constraint de banco.
    """

    requisicao = models.ForeignKey(
        Requisicao,
        on_delete=models.CASCADE,
        related_name='itens',
        verbose_name='requisição',
    )
    material = models.ForeignKey(
        'estoque.Material',
        on_delete=models.PROTECT,
        related_name='itens_requisicao',
        verbose_name='material',
    )
    quantidade_solicitada = models.DecimalField(
        'quantidade solicitada',
        max_digits=12,
        decimal_places=3,
    )
    quantidade_autorizada = models.DecimalField(
        'quantidade autorizada',
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
    )
    quantidade_entregue = models.DecimalField(
        'quantidade entregue',
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
    )
    justificativa_entrega = models.TextField('justificativa de entrega', blank=True)

    class Meta:
        verbose_name = 'item de requisição'
        verbose_name_plural = 'itens de requisição'
        ordering = ('id',)
        constraints = [
            models.UniqueConstraint(
                fields=['requisicao', 'material'],
                name='unico_material_por_requisicao',
            ),
            models.CheckConstraint(
                condition=models.Q(quantidade_solicitada__gt=0),
                name='item_solicitada_positiva',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(quantidade_autorizada__isnull=True)
                    | models.Q(quantidade_autorizada__gt=0)
                ),
                name='item_autorizada_nula_ou_positiva',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(quantidade_entregue__isnull=True)
                    | models.Q(quantidade_entregue__gte=0)
                ),
                name='item_entregue_nula_ou_nao_negativa',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(quantidade_entregue__isnull=True)
                    | models.Q(quantidade_autorizada__isnull=True)
                    | models.Q(
                        quantidade_entregue__lte=models.F('quantidade_autorizada')
                    )
                ),
                name='item_entregue_ate_autorizada',
            ),
        ]

    def __str__(self):
        return f'{self.material} × {self.quantidade_solicitada}'


class EventoTimeline(models.TextChoices):
    """Os 13 eventos canônicos da timeline da requisição."""

    CRIACAO = 'criacao', 'Criação'
    ENVIO_AUTORIZACAO = 'envio_autorizacao', 'Envio para autorização'
    RETORNO_RASCUNHO = 'retorno_rascunho', 'Retorno para rascunho'
    RECUSA = 'recusa', 'Recusa'
    AUTORIZACAO_TOTAL = 'autorizacao_total', 'Autorização total'
    CANCELAMENTO = 'cancelamento', 'Cancelamento'
    SEPARACAO_RETIRADA = 'separacao_retirada', 'Separação para retirada'
    ATENDIMENTO_TOTAL = 'atendimento_total', 'Atendimento total'
    ATENDIMENTO_PARCIAL = 'atendimento_parcial', 'Atendimento parcial'
    LIBERACAO_RESERVA = 'liberacao_reserva', 'Liberação de reserva'
    DEVOLUCAO_REGISTRADA = 'devolucao_registrada', 'Devolução registrada'
    ESTORNO = 'estorno', 'Estorno'
    ATUALIZACAO_ESTOQUE_RELEVANTE = (
        'atualizacao_estoque_relevante',
        'Atualização de estoque relevante',
    )


class Operacao(models.TextChoices):
    """Vocabulário de operações que alteram o estado de uma Requisicao.

    Cada membro tem uma TransicaoRequisicao correspondente em
    ``apps.requisicoes.transitions.TRANSICOES`` (ADR-0011, emenda
    2026-06-26). Não inclui TR-001 (criação, sem estado de origem) nem
    TR-003 (descarte de rascunho não enviado, é DELETE, não transição).
    """

    EDITAR_RASCUNHO = 'editar_rascunho', 'Editar rascunho'
    ENVIAR_PARA_AUTORIZACAO = 'enviar_para_autorizacao', 'Enviar para autorização'
    RETORNAR_PARA_RASCUNHO = 'retornar_para_rascunho', 'Retornar para rascunho'
    RECUSAR = 'recusar', 'Recusar'
    AUTORIZAR = 'autorizar', 'Autorizar'
    CANCELAR = 'cancelar', 'Cancelar'
    SEPARAR_PARA_RETIRADA = 'separar_para_retirada', 'Separar para retirada'
    REGISTRAR_ATENDIMENTO = 'registrar_atendimento', 'Registrar atendimento'
    REGISTRAR_DEVOLUCAO = 'registrar_devolucao', 'Registrar devolução'
    ESTORNAR = 'estornar', 'Estornar'


class CancelamentoVariant(models.TextChoices):
    """Classificação do cancelamento de uma Requisicao (CONTEXT.md, "Variante de cancelamento").

    Descarte é uma variante do cancelamento, não uma operação à parte — a
    variante apenas classifica o caso. Os atributos de execução
    (requer_justificativa, libera_reserva) vivem em CancelamentoInfo
    (apps.requisicoes.transitions), derivados do TransitionSpec de
    Operacao.CANCELAR, não desta enumeração.
    """

    DESCARTE = 'descarte', 'Descarte'
    CANCELAMENTO = 'cancelamento', 'Cancelamento'


class TimelineRequisicao(models.Model):
    """Evento de histórico de domínio de uma requisição (ADR-0002).

    Append-only: eventos são criados explicitamente pelos services de
    domínio, nunca por signals de ``save()``. Não há edição nem remoção
    operacional — correções entram como um novo evento. A obrigatoriedade de
    ``justificativa`` por tipo de evento é validada nos services.
    """

    requisicao = models.ForeignKey(
        Requisicao,
        on_delete=models.CASCADE,
        related_name='eventos',
        verbose_name='requisição',
    )
    evento = models.CharField('evento', max_length=40, choices=EventoTimeline.choices)
    ator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='eventos_timeline',
        verbose_name='ator',
    )
    estado_resultante = models.CharField(
        'estado resultante',
        max_length=30,
        choices=EstadoRequisicao.choices,
        null=True,
        blank=True,
    )
    justificativa = models.TextField('justificativa', blank=True)
    metadata = models.JSONField('metadados', default=dict, blank=True)
    criado_em = models.DateTimeField('criado em', auto_now_add=True)

    class Meta:
        verbose_name = 'evento de timeline'
        verbose_name_plural = 'eventos de timeline'
        ordering = ('criado_em', 'id')

    def __str__(self):
        return f'{self.get_evento_display()} — {self.requisicao}'
