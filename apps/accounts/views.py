"""Views do app accounts."""

from django.contrib.auth.views import LoginView

from apps.accounts.forms import MatriculaAuthenticationForm


class MatriculaLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = MatriculaAuthenticationForm
    redirect_authenticated_user = True
