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
    path('checkout/', views.checkout, name='checkout'),

    # Search & Result
    path('search/', views.search_items, name='search_items'),
    path('collection/<str:collection_title>/', views.collection_detail, name='collection_detail'),
    path('item/<str:identifier>/', views.item_detail, name='item_detail'),

    # Temporary
    path('upload-xlsx/', views.upload_xlsx, name='upload_xlsx'),
    path('items/', views.items_list, name='items_list'),

    # Menu
    path('profile/', views.profile, name='profile'),
    path('settings/', views.setting, name='setting'),

    path('items/create/', views.create_item, name='create_item'),
    path('collections/create/', views.create_collection, name='create_collection'),
    path('collections/<int:pk>/edit/', views.edit_collection, name='edit_collection'),
    path('collections/<int:pk>/delete/', views.delete_collection, name='delete_collection'),

    path('upgrade-user/<int:user_id>/', views.upgrade_user, name='upgrade_user'),

]