import logging
import requests
import numpy as np
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import render_template, jsonify
from flask import current_app as app

# AppSheet configuration
APPSHEET_APP_ACESS_KEY = "V2-KLYht-jOMHZ-33hfr-K0sCr-siVnO-KA55Z-Lyvxc-fiWHL"
APPSHEET_API_KEY = "kS0op-icEVh-KJCd9-5WyTB-tLavx-M1JQk-jFBcN-Edz6U"
APPSHEET_APP_ID = 'e908dc7d-71b5-4698-9456-a0a4df62531e'
APPSHEET_TABLE = 'Table 1'

# Daylight hours check configuration
MAURITIUS_LAT = -20.21863
MAURITIUS_LNG = 57.50339

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Location definitions
LOCATIONS = {
    'Le Bocage': {'lat': -20.2, 'lng': 57.5},
    'Curepipe': {'lat': -20.3162, 'lng': 57.5166},
    'Mahebourg': {'lat': -20.4081, 'lng': 57.7},
    'Henrietta': {'lat': -20.2344, 'lng': 57.4761},
    'Bambous': {'lat': -20.2667, 'lng': 57.4000},
    'Triolet': {'lat': -20.0589, 'lng': 57.5506},
    'Laventure': {'lat': -20.1667, 'lng': 57.6667},
    'Queen Victoria': {'lat': -20.2167, 'lng': 57.4833},
    'Bel Air Riviere Sèche': {'lat': -20.2583, 'lng': 57.7500},
    'Cap Malheureux': {'lat': -19.9833, 'lng': 57.6167},
    'Le Morne': {'lat': -20.4500, 'lng': 57.3167}
}

def get_solar_wind_data():
    url = "https://services.swpc.noaa.gov/products/solar-wind/plasma-5-minute.json"
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception("Failed to fetch solar wind data")
    
    solar_wind_data = response.json()
    last_data = next(data for data in reversed(solar_wind_data) 
                     if all(data[i].replace('.', '', 1).isdigit() for i in [1, 2, 3]))
    
    return {
        'density': float(last_data[1]),
        'speed': float(last_data[2]),
        'temperature': float(last_data[3])
    }

def get_weather_data(location):
    api_url = f"https://www.meteosource.com/api/v1/free/point?place_id={location}&sections=all&timezone=UTC&language=en&units=metric&key=u7mmlfv3tjgmk0c1lqj28ls7cv5xmtip7z3c"
    response = requests.get(api_url)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch weather data for {location}")
    return response.json()

def calculate_power_metrics(solar_wind_data, cloud_cover):
    power_output_above_clouds = (np.log((solar_wind_data['density'] * 
                                        solar_wind_data['speed'] * 
                                        solar_wind_data['temperature']) / 3) * 10) - 100
    power_output_on_ground = power_output_above_clouds * (1 - cloud_cover / 100)
    power_loss = power_output_above_clouds - power_output_on_ground
    
    return {
        'power_output_above_clouds': power_output_above_clouds,
        'power_output_on_ground': power_output_on_ground,
        'power_loss': power_loss
    }

def is_daylight_hours():
    sunrise_sunset_url = f"https://api.sunrisesunset.io/json?lat={MAURITIUS_LAT}&lng={MAURITIUS_LNG}"
    try:
        response = requests.get(sunrise_sunset_url)
        if response.status_code == 200:
            data = response.json()
            sunrise = datetime.strptime(data['results']['sunrise'], "%I:%M:%S %p").time()
            sunset = datetime.strptime(data['results']['sunset'], "%I:%M:%S %p").time()
            now = datetime.now(ZoneInfo("Indian/Mauritius")).time()
            return sunrise <= now <= sunset
        return True  # Default to allowing access if API fails
    except Exception:
        return True  # Default to allowing access if there's an error

def save_to_appsheet(data):
    # Check if it's daylight hours
    if not is_daylight_hours():
        logger.info(f"[SKIPPED] Location {data.get('location', 'unknown')}: Not saving data during nighttime hours")
        return False

    url = f"https://api.appsheet.com/api/v2/apps/{APPSHEET_APP_ID}/tables/{APPSHEET_TABLE}/Action"
    headers = {
        'applicationAccessKey': APPSHEET_APP_ACESS_KEY,
        'Content-Type': 'application/json'
    }
    
    payload = {
        "Action": "Add",
        "Properties": {
            "Locale": "en-US",
            "TimeZone": "Indian/Mauritius"
        },
        "Rows": [data]
    }
    
    location = data.get('location', 'unknown')
    logger.info(f"Attempting to save data for location {location}")
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            logger.info(f"[SUCCESS] Location {location}: Successfully saved data to AppSheet")
            logger.info(f"[SUCCESS] Location {location}: AppSheet Response: {response.text}")
            return True
        else:
            logger.error(f"[FAILED] Location {location}: Failed to save data to AppSheet")
            logger.error(f"[FAILED] Location {location}: Status Code {response.status_code}")
            logger.error(f"[FAILED] Location {location}: Response Text: {response.text}")
            logger.error(f"[FAILED] Location {location}: Payload: {json.dumps(payload, indent=2)}")
            return False
    except Exception as e:
        logger.error(f"[ERROR] Location {location}: Error saving to AppSheet: {str(e)}")
        logger.error(f"[ERROR] Location {location}: Payload that failed: {json.dumps(payload, indent=2)}")
        return False

def register_routes(app):
    @app.route("/")
    def home_route():
        return render_template("home.html")
    
    @app.route("/api/solar-data")
    def solar_data():
        try:
            solar_wind_data = get_solar_wind_data()
            results = {}
            timestamp = datetime.utcnow().isoformat()
            
            for location in LOCATIONS:
                try:
                    weather_data = get_weather_data(location)
                    cloud_cover = weather_data['current']['cloud_cover']
                    is_fallback = False
                except Exception as e:
                    logger.error(f"Weather API error for {location}: {str(e)}")
                    cloud_cover = 50  # Default cloud cover value
                    is_fallback = True
                
                power_metrics = calculate_power_metrics(solar_wind_data, cloud_cover)
                
                # Determine status based on power output
                if is_fallback:
                    status = "unknown"
                elif power_metrics['power_output_on_ground'] > 70:
                    status = "optimal"
                elif power_metrics['power_output_on_ground'] > 40:
                    status = "normal"
                else:
                    status = "low"
                
                results[location] = {
                    'cloud_cover': cloud_cover,
                    'is_fallback': is_fallback,
                    'status': status,
                    **power_metrics
                }
                
                # Save data to AppSheet
                # Create unique ID combining timestamp and location
                unique_id = f"{timestamp}_{location.replace(' ', '_')}"
                appsheet_data = {
                    'ID': unique_id,
                    'datetime': timestamp,
                    'location': location,
                    'cloud_cover': cloud_cover,
                    'power_output_above_clouds': power_metrics['power_output_above_clouds'],
                    'power_output_on_ground': power_metrics['power_output_on_ground'],
                    'status': status,
                    'solar_power_status': status,  # Assuming this is the same as 'status'
                    'is_fallback': is_fallback
                }
                save_to_appsheet(appsheet_data)
            
            return jsonify(results)
            
        except Exception as e:
            logger.error(f"Error in solar_data route: {str(e)}")
            return jsonify({'error': 'Failed to fetch solar power data'}), 500