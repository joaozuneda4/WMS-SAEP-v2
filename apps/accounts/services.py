"""Comandos de domínio de accounts — gestão de usuários, setores e vínculos."""

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Setor, User, VinculoAuxiliar
from apps.core.exceptions import ConflitoDominio, DadosInvalidos


@transaction.atomic
def trocar_chefe_setor(*, ator_id: int, setor_id: int, novo_chefe_id: int) -> None:
    """Designa novo chefe para um setor (USR-04/USR-05)."""
    from apps.accounts.policies import exigir_pode_gerir_cadastro

    try:
        ator = User.objects.get(pk=ator_id)
        setor = Setor.objects.select_for_update().get(pk=setor_id)
        novo_chefe = User.objects.select_for_update().get(pk=novo_chefe_id)
    except ObjectDoesNotExist as exc:
        raise DadosInvalidos(
            'Referência inválida.', code='referencia_invalida'
        ) from exc

    exigir_pode_gerir_cadastro(ator)

    if not novo_chefe.is_active:
        raise DadosInvalidos(
            f"Usuário '{novo_chefe.nome}' está inativo e não pode ser designado como chefe.",
            code='chefe_inativo',
        )

    if novo_chefe.setor_id != setor.pk:
        raise DadosInvalidos(
            f"Usuário '{novo_chefe.nome}' não pertence ao setor '{setor.nome}'.",
            code='chefe_setor_errado',
        )

    setor_ja_chefiado = (
        Setor.objects.filter(chefe=novo_chefe).exclude(pk=setor.pk).first()
    )
    if setor_ja_chefiado:
        raise ConflitoDominio(
            f"Usuário '{novo_chefe.nome}' já chefia o setor '{setor_ja_chefiado.nome}'.",
            code='chefe_duplicado',
        )

    setor.chefe = novo_chefe
    setor.save(update_fields=['chefe'])


@transaction.atomic
def desativar_usuario(
    *, ator_id: int, usuario_id: int, novo_chefe_id: int | None = None
) -> None:
    """Desativa usuário, bloqueando se chefe de setor ativo sem substituto (USR-07)."""
    from apps.accounts.policies import exigir_pode_gerir_cadastro

    try:
        ator = User.objects.get(pk=ator_id)
        usuario = User.objects.select_for_update().get(pk=usuario_id)
    except ObjectDoesNotExist as exc:
        raise DadosInvalidos(
            'Referência inválida.', code='referencia_invalida'
        ) from exc

    exigir_pode_gerir_cadastro(ator)

    if not usuario.is_active:
        return

    setor_chefiado = Setor.objects.filter(chefe=usuario, ativo=True).first()
    if setor_chefiado:
        if novo_chefe_id is None:
            raise ConflitoDominio(
                f"Usuário '{usuario.nome}' é chefe do setor '{setor_chefiado.nome}'. "
                'Informe um novo chefe antes de desativar.',
                code='usuario_chefe_sem_substituto',
            )
        trocar_chefe_setor(
            ator_id=ator_id,
            setor_id=setor_chefiado.pk,
            novo_chefe_id=novo_chefe_id,
        )

    usuario.is_active = False
    usuario.save(update_fields=['is_active'])


@transaction.atomic
def ativar_vinculo_auxiliar(
    *, ator_id: int, usuario_id: int, setor_id: int
) -> VinculoAuxiliar:
    """Cria ou reativa vínculo auxiliar entre usuário e setor."""
    from apps.accounts.policies import exigir_pode_gerir_cadastro

    try:
        ator = User.objects.get(pk=ator_id)
        usuario = User.objects.get(pk=usuario_id)
        setor = Setor.objects.get(pk=setor_id)
    except ObjectDoesNotExist as exc:
        raise DadosInvalidos(
            'Referência inválida.', code='referencia_invalida'
        ) from exc

    exigir_pode_gerir_cadastro(ator)

    vinculo = (
        VinculoAuxiliar.objects.select_for_update()
        .filter(usuario=usuario, setor=setor)
        .first()
    )
    if vinculo and vinculo.ativo:
        raise ConflitoDominio(
            f"Vínculo auxiliar já está ativo para '{usuario.nome}' no setor '{setor.nome}'.",
            code='vinculo_ja_ativo',
        )

    if vinculo:
        vinculo.ativo = True
        vinculo.desativado_em = None
        vinculo.save(update_fields=['ativo', 'desativado_em'])
    else:
        vinculo = VinculoAuxiliar.objects.create(
            usuario=usuario, setor=setor, ativo=True
        )
    return vinculo


@transaction.atomic
def desativar_vinculo_auxiliar(*, ator_id: int, vinculo_id: int) -> VinculoAuxiliar:
    """Desativa vínculo auxiliar existente."""
    from apps.accounts.policies import exigir_pode_gerir_cadastro

    try:
        ator = User.objects.get(pk=ator_id)
        vinculo = VinculoAuxiliar.objects.select_for_update().get(pk=vinculo_id)
    except ObjectDoesNotExist as exc:
        raise DadosInvalidos(
            'Referência inválida.', code='referencia_invalida'
        ) from exc

    exigir_pode_gerir_cadastro(ator)

    if not vinculo.ativo:
        raise ConflitoDominio(
            'Vínculo auxiliar já está inativo.',
            code='vinculo_ja_inativo',
        )

    vinculo.ativo = False
    vinculo.desativado_em = timezone.now()
    vinculo.save(update_fields=['ativo', 'desativado_em'])
    return vinculo
