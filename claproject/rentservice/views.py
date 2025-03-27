from django.shortcuts import render

# Create your views here.
import os
import logging

from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from google.oauth2 import id_token
from google.auth.transport import requests
from django.contrib.auth import login, logout
from django.contrib.auth.models import Group
from .models import Profile, User
from .models import Profile, Item
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required


from .models import Item, Collection
from django.db.models import Q 


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

def anonymous_home(request):
    public_collections = Collection.objects.filter(is_public=True)
    items_not_in_any_collection = Item.objects.filter(collections=None)
    items_in_public_collection = Item.objects.filter(collections__in=public_collections)

    visible_to_user = (items_not_in_any_collection | items_in_public_collection).distinct()
    return render(request, "anonymous_home.html", {
        "collections": public_collections, 
        "items": visible_to_user
    })

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

def patron_dashboard_view(request):
    profile = Profile.objects.get(user=request.user)

    if request.method == 'POST':
        print("📢 Form submitted!")  # Debugging print

        if 'profile_picture' in request.FILES:
            profile_picture = request.FILES['profile_picture']
            print(f"📢 Received file: {profile_picture.name}")  # Debugging print

            profile.profile_picture = profile_picture
            profile.save()

            print("✅ Profile picture updated!")
            return redirect('patron_dashboard')
        else:
            print("❌ No file received in request.FILES!")

    return render(request, 'patron_dashboard.html', {'profile': profile})


@csrf_exempt
def search_items(request):
    query = request.GET.get('q', '')  
    results = []

    if query:
        results = Item.objects.filter(title__icontains=query)
    return render(request, 'search_results.html', {
        'query': query,
        'results': results
    })

def patron_dashboard_view(request):
    profile = Profile.objects.get(user=request.user)

    if request.method == 'POST' and request.FILES.get('profile_picture'):
        profile_picture = request.FILES['profile_picture']
        
        profile.profile_picture = profile_picture
        profile.save()

        return redirect('patron_dashboard')  # Redirect to the dashboard to see the updated picture

    return render(request, 'patron_dashboard.html', {'profile': profile})

@login_required
def add_to_cart(request, item_id):
    """
    Adds the specified Item to the user's session-based cart.
    """
    item = get_object_or_404(Item, id=item_id)

    # Get current cart from session; if none, create empty list
    cart = request.session.get('cart', [])

    # Convert IDs to strings if you prefer
    # If you only want to store unique items, check first
    if item_id not in cart:
        cart.append(item_id)

    request.session['cart'] = cart
    return redirect('cart')  # or wherever you want to go after adding


@login_required
def remove_from_cart(request, item_id):
    """
    Removes the specified Item from the user's session-based cart.
    """
    cart = request.session.get('cart', [])
    if item_id in cart:
        cart.remove(item_id)
        request.session['cart'] = cart
    return redirect('cart')


@login_required
def view_cart(request):
    """
    Displays the items currently in the session-based cart.
    """
    cart = request.session.get('cart', [])
    # Retrieve actual Item objects from the IDs
    items = Item.objects.filter(id__in=cart)

    return render(request, 'cart.html', {'items': items})


@login_required
def checkout(request):
    """
    Example checkout view that clears the cart.
    Later, you can create BorrowRequests or other records here.
    """
    cart = request.session.get('cart', [])
    items = Item.objects.filter(id__in=cart)

    # Example: create BorrowRequests, or do other logic
    # for item in items:
    #     BorrowRequest.objects.create(user=request.user, item=item, status='pending')

    # Clear the cart after processing
    request.session['cart'] = []

    return render(request, 'checkout.html', {'items': items})