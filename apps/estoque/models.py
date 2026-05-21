"""Modelos de estoque: catálogo de materiais, locais de estoque e saldos.

Toda mutação de saldo deve ocorrer via ``estoque.services``, sob
``transaction.atomic`` e ``select_for_update`` sobre ``SaldoEstoque``, em
ordem determinística (EST-06). Nenhum outro app escreve saldo diretamente.
"""

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
