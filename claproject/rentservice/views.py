import os
import logging
import slugify
import openpyxl

from django.http import HttpResponse
from django.contrib import messages
from .models import Profile, User, Item, Rating, Comment
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, AnonymousUser
from .forms import CollectionForm, ItemForm, RatingCommentForm
from .models import Item, Collection, BorrowRequest
from django.db.models import Avg
from django.utils import timezone

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
    patrons = None
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
        if request.user.is_librarian():
            patrons = User.objects.filter(role='patron')

    else:
        user_type = "anonymous"

    data = get_visible_data_for_user(request.user)

    return render(request, 'dashboard/dashboard.html', {
        'user_type': user_type,
        'profile': profile,
        'items': data['items'],
        'collections': data['collections'],
        'patrons': patrons
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

@login_required
def upgrade_user(request, user_id):
    if not request.user.is_librarian():
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('dashboard')

    user = get_object_or_404(User, id=user_id)
    user.role = 'librarian'
    user.save()
    messages.success(request, f"{user.username} has been upgraded to librarian.")
    return redirect('dashboard')


def sign_out(request):
    logout(request)
    return redirect('dashboard')

def items_list(request):
    items = Item.objects.filter(deleted=False)
    return render(request, 'search/items_list.html', {'items': items})

def item_detail(request, identifier):
    item = get_object_or_404(Item, identifier=identifier)

    # Calculate rating
    ratings = item.ratings.all()
    avg_rating = round(ratings.aggregate(Avg('score'))['score__avg'] or 0, 1)

    # Comments retrieving
    recent_comments = item.comments.order_by('-created_at')[:5]

    if request.method == 'POST':
        form = RatingCommentForm(request.POST)
        if form.is_valid():
            Rating.objects.update_or_create(
                user=request.user,
                item=item,
                defaults={'score': form.cleaned_data['score']}
            )

            Comment.objects.create(
                user=request.user,
                item=item,
                text=form.cleaned_data['text']
            )

            messages.success(request, "Thanks for your rating and comment!")
            return redirect('item_detail', identifier=item.identifier)
    else:
        form = RatingCommentForm()

    return render(request, "collections/item_detail.html", {
        'item': item,
        'avg_rating': avg_rating,
        'recent_comments': recent_comments,
        'form': form
    })

def collection_detail(request, collection_title):
    visible_data = get_visible_data_for_user(request.user)
    collection = visible_data["collections"].filter(title=collection_title).first()

    if not collection:
        messages.warning(request, "You don't have permission to view this collection.")
        return redirect("dashboard")

    visible_items = collection.items.filter(id__in=visible_data["items"].values_list('id', flat=True))

    return render(request, "collections/collection_detail.html", {
        "collection": collection,
        "items": visible_items
    })

@csrf_exempt
def search_items(request):
    from django.db.models import Q

    query = request.GET.get('q', '').strip()
    item_results = []
    collection_results = []

    if request.user.is_authenticated:
        if request.user.is_librarian():
            visible_collections = Collection.objects.all()
        else:
            visible_collections = Collection.objects.all()
            visible_item_collections = Collection.objects.filter(
                Q(is_public=True) | Q(private_users=request.user)
            ).distinct()
    else:
        visible_collections = Collection.objects.filter(is_public=True)
        visible_item_collections = visible_collections

    if query:
        collection_results = visible_collections.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        ).distinct()


        if request.user.is_authenticated and request.user.is_librarian():
            item_results = Item.objects.filter(
                Q(title__icontains=query) | Q(description__icontains=query)
            ).distinct()
        else:
            items_in_visible_collections = Item.objects.filter(
                collections__in=visible_item_collections
            )
            items_without_collections = Item.objects.filter(collections=None)

            visible_items = (items_in_visible_collections | items_without_collections).distinct()

            item_results = visible_items.filter(
                Q(title__icontains=query) | Q(description__icontains=query)
            ).distinct()

    return render(request, 'search/search_results.html', {
        'query': query,
        'item_results': item_results,
        'collection_results': collection_results,
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

# Librarian view
def view_borrow_requests(request):
    if request.method == "POST":
        request_id = request.POST.get("request_id")
        action = request.POST.get("action")

        borrow_request = get_object_or_404(BorrowRequest, id=request_id)

        if action == "approve":
            borrow_request.status = "approved"
            borrow_request.item.mark_as_borrowed()
        elif action == "decline":
            borrow_request.status = "declined"

        borrow_request.save()
        return redirect("view_borrow_requests")

    requests = BorrowRequest.objects.select_related("user", "item").filter(status="requested").order_by("-timestamp")

    return render(request, "base/view_request.html", {"requests": requests})

# approve/decline handling
def respond_borrow_request(request, request_id, action):
    borrow_request = get_object_or_404(BorrowRequest, id=request_id)

    if action == 'approve':
        borrow_request.status = 'approved'
        borrow_request.borrowed_condition = borrow_request.item.condition
        borrow_request.borrowed_at = timezone.now()
        borrow_request.item.mark_as_borrowed()
        borrow_request.save()

    elif action == 'decline':
        borrow_request.status = 'declined'
        borrow_request.save()

    return redirect('view_borrow_requests')

# For Borrow Request Button
@login_required
def borrow_request(request):
    if request.method == "POST":
        item_id = request.POST.get("item")
        item = get_object_or_404(Item, pk=item_id)

        # Check if the user already has a request for this item
        existing_request = BorrowRequest.objects.filter(user=request.user, item=item).exists()
        if existing_request:
            messages.warning(request, "You have already requested this item.")
            return redirect('item_detail', identifier=item.identifier)

        BorrowRequest.objects.create(user=request.user, item=item)
        return render(request, "rentservice/borrow_request_success.html")
    return redirect("dashboard")


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
    
    return render(request, 'collections/create_item.html', {'form': form})

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

@login_required
def my_items(request):
    approved = BorrowRequest.objects.filter(user=request.user, status='approved')
    returned = BorrowRequest.objects.filter(user=request.user, status='returned')
    declined = BorrowRequest.objects.filter(user=request.user, status='declined')
    return render(request, 'base/my_items.html', {
        'currently_borrowing': approved,
        'history': returned | declined
    })

@login_required
def return_item(request, request_id):
    borrow_request = get_object_or_404(BorrowRequest, id=request_id, user=request.user, status='approved')
    borrow_request.status = 'returned'
    borrow_request.returned_at = timezone.now()
    borrow_request.returned_condition = borrow_request.item.condition
    borrow_request.item.mark_as_being_inspected()
    borrow_request.save()
    return redirect('my_items')


def main():
    for result in get_visible_data_for_user(AnonymousUser()):
        print(result)


for result in get_visible_data_for_user(AnonymousUser()):
    print(result)

