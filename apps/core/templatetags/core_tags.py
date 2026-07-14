from django.core.exceptions import ImproperlyConfigured
from django import template

register = template.Library()


@register.simple_tag
def validar_contrato_modal(action_url, submit_form_id):
    """Exige exatamente um entre action_url e submit_form_id em components/modal.html."""
    if bool(action_url) == bool(submit_form_id):
        raise ImproperlyConfigured(
            'components/modal.html exige exatamente um entre action_url e '
            'submit_form_id (recebido: '
            f'action_url={action_url!r}, submit_form_id={submit_form_id!r}).'
        )
    return ''
