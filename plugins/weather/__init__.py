#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Weather Plugin for Jarvis Assistant

This plugin provides weather information using the OpenWeatherMap API.
It supports current weather, forecasts, and weather alerts.
"""

import os
import json
import time
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import threading

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from modules.plugins.plugin_manager import Plugin


class WeatherPlugin(Plugin):
    """Weather plugin for Jarvis Assistant"""
    
    def _initialize(self):
        """Initialize the plugin"""
        self.logger.info("Initializing weather plugin")
        
        # Check if requests is available
        if not REQUESTS_AVAILABLE:
            self.error = "The 'requests' package is required for the weather plugin"
            self.logger.error(self.error)
            return False
        
        # Get configuration
        self.api_key = self.config.get("api_key")
        self.default_location = self.config.get("default_location", "London")
        self.units = self.config.get("units", "metric")
        self.cache_time = self.config.get("cache_time", 1800)  # 30 minutes
        
        # Check if API key is provided
        if not self.api_key:
            self.error = "OpenWeatherMap API key is required"
            self.logger.error(self.error)
            return False
        
        # Initialize cache
        self.cache_dir = os.path.join("data", "plugins", "weather")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.cache_file = os.path.join(self.cache_dir, "cache.json")
        self.cache = self._load_cache()
        
        # Initialize lock for thread safety
        self.lock = threading.RLock()
        
        # Base URLs for API
        self.current_weather_url = "https://api.openweathermap.org/data/2.5/weather"
        self.forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
        self.onecall_url = "https://api.openweathermap.org/data/3.0/onecall"
        
        # Unit symbols
        self.temp_symbol = "°C" if self.units == "metric" else "°F" if self.units == "imperial" else "K"
        self.speed_symbol = "m/s" if self.units == "metric" else "mph" if self.units == "imperial" else "m/s"
        
        # Weather condition emojis
        self.weather_emojis = {
            "01": "☀️",  # clear sky
            "02": "🌤️",  # few clouds
            "03": "☁️",  # scattered clouds
            "04": "☁️",  # broken clouds
            "09": "🌧️",  # shower rain
            "10": "🌦️",  # rain
            "11": "⛈️",  # thunderstorm
            "13": "❄️",  # snow
            "50": "🌫️"   # mist
        }
        
        self.logger.info("Weather plugin initialized successfully")
        return True
    
    def _load_cache(self) -> Dict[str, Any]:
        """Load cache from file
        
        Returns:
            Cache dictionary
        """
        if not os.path.exists(self.cache_file):
            return {}
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading cache: {e}")
            return {}
    
    def _save_cache(self):
        """Save cache to file"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving cache: {e}")
    
    def _get_cached_data(self, key: str) -> Optional[Dict[str, Any]]:
        """Get data from cache
        
        Args:
            key: Cache key
            
        Returns:
            Cached data, or None if not found or expired
        """
        with self.lock:
            if key not in self.cache:
                return None
            
            cache_entry = self.cache[key]
            timestamp = cache_entry.get("timestamp", 0)
            
            # Check if cache is expired
            if time.time() - timestamp > self.cache_time:
                return None
            
            return cache_entry.get("data")
    
    def _set_cached_data(self, key: str, data: Dict[str, Any]):
        """Set data in cache
        
        Args:
            key: Cache key
            data: Data to cache
        """
        with self.lock:
            self.cache[key] = {
                "timestamp": time.time(),
                "data": data
            }
            self._save_cache()
    
    def _get_weather_emoji(self, icon_code: str) -> str:
        """Get weather emoji for icon code
        
        Args:
            icon_code: OpenWeatherMap icon code
            
        Returns:
            Weather emoji
        """
        if not icon_code or len(icon_code) < 2:
            return ""
        
        return self.weather_emojis.get(icon_code[:2], "")
    
    def _format_temperature(self, temp: float) -> str:
        """Format temperature with unit
        
        Args:
            temp: Temperature value
            
        Returns:
            Formatted temperature string
        """
        return f"{temp:.1f}{self.temp_symbol}"
    
    def _get_current_weather(self, location: str) -> Dict[str, Any]:
        """Get current weather for a location
        
        Args:
            location: Location name or coordinates
            
        Returns:
            Weather data dictionary
        """
        # Check cache first
        cache_key = f"current_{location}_{self.units}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        # Make API request
        try:
            params = {
                "q": location,
                "appid": self.api_key,
                "units": self.units
            }
            
            response = requests.get(self.current_weather_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Cache the data
            self._set_cached_data(cache_key, data)
            
            return data
        
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error getting current weather: {e}")
            return {"error": str(e)}
    
    def _get_forecast(self, location: str, days: int = 5) -> Dict[str, Any]:
        """Get weather forecast for a location
        
        Args:
            location: Location name or coordinates
            days: Number of days for forecast (max 5)
            
        Returns:
            Forecast data dictionary
        """
        # Check cache first
        cache_key = f"forecast_{location}_{self.units}_{days}"
        cached_data = self._get_cached_data(cache_key)
        if cached_data:
            return cached_data
        
        # Make API request
        try:
            params = {
                "q": location,
                "appid": self.api_key,
                "units": self.units,
                "cnt": min(days * 8, 40)  # 8 forecasts per day, max 40 (5 days)
            }
            
            response = requests.get(self.forecast_url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Cache the data
            self._set_cached_data(cache_key, data)
            
            return data
        
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error getting forecast: {e}")
            return {"error": str(e)}
    
    def _format_current_weather(self, data: Dict[str, Any]) -> str:
        """Format current weather data for display
        
        Args:
            data: Weather data dictionary
            
        Returns:
            Formatted weather string
        """
        if "error" in data:
            return f"Error: {data['error']}"
        
        try:
            # Extract data
            location = data.get("name", "Unknown")
            country = data.get("sys", {}).get("country", "")
            temp = data.get("main", {}).get("temp", 0)
            feels_like = data.get("main", {}).get("feels_like", 0)
            humidity = data.get("main", {}).get("humidity", 0)
            pressure = data.get("main", {}).get("pressure", 0)
            wind_speed = data.get("wind", {}).get("speed", 0)
            wind_direction = data.get("wind", {}).get("deg", 0)
            clouds = data.get("clouds", {}).get("all", 0)
            weather = data.get("weather", [{}])[0]
            description = weather.get("description", "Unknown")
            icon = weather.get("icon", "")
            emoji = self._get_weather_emoji(icon)
            
            # Format output
            output = f"Current weather for {location}, {country}:\n"
            output += f"{emoji} {description.capitalize()}\n"
            output += f"Temperature: {self._format_temperature(temp)} (feels like {self._format_temperature(feels_like)})\n"
            output += f"Humidity: {humidity}%\n"
            output += f"Pressure: {pressure} hPa\n"
            output += f"Wind: {wind_speed} {self.speed_symbol} ({self._get_wind_direction(wind_direction)})\n"
            output += f"Clouds: {clouds}%"
            
            return output
        
        except Exception as e:
            self.logger.error(f"Error formatting current weather: {e}")
            return "Error formatting weather data"
    
    def _format_forecast(self, data: Dict[str, Any]) -> str:
        """Format forecast data for display
        
        Args:
            data: Forecast data dictionary
            
        Returns:
            Formatted forecast string
        """
        if "error" in data:
            return f"Error: {data['error']}"
        
        try:
            # Extract data
            location = data.get("city", {}).get("name", "Unknown")
            country = data.get("city", {}).get("country", "")
            forecasts = data.get("list", [])
            
            if not forecasts:
                return "No forecast data available"
            
            # Group forecasts by day
            days = {}
            for forecast in forecasts:
                dt = datetime.fromtimestamp(forecast.get("dt", 0))
                day = dt.strftime("%Y-%m-%d")
                
                if day not in days:
                    days[day] = []
                
                days[day].append(forecast)
            
            # Format output
            output = f"Weather forecast for {location}, {country}:\n\n"
            
            for day, day_forecasts in days.items():
                dt = datetime.strptime(day, "%Y-%m-%d")
                day_name = dt.strftime("%A")
                
                # Get min/max temperature for the day
                temps = [f.get("main", {}).get("temp", 0) for f in day_forecasts]
                min_temp = min(temps) if temps else 0
                max_temp = max(temps) if temps else 0
                
                # Get most common weather condition for the day
                conditions = [f.get("weather", [{}])[0].get("description", "") for f in day_forecasts]
                condition = max(set(conditions), key=conditions.count) if conditions else "Unknown"
                
                # Get icon for the most common condition
                icons = [f.get("weather", [{}])[0].get("icon", "") for f in day_forecasts]
                icon = max(set(icons), key=icons.count) if icons else ""
                emoji = self._get_weather_emoji(icon)
                
                output += f"{day_name}: {emoji} {condition.capitalize()}, "
                output += f"{self._format_temperature(min_temp)} to {self._format_temperature(max_temp)}\n"
            
            return output
        
        except Exception as e:
            self.logger.error(f"Error formatting forecast: {e}")
            return "Error formatting forecast data"
    
    def _get_wind_direction(self, degrees: float) -> str:
        """Convert wind direction in degrees to cardinal direction
        
        Args:
            degrees: Wind direction in degrees
            
        Returns:
            Cardinal direction
        """
        directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                      "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        index = round(degrees / 22.5) % 16
        return directions[index]
    
    def get_commands(self) -> Dict[str, Dict[str, Any]]:
        """Get commands provided by the plugin
        
        Returns:
            Dictionary of command names to command metadata
        """
        return {
            "weather": {
                "description": "Get current weather for a location",
                "usage": "weather [location]",
                "examples": ["weather", "weather London", "weather New York"],
                "args": {
                    "location": {
                        "description": "Location to get weather for (default: configured default location)",
                        "required": False,
                        "type": "string"
                    }
                }
            },
            "forecast": {
                "description": "Get weather forecast for a location",
                "usage": "forecast [location] [days]",
                "examples": ["forecast", "forecast London", "forecast New York 3"],
                "args": {
                    "location": {
                        "description": "Location to get forecast for (default: configured default location)",
                        "required": False,
                        "type": "string"
                    },
                    "days": {
                        "description": "Number of days for forecast (max 5, default: 5)",
                        "required": False,
                        "type": "integer"
                    }
                }
            }
        }
    
    def execute_command(self, command: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a command
        
        Args:
            command: Command name
            args: Command arguments
            
        Returns:
            Command result
        """
        if command == "weather":
            location = args.get("location", self.default_location)
            data = self._get_current_weather(location)
            formatted = self._format_current_weather(data)
            
            return {
                "success": "error" not in data,
                "result": formatted,
                "data": data
            }
        
        elif command == "forecast":
            location = args.get("location", self.default_location)
            days = args.get("days", 5)
            
            # Validate days
            try:
                days = int(days)
                days = max(1, min(days, 5))  # Limit to 1-5 days
            except (ValueError, TypeError):
                days = 5
            
            data = self._get_forecast(location, days)
            formatted = self._format_forecast(data)
            
            return {
                "success": "error" not in data,
                "result": formatted,
                "data": data
            }
        
        else:
            return {
                "success": False,
                "error": f"Unknown command: {command}"
            }
    
    def get_intents(self) -> Dict[str, List[str]]:
        """Get intents provided by the plugin
        
        Returns:
            Dictionary of intent names to example phrases
        """
        return {
            "get_weather": [
                "What's the weather like?",
                "What's the weather like in London?",
                "How's the weather today?",
                "Is it raining outside?",
                "What's the temperature in New York?",
                "Tell me the weather forecast",
                "Will it rain tomorrow?",
                "What's the weather going to be like this weekend?"
            ]
        }
    
    def handle_intent(self, intent: str, entities: Dict[str, Any], text: str) -> Dict[str, Any]:
        """Handle an intent
        
        Args:
            intent: Intent name
            entities: Extracted entities
            text: Original text
            
        Returns:
            Intent handling result
        """
        if intent == "get_weather":
            # Extract location from entities or text
            location = None
            
            # Check for location entity
            if "location" in entities:
                location = entities["location"]
            
            # Check for forecast keywords
            forecast_keywords = ["forecast", "tomorrow", "next week", "weekend", "days"]
            is_forecast = any(keyword in text.lower() for keyword in forecast_keywords)
            
            if is_forecast:
                # Handle forecast intent
                days = 5
                
                # Try to extract number of days
                if "days" in entities:
                    try:
                        days = int(entities["days"])
                        days = max(1, min(days, 5))  # Limit to 1-5 days
                    except (ValueError, TypeError):
                        pass
                
                return self.execute_command("forecast", {
                    "location": location or self.default_location,
                    "days": days
                })
            else:
                # Handle current weather intent
                return self.execute_command("weather", {
                    "location": location or self.default_location
                })
        
        return {
            "success": False,
            "error": f"Unknown intent: {intent}"
        }
    
    def get_hooks(self) -> Dict[str, List[str]]:
        """Get hooks provided by the plugin
        
        Returns:
            Dictionary of hook names to event types
        """
        return {
            "weather_alert": ["startup", "daily", "weather_change"]
        }
    
    def handle_hook(self, hook: str, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a hook
        
        Args:
            hook: Hook name
            event_type: Event type
            data: Event data
            
        Returns:
            Hook handling result
        """
        if hook == "weather_alert":
            if event_type == "startup":
                # Check for severe weather on startup
                location = self.default_location
                weather_data = self._get_current_weather(location)
                
                # Check for severe weather conditions
                alerts = self._check_for_alerts(weather_data)
                
                if alerts:
                    return {
                        "success": True,
                        "alerts": alerts,
                        "notification": {
                            "title": "Weather Alert",
                            "message": "\n".join(alerts),
                            "level": "warning"
                        }
                    }
                
                return {"success": True, "alerts": []}
            
            elif event_type == "daily":
                # Daily weather summary
                location = self.default_location
                weather_data = self._get_current_weather(location)
                forecast_data = self._get_forecast(location, 1)
                
                # Format summary
                summary = self._format_daily_summary(weather_data, forecast_data)
                
                return {
                    "success": True,
                    "summary": summary,
                    "notification": {
                        "title": "Daily Weather Summary",
                        "message": summary,
                        "level": "info"
                    }
                }
            
            elif event_type == "weather_change":
                # Handle weather change event
                return {"success": True}
        
        return {"success": False, "error": f"Unknown hook or event type: {hook}/{event_type}"}
    
    def _check_for_alerts(self, weather_data: Dict[str, Any]) -> List[str]:
        """Check for severe weather conditions
        
        Args:
            weather_data: Weather data dictionary
            
        Returns:
            List of alert messages
        """
        alerts = []
        
        if "error" in weather_data:
            return alerts
        
        try:
            # Check for extreme temperatures
            temp = weather_data.get("main", {}).get("temp", 0)
            if self.units == "metric" and temp > 35:
                alerts.append(f"Extreme heat alert: {self._format_temperature(temp)}")
            elif self.units == "metric" and temp < -10:
                alerts.append(f"Extreme cold alert: {self._format_temperature(temp)}")
            elif self.units == "imperial" and temp > 95:
                alerts.append(f"Extreme heat alert: {self._format_temperature(temp)}")
            elif self.units == "imperial" and temp < 14:
                alerts.append(f"Extreme cold alert: {self._format_temperature(temp)}")
            
            # Check for severe weather conditions
            weather_id = weather_data.get("weather", [{}])[0].get("id", 0)
            
            # Thunderstorm
            if 200 <= weather_id < 300:
                alerts.append("Thunderstorm alert")
            
            # Heavy rain
            if weather_id in [502, 503, 504, 522, 531]:
                alerts.append("Heavy rain alert")
            
            # Heavy snow
            if weather_id in [602, 622]:
                alerts.append("Heavy snow alert")
            
            # Tornado
            if weather_id == 781:
                alerts.append("Tornado alert")
            
            # Strong wind
            wind_speed = weather_data.get("wind", {}).get("speed", 0)
            if (self.units == "metric" and wind_speed > 20) or \
               (self.units == "imperial" and wind_speed > 45):
                alerts.append(f"Strong wind alert: {wind_speed} {self.speed_symbol}")
        
        except Exception as e:
            self.logger.error(f"Error checking for alerts: {e}")
        
        return alerts
    
    def _format_daily_summary(self, weather_data: Dict[str, Any], forecast_data: Dict[str, Any]) -> str:
        """Format daily weather summary
        
        Args:
            weather_data: Current weather data dictionary
            forecast_data: Forecast data dictionary
            
        Returns:
            Formatted summary string
        """
        if "error" in weather_data or "error" in forecast_data:
            return "Unable to generate weather summary"
        
        try:
            # Extract current weather data
            location = weather_data.get("name", "Unknown")
            country = weather_data.get("sys", {}).get("country", "")
            temp = weather_data.get("main", {}).get("temp", 0)
            description = weather_data.get("weather", [{}])[0].get("description", "Unknown")
            icon = weather_data.get("weather", [{}])[0].get("icon", "")
            emoji = self._get_weather_emoji(icon)
            
            # Extract forecast data for today
            forecasts = forecast_data.get("list", [])
            today_forecasts = []
            tomorrow_forecasts = []
            
            if forecasts:
                today = datetime.now().strftime("%Y-%m-%d")
                tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
                
                for forecast in forecasts:
                    dt = datetime.fromtimestamp(forecast.get("dt", 0))
                    day = dt.strftime("%Y-%m-%d")
                    
                    if day == today:
                        today_forecasts.append(forecast)
                    elif day == tomorrow:
                        tomorrow_forecasts.append(forecast)
            
            # Format summary
            summary = f"Good morning! Here's your daily weather summary for {location}, {country}:\n\n"
            summary += f"Currently: {emoji} {description.capitalize()}, {self._format_temperature(temp)}\n\n"
            
            # Add today's forecast
            if today_forecasts:
                temps = [f.get("main", {}).get("temp", 0) for f in today_forecasts]
                min_temp = min(temps) if temps else 0
                max_temp = max(temps) if temps else 0
                
                conditions = [f.get("weather", [{}])[0].get("description", "") for f in today_forecasts]
                condition = max(set(conditions), key=conditions.count) if conditions else "Unknown"
                
                icons = [f.get("weather", [{}])[0].get("icon", "") for f in today_forecasts]
                icon = max(set(icons), key=icons.count) if icons else ""
                emoji = self._get_weather_emoji(icon)
                
                summary += f"Today: {emoji} {condition.capitalize()}, "
                summary += f"{self._format_temperature(min_temp)} to {self._format_temperature(max_temp)}\n"
            
            # Add tomorrow's forecast
            if tomorrow_forecasts:
                temps = [f.get("main", {}).get("temp", 0) for f in tomorrow_forecasts]
                min_temp = min(temps) if temps else 0
                max_temp = max(temps) if temps else 0
                
                conditions = [f.get("weather", [{}])[0].get("description", "") for f in tomorrow_forecasts]
                condition = max(set(conditions), key=conditions.count) if conditions else "Unknown"
                
                icons = [f.get("weather", [{}])[0].get("icon", "") for f in tomorrow_forecasts]
                icon = max(set(icons), key=icons.count) if icons else ""
                emoji = self._get_weather_emoji(icon)
                
                summary += f"Tomorrow: {emoji} {condition.capitalize()}, "
                summary += f"{self._format_temperature(min_temp)} to {self._format_temperature(max_temp)}"
            
            return summary
        
        except Exception as e:
            self.logger.error(f"Error formatting daily summary: {e}")
            return "Unable to generate weather summary"
    
    def shutdown(self):
        """Shutdown the plugin"""
        self.logger.info("Shutting down weather plugin")
        
        # Save cache
        self._save_cache()