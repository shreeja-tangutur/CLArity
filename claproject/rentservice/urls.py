from django.urls import path
from . import views

urlpatterns = [
    path('', views.sign_in, name='sign_in'),
    path('sign-out', views.sign_out, name='sign_out'),
    path('auth-receiver', views.auth_receiver, name='auth_receiver'),
    path('librarian-dashboard/', views.librarian_dashboard, name='librarian_dashboard'),
    path('patron-dashboard/', views.patron_dashboard, name='patron_dashboard'),
    path('textbooks/', views.textbooks, name= 'textbooks'), 
    path('calculators/', views.calculators, name = 'calculators'),
    path('chargers/', views.chargers, name = 'chargers'),
    path('search/', views.search_items, name='search_items'),
    path('cart/', views.view_cart, name='cart'),
    path('cart/add/<int:item_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('browse/', views.anonymous_home, name='anonymous_home'),


    # Collection & Search
    path('collection/<slug:collection_slug>/', views.collection_detail, name='collection_detail'),
    path('search/<slug:search_slug>/', views.search_results, name='search_results'),

    # Item Detail
    path('item/<str:identifier>/', views.item_detail, name='item_detail'),

    # Process the search form
    path('process-search/', views.process_search, name='process_search'),

]
