"""Views da camada compartilhada de UI. Sem regra de domínio."""

from django.shortcuts import render


def home(request):
    return render(request, 'core/home.html')
