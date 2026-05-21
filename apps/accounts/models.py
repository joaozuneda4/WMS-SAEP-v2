"""Modelos de identidade e organização: Setor e Usuário."""

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.accounts.managers import UserManager


class SetorClassificacao(models.TextChoices):
    """Classificação funcional de um Setor."""

    COMUM = 'comum', 'Comum'
    ALMOXARIFADO = 'almoxarifado', 'Almoxarifado'


class Setor(models.Model):
    """Unidade organizacional da SAEP à qual um usuário pertence.

    O almoxarifado é identificado por ``classificacao``, nunca pelo nome.
    Vínculo de auxiliar ainda não modelado (ver ADR-0001). Invariante de
    domínio reforçada em service/policy: se o setor tem chefe, o chefe
    pertence ao próprio setor (``chefe.setor_id == setor.id``).
    """

    codigo = models.CharField('código', max_length=20, unique=True)
    nome = models.CharField('nome', max_length=120, unique=True)
    classificacao = models.CharField(
        'classificação',
        max_length=20,
        choices=SetorClassificacao.choices,
        default=SetorClassificacao.COMUM,
    )
    chefe = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='setor_chefiado',
        verbose_name='chefe',
    )
    ativo = models.BooleanField('ativo', default=True)

    class Meta:
        verbose_name = 'setor'
        verbose_name_plural = 'setores'
        ordering = ('nome',)
        constraints = [
            models.UniqueConstraint(
                fields=['classificacao'],
                condition=models.Q(classificacao=SetorClassificacao.ALMOXARIFADO),
                name='unico_setor_almoxarifado',
            ),
        ]

    def __str__(self):
        return f'{self.codigo} — {self.nome}'


class User(AbstractUser):
    """Usuário do sistema, autenticado por matrícula e senha."""

    username = None
    first_name = None
    last_name = None

    matricula = models.CharField('matrícula', max_length=30, unique=True)
    nome = models.CharField('nome completo', max_length=150)
    email = models.EmailField('e-mail', blank=True)
    # Nula para bootstrap, superusuário técnico e cadastro incompleto; a
    # exigência de setor para operar é regra de domínio (services/policies).
    setor = models.ForeignKey(
        Setor,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='usuarios',
        verbose_name='setor',
    )

    USERNAME_FIELD = 'matricula'
    REQUIRED_FIELDS = ['nome']

    objects = UserManager()

    class Meta:
        verbose_name = 'usuário'
        verbose_name_plural = 'usuários'
        ordering = ('nome',)

    def __str__(self):
        return f'{self.nome} ({self.matricula})'

    def get_full_name(self):
        return self.nome

    def get_short_name(self):
        return self.nome


class VinculoAuxiliar(models.Model):
    """Atribuição operacional de auxiliar entre um usuário e um setor.

    Independente da lotação principal (``User.setor``). O papel "auxiliar de
    almoxarifado" deriva de um vínculo ativo cujo setor está ativo e tem
    ``classificacao == ALMOXARIFADO`` — não há model separado.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='vinculos_auxiliares',
        verbose_name='usuário',
    )
    setor = models.ForeignKey(
        Setor,
        on_delete=models.PROTECT,
        related_name='vinculos_auxiliares',
        verbose_name='setor',
    )
    ativo = models.BooleanField('ativo', default=True)
    criado_em = models.DateTimeField('criado em', auto_now_add=True)
    atualizado_em = models.DateTimeField('atualizado em', auto_now=True)
    desativado_em = models.DateTimeField('desativado em', null=True, blank=True)

    class Meta:
        verbose_name = 'vínculo de auxiliar'
        verbose_name_plural = 'vínculos de auxiliar'
        ordering = ('-criado_em',)
        constraints = [
            models.UniqueConstraint(
                fields=['usuario', 'setor'],
                condition=models.Q(ativo=True),
                name='unico_vinculo_auxiliar_ativo',
            ),
        ]

    def __str__(self):
        estado = 'ativo' if self.ativo else 'inativo'
        return f'{self.usuario} ⇄ {self.setor} ({estado})'
