from django.shortcuts import render

# Create your views here.
from django.http import JsonResponse
from . import utils 

def get_route(request):
    # start_location = request.GET.get('start', '')
    # end_location = request.GET.get('end', '')
    start_lat = request.GET.get("start_lat","")
    start_lng = request.GET.get("start_lng","")
    end_lat = request.GET.get("end_lat","")
    end_lng = request.GET.get("end_lng","")

    if start_lat and start_lng and end_lat and end_lng:
        start_location = (start_lat,start_lng)
        end_location = (end_lat,end_lng)
        routes,cum_cost = utils.get_routes(start_location, end_location, alternatives=2)
        if routes:
            return JsonResponse({'routes': routes,"cum_cost":cum_cost}) # Return the routes and cum cost as JSON
        else:
            return JsonResponse({'error': 'No routes found.'}, status=404)    
    else:
        return JsonResponse({'error': 'Missing start or end location.'}, status=400)