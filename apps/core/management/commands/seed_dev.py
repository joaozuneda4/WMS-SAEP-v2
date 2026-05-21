"""Seed canônico para ambiente local de desenvolvimento."""

import os
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Setor, SetorClassificacao, VinculoAuxiliar
from apps.estoque.models import Estoque, Material, SaldoEstoque, UnidadeMedida
from apps.requisicoes.models import SequenciaRequisicao


SEED_DEV_SENHA_PADRAO = 'senha@dev'

SETORES = {
    'ALMOX': {
        'nome': 'Almoxarifado',
        'classificacao': SetorClassificacao.ALMOXARIFADO,
    },
    'OBRAS': {
        'nome': 'Obras',
        'classificacao': SetorClassificacao.COMUM,
    },
}

USUARIOS = {
    'SUPER001': {
        'nome': 'Administrador',
        'setor': None,
        'email': '',
        'is_staff': True,
        'is_superuser': True,
    },
    'ALMOX001': {
        'nome': 'Chefe Almoxarifado',
        'setor': 'ALMOX',
        'email': '',
        'is_staff': False,
        'is_superuser': False,
    },
    'ALMOX002': {
        'nome': 'Auxiliar Almoxarifado',
        'setor': 'OBRAS',
        'email': '',
        'is_staff': False,
        'is_superuser': False,
    },
    'OBRAS001': {
        'nome': 'Chefe de Obras',
        'setor': 'OBRAS',
        'email': '',
        'is_staff': False,
        'is_superuser': False,
    },
    'OBRAS002': {
        'nome': 'Auxiliar de Obras',
        'setor': 'OBRAS',
        'email': '',
        'is_staff': False,
        'is_superuser': False,
    },
    'OBRAS003': {
        'nome': 'Usuário Obras',
        'setor': 'OBRAS',
        'email': '',
        'is_staff': False,
        'is_superuser': False,
    },
}

CHEFIAS = {
    'ALMOX': 'ALMOX001',
    'OBRAS': 'OBRAS001',
}

VINCULOS_AUXILIARES = {
    ('ALMOX002', 'ALMOX'),
    ('OBRAS002', 'OBRAS'),
}

MATERIAIS = {
    'MAT-001': {
        'nome': 'Papel A4',
        'unidade': UnidadeMedida.UNIDADE,
        'saldo_fisico': Decimal('50.000'),
    },
    'MAT-002': {
        'nome': 'Caneta esferográfica',
        'unidade': UnidadeMedida.UNIDADE,
        'saldo_fisico': Decimal('10.000'),
    },
    'MAT-003': {
        'nome': 'Fita crepe',
        'unidade': UnidadeMedida.ROLO,
        'saldo_fisico': Decimal('0.000'),
    },
}

ESTOQUE_PRINCIPAL = {
    'codigo': 'EST-PRINCIPAL',
    'nome': 'Estoque Principal',
}


class Command(BaseCommand):
    """Carrega dados canônicos mínimos do piloto."""

    help = 'Carrega dados canônicos mínimos do ambiente local.'

    def handle(self, *args, **options):
        _exigir_ambiente_local()

        with transaction.atomic():
            _validar_conflito_almoxarifado()
            setores = _seed_setores()
            usuarios = _seed_usuarios(setores)
            _seed_chefias(setores, usuarios)
            _seed_vinculos_auxiliares(setores, usuarios)
            materiais = _seed_materiais()
            estoque = _seed_estoque()
            _seed_saldos_iniciais_bootstrap_exception(estoque, materiais)
            _seed_sequencia_requisicao()

        self.stdout.write(self.style.SUCCESS('Seed de desenvolvimento aplicado.'))


def _exigir_ambiente_local():
    if not settings.DEBUG:
        raise CommandError('seed_dev exige DEBUG=True.')
    if os.environ.get('SEED_DEV_HABILITADO') != 'true':
        raise CommandError('seed_dev exige SEED_DEV_HABILITADO=true.')


def _validar_conflito_almoxarifado():
    conflito = (
        Setor.objects.filter(
            classificacao=SetorClassificacao.ALMOXARIFADO,
        )
        .exclude(codigo='ALMOX')
        .first()
    )
    if conflito is not None:
        raise CommandError(
            'Já existe setor classificado como Almoxarifado com código '
            f'{conflito.codigo}. Ajuste o dado antes de rodar seed_dev.',
        )


def _seed_setores():
    setores = {}
    for codigo, dados in SETORES.items():
        setor, _created = Setor.objects.update_or_create(
            codigo=codigo,
            defaults={
                'nome': dados['nome'],
                'classificacao': dados['classificacao'],
                'ativo': True,
            },
        )
        setores[codigo] = setor
    return setores


def _seed_usuarios(setores):
    User = get_user_model()
    senha = os.environ.get('SEED_DEV_PASSWORD', SEED_DEV_SENHA_PADRAO)
    usuarios = {}
    for matricula, dados in USUARIOS.items():
        setor_codigo = dados['setor']
        usuario, _created = User.objects.update_or_create(
            matricula=matricula,
            defaults={
                'nome': dados['nome'],
                'email': dados['email'],
                'setor': setores[setor_codigo] if setor_codigo else None,
                'is_staff': dados['is_staff'],
                'is_superuser': dados['is_superuser'],
                'is_active': True,
            },
        )
        if not usuario.check_password(senha):
            usuario.set_password(senha)
            usuario.save(update_fields=['password'])
        usuarios[matricula] = usuario
    return usuarios


def _seed_chefias(setores, usuarios):
    for setor_codigo, matricula in CHEFIAS.items():
        setor = setores[setor_codigo]
        setor.chefe = usuarios[matricula]
        setor.save(update_fields=['chefe'])


def _seed_vinculos_auxiliares(setores, usuarios):
    for matricula, setor_codigo in VINCULOS_AUXILIARES:
        VinculoAuxiliar.objects.update_or_create(
            usuario=usuarios[matricula],
            setor=setores[setor_codigo],
            ativo=True,
            defaults={'desativado_em': None},
        )


def _seed_materiais():
    materiais = {}
    for codigo, dados in MATERIAIS.items():
        material, _created = Material.objects.update_or_create(
            codigo=codigo,
            defaults={
                'nome': dados['nome'],
                'unidade': dados['unidade'],
                'observacao_interna': '',
                'ativo': True,
            },
        )
        materiais[codigo] = material
    return materiais


def _seed_estoque():
    estoque, _created = Estoque.objects.update_or_create(
        codigo=ESTOQUE_PRINCIPAL['codigo'],
        defaults={'nome': ESTOQUE_PRINCIPAL['nome'], 'ativo': True},
    )
    return estoque


def _seed_saldos_iniciais_bootstrap_exception(estoque, materiais):
    # SEED BOOTSTRAP EXCEPTION: ver docs/CONVENTIONS.md#seed-bootstrap-exceptions.
    for codigo, material in materiais.items():
        SaldoEstoque.objects.update_or_create(
            estoque=estoque,
            material=material,
            defaults={
                'saldo_fisico': MATERIAIS[codigo]['saldo_fisico'],
                'saldo_reservado': Decimal('0.000'),
            },
        )


def _seed_sequencia_requisicao():
    SequenciaRequisicao.objects.get_or_create(ano=timezone.localdate().year)
