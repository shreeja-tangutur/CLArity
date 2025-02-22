from django.urls import path
from . import views

urlpatterns = [
    path('rent/', views.rent_item, name='rent_item'),
    path('rental_success/', views.rental_success, name='rental_success'),
]
