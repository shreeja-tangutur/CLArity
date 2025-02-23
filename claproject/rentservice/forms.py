from django import forms
from .models import BorrowRequest

class BorrowRequestForm(forms.ModelForm):
    class Meta:
        model = BorrowRequest
        fields = ['item'] 