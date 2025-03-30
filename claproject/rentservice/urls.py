from django.urls import path, include
from . import views

urlpatterns = [
    # Log-in
    path('accounts/', include('allauth.urls')),
    path('', views.dashboard, name='dashboard'),
    path('anonymous-home/', views.anonymous_home, name='anonymous_home'),
    path('sign-out/', views.sign_out, name='sign_out'),

    # Cart
    path('cart/', views.view_cart, name='cart'),
    path('cart/add/<int:item_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('browse/', views.anonymous_home, name='anonymous_home'),

    # Search & Result
    path('search/', views.search_items, name='search_items'),
    path('collection/<slug:collection_slug>/', views.collection_detail, name='collection_detail'),
    path('search/<slug:search_slug>/', views.search_items, name='search_results'),
    path('item/<str:identifier>/', views.item_detail, name='item_detail'),

    # Temporary
    path('upload-xlsx/', views.upload_xlsx, name='upload_xlsx'),
    path('items/', views.items_list, name='items_list'),

    # Menu
    path('profile/', views.dashboard, name='profile'),
    path('settings/', views.setting, name='setting'),
]