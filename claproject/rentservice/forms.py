from django import forms
from .models import BorrowRequest
from .models import Item, Collection, Tag, User
from django.core.exceptions import ValidationError
from django.db.models import Q


class RatingCommentForm(forms.Form):
    score = forms.ChoiceField(
        choices=[(i, str(i)) for i in range(1, 6)],
        label='Rating',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    text = forms.CharField(
        label='Leave a Comment',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        max_length=500
    )

class ItemForm(forms.ModelForm):
    tags = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'id': 'tag-input'})
    )

    collections = forms.ModelMultipleChoiceField(
        queryset=Collection.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Item
        fields = [
            'title',
            'status',
            'location',
            'description',
            'image',
            'borrow_period_days',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'borrow_period_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        self.user = user
        super().__init__(*args, **kwargs)
        if self.user:
            if self.user.role == 'librarian':
                self.fields['collections'].queryset = Collection.objects.all()
            else:
                self.fields['collections'].queryset = Collection.objects.filter(is_public=True)
        if self.instance.pk:
            self.fields['collections'].initial = self.instance.collections.all()


class CollectionForm(forms.ModelForm):
    items = forms.ModelMultipleChoiceField(
        queryset=Item.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = Collection
        fields = ['title', 'description', 'is_public', 'items']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        current_collection = self.instance if self.instance and self.instance.pk else None
        is_edit_mode = current_collection is not None

        if is_edit_mode:
            if current_collection.is_public:
                private_item_ids = Item.objects.filter(
                    collections__is_public=False
                ).exclude(
                    collections=current_collection
                ).values_list('id', flat=True)

                self.fields['items'].queryset = Item.objects.exclude(
                    id__in=private_item_ids
                ).distinct()
            else:
                self.fields['items'].queryset = Item.objects.filter(
                    Q(collections__isnull=True) | Q(collections=current_collection)
                ).distinct()
        else:
            self.fields['items'].queryset = Item.objects.all()

        if self.user and not self.user.is_librarian():
            self.fields['is_public'].widget = forms.HiddenInput()
            self.fields['is_public'].initial = True

    def clean(self):
        """
        Enforce:
         - An item in a private collection cannot belong to any other collection.
         - Items in public collections can belong to multiple public collections.
         - If the current collection is public, check that none of the items selected is already in a private collection.
         - If the current collection is private, check that none of the items is in any other collection.
        """
        cleaned_data = super().clean()
        items = cleaned_data.get('items')
        is_public = cleaned_data.get('is_public')

        # When editing, self.instance.pk may exist.
        current_pk = self.instance.pk if self.instance else None

        if items:
            if not is_public:
                # This is a private collection.
                for item in items:
                    # Exclude the current collection (in case of editing)
                    other_collections = item.collections.exclude(pk=current_pk)
                    if other_collections.exists():
                        raise ValidationError(
                            f"Item '{item.title}' is already in another collection. "
                            "An item in a private collection cannot be added to another collection."
                        )
            else:
                # This is a public collection.
                for item in items:
                    # Check if this item is already in any private collection (other than the current one if editing)
                    private_collections = item.collections.filter(is_public=False).exclude(pk=current_pk)
                    if private_collections.exists():
                        existing_private = private_collections.first().title
                        raise ValidationError(
                            f"Item '{item.title}' is already in a private collection ('{existing_private}') and "
                            "cannot be added to a public collection."
                        )
        return cleaned_data

