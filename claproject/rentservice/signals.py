from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, Profile
from django.contrib.auth.models import Group
from allauth.socialaccount.signals import social_account_added
from django.dispatch import receiver
from django.contrib.auth import get_user_model

'''
@receiver(social_account_added)
def social_account_added_handler(request, sociallogin, **kwargs):
    """
    Assign the user to a 'Patron' group after their Google login
    and set the default 'role' if not already assigned.
    """
    user = sociallogin.user

    # Set default 'patron' role if it's not already assigned
    if not user.role:
        user.role = 'patron'
        user.save()

    # Assign the user to the Patron group (if not already in it)
    patron_group, _ = Group.objects.get_or_create(name="Patron")
    if not user.groups.filter(name="Patron").exists():
        user.groups.add(patron_group)'
'''

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()
