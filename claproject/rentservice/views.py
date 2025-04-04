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
from django.contrib.auth.models import Group, AnonymousUser
from allauth.account.views import LogoutView
from .forms import CollectionForm
from .forms import ItemForm
from .models import Item, Collection

from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('dashboard')
    else:
        form = AuthenticationForm()

    return render(request, 'account/login.html', {'form': form})

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

def dashboard(request):
    profile = None

    if request.user.is_authenticated:
        profile, _ = Profile.objects.get_or_create(user=request.user)

        if request.method == 'POST' and 'profile_picture' in request.FILES:
            print("📨 POST form submitted")
            profile_picture = request.FILES['profile_picture']
            print(f"📷 File received: {profile_picture.name}")
            profile.profile_picture = profile_picture
            profile.save()
            print("✅ Profile picture saved!")
            return redirect('dashboard')

        user_type = request.user.role
    else:
        user_type = "anonymous"

    data = get_visible_data_for_user(request.user)

    return render(request, 'dashboard/dashboard.html', {
        'user_type': user_type,
        'profile': profile,
        'items': data['items'],
        'collections': data['collections'],
    })


def get_visible_data_for_user(user):

    # print("🧪 DEBUG: user =", user)
    # print("🧪 DEBUG: is_authenticated =", user.is_authenticated)
    # print("🧪 DEBUG: user.role =", getattr(user, 'role', '❌ No role'))

    public_collections = Collection.objects.filter(is_public=True)
    private_collections = Collection.objects.filter(is_public=False)

    items_not_in_any_collection = Item.objects.filter(collections=None)
    items_in_public_collections = Item.objects.filter(collections__in=public_collections)

    if not user.is_authenticated:
        visible_collections = public_collections
        visible_items = (items_not_in_any_collection | items_in_public_collections).distinct()

    elif user.role == 'patron':
        visible_collections = (public_collections | private_collections).distinct()
        visible_items = (items_not_in_any_collection | items_in_public_collections).distinct()

    elif user.role == 'librarian':
        visible_collections = Collection.objects.all()
        visible_items = Item.objects.all()

    return {
        "collections": visible_collections,
        "items": visible_items
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

def collection_detail(request, collection_title):
    collection = get_object_or_404(Collection, title=collection_title)
    items = collection.items.all()
    return render(request, 'collections/collection_detail.html', {
        'collection': collection,
        'items': items
    })

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
def create_item(request):
    if not request.user.is_librarian():
        messages.error(request, "Only librarians can add new items.")
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = ItemForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save()  # Save the new item to the database
            messages.success(request, "Item created successfully!")
            # Redirect to a detail page or list page for the item
            return redirect('item_detail', identifier=item.identifier)
    else:
        form = ItemForm()
    
    return render(request, 'items/create_item.html', {'form': form})

@login_required
def create_collection(request):
    if request.method == 'POST':
        form = CollectionForm(request.POST, user=request.user)
        if form.is_valid():
            collection = form.save(commit=False)
            
            if not request.user.is_librarian():
                collection.is_public = True

            collection.save()
            form.save_m2m()  
            messages.success(request, "Collection created successfully!")
            return redirect('collection_detail', collection_title=collection.title)
    else:
        form = CollectionForm(user=request.user)
    
    return render(request, 'collections/create_collection.html', {'form': form})

@login_required
def edit_collection(request, pk):
    # pk is the primary key of the Collection
    collection = get_object_or_404(Collection, pk=pk)

    # Optionally, only allow the creator or any librarian to edit
    if not request.user.is_librarian() and request.user != collection.creator:
        messages.error(request, "You do not have permission to edit this collection.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = CollectionForm(request.POST, user=request.user, instance=collection)
        if form.is_valid():
            updated_collection = form.save(commit=False)
            
            # Patron cannot make a collection private
            if request.user.is_patron():
                updated_collection.is_public = True

            updated_collection.save()
            form.save_m2m()
            messages.success(request, "Collection updated successfully!")
            return redirect('collection_detail', collection_title=updated_collection.title)
    else:
        form = CollectionForm(user=request.user, instance=collection)

    return render(request, 'collections/edit_collection.html', {
        'form': form,
        'collection': collection
    })

@login_required
def delete_collection(request, pk):
    collection = get_object_or_404(Collection, pk=pk)

    # Optionally, only the librarian or the collection creator can delete
    if not request.user.is_librarian() and request.user != collection.creator:
        messages.error(request, "You do not have permission to delete this collection.")
        return redirect('dashboard')

    if request.method == 'POST':
        collection.delete()
        messages.success(request, "Collection deleted successfully!")
        return redirect('dashboard')

    return render(request, 'collections/confirm_delete_collection.html', {
        'collection': collection
    })


@login_required
def add_to_cart(request, item_id):
    """
    Adds the specified Item to the user's session-based cart.
    """
    item = get_object_or_404(Item, id=item_id)

    cart = request.session.get('cart', [])

    
    if item_id not in cart:
        cart.append(item_id)

    request.session['cart'] = cart
    return redirect('cart')  

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

        headers = [str(cell.value).strip().lower() if cell.value else "" for cell in next(ws.iter_rows(min_row=1, max_row=1))]

        for row in ws.iter_rows(min_row=2, values_only=True):
            data = dict(zip(headers, row))

            identifier = data.get("identifier", "")
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

def main():
    for result in get_visible_data_for_user(AnonymousUser()):
        print(result)


for result in get_visible_data_for_user(AnonymousUser()):
    print(result)