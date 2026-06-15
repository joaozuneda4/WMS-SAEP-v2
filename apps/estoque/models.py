"""Modelos de estoque: catálogo de materiais, locais de estoque e saldos.

Toda mutação de saldo deve ocorrer via ``estoque.services``, sob
``transaction.atomic`` e ``select_for_update`` sobre ``SaldoEstoque``, em
ordem determinística (EST-06). Nenhum outro app escreve saldo diretamente.
"""

from django.conf import settings
from django.db import models


class UnidadeMedida(models.TextChoices):
    """Unidade de medida de um material."""

    UNIDADE = 'un', 'Unidade'
    CAIXA = 'cx', 'Caixa'
    PACOTE = 'pct', 'Pacote'
    PAR = 'par', 'Par'
    ROLO = 'rolo', 'Rolo'
    METRO = 'm', 'Metro'
    METRO_QUADRADO = 'm2', 'Metro quadrado'
    QUILOGRAMA = 'kg', 'Quilograma'
    LITRO = 'l', 'Litro'


class Material(models.Model):
    """Item do catálogo de materiais do almoxarifado.

    O catálogo não detém saldo: o saldo é de ``SaldoEstoque``.
    """

    codigo = models.CharField('código', max_length=30, unique=True)
    nome = models.CharField('nome', max_length=200)
    unidade = models.CharField(
        'unidade de medida',
        max_length=10,
        choices=UnidadeMedida.choices,
    )
    observacao_interna = models.TextField('observação interna', blank=True)
    ativo = models.BooleanField('ativo', default=True)

    class Meta:
        verbose_name = 'material'
        verbose_name_plural = 'materiais'
        ordering = ('nome',)

    def __str__(self):
        return f'{self.codigo} — {self.nome}'


class Estoque(models.Model):
    """Contexto/local que detém saldos de materiais.

    Fase atual: um estoque principal do almoxarifado. O schema admite
    estoques futuros (por exemplo, por equipe) sem alteração estrutural.
    """

    codigo = models.CharField('código', max_length=30, unique=True)
    nome = models.CharField('nome', max_length=120, unique=True)
    ativo = models.BooleanField('ativo', default=True)

    class Meta:
        verbose_name = 'estoque'
        verbose_name_plural = 'estoques'
        ordering = ('nome',)

    def __str__(self):
        return self.nome


class SaldoEstoque(models.Model):
    """Dono do saldo físico e reservado de um material em um estoque.

    ``saldo_disponivel`` e ``divergente`` são derivados, nunca persistidos.
    A divergência (físico < reservado) é estado de domínio válido — por isso
    não há constraint ``saldo_fisico >= saldo_reservado``.
    """

    estoque = models.ForeignKey(
        Estoque,
        on_delete=models.PROTECT,
        related_name='saldos',
        verbose_name='estoque',
    )
    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name='saldos',
        verbose_name='material',
    )
    saldo_fisico = models.DecimalField(
        'saldo físico',
        max_digits=12,
        decimal_places=3,
        default=0,
    )
    saldo_reservado = models.DecimalField(
        'saldo reservado',
        max_digits=12,
        decimal_places=3,
        default=0,
    )

    class Meta:
        verbose_name = 'saldo de estoque'
        verbose_name_plural = 'saldos de estoque'
        ordering = ('estoque', 'material')
        constraints = [
            models.UniqueConstraint(
                fields=['estoque', 'material'],
                name='unico_saldo_por_estoque_material',
            ),
            models.CheckConstraint(
                condition=models.Q(saldo_fisico__gte=0),
                name='saldo_fisico_nao_negativo',
            ),
            models.CheckConstraint(
                condition=models.Q(saldo_reservado__gte=0),
                name='saldo_reservado_nao_negativo',
            ),
        ]

    @property
    def saldo_disponivel(self):
        return self.saldo_fisico - self.saldo_reservado

    @property
    def divergente(self):
        return self.saldo_fisico < self.saldo_reservado

    def __str__(self):
        return f'{self.material} @ {self.estoque}'


class EstadoSaidaExcepcional(models.TextChoices):
    REGISTRADA = 'registrada', 'Registrada'
    ESTORNADA = 'estornada', 'Estornada'


class SaidaExcepcional(models.Model):
    """Documento de baixa administrativa direta de material no estoque.

    Independente do ciclo de vida de Requisição. Mutações apenas via
    ``estoque.services`` (EST-saida-01).
    """

    numero_publico = models.CharField(
        'número público',
        max_length=30,
        unique=True,
        null=True,
        blank=True,
    )
    criado_em = models.DateTimeField('criado em', auto_now_add=True)
    motivo = models.TextField('motivo')
    observacao = models.TextField('observação', blank=True)
    estado = models.CharField(
        'estado',
        max_length=20,
        choices=EstadoSaidaExcepcional.choices,
        default=EstadoSaidaExcepcional.REGISTRADA,
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='saidas_excepcionais_registradas',
        verbose_name='registrado por',
    )
    estoque = models.ForeignKey(
        Estoque,
        on_delete=models.PROTECT,
        related_name='saidas_excepcionais',
        verbose_name='estoque',
    )
    estornado_em = models.DateTimeField('estornado em', null=True, blank=True)
    estornado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='saidas_excepcionais_estornadas',
        verbose_name='estornado por',
        null=True,
        blank=True,
    )
    justificativa_estorno = models.TextField('justificativa de estorno', blank=True)

    class Meta:
        verbose_name = 'saída excepcional'
        verbose_name_plural = 'saídas excepcionais'
        ordering = ('-criado_em',)
        constraints = [
            models.CheckConstraint(
                name='saida_excepcional_estorno_consistente',
                condition=(
                    (
                        models.Q(estado=EstadoSaidaExcepcional.REGISTRADA)
                        & models.Q(estornado_em__isnull=True)
                        & models.Q(estornado_por__isnull=True)
                    )
                    | (
                        models.Q(estado=EstadoSaidaExcepcional.ESTORNADA)
                        & models.Q(estornado_em__isnull=False)
                        & models.Q(estornado_por__isnull=False)
                    )
                ),
            ),
        ]

    def __str__(self):
        return self.numero_publico or f'Saída #{self.pk}'


class ItemSaidaExcepcional(models.Model):
    """Item de uma saída excepcional — um material e sua quantidade baixada."""

    saida = models.ForeignKey(
        SaidaExcepcional,
        on_delete=models.CASCADE,
        related_name='itens',
        verbose_name='saída excepcional',
    )
    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name='itens_saida_excepcional',
        verbose_name='material',
    )
    quantidade = models.DecimalField(
        'quantidade',
        max_digits=12,
        decimal_places=3,
    )

    class Meta:
        verbose_name = 'item de saída excepcional'
        verbose_name_plural = 'itens de saída excepcional'
        constraints = [
            models.UniqueConstraint(
                fields=['saida', 'material'],
                name='unico_material_por_saida_excepcional',
            ),
            models.CheckConstraint(
                condition=models.Q(quantidade__gt=0),
                name='quantidade_saida_excepcional_positiva',
            ),
        ]

    def __str__(self):
        return f'{self.material} × {self.quantidade} ({self.saida})'


class SequenciaSaidaExcepcional(models.Model):
    """Contador anual para emissão do número público da saída excepcional.

    Emitido exclusivamente por ``estoque.services`` dentro de
    ``transaction.atomic`` com ``select_for_update`` (EST-saida-01).
    """

    ano = models.PositiveIntegerField('ano', unique=True)
    ultimo_numero = models.PositiveIntegerField('último número', default=0)

    class Meta:
        verbose_name = 'sequência de saída excepcional'
        verbose_name_plural = 'sequências de saída excepcional'
        ordering = ('-ano',)

    def __str__(self) -> str:
        return f'{self.ano}: {self.ultimo_numero}'


class StatusImportacaoSCPI(models.TextChoices):
    CONCLUIDA = 'concluida', 'Concluída'
    COM_ALERTAS = 'com_alertas', 'Concluída com alertas'


class ImportacaoSCPI(models.Model):
    """Metadados de uma confirmação de importação SCPI.

    Não armazena o CSV bruto nem snapshot do preview — apenas metadados e resumo mínimo.
    O hash garante bloqueio de reimportação exata do mesmo arquivo.
    """

    arquivo_nome = models.CharField('nome do arquivo', max_length=255)
    arquivo_hash = models.CharField(
        'hash SHA-256 do arquivo',
        max_length=64,
        unique=True,
    )
    importado_por = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='importacoes_scpi',
        verbose_name='importado por',
    )
    importado_em = models.DateTimeField('importado em', auto_now_add=True)
    estoque = models.ForeignKey(
        Estoque,
        on_delete=models.PROTECT,
        related_name='importacoes_scpi',
        verbose_name='estoque',
    )
    status = models.CharField(
        'status',
        max_length=20,
        choices=StatusImportacaoSCPI.choices,
        default=StatusImportacaoSCPI.CONCLUIDA,
    )
    total_linhas = models.PositiveIntegerField('total de linhas', default=0)
    total_novos = models.PositiveIntegerField('materiais novos criados', default=0)
    total_divergentes = models.PositiveIntegerField('linhas divergentes', default=0)

    class Meta:
        verbose_name = 'importação SCPI'
        verbose_name_plural = 'importações SCPI'
        ordering = ('-importado_em',)

    def __str__(self):
        return f'Importação SCPI #{self.pk} — {self.arquivo_nome}'


class MovimentacaoEstoqueImutavel(Exception):
    """Levantada ao tentar alterar ou excluir um registro de MovimentacaoEstoque.

    Violação de imutabilidade é erro de programação, não condição de negócio.
    Fora da árvore ErroDominio intencionalmente.
    """


class TipoMovimentacaoEstoque(models.TextChoices):
    RESERVA = 'reserva', 'Reserva'
    LIBERACAO = 'liberacao', 'Liberação'
    CONSUMO = 'consumo', 'Consumo'
    SAIDA_EXCEPCIONAL = 'saida_excepcional', 'Saída excepcional'
    ESTORNO_SAIDA = 'estorno_saida', 'Estorno de saída'
    DEVOLUCAO = 'devolucao', 'Devolução'
    ESTORNO_REQUISICAO = 'estorno_requisicao', 'Estorno de requisição'


_TIPOS_ORIGEM_REQUISICAO = [
    TipoMovimentacaoEstoque.RESERVA,
    TipoMovimentacaoEstoque.LIBERACAO,
    TipoMovimentacaoEstoque.CONSUMO,
    TipoMovimentacaoEstoque.DEVOLUCAO,
    TipoMovimentacaoEstoque.ESTORNO_REQUISICAO,
]

_TIPOS_ORIGEM_SAIDA = [
    TipoMovimentacaoEstoque.SAIDA_EXCEPCIONAL,
    TipoMovimentacaoEstoque.ESTORNO_SAIDA,
]


class MovimentacaoEstoqueQuerySet(models.QuerySet):
    """QuerySet que bloqueia mutações em lote para preservar o ledger append-only."""

    def update(self, **kwargs):
        raise MovimentacaoEstoqueImutavel(
            'MovimentacaoEstoque não pode ser alterada em lote.'
        )

    def bulk_update(self, objs, fields, batch_size=None):
        raise MovimentacaoEstoqueImutavel(
            'MovimentacaoEstoque não pode ser alterada em lote.'
        )

    def delete(self):
        raise MovimentacaoEstoqueImutavel(
            'MovimentacaoEstoque não pode ser excluída em lote.'
        )


class MovimentacaoEstoque(models.Model):
    """Ledger auditável de mutações de SaldoEstoque.

    Cada linha registra um evento de domínio por material afetado, com dois
    deltas assinados (delta_fisico, delta_reservado). Imutável após criação:
    save() e delete() levantam MovimentacaoEstoqueImutavel.

    Invariante de reconciliação:
        Σ delta_fisico por (estoque, material) == saldo_fisico atual
        Σ delta_reservado por (estoque, material) == saldo_reservado atual
    (válida apenas para movimentações geridas por este ledger; saldo inicial
    de importação SCPI é lacuna conhecida — ver ADR-0015.)
    """

    tipo = models.CharField(
        'tipo',
        max_length=25,
        choices=TipoMovimentacaoEstoque.choices,
    )
    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name='movimentacoes_estoque',
        verbose_name='material',
    )
    estoque = models.ForeignKey(
        Estoque,
        on_delete=models.PROTECT,
        related_name='movimentacoes',
        verbose_name='estoque',
    )
    delta_fisico = models.DecimalField(
        'delta físico',
        max_digits=12,
        decimal_places=3,
        default=0,
    )
    delta_reservado = models.DecimalField(
        'delta reservado',
        max_digits=12,
        decimal_places=3,
        default=0,
    )
    requisicao = models.ForeignKey(
        'requisicoes.Requisicao',
        on_delete=models.PROTECT,
        related_name='movimentacoes_estoque',
        verbose_name='requisição',
        null=True,
        blank=True,
    )
    saida_excepcional = models.ForeignKey(
        SaidaExcepcional,
        on_delete=models.PROTECT,
        related_name='movimentacoes_estoque',
        verbose_name='saída excepcional',
        null=True,
        blank=True,
    )
    ator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='movimentacoes_estoque',
        verbose_name='ator',
    )
    criado_em = models.DateTimeField('criado em', auto_now_add=True)

    objects = MovimentacaoEstoqueQuerySet.as_manager()

    class Meta:
        verbose_name = 'movimentação de estoque'
        verbose_name_plural = 'movimentações de estoque'
        ordering = ('criado_em',)
        indexes = [
            models.Index(
                fields=['requisicao', 'material', 'tipo'],
                name='idx_mov_req_mat_tipo',
            ),
            models.Index(
                fields=['estoque', 'material'],
                name='idx_mov_est_mat',
            ),
        ]
        constraints = [
            models.CheckConstraint(
                name='movimentacao_exatamente_uma_origem',
                condition=(
                    (
                        models.Q(requisicao__isnull=False)
                        & models.Q(saida_excepcional__isnull=True)
                    )
                    | (
                        models.Q(requisicao__isnull=True)
                        & models.Q(saida_excepcional__isnull=False)
                    )
                ),
            ),
            models.CheckConstraint(
                name='movimentacao_ao_menos_um_delta_nao_nulo',
                condition=(~models.Q(delta_fisico=0) | ~models.Q(delta_reservado=0)),
            ),
            models.CheckConstraint(
                name='movimentacao_tipo_origem_coerente',
                condition=(
                    (
                        models.Q(tipo__in=[t.value for t in _TIPOS_ORIGEM_REQUISICAO])
                        & models.Q(requisicao__isnull=False)
                    )
                    | (
                        models.Q(tipo__in=[t.value for t in _TIPOS_ORIGEM_SAIDA])
                        & models.Q(saida_excepcional__isnull=False)
                    )
                ),
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise MovimentacaoEstoqueImutavel(
                f'MovimentacaoEstoque pk={self.pk} é imutável após criação.'
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise MovimentacaoEstoqueImutavel(
            f'MovimentacaoEstoque pk={self.pk} não pode ser excluída.'
        )

    def __str__(self):
        return (
            f'{self.get_tipo_display()} — {self.material} ({self.criado_em:%Y-%m-%d})'
        )
