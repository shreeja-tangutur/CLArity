from django import forms # type: ignore
from django.contrib.auth.models import User # type: ignore

class RegisterForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput())

    class Meta: 
        model = User
        fields = ['username', 'email','password', ]

