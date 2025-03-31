import os
import logging
import slugify
import openpyxl

from django.http import HttpResponse
from django.contrib import messages
from .models import Profile, User, Item
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from allauth.account.views import LogoutView

from .models import Item, Collection

def google_login_callback(request):
    # Assuming user has been authenticated via Google
    user = request.user  # Get the logged-in user

    # Check if the user already exists and has a role
    if not hasattr(user, 'role') or not user.role:
        # Assign 'patron' role by default if not set
        user.role = 'patron'
        user.save()

    # Assign the user to the correct group based on their role
    if user.role == 'librarian':
        librarian_group, _ = Group.objects.get_or_create(name="Librarian")
        user.groups.add(librarian_group)
    else:
        patron_group, _ = Group.objects.get_or_create(name="Patron")
        user.groups.add(patron_group)

    login(request, user)

    # Redirect to the dashboard
    return redirect('dashboard')

@login_required
def dashboard(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST' and 'profile_picture' in request.FILES:
        print("📨 POST form submitted")
        profile_picture = request.FILES['profile_picture']
        print(f"📷 File received: {profile_picture.name}")
        profile.profile_picture = profile_picture
        profile.save()
        print("✅ Profile picture saved!")
        return redirect('dashboard')

    return render(request, 'dashboard/dashboard.html', {
        'user_type': request.user.role,
        'profile': profile,
        'visible_item': get_visible_items_for_user(request.user),
    })

def get_visible_items_for_user(user):
    public_collections = Collection.objects.filter(is_public=True)
    private_collections = Collection.objects.filter(is_public=False)
    items_not_in_any_collection = Item.objects.filter(collections=None)
    items_in_public_collection = Item.objects.filter(collections__in=public_collections)

    visible_collections = public_collections
    visible_items = (items_not_in_any_collection | items_in_public_collection).distinct()

    if user.is_authenticated and user.role == 'patron':
        visible_collections = public_collections | private_collections
        visible_items = (items_not_in_any_collection | items_in_public_collection).distinct()

    elif user.is_authenticated and user.role == 'librarian':
        visible_collections = Collection.objects.all()
        visible_items = Item.objects.all()

    return {
        "collections": visible_collections.distinct(),
        "items": visible_items.distinct(),
    }


def sign_out(request):
    logout(request)
    return redirect('dashboard')

def items_list(request):
    items = Item.objects.filter(deleted=False)
    return render(request, 'search/items_list.html', {'items': items})

def item_detail(request, identifier):
    item = get_object_or_404(Item, identifier=identifier)
    return render(request, "collections/item_detail.html", {"item": item})

def collection_detail(request, collection_slug):
    collections = {
        'textbooks': {
            'title': 'Textbooks',
            'description': 'Browse through a wide range of textbooks available for rent, covering all subjects and majors.',
            'image': 'images/textbook.jpg',
        },
        'calculators': {
            'title': 'Calculators',
            'description': 'Need a calculator for your exams or projects? Check out our collection of scientific and graphing calculators.',
            'image': 'images/calculator.jpg',
        },
        'chargers': {
            'title': 'Chargers',
            'description': 'Find any charger from phone chargers to laptop chargers.',
            'image': 'images/charger.jpg',
        },
    }

    collection = collections.get(collection_slug)
    if not collection:
        return render(request, '404.html', status=404)

    items = Item.objects.filter(collections__title__iexact=collection['title'])

    return render(request, 'collections/collection_detail.html', {
        'collection': collection,
        'items': items,
        'slug': collection_slug
    })


# def patron_dashboard_view(request):
#     profile = Profile.objects.get(user=request.user)
#
#     if request.method == 'POST':
#         print("📢 Form submitted!")  # Debugging print
#
#         if 'profile_picture' in request.FILES:
#             profile_picture = request.FILES['profile_picture']
#             print(f"📢 Received file: {profile_picture.name}")  # Debugging print
#
#             profile.profile_picture = profile_picture
#             profile.save()
#
#             print("✅ Profile picture updated!")
#             return redirect('patron_dashboard')
#         else:
#             print("❌ No file received in request.FILES!")
#
#     return render(request, '_patron_dashboard.html', {'profile': profile})

@csrf_exempt
def search_items(request):
    query = request.GET.get('q', '')
    results = []

    if query:
        results = Item.objects.filter(title__icontains=query)
    return render(request, 'search/search_results.html', {
        'query': query,
        'results': results
    })

# def patron_dashboard_view(request):
#     profile = Profile.objects.get(user=request.user)
#
#     if request.method == 'POST' and request.FILES.get('profile_picture'):
#         profile_picture = request.FILES['profile_picture']
#
#         profile.profile_picture = profile_picture
#         profile.save()
#
#         return redirect('patron_dashboard')  # Redirect to the dashboard to see the updated picture
#
#     return render(request, '_patron_dashboard.html', {'profile': profile})


@login_required
def profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST' and 'profile_picture' in request.FILES:
        print("📨 Upload submitted!")
        profile.profile_picture = request.FILES['profile_picture']
        profile.save()
        print("✅ Profile picture updated.")
        return redirect('profile')

    return render(request, 'base/profile.html', {'profile': profile})


def setting(request):
    return render(request, 'base/setting.html')

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

    return render(request, 'cart/cart.html', {'items': items})


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

    return render(request, 'cart/checkout.html', {'items': items})

def upload_xlsx(request):
    if request.method == 'POST' and request.FILES.get('xlsx_file'):
        xlsx_file = request.FILES['xlsx_file']
        try:
            wb = openpyxl.load_workbook(xlsx_file)
            ws = wb.active
        except Exception as e:
            messages.error(request, f"Error reading XLSX file: {e}")
            return render(request, 'base/upload.html')

        # Read the first row as headers
        headers = []
        for cell in next(ws.iter_rows(min_row=1, max_row=1)):
            headers.append(str(cell.value).strip() if cell.value else "")

        for row in ws.iter_rows(min_row=2, values_only=True):
            data = dict(zip(headers, row))
            identifier = data.get("identifier")
            title = data.get("title", "")
            description = data.get("description", "")
            location = data.get("location", "")
            status = data.get("status", "available")
            try:
                rating = float(data.get("rating", 0))
            except (TypeError, ValueError):
                rating = 0.0
            try:
                borrow_period_days = int(data.get("borrow_period_days", 30))
            except (TypeError, ValueError):
                borrow_period_days = 30
            try:
                condition = int(data.get("condition", 10))
            except (TypeError, ValueError):
                condition = 10

            if not identifier:
                messages.error(request, "Identifier missing for a row; skipping it.")
                continue

            try:
                item, created = Item.objects.get_or_create(
                    identifier=identifier,
                    defaults={
                        'title': title,
                        'description': description,
                        'location': location,
                        'status': status if status in dict(Item.STATUS_CHOICES) else 'available',
                        'rating': rating,
                        'borrow_period_days': borrow_period_days,
                        'condition': condition,
                    }
                )
                if not created:
                    item.title = title
                    item.description = description
                    item.location = location
                    if status in dict(Item.STATUS_CHOICES):
                        item.status = status
                    item.rating = rating
                    item.borrow_period_days = borrow_period_days
                    item.condition = condition
                    item.save()

                collections_str = data.get("collections", "")
                if collections_str:
                    collection_names = [name.strip() for name in collections_str.split(",") if name.strip()]
                    for col_name in collection_names:
                        collection_obj, _ = Collection.objects.get_or_create(title=col_name)
                        item.collections.add(collection_obj)
            except Exception as e:
                messages.error(request, f"Error processing item with identifier {identifier}: {e}")
                continue

        messages.success(request, "XLSX data uploaded successfully!")
        return redirect('items_list')
    return render(request, 'base/upload.html')
