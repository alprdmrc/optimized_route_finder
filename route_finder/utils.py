import googlemaps
from django.conf import settings
from route_finder.models import TruckStop
import math
import time
import traceback

TRUCK_TANK_CAPACITY = 50  # Gallons
MILES_PER_GALLON = 10
TRUCK_RANGE = TRUCK_TANK_CAPACITY * MILES_PER_GALLON

PROX_THRESHOLD = 2 # miles # higher value means more truck stops means possibly lower cost

def haversine(lat1, lon1, lat2, lon2):  # Haversine formula for distance # googlemaps' distane matrix api can be used instead
    # EXPENSIVE CALCULATION
    R = 6371  # Radius of Earth in km
    dLat = math.radians(lat2 - lat1)
    dLon = math.radians(lon2 - lon1)
    a = math.sin(dLat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c  # Distance in km
    return distance * 0.621371  # Convert to miles

def decode_polyline(encoded_polyline):
    """Decodes an encoded polyline string into a list of (lat, lng) tuples (floats)."""
    if not encoded_polyline:  # Check if polyline is empty or None
        return []  # Return an empty list if no polyline
    
    decoded_points = googlemaps.convert.decode_polyline(encoded_polyline)
    lat_lng_tuples = []
    for point in decoded_points:
        lat_lng_tuples.append((float(point['lat']), float(point['lng']))) # Convert to float here!
    return lat_lng_tuples

def is_truckstop (lat, lng, truck_stops: TruckStop):
    for truckstop in truck_stops:
        if haversine(truckstop.latitude,truckstop.longitude, lat,lng) < PROX_THRESHOLD:
            return True, truckstop
    return False, 0

def find_optimized_truck_stops_and_cum_cost(decoded_polyline):
    """Finds truck stops with proximity treshold along the route. Assume that the truck stops are exactly on the route."""
    t0 = time.time()
    truckstops = TruckStop.objects.all()
    t1 = time.time()
    print("Time taken to fetch truck stops: ", t1-t0)
    waypoints = []
    cum_distance = 0
    station_indexes = []
    for index,waypoint in enumerate(decoded_polyline):
        _waypoint = {
            'index': index,
            'lat': waypoint[0],
            'lng': waypoint[1],
        }
        is_this_truckstop, truckstop = is_truckstop(waypoint[0], waypoint[1], truckstops)
        _waypoint["is_truckstop"] = is_this_truckstop
        if(is_this_truckstop):
            _waypoint["price"] = float(truckstop.retail_price)
            _waypoint["address"] = truckstop.address
            _waypoint["name"] = truckstop.name
            station_indexes.append(index)

        if index == 0:
            distance = 0
        else:
            distance = haversine(decoded_polyline[index-1][0], decoded_polyline[index-1][1], waypoint[0], waypoint[1]) 
        cum_distance += distance
        _waypoint["distance"] = cum_distance
        waypoints.append(_waypoint)
    t2 = time.time()
    print("Time taken to find truck stops: ", t2-t1)
    # iterate over the station indexes reversly
    # use a stack to efficiently find the next cheaper station for every station
    stack = []
    for i in range(len(station_indexes)-1, -1, -1):
        current_station_index = station_indexes[i]
        current_station = waypoints[current_station_index]
        
        while len(stack) > 0 and waypoints[stack[-1]]['price'] >= current_station['price']:
            stack.pop()
        if(len(stack) == 0):
            current_station['next_cheaper_station_index'] = None 
        else :
            current_station['next_cheaper_station_index'] = stack[-1]
        stack.append(current_station_index)
    t3 = time.time()
    print("Time taken to find next cheaper station: ", t3-t2)
    fuel = TRUCK_TANK_CAPACITY
    cum_cost = 0
    for index,station_index in enumerate(station_indexes):
        station = waypoints[station_index]
        if(index == 0):
            fuel -= station["distance"] / MILES_PER_GALLON
        else:
            fuel -= (waypoints[station_index]['distance'] - waypoints[station_indexes[index-1]]['distance']) / MILES_PER_GALLON
        if(fuel<0):
            print("There are not enough truckstops on the route")
            return None,None
        station["remaining_fuel"] = fuel
        next_cheaper_station_index = station['next_cheaper_station_index']
        if(next_cheaper_station_index is None):
            if(index==len(station_indexes)-1):
                # if the last station, check if fuel is enough to reach the destination (greedy approach)
                distance = waypoints[-1]['distance'] - station['distance']
                fuel_needed = distance / MILES_PER_GALLON
                if(fuel>=fuel_needed):
                    # dont buy fuel
                    station["fuel_to_buy"] = 0
                    continue
                else:
                    # buy enough fuel to reach the destination
                    fuel_to_buy = fuel_needed - fuel
                    fuel_cost = fuel_to_buy * station['price']
                    cum_cost += fuel_cost
                    fuel+=fuel_to_buy
                    station["fuel_to_buy"] = fuel_to_buy
            else:
                # full the fuel
                fuel_to_buy = TRUCK_TANK_CAPACITY - fuel
                fuel_cost = fuel_to_buy * station['price']
                cum_cost += fuel_cost
                fuel+=fuel_to_buy
                station["fuel_to_buy"] = fuel_to_buy
                continue
        else:
            # find the distance between the stations
            distance = waypoints[next_cheaper_station_index]['distance'] - station['distance']
            is_greater_than_range = distance > TRUCK_RANGE
            if(is_greater_than_range):
                # full the fuel
                fuel_to_buy = TRUCK_TANK_CAPACITY - fuel
                fuel_cost = fuel_to_buy * station['price']
                cum_cost += fuel_cost
                fuel+=fuel_to_buy
                station["fuel_to_buy"] = fuel_to_buy
                continue
            else:
                # is fuel enough to reach the next cheaper station
                fuel_needed = distance / MILES_PER_GALLON
                if(fuel>=fuel_needed):
                    # fuel is enough dont buy any fuel
                    station["fuel_to_buy"] = 0
                    continue
                else:
                    # buy fuel
                    fuel_to_buy = fuel_needed - fuel
                    fuel_cost = fuel_to_buy * station['price']
                    cum_cost += fuel_cost
                    fuel+=fuel_to_buy
                    station["fuel_to_buy"] = fuel_to_buy
    t4 = time.time()
    print("Time taken to calculate fuel cost: ", t4-t3)
    return waypoints,cum_cost

def get_routes(start_location, end_location, alternatives=2):  # alternatives: Number of alternative routes
    """
    Gets route information from the Google Maps Directions API.

    Args:
        start_location: A string representing the starting location (e.g., "New York, NY").
        end_location: A string representing the ending location (e.g., "Los Angeles, CA").
        alternatives: The number of alternative routes to return (including the best route).

    Returns:
        A list of dictionaries, where each dictionary represents a route and contains
        information such as distance, duration, polyline (for drawing the route on a map),
        and other details.  Returns None if there's an error.
    """
    api_key = settings.GOOGLEMAPS_API_KEY 
    gmaps = googlemaps.Client(key=api_key) 

    try:
        directions_result = gmaps.directions(
            start_location,
            end_location,
            mode="driving", 
            alternatives=alternatives, # get alternative routes.
        )

        if directions_result:  # Check if the request was successful
            routes = []
            for route in directions_result:
                route_data = {
                    "distance": route["legs"][0]["distance"]["text"], 
                    "duration": route["legs"][0]["duration"]["text"],  
                    "polyline": route["overview_polyline"]["points"], 
                    "start_address": route["legs"][0]["start_address"],
                    "end_address": route["legs"][0]["end_address"],
                }
                routes.append(route_data)

            waypoints0 = decode_polyline(routes[0]["polyline"]) # assume first route is the best route
            waypoints_with_truckstops,cum_cost = find_optimized_truck_stops_and_cum_cost(waypoints0)

            return waypoints_with_truckstops,cum_cost
        else:
            return None,None  # Return None if no routes were found

    except Exception as e:  # Handle API errors
        print(f"Error getting directions: {e}")  
        traceback.print_exc()  
        return None
    

