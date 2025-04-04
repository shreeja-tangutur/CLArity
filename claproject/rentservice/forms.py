from django import forms
from .models import BorrowRequest
from .models import Item, Collection
from django.core.exceptions import ValidationError


class BorrowRequestForm(forms.ModelForm):
    class Meta:
        model = BorrowRequest
        fields = ['item'] 


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = [
            'title', 
            'identifier',
            'status',
            'location',
            'description',
            'image',
            # 'rating',
            'borrow_period_days',
            # 'condition',
        ]

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
        # If the user is not a librarian, they can only create public collections.
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

