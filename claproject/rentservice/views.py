from django.shortcuts import render

# Create your views here.
import os

from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from google.oauth2 import id_token
from google.auth.transport import requests
from django.contrib.auth import login, logout
from django.contrib.auth.models import User, Group

import logging

@csrf_exempt
def sign_in(request):
    if request.user.is_authenticated:
        if request.user.groups.filter(name="Librarian").exists():
            return redirect('librarian_dashboard')
        else:
            return redirect('patron_dashboard')
    
    return render(request, 'sign_in.html')


@csrf_exempt
def auth_receiver(request):
    
    token = request.POST.get('credential')
    if not token:
        return HttpResponse("No token provided", status=400)

    try:
        user_data = id_token.verify_oauth2_token(
            token, requests.Request(), os.environ['GOOGLE_OAUTH_CLIENT_ID']
        )
    except ValueError:
        return HttpResponse("Invalid token", status=403)

    email = user_data.get("email")
    name = user_data.get("name")

    user, created = User.objects.get_or_create(username=email, defaults={"email": email, "first_name": name})

    # user is patron by default
    if created:
        patron_group, _ = Group.objects.get_or_create(name="Patron")
        user.groups.add(patron_group)

    login(request, user)

    return redirect('sign_in')


def sign_out(request):
    logout(request)
    return redirect('sign_in')


def librarian_dashboard(request):
    return render(request, "librarian_dashboard.html")


def patron_dashboard(request):
    return render(request, "patron_dashboard.html")

def textbooks(request):
    return render(request, 'collections/textbooks.html')

def calculators(request):
    return render(request, 'collections/calculators.html')

def chargers(request):
    return render(request, 'collections/chargers.html')