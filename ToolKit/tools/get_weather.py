import os
import sys
import requests
from typing import Dict, Any
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ToolKit.base_tool import BaseTool

class GetWeatherTool(BaseTool):
    """Tool for getting weather information using Open-Meteo (no API key needed!)"""
    
    def __init__(self):
        super().__init__()
        # Default location (you can change this)
        self.default_lat = 40.7128  # NYC latitude
        self.default_lon = -74.0060  # NYC longitude
        self.default_location = "New York"
        
        # Common city coordinates
        self.cities = {
            "new york": (40.7128, -74.0060),
            "nyc": (40.7128, -74.0060),
            "los angeles": (34.0522, -118.2437),
            "la": (34.0522, -118.2437),
            "chicago": (41.8781, -87.6298),
            "houston": (29.7604, -95.3698),
            "phoenix": (33.4484, -112.0740),
            "philadelphia": (39.9526, -75.1652),
            "san antonio": (29.4241, -98.4936),
            "san diego": (32.7157, -117.1611),
            "dallas": (32.7767, -96.7970),
            "san jose": (37.3382, -121.8863),
            "austin": (30.2672, -97.7431),
            "boston": (42.3601, -71.0589),
            "seattle": (47.6062, -122.3321),
            "denver": (39.7392, -104.9903),
            "washington dc": (38.9072, -77.0369),
            "miami": (25.7617, -80.1918),
            "atlanta": (33.7490, -84.3880),
            "san francisco": (37.7749, -122.4194),
            "sf": (37.7749, -122.4194),
            "columbus": (39.9612, -82.9988),
            "columbus ohio": (39.9612, -82.9988),
            "cleveland": (41.4993, -81.6944),
            "cleveland ohio": (41.4993, -81.6944),
        }
    
    def get_name(self) -> str:
        return "get_weather"
    
    def get_description(self) -> str:
        return "Get current weather and forecast for any city. No API key needed!"
    
    def get_tool_type(self):
        """This is a retrieval tool - data needs to be fed back to LLM"""
        return "retrieval"
    
    def get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City name (e.g., 'New York', 'Los Angeles')"
                },
                "forecast_days": {
                    "type": "integer",
                    "description": "Number of forecast days (1-7)"
                }
            },
            "required": []  # All optional, will use defaults
        }
    
    def get_coordinates(self, location: str) -> tuple:
        """Get coordinates for a location"""
        if not location:
            return self.default_lat, self.default_lon, self.default_location
        
        # Clean up the location string
        location_lower = location.lower().strip()
        # Remove commas and extra spaces for matching
        location_normalized = location_lower.replace(',', '').replace('  ', ' ')
        
        # Check our city database first
        if location_normalized in self.cities:
            lat, lon = self.cities[location_normalized]
            return lat, lon, location
        
        # Also try without state name
        if location_lower in self.cities:
            lat, lon = self.cities[location_lower]
            return lat, lon, location
        
        # Try geocoding API (also free from Open-Meteo!)
        try:
            geocoding_url = "https://geocoding-api.open-meteo.com/v1/search"
            response = requests.get(geocoding_url, params={
                "name": location,
                "count": 1,
                "language": "en",
                "format": "json"
            }, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("results"):
                    result = data["results"][0]
                    return result["latitude"], result["longitude"], result["name"]
        except:
            pass
        
        # Fallback to default
        return self.default_lat, self.default_lon, self.default_location
    
    def get_weather_emoji(self, weather_code: int) -> str:
        """Convert weather code to emoji"""
        # WMO Weather interpretation codes
        weather_emojis = {
            0: "☀️",   # Clear sky
            1: "🌤️",   # Mainly clear
            2: "⛅",   # Partly cloudy
            3: "☁️",   # Overcast
            45: "🌫️",  # Foggy
            48: "🌫️",  # Rime fog
            51: "🌦️",  # Light drizzle
            53: "🌦️",  # Moderate drizzle
            55: "🌧️",  # Dense drizzle
            61: "🌦️",  # Slight rain
            63: "🌧️",  # Moderate rain
            65: "⛈️",  # Heavy rain
            71: "🌨️",  # Slight snow
            73: "❄️",   # Moderate snow
            75: "❄️",   # Heavy snow
            77: "❄️",   # Snow grains
            80: "🌦️",  # Slight rain showers
            81: "🌧️",  # Moderate rain showers
            82: "⛈️",  # Violent rain showers
            85: "🌨️",  # Slight snow showers
            86: "❄️",   # Heavy snow showers
            95: "⛈️",  # Thunderstorm
            96: "⛈️",  # Thunderstorm with hail
            99: "⛈️",  # Severe thunderstorm with hail
        }
        return weather_emojis.get(weather_code, "🌡️")
    
    def execute(self, location: str = None, forecast_days: int = 3, **kwargs) -> Dict[str, Any]:
        """Get weather information"""
        try:
            # Get coordinates
            lat, lon, location_name = self.get_coordinates(location)
            
            # Ensure forecast_days is an integer (might come as string from JSON)
            if forecast_days is not None:
                forecast_days = int(forecast_days)
            else:
                forecast_days = 3
            
            # Limit forecast days
            forecast_days = min(max(forecast_days, 1), 7)
            
            # Build API request to Open-Meteo
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
                "timezone": "auto",
                "forecast_days": forecast_days
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"Weather API returned status {response.status_code}"
                }
            
            data = response.json()
            
            # Format current weather
            current = data.get("current", {})
            daily = data.get("daily", {})
            
            # Get weather emoji
            weather_emoji = self.get_weather_emoji(current.get("weather_code", 0))
            
            # Build response
            weather_info = f"Weather for {location_name}:\n\n"
            weather_info += f"Current Conditions {weather_emoji}:\n"
            weather_info += f"  Temperature: {current.get('temperature_2m', 'N/A')}°F\n"
            weather_info += f"  Feels Like: {current.get('apparent_temperature', 'N/A')}°F\n"
            weather_info += f"  Humidity: {current.get('relative_humidity_2m', 'N/A')}%\n"
            weather_info += f"  Wind: {current.get('wind_speed_10m', 'N/A')} mph\n"
            
            # Add forecast
            if daily and daily.get("time"):
                weather_info += f"\n{forecast_days}-Day Forecast:\n"
                for i in range(min(forecast_days, len(daily["time"]))):
                    date = datetime.fromisoformat(daily["time"][i]).strftime("%a %b %d")
                    emoji = self.get_weather_emoji(daily["weather_code"][i])
                    high = daily["temperature_2m_max"][i]
                    low = daily["temperature_2m_min"][i]
                    rain_chance = daily["precipitation_probability_max"][i] if "precipitation_probability_max" in daily else 0
                    
                    weather_info += f"  {date} {emoji}: {low:.0f}°F - {high:.0f}°F"
                    if rain_chance > 0:
                        weather_info += f" (💧 {rain_chance}%)"
                    weather_info += "\n"
            
            return {
                "success": True,
                "weather": weather_info,
                "location": location_name,
                "coordinates": {"lat": lat, "lon": lon}
            }
            
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Weather API request timed out"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }