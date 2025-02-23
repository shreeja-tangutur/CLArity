from django.urls import path
from . import views

urlpatterns = [
    path('', views.sign_in, name='sign_in'),
    path('sign-out', views.sign_out, name='sign_out'),
    path('auth-receiver', views.auth_receiver, name='auth_receiver'),
    path('librarian-dashboard/', views.librarian_dashboard, name='librarian_dashboard'),
    path('patron-dashboard/', views.patron_dashboard, name='patron_dashboard'),
]
