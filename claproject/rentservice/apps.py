from django.apps import AppConfig


class RentserviceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'claproject.claproject.rentservice'

    def ready(self):
        import claproject.rentservice.signals
