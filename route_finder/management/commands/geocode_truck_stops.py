from django.core.management.base import BaseCommand
import pandas as pd
import googlemaps
import time
from route_finder.models import TruckStop 
from django.conf import settings

class Command(BaseCommand):
    help = 'Geocodes truck stop addresses and saves them to the database.'

    def handle(self, *args, **options):
        csv_file = "truck_stops_copy.csv"
        try:
            df = pd.read_csv(csv_file)
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"File '{csv_file}' not found."))
            return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"An unexpected error occurred: {e}"))
            return
        
        api_key = settings.GOOGLEMAPS_API_KEY
        gmaps = googlemaps.Client(key=api_key)

        geocoded_count = 0
        failed_count = 0

        for index, row in df.iterrows():
            address = row['Address']
            city = row['City']
            state = row['State']
            opis_id = row.get("OPIS Truckstop ID")
            name = row.get("Truckstop Name")
            rack_id = row.get("Rack ID")
            retail_price = row.get("Retail Price")
            try:
                geocode_result = gmaps.geocode(f"{address}, {city}, {state}, USA")
                if geocode_result:
                    location = geocode_result[0]['geometry']['location']  # Get the first result
                    latitude = location['lat']
                    longitude = location['lng']
                    try:
                        TruckStop.objects.create(
                            opis_id=opis_id,
                            name=name,
                            address=address,
                            city=city,
                            state=state,
                            rack_id=rack_id,
                            retail_price=retail_price,
                            latitude=latitude,
                            longitude=longitude
                        )
                        geocoded_count += 1
                        self.stdout.write(f"Geocoded and saved successfuly: {address}, {city}, {state}")
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error saving truck stop to database: {e} for {address}, {city}, {state}"))
                        failed_count += 1
                else:
                    self.stdout.write(self.style.ERROR(f"Could not geocode: {address}, {city}, {state}"))
                    failed_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Geocoding error: {e} for {address}, {city}, {state}"))
                time.sleep(1)
                failed_count += 1

        self.stdout.write(self.style.SUCCESS('Geocoding and database update complete.'))