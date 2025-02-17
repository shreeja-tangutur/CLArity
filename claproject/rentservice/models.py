#Author: Dongju Park
#Date: 2/17/2025
from datetime import timedelta

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from typing import List

from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLE_CHOICES = [
        ('patron', 'Patron'),
        ('librarian', 'Librarian'),
        # Anonymous user is not stored inside the database
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='patron')
    google_account = models.EmailField(unique=True)  # Have to implement Google API
    joined_date = models.DateTimeField(auto_now_add=True)

    def is_librarian(self):
        return self.role == 'librarian'

class DjangoAdministrator(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)


class Item(models.Model):
    title = models.CharField(max_length=255)
    identifier = models.CharField(max_length=255, unique=True)  # Can store ISBN, QR codes, barcodes
    """
    Steps:
        1. User Request: in_stock
        2. Librarian Approves + User Receives Item: in_circulation // May seperate these steps later on
        3. User Returns: inspection
            3-1. Librarian Process return: in_stock
            3-2. Item Needs Repair: being_repaired
                3-2-2 Item is Restored: in_stock
    """
    STATUS_CHOICES = [
        ('available', 'Is Available'),
        ('inspection', 'Being Inspected'),
        ('in_circulation', 'In Circulation'),
        ('being_repaired', 'Being Repaired'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_stock')
    location = models.CharField(max_length=255)
    description = models.TextField()
    image = models.ImageField(upload_to='items/', null=True, blank=True)
    rating = models.FloatField(default=0.0, validators=[MinValueValidator(1), MaxValueValidator(5)])
    borrow_period_days = models.PositiveIntegerField(default=30)

    collections = models.ManyToManyField('Collection', blank=True)
    deleted = models.BooleanField(default=False)

    def mark_as_available(self):
        self.status = 'available'
        self.save()

    def mark_as_being_inspected(self):
        self.status = 'being_inspected'
        self.save()

    def mark_as_being_repaired(self):
        self.status = 'being_repaired'
        self.save()

    def mark_as_borrowed(self):
        self.status = 'in_circulation'
        self.save()

    def delete(self, *args, **kwargs):
        if self.image:
            self.image.delete(save=False)
        super().delete(*args, **kwargs)


class Comment(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

class Rating(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    value = models.FloatField(default=0.0, validators=[MinValueValidator(1), MaxValueValidator(5)])
    timestamp = models.DateTimeField(auto_now_add=True)


class Collection(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    items = models.ManyToManyField(Item, blank=True)
    is_public = models.BooleanField(default=True)
    private_users = models.ManyToManyField(User, blank=True, related_name='private_collections')

    def can_user_access(self, user):
        """
        Determines if a given user can access this collection.
        - Librarians can always access collections.
        - Patrons can access public collections.
        - Patrons need to be in `private_users` for private collections.
        """
        if user.is_librarian():
            return True
        if self.is_public:
            return True
        return self.private_users.filter(id=user.id).exists()


class Library(models.Model):
    name = models.CharField(max_length=255, unique=True)
    collections = models.ManyToManyField(Collection, blank=True)
    items = models.ManyToManyField(Item, blank=True)

class BorrowRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('denied', 'Denied'),
        ('returned', 'Returned'),
    ]
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    request_date = models.DateTimeField(auto_now_add=True)
    approved_date = models.DateTimeField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    return_date = models.DateField(null=True, blank=True)

    def approve(self):
        if self.status == 'pending' and self.item.status == 'available':
            self.status = 'approved'
            self.approved_date = timezone.now()
            self.due_date = timezone.now().date() + timedelta(days=self.item.borrow_period_days)
            self.item.status = 'in_circulation'
            self.item.save()
            self.save()

    def deny(self):
        if self.status == 'pending':
            self.status = 'denied'
            self.save()

    def return_item(self): #May have to separate the return to other request
        if self.status == 'approved':
            self.status = 'returned'
            self.return_date = timezone.now().date()
            self.item.status = 'being_inspected'
            self.item.save()
            self.save()

