from django.db import models

# Create your models here.
class TruckStop(models.Model):
    opis_id = models.CharField(max_length=255, unique=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=255)
    state = models.CharField(max_length=2)
    rack_id = models.CharField(max_length=255, blank=True, null=True)  # Allow nulls
    retail_price = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True) # Allow nulls
    latitude = models.FloatField(blank=True, null=True) # Add lat/lng
    longitude = models.FloatField(blank=True, null=True)

    def __str__(self):
        return self.name