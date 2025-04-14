from django.urls import path, include
from . import views

urlpatterns = [
    # Log-in
    path('', views.dashboard, name='dashboard'),
    path('accounts/', include('allauth.urls')),
    path('login/', views.login_view, name='login'),
    path('sign-out/', views.sign_out, name='sign_out'),

    # Cart
    path('cart/', views.view_cart, name='cart'),
    path('cart/add/<int:item_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('cart/empty/', views.empty_cart, name='empty_cart'),
    path('checkout/', views.checkout, name='checkout'),
    

    # Search & Result
    path('search/', views.search_items, name='search_items'),
    path('collection/<str:collection_title>/', views.collection_detail, name='collection_detail'),
    path('item/<str:identifier>/', views.item_detail, name='item_detail'),

    # Temporary
    path('items/', views.items_list, name='items_list'),

    # Menu
    path('profile/', views.profile, name='profile'),
    path('settings/', views.setting, name='setting'),
    path('my-items/', views.my_items, name='my_items'),
    path("quality-assurance/", views.quality_assurance, name="quality_assurance"),
    path('access-requests/', views.access_requests, name='access_requests'),
    path("handle-access-request/<int:request_id>/", views.handle_access_request, name="handle_access_request"),
    path("request-access/<int:collection_id>/", views.request_access, name="request_access"),
    path('catalog-manager/', views.catalog_manager, name='catalog_manager'),

    # Quality Check & Repair
    path("mark-available/<int:item_id>/", views.mark_item_available, name="mark_item_available"),
    path("mark-repaired/<int:item_id>/", views.mark_item_repaired, name="mark_item_repaired"),

    # Return
    path("return-item/<int:request_id>/", views.return_item, name="return_item"),

    # Item-Collection CRUD
    path('items/create/', views.create_item, name='create_item'),
    path('items/<int:item_id>/edit/', views.edit_item, name='edit_item'),
    path('items/<int:item_id>/delete/', views.delete_item, name='delete_item'),
    path('collections/create/', views.create_collection, name='create_collection'),
    path('collections/<str:identifier>/edit/', views.edit_collection, name='edit_collection'),
    path('collections/<str:identifier>/delete/', views.delete_collection, name='delete_collection'),

    # Borrow Request
    path("borrow/", views.borrow_request, name="borrow_request"),
    path("view-requests/", views.view_borrow_requests, name="view_borrow_requests"),  # only to librarians

    # Upgrade User
    path('upgrade-user/<int:user_id>/', views.upgrade_user, name='upgrade_user'),

    # Notification
    path("notifications/", views.notifications, name="notifications")


]