#Author: Dongju Park
#Date: 2/17/2025
import uuid

from datetime import timedelta
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from typing import List

from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
    
class User(AbstractUser):
    ROLE_CHOICES = [
        ('patron', 'Patron'),
        ('librarian', 'Librarian'),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='patron')
    joined_date = models.DateTimeField(auto_now_add=True)

    def is_librarian(self):
        return self.role == 'librarian'

    def is_patron(self):
        return self.role == 'patron'


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)

class DjangoAdministrator(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

class Item(models.Model):
    title = models.CharField(max_length=255)
    identifier = models.CharField(max_length=255, unique=True)  # Can store ISBN, QR codes, barcodes
    """
    Steps:
        1. User Request: in_stock
        2. Librarian Approves + User Receives Item: in_circulation // May separate these steps later on
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
    condition = models.IntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(10)])

    tags = models.ManyToManyField(Tag, blank=True)

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

    def __str__(self):
        return self.title


class Comment(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class Rating(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="ratings")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    score = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], default=0.0)

class Collection(models.Model):
    title = models.CharField(max_length=255)
    identifier = models.CharField(max_length=255, unique=True)
    description = models.TextField()
    items = models.ManyToManyField(Item, blank=True)
    is_public = models.BooleanField(default=True)
    creator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='collections',
        null=True, 
        blank=True
    )
    
    private_users = models.ManyToManyField(User, blank=True, related_name='private_collections')

    def __str__(self):
        return self.title


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

class BorrowRequest(models.Model):
    STATUS_CHOICES = [
        ('requested', 'Requested'),
        ('approved', 'Approved'),
        ('declined', 'Declined'),
        ('returned', 'Returned'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='requested')
    timestamp = models.DateTimeField(auto_now_add=True) # When the request was first made

    borrowed_condition = models.IntegerField(null=True, blank=True)
    returned_condition = models.IntegerField(null=True, blank=True)
    borrowed_at = models.DateTimeField(null=True, blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)

    is_complete = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} requests {self.item.name}"

class CollectionAccessRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("denied", "Denied"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    collection = models.ForeignKey("Collection", on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    requested_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'collection')  # prevent duplicate requests

    def __str__(self):
        return f"{self.user.email} requests access to '{self.collection.title}'"

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)



