import os
import uuid
import logging
import slugify
import openpyxl

from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from .models import Profile, User, Item, Rating, Comment, Notification, Tag
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, AnonymousUser
from .forms import CollectionForm, ItemForm, RatingCommentForm
from .models import Item, Collection, BorrowRequest, CollectionAccessRequest
from django.db.models import Avg, Q, Count
from django.utils import timezone

from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login

# Views are structured in the following sections:
# 1. Authentication & User Management
# 2. Dashboard
# 3. Item & Collection Views
# 4. Cart System
# 5. Renting System
# 6. Request System

# ---------------- Authentication & User Management -----------------

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

def sign_out(request):
    logout(request)
    return redirect('dashboard')

@login_required
def profile(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        if 'profile_picture' in request.FILES:
            profile.profile_picture = request.FILES['profile_picture']

        visible_name = request.POST.get('visible_name')
        if visible_name is not None:
            profile.visible_name = visible_name

        profile.save()
        return redirect('profile')

    return render(request, 'base/profile.html', {'profile': profile})



# ------------------ DASHBOARD ------------------

def dashboard(request):
    profile = None
    patrons = None
    if request.user.is_authenticated:
        profile, _ = Profile.objects.get_or_create(user=request.user)

        if request.method == 'POST' and 'profile_picture' in request.FILES:
            profile.profile_picture = request.FILES['profile_picture']
            profile.save()
            return redirect('dashboard')

        user_type = request.user.role
        if request.user.is_librarian():
            patrons = User.objects.filter(role='patron')

    else:
        user_type = "anonymous"

    data = get_visible_data_for_user(request.user)

    if request.user.is_authenticated and request.user.role == 'patron':
        collections = Collection.objects.all()  # Include private
    else:
        collections = data['collections']

    return render(request, 'dashboard/dashboard.html', {
        'user_type': user_type,
        'profile': profile,
        'items': data['items'],
        'collections': collections,
        'patrons': patrons,
        "has_unread": has_unread_notifications(request.user),
    })


def get_visible_data_for_user(user):
    public_collections = Collection.objects.filter(is_public=True)

    if not user.is_authenticated:
        visible_collections = public_collections
        visible_items = Item.objects.filter(
            Q(collections__isnull=True) |
            Q(collections__in=public_collections)
        ).distinct()

    elif user.role == 'patron':
        private_collections_shared = Collection.objects.filter(is_public=False, private_users=user)
        visible_collections = (public_collections | private_collections_shared).distinct()

        visible_items = Item.objects.filter(
            Q(collections__isnull=True) |
            Q(collections__in=public_collections) |
            Q(collections__in=private_collections_shared)
        ).distinct()

    elif user.role == 'librarian':
        visible_collections = Collection.objects.all()
        visible_items = Item.objects.all()

    return {
        "collections": visible_collections,
        "items": visible_items
    }

# ----------------Item & Collection View ------------------

def items_list(request):
    items = Item.objects.filter(deleted=False)
    return render(request, 'search/items_list.html', {'items': items})

@login_required
def get_available_items(request):
    is_public = request.GET.get('is_public') == 'true'

    if is_public:
        private_item_ids = Item.objects.filter(
            collections__is_public=False
        ).values_list('id', flat=True)
        items = Item.objects.exclude(id__in=private_item_ids)
    else:
        items = Item.objects.filter(collections__isnull=True)

    return JsonResponse({
        'items': [{'id': item.id, 'title': item.title} for item in items]
    })

@login_required
def item_detail(request, identifier):
    item = get_object_or_404(Item, identifier=identifier)

    ratings = item.ratings.all()
    avg_rating = round(ratings.aggregate(Avg('score'))['score__avg'] or 0, 1)
    recent_comments = item.comments.order_by('-created_at')[:5]

    for comment in recent_comments:
        user_rating = ratings.filter(user=comment.user).first()
        comment.user_score = user_rating.score if user_rating else 0

    existing_rating = item.ratings.filter(user=request.user).first()
    existing_comment = item.comments.filter(user=request.user).first()

    if request.method == 'POST':
        if existing_rating and existing_comment:
            messages.error(request, "You have already submitted a review for this item.")
            return redirect('item_detail', identifier=item.identifier)

        form = RatingCommentForm(request.POST)
        if form.is_valid():
            Rating.objects.update_or_create(
                user=request.user,
                item=item,
                defaults={'score': form.cleaned_data['score']}
            )
            text = form.cleaned_data['text']
            if text:
                Comment.objects.create(
                    user=request.user,
                    item=item,
                    text=text
                )
            messages.success(request, "Thanks for your rating and comment!")
            return redirect('item_detail', identifier=item.identifier)
    else:
        form = RatingCommentForm()

    return render(request, "collections/item_detail.html", {
        'item': item,
        'avg_rating': avg_rating,
        'recent_comments': recent_comments,
        'form': form,
        'existing_comment': existing_comment,
    })


@login_required
def edit_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id, user=request.user)
    item = comment.item

    if request.method == 'POST':
        new_text = request.POST.get('text', '').strip()
        new_score = request.POST.get('score')
        if new_text and new_score:
            comment.text = new_text
            comment.save()
            Rating.objects.update_or_create(
                user=request.user,
                item=item,
                defaults={'score': int(new_score)}
            )
            messages.success(request, "Your comment and rating were updated.")
        return redirect('item_detail', identifier=item.identifier)


@login_required
def delete_review(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id, user=request.user)
    item = comment.item

    Rating.objects.filter(user=request.user, item=item).delete()
    comment.delete()

    messages.success(request, "Your review has been deleted.")
    return redirect('item_detail', identifier=item.identifier)

def collection_detail(request, slug):
    try:
        collection = Collection.objects.get(slug=slug)
    except Collection.DoesNotExist:
        messages.warning(request, "Collection not found.")
        return redirect("dashboard")

    if not collection.is_public:
        if not request.user.is_authenticated or \
           (request.user.role == 'patron' and request.user not in collection.private_users.all()) or \
           (request.user.role != 'librarian' and request.user.role != 'patron'):
            messages.warning(request, "You don't have permission to view this collection.")
            return redirect("dashboard")

    visible_items = collection.items.all()

    return render(request, "collections/collection_detail.html", {
        "collection": collection,
        "items": visible_items
    })


@login_required
def catalog_manager(request):
    if not request.user.is_librarian():
        return redirect('dashboard')

    items = Item.objects.all()
    collections = Collection.objects.all()
    return render(request, 'base/catalog_manager.html', {
        'items': items,
        'collections': collections
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
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(tags__name__icontains=query)  
            ).distinct()

        else:
            items_in_visible_collections = Item.objects.filter(
                collections__in=visible_item_collections
            )
            items_without_collections = Item.objects.filter(collections__isnull=True)

            visible_items = (items_in_visible_collections | items_without_collections).distinct()

            item_results = visible_items.filter(
                Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(tags__name__icontains=query)  
            ).distinct()


    return render(request, 'search/search_results.html', {
        'query': query,
        'item_results': item_results,
        'collection_results': collection_results,
    })

@login_required
def create_item(request):
    if request.method == "POST":
        form = ItemForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            item = form.save(commit=False)
            item.identifier = str(uuid.uuid4())
            item.save()

            tag_string = form.cleaned_data.get('tags', '')
            tag_names = [name.strip() for name in tag_string.split(',') if name.strip()]
            tags = [Tag.objects.get_or_create(name=name)[0] for name in tag_names]
            item.tags.set(tags)
            item.collections.set(form.cleaned_data.get('collections', []))

            messages.success(request, "Item created successfully!")
            return redirect('item_detail', identifier=item.identifier)
    else:
        form = ItemForm(user=request.user)

    collection_field = form.fields['collections']
    collection_objects = collection_field.queryset
    collection_widgets = form['collections']
    collection_pairs = zip(collection_objects, collection_widgets)

    return render(request, 'collections/create_item.html', {
        'form': form,
        'collection_pairs': collection_pairs,
    })

@login_required
def edit_item(request, item_id):
    item = get_object_or_404(Item, id=item_id)

    if request.method == 'POST':
        form = ItemForm(request.POST, request.FILES, instance=item, user=request.user)
        if form.is_valid():
            item = form.save()
            item.collections.clear()
            selected_collections = form.cleaned_data.get('collections')
            for collection in selected_collections:
                collection.items.add(item)

            messages.success(request, "Item updated successfully.")
            return redirect("catalog_manager")
    else:
        form = ItemForm(instance=item, user=request.user)

    all_collections = form.fields['collections'].queryset
    selected_collection_ids = set(item.collections.values_list('id', flat=True))
    collection_pairs = [
        {
            "collection": collection,
            "id": f"id_collections_{i}",
            "value": collection.pk,
            "selected": collection.pk in selected_collection_ids
        }
        for i, collection in enumerate(all_collections)
    ]

    return render(request, "collections/edit_item.html", {
        "form": form,
        "item": item,
        "collection_pairs": collection_pairs,
    })

@login_required
def delete_item(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    if request.method == "POST":
        item.delete()
        messages.success(request, "Item deleted successfully.")
        return redirect("catalog_manager")
    return render(request, "collections/delete_item.html", {"item": item})

@login_required
def create_collection(request):
    if request.method == 'POST':
        form = CollectionForm(request.POST, user=request.user)
        if form.is_valid():
            collection = form.save(commit=False)
            collection.identifier = str(uuid.uuid4())

            if not request.user.is_librarian():
                collection.is_public = True

            collection.save()
            form.save_m2m()
            messages.success(request, "Collection created successfully!")
            return redirect('collection_detail',slug=collection.slug)
    else:
        form = CollectionForm(user=request.user)

    return render(request, 'collections/create_collection.html', {'form': form})


@login_required
def edit_collection(request, identifier):
    collection = get_object_or_404(Collection, identifier=identifier)

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
            return redirect('collection_detail', slug=updated_collection.slug)
    else:
        form = CollectionForm(user=request.user, instance=collection)

    return render(request, 'collections/edit_collection.html', {
        'form': form,
        'collection': collection
    })


@login_required
def delete_collection(request, identifier):
    collection = get_object_or_404(Collection, identifier=identifier)

    # Optionally, only the librarian or the collection creator can delete
    if not request.user.is_librarian() and request.user != collection.creator:
        messages.error(request, "You do not have permission to delete this collection.")
        return redirect('dashboard')

    if request.method == 'POST':
        collection.delete()
        messages.success(request, "Collection deleted successfully!")
        return redirect('dashboard')

    return render(request, 'collections/delete_collection.html', {
        'collection': collection
    })

# ---------------- Cart system ------------------

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

    messages.success(request, f"'{item.title}' has been added to your cart!")
    
    return redirect('item_detail', identifier=item.identifier)



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
def empty_cart(request):
    """
    Empties the user's session-based cart.
    """
    request.session['cart'] = []
    
    from django.contrib import messages
    messages.success(request, "Your cart has been emptied.")
    
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
    if request.method == "POST":
        cart = request.session.get('cart', [])
        items = Item.objects.filter(id__in=cart)
        
        for item in items:
            BorrowRequest.objects.create(
                user=request.user,
                item=item,
                status='requested'
            )

        request.session['cart'] = []

        return render(request, "rentservice/borrow_request_success.html", {"items": items})
    else:
        cart = request.session.get('cart', [])
        items = Item.objects.filter(id__in=cart)
        return render(request, 'cart/checkout.html', {'items': items})



# ---------------- Renting system ------------------

@login_required
def borrow_request(request):
    if request.method == "POST":
        item_id = request.POST.get("item")
        item = get_object_or_404(Item, pk=item_id)

        # Prevent duplicate active request
        existing_request = BorrowRequest.objects.filter(
            user=request.user,
            item=item,
            is_complete=False
        ).exists()

        if existing_request:
            messages.warning(request, "You have already requested or are currently borrowing this item.")
            return redirect('item_detail', identifier=item.identifier)

        BorrowRequest.objects.create(user=request.user, item=item, status='requested')
        return render(request, "rentservice/borrow_request_success.html")

    return redirect("dashboard")

@login_required
def view_borrow_requests(request):
    if request.method == "POST":
        request_id = request.POST.get("request_id")
        action = request.POST.get("action")

        borrow_request = get_object_or_404(BorrowRequest, id=request_id)

        if action == "approve":
            borrow_request.status = "approved"
            borrow_request.borrowed_condition = borrow_request.item.condition
            borrow_request.borrowed_at = timezone.now()
            borrow_request.is_complete = False  # Still active
            borrow_request.item.mark_as_borrowed()

            Notification.objects.create(
                user=borrow_request.user,
                message=f"Your borrow request for '{borrow_request.item.title}' has been approved!"
            )

        elif action == "decline":
            borrow_request.status = "declined"
            borrow_request.is_complete = True  # Done

            Notification.objects.create(
                user=borrow_request.user,
                message=f"Your borrow request for '{borrow_request.item.title}' has been declined."
            )

        borrow_request.save()
        return redirect("view_borrow_requests")

    requests = BorrowRequest.objects.select_related("user", "item").filter(status="requested").order_by("-request_date")
    return render(request, "base/view_request.html", {"requests": requests})

@login_required
def respond_borrow_request(request, request_id, action):
    borrow_request = get_object_or_404(BorrowRequest, id=request_id)

    if action == 'approve':
        borrow_request.status = 'approved'
        borrow_request.borrowed_condition = borrow_request.item.condition
        borrow_request.borrowed_at = timezone.now()
        borrow_request.is_complete = False
        borrow_request.item.mark_as_borrowed()
        message = f"Your borrow request for '{borrow_request.item.title}' was approved!"

    elif action == 'decline':
        borrow_request.status = 'declined'
        borrow_request.is_complete = True
        message = f"Your borrow request for '{borrow_request.item.title}' was declined!"

    borrow_request.save()
    Notification.objects.create(user=borrow_request.user, message=message)
    return redirect('view_borrow_requests')

@login_required
def my_items(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    currently_borrowing = BorrowRequest.objects.filter(
        user=request.user,
        status='approved',
        item__status='in_circulation'
    ).select_related("item")

    history = BorrowRequest.objects.filter(
        user=request.user,
        status__in=['returned', 'declined']
    ).select_related("item")

    return render(request, 'base/my_items.html', {
        'currently_borrowing': currently_borrowing,
        'history': history
    })

# Notification
@login_required
def notifications(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)

    user_notifications = request.user.notifications.order_by('-created_at')
    has_unread = has_unread_notifications(request.user)
    return render(request, "base/notifications.html", {
        "notifications": user_notifications,
        "has_unread": has_unread,
    })

def has_unread_notifications(user):
    if user.is_authenticated:
        return Notification.objects.filter(user=user, is_read=False).exists()
    return False
# Notification

@login_required
def return_item(request, request_id):
    borrow_request = get_object_or_404(BorrowRequest, id=request_id, user=request.user, status='approved')
    borrow_request.status = 'returned'
    borrow_request.returned_at = timezone.now()
    borrow_request.returned_condition = None  # Let librarian input later in QA
    borrow_request.is_complete = False
    borrow_request.item.mark_as_being_inspected()
    borrow_request.item.save()
    borrow_request.save()
    return redirect('my_items')

@login_required
def quality_assurance(request):
    if not request.user.is_librarian():
        return redirect("dashboard")

    if request.method == "POST":
        request_id = request.POST.get("request_id")
        returned_condition = request.POST.get("returned_condition")
        try:
            borrow_request = BorrowRequest.objects.get(id=request_id)
            condition = int(returned_condition)
            if 1 <= condition <= 10:
                borrow_request.returned_condition = condition
                borrow_request.save()
            else:
                messages.warning(request, "Returned condition must be between 1 and 10.")
        except Exception as e:
            messages.error(request, f"Failed to update condition: {e}")
        return redirect("quality_assurance")

    returned_requests = BorrowRequest.objects.filter(
        status="returned",
        is_complete=False,
        returned_condition__isnull=True
    ).select_related("item")

    seen_item_ids = set()
    passed_qc = []
    needs_repair = []

    post_condition_requests = BorrowRequest.objects.filter(
        status="returned",
        is_complete=False,
        returned_condition__isnull=False
    ).select_related("item")

    for req in post_condition_requests:
        item = req.item
        if item.id in seen_item_ids or item.status != "being_inspected":
            continue
        seen_item_ids.add(item.id)

        if req.returned_condition >= 6:
            passed_qc.append(item)
        else:
            needs_repair.append(item)

    return render(request, "base/quality_assurance.html", {
        "returned_requests": returned_requests,
        "passed_qc": passed_qc,
        "needs_repair": needs_repair,
    })

@login_required
def mark_item_repaired(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    item.mark_as_available()
    BorrowRequest.objects.filter(item=item, status="returned", is_complete=False).update(is_complete=True)
    return redirect('quality_assurance')

@login_required
def mark_item_available(request, item_id):
    item = get_object_or_404(Item, id=item_id)
    if item.status == "being_inspected":
        item.mark_as_available()
        BorrowRequest.objects.filter(item=item, status="returned", is_complete=False).update(is_complete=True)
    return redirect("quality_assurance")

# ---------------- Request system ------------------

@login_required
def request_access(request, collection_id):
    collection = get_object_or_404(Collection, id=collection_id)

    already_approved = collection.private_users.filter(id=request.user.id).exists()
    existing_request = CollectionAccessRequest.objects.filter(user=request.user, collection=collection).first()

    if already_approved:
        messages.info(request, "You already have access to this collection.")

    elif existing_request:
        if existing_request.status == "pending":
            messages.info(request, "You already have a pending access request.")
        elif existing_request.status == "approved":
            messages.info(request, "Access already approved.")
        elif existing_request.status == "denied":
            existing_request.delete()
            CollectionAccessRequest.objects.create(
                user=request.user,
                collection=collection,
                status="pending"
            )
            messages.success(request, "Your access request has been resubmitted.")
            
    else:
        CollectionAccessRequest.objects.create(
            user=request.user,
            collection=collection,
            status="pending"
        )
        messages.success(request, "Access request submitted.")

    return redirect("dashboard")


@login_required
def access_requests(request):
    if not request.user.is_librarian():
        return redirect('dashboard')

    patrons = User.objects.filter(role='patron')
    access_requests = CollectionAccessRequest.objects.select_related('user', 'collection').filter(status='pending')

    return render(request, "base/access_requests.html", {
        "patrons": patrons,
        "access_requests": access_requests
    })

@login_required
def handle_access_request(request, request_id):
    if not request.user.is_librarian():
        return redirect("dashboard")

    action = request.POST.get("action")
    access_request = get_object_or_404(CollectionAccessRequest, id=request_id)

    if action == "approve":
        access_request.status = "approved"
        access_request.collection.private_users.add(access_request.user)
    elif action == "deny":
        access_request.status = "denied"

    access_request.save()
    return redirect("access_requests")

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