#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Web Services for Jarvis Assistant

This module handles the web-related capabilities of the Jarvis assistant,
including web search, API integration, and information retrieval.
"""

import os
import json
import logging
import time
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
import re

# Import for HTTP requests
try:
    import requests
    from requests.exceptions import RequestException
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Import for HTML parsing
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

# Import for geocoding
try:
    import geopy.geocoders
    from geopy.geocoders import Nominatim
    GEOPY_AVAILABLE = True
except ImportError:
    GEOPY_AVAILABLE = False


class WebServices:
    """Web services for Jarvis Assistant"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the web services
        
        Args:
            config: Configuration dictionary for web services settings
        """
        self.logger = logging.getLogger("jarvis.web")
        self.config = config
        
        # Set up web services configuration
        self.enabled = config.get("enable_web_services", True)
        self.cache_dir = os.path.join("data", "web_cache")
        self.cache_expiry = config.get("cache_expiry", 3600)  # seconds
        self.user_agent = config.get("user_agent", "Jarvis Assistant/1.0")
        
        # API keys
        self.api_keys = config.get("api_keys", {})
        
        # Create cache directory
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Initialize HTTP session
        self.session = None
        if REQUESTS_AVAILABLE and self.enabled:
            self.session = requests.Session()
            self.session.headers.update({"User-Agent": self.user_agent})
        
        # Initialize geocoder
        self.geocoder = None
        if GEOPY_AVAILABLE and self.enabled:
            try:
                self.geocoder = Nominatim(user_agent=self.user_agent)
            except Exception as e:
                self.logger.error(f"Error initializing geocoder: {e}")
        
        self.logger.info(f"Web services initialized (enabled: {self.enabled})")
    
    def _get_cache_path(self, cache_key: str) -> str:
        """Get cache file path for a cache key
        
        Args:
            cache_key: Cache key
            
        Returns:
            Path to cache file
        """
        # Sanitize cache key to create a valid filename
        safe_key = re.sub(r'[^a-zA-Z0-9_-]', '_', cache_key)
        return os.path.join(self.cache_dir, f"{safe_key}.json")
    
    def _get_from_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get data from cache
        
        Args:
            cache_key: Cache key
            
        Returns:
            Cached data, or None if not found or expired
        """
        cache_path = self._get_cache_path(cache_key)
        
        if not os.path.exists(cache_path):
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # Check if cache is expired
            if "timestamp" in cache_data:
                cache_time = datetime.fromisoformat(cache_data["timestamp"])
                if (datetime.now() - cache_time).total_seconds() > self.cache_expiry:
                    # Cache expired
                    return None
            
            return cache_data.get("data")
        
        except Exception as e:
            self.logger.error(f"Error reading from cache: {e}")
            return None
    
    def _save_to_cache(self, cache_key: str, data: Any) -> bool:
        """Save data to cache
        
        Args:
            cache_key: Cache key
            data: Data to cache
            
        Returns:
            True if successful, False otherwise
        """
        cache_path = self._get_cache_path(cache_key)
        
        try:
            cache_data = {
                "timestamp": datetime.now().isoformat(),
                "data": data
            }
            
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error saving to cache: {e}")
            return False
    
    def search_web(self, query: str, num_results: int = 5, use_cache: bool = True) -> List[Dict[str, Any]]:
        """Search the web for information
        
        Args:
            query: Search query
            num_results: Number of results to return
            use_cache: Whether to use cached results
            
        Returns:
            List of search results
        """
        if not self.enabled or not REQUESTS_AVAILABLE:
            return []
        
        # Generate cache key
        cache_key = f"search_{query}_{num_results}"
        
        # Check cache
        if use_cache:
            cached_results = self._get_from_cache(cache_key)
            if cached_results is not None:
                self.logger.info(f"Using cached search results for: {query}")
                return cached_results
        
        try:
            # This is a simplified implementation
            # In a real implementation, you would use a search API like Google Custom Search, Bing, or DuckDuckGo
            
            # For demonstration, we'll create a simple search result
            # In a real implementation, replace this with actual API calls
            
            self.logger.info(f"Searching web for: {query}")
            
            # Simulate search delay
            time.sleep(0.5)
            
            # Create dummy results
            results = [
                {
                    "title": f"Result {i+1} for {query}",
                    "url": f"https://example.com/result{i+1}",
                    "snippet": f"This is a sample search result for {query}. In a real implementation, this would contain actual search results."
                }
                for i in range(num_results)
            ]
            
            # Add note about implementation
            results.insert(0, {
                "title": "Search Implementation Note",
                "url": "https://example.com/note",
                "snippet": "This is a placeholder implementation. To implement actual web search, you would need to use a search API like Google Custom Search, Bing, or DuckDuckGo."
            })
            
            # Cache results
            self._save_to_cache(cache_key, results)
            
            return results
        
        except Exception as e:
            self.logger.error(f"Error searching web: {e}")
            return []
    
    def get_weather(self, location: str = None, lat: float = None, lon: float = None, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """Get weather information for a location
        
        Args:
            location: Location name (city, address, etc.)
            lat: Latitude (alternative to location)
            lon: Longitude (alternative to location)
            use_cache: Whether to use cached results
            
        Returns:
            Weather information, or None if not available
        """
        if not self.enabled or not REQUESTS_AVAILABLE:
            return None
        
        # Check if we have required parameters
        if location is None and (lat is None or lon is None):
            self.logger.error("No location or coordinates provided for weather")
            return None
        
        # If location is provided but not coordinates, geocode the location
        if location is not None and (lat is None or lon is None):
            if not GEOPY_AVAILABLE or self.geocoder is None:
                self.logger.error("Geocoding not available")
                return None
            
            try:
                # Geocode the location
                geocode_result = self.geocoder.geocode(location)
                if geocode_result is None:
                    self.logger.error(f"Could not geocode location: {location}")
                    return None
                
                lat = geocode_result.latitude
                lon = geocode_result.longitude
                self.logger.debug(f"Geocoded {location} to {lat}, {lon}")
            
            except Exception as e:
                self.logger.error(f"Error geocoding location: {e}")
                return None
        
        # Generate cache key
        cache_key = f"weather_{lat}_{lon}"
        
        # Check cache
        if use_cache:
            cached_weather = self._get_from_cache(cache_key)
            if cached_weather is not None:
                self.logger.info(f"Using cached weather for: {lat}, {lon}")
                return cached_weather
        
        try:
            # Get API key
            api_key = self.api_keys.get("openweathermap")
            if not api_key:
                self.logger.error("OpenWeatherMap API key not found")
                return None
            
            # Make API request
            url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={api_key}&units=metric"
            response = self.session.get(url)
            response.raise_for_status()
            
            # Parse response
            weather_data = response.json()
            
            # Format weather data
            weather = {
                "location": {
                    "name": weather_data.get("name", "Unknown"),
                    "country": weather_data.get("sys", {}).get("country", "Unknown"),
                    "lat": lat,
                    "lon": lon,
                },
                "current": {
                    "temp": weather_data.get("main", {}).get("temp"),
                    "feels_like": weather_data.get("main", {}).get("feels_like"),
                    "humidity": weather_data.get("main", {}).get("humidity"),
                    "pressure": weather_data.get("main", {}).get("pressure"),
                    "wind_speed": weather_data.get("wind", {}).get("speed"),
                    "wind_direction": weather_data.get("wind", {}).get("deg"),
                    "condition": weather_data.get("weather", [{}])[0].get("main"),
                    "description": weather_data.get("weather", [{}])[0].get("description"),
                    "icon": weather_data.get("weather", [{}])[0].get("icon"),
                },
                "timestamp": datetime.now().isoformat(),
            }
            
            # Cache weather data
            self._save_to_cache(cache_key, weather)
            
            return weather
        
        except Exception as e:
            self.logger.error(f"Error getting weather: {e}")
            return None
    
    def get_news(self, category: str = None, query: str = None, num_results: int = 5, use_cache: bool = True) -> List[Dict[str, Any]]:
        """Get news articles
        
        Args:
            category: News category (e.g., "technology", "business")
            query: Search query for news
            num_results: Number of results to return
            use_cache: Whether to use cached results
            
        Returns:
            List of news articles
        """
        if not self.enabled or not REQUESTS_AVAILABLE:
            return []
        
        # Generate cache key
        cache_key = f"news_{category or 'general'}_{query or 'top'}_{num_results}"
        
        # Check cache
        if use_cache:
            cached_news = self._get_from_cache(cache_key)
            if cached_news is not None:
                self.logger.info(f"Using cached news for: {category or 'general'}, {query or 'top'}")
                return cached_news
        
        try:
            # Get API key
            api_key = self.api_keys.get("newsapi")
            if not api_key:
                self.logger.error("News API key not found")
                return []
            
            # Build API URL
            if query:
                # Search for news
                url = f"https://newsapi.org/v2/everything?q={query}&apiKey={api_key}&pageSize={num_results}"
            else:
                # Get top headlines
                url = f"https://newsapi.org/v2/top-headlines?apiKey={api_key}&pageSize={num_results}"
                if category:
                    url += f"&category={category}"
                else:
                    url += "&country=us"  # Default to US news
            
            # Make API request
            response = self.session.get(url)
            response.raise_for_status()
            
            # Parse response
            news_data = response.json()
            
            # Format news articles
            articles = []
            for article in news_data.get("articles", []):
                articles.append({
                    "title": article.get("title"),
                    "description": article.get("description"),
                    "url": article.get("url"),
                    "source": article.get("source", {}).get("name"),
                    "published_at": article.get("publishedAt"),
                    "content": article.get("content"),
                })
            
            # Cache news articles
            self._save_to_cache(cache_key, articles)
            
            return articles
        
        except Exception as e:
            self.logger.error(f"Error getting news: {e}")
            return []
    
    def get_stock_price(self, symbol: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """Get stock price information
        
        Args:
            symbol: Stock symbol (e.g., "AAPL" for Apple)
            use_cache: Whether to use cached results
            
        Returns:
            Stock price information, or None if not available
        """
        if not self.enabled or not REQUESTS_AVAILABLE:
            return None
        
        # Generate cache key
        cache_key = f"stock_{symbol}"
        
        # Check cache
        if use_cache:
            cached_stock = self._get_from_cache(cache_key)
            if cached_stock is not None:
                # Check if cache is recent (stocks should be more recent than general cache)
                cache_time = datetime.fromisoformat(cached_stock.get("timestamp", "2000-01-01T00:00:00"))
                if (datetime.now() - cache_time).total_seconds() < 300:  # 5 minutes
                    self.logger.info(f"Using cached stock price for: {symbol}")
                    return cached_stock
        
        try:
            # Get API key
            api_key = self.api_keys.get("alphavantage")
            if not api_key:
                self.logger.error("Alpha Vantage API key not found")
                return None
            
            # Make API request
            url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={api_key}"
            response = self.session.get(url)
            response.raise_for_status()
            
            # Parse response
            stock_data = response.json()
            
            # Check if we got valid data
            if "Global Quote" not in stock_data or not stock_data["Global Quote"]:
                self.logger.error(f"No stock data found for symbol: {symbol}")
                return None
            
            quote = stock_data["Global Quote"]
            
            # Format stock data
            stock = {
                "symbol": quote.get("01. symbol"),
                "price": float(quote.get("05. price", 0)),
                "change": float(quote.get("09. change", 0)),
                "change_percent": quote.get("10. change percent", "0%"),
                "volume": int(quote.get("06. volume", 0)),
                "latest_trading_day": quote.get("07. latest trading day"),
                "timestamp": datetime.now().isoformat(),
            }
            
            # Cache stock data
            self._save_to_cache(cache_key, stock)
            
            return stock
        
        except Exception as e:
            self.logger.error(f"Error getting stock price: {e}")
            return None
    
    def get_wikipedia_summary(self, query: str, sentences: int = 3, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """Get a summary from Wikipedia
        
        Args:
            query: Search query
            sentences: Number of sentences to include in the summary
            use_cache: Whether to use cached results
            
        Returns:
            Wikipedia summary, or None if not available
        """
        if not self.enabled or not REQUESTS_AVAILABLE:
            return None
        
        # Generate cache key
        cache_key = f"wiki_{query}_{sentences}"
        
        # Check cache
        if use_cache:
            cached_wiki = self._get_from_cache(cache_key)
            if cached_wiki is not None:
                self.logger.info(f"Using cached Wikipedia summary for: {query}")
                return cached_wiki
        
        try:
            # Make API request to Wikipedia
            url = "https://en.wikipedia.org/w/api.php"
            params = {
                "action": "query",
                "format": "json",
                "prop": "extracts|info",
                "exintro": True,
                "explaintext": True,
                "inprop": "url",
                "redirects": 1,
                "exsentences": sentences,
                "titles": query
            }
            
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            # Parse response
            wiki_data = response.json()
            
            # Extract page data
            pages = wiki_data.get("query", {}).get("pages", {})
            if not pages:
                self.logger.error(f"No Wikipedia pages found for: {query}")
                return None
            
            # Get the first page (there should only be one)
            page_id = next(iter(pages))
            page = pages[page_id]
            
            # Check if page exists
            if "missing" in page:
                self.logger.error(f"Wikipedia page not found for: {query}")
                return None
            
            # Format Wikipedia data
            wiki = {
                "title": page.get("title"),
                "extract": page.get("extract"),
                "url": page.get("fullurl"),
                "timestamp": datetime.now().isoformat(),
            }
            
            # Cache Wikipedia data
            self._save_to_cache(cache_key, wiki)
            
            return wiki
        
        except Exception as e:
            self.logger.error(f"Error getting Wikipedia summary: {e}")
            return None
    
    def get_location_info(self, location: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """Get information about a location
        
        Args:
            location: Location name (city, address, etc.)
            use_cache: Whether to use cached results
            
        Returns:
            Location information, or None if not available
        """
        if not self.enabled or not GEOPY_AVAILABLE or self.geocoder is None:
            return None
        
        # Generate cache key
        cache_key = f"location_{location}"
        
        # Check cache
        if use_cache:
            cached_location = self._get_from_cache(cache_key)
            if cached_location is not None:
                self.logger.info(f"Using cached location info for: {location}")
                return cached_location
        
        try:
            # Geocode the location
            geocode_result = self.geocoder.geocode(location, exactly_one=True, addressdetails=True)
            if geocode_result is None:
                self.logger.error(f"Could not geocode location: {location}")
                return None
            
            # Format location data
            location_info = {
                "name": geocode_result.raw.get("display_name"),
                "lat": geocode_result.latitude,
                "lon": geocode_result.longitude,
                "address": geocode_result.raw.get("address", {}),
                "timestamp": datetime.now().isoformat(),
            }
            
            # Cache location data
            self._save_to_cache(cache_key, location_info)
            
            return location_info
        
        except Exception as e:
            self.logger.error(f"Error getting location info: {e}")
            return None
    
    def get_timezone(self, lat: float, lon: float, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """Get timezone information for a location
        
        Args:
            lat: Latitude
            lon: Longitude
            use_cache: Whether to use cached results
            
        Returns:
            Timezone information, or None if not available
        """
        if not self.enabled or not REQUESTS_AVAILABLE:
            return None
        
        # Generate cache key
        cache_key = f"timezone_{lat}_{lon}"
        
        # Check cache
        if use_cache:
            cached_timezone = self._get_from_cache(cache_key)
            if cached_timezone is not None:
                self.logger.info(f"Using cached timezone info for: {lat}, {lon}")
                return cached_timezone
        
        try:
            # Make API request
            url = f"http://api.geonames.org/timezoneJSON?lat={lat}&lng={lon}&username={self.config.get('geonames_username', 'demo')}"
            response = self.session.get(url)
            response.raise_for_status()
            
            # Parse response
            timezone_data = response.json()
            
            # Check if we got valid data
            if "timezoneId" not in timezone_data:
                self.logger.error(f"No timezone data found for: {lat}, {lon}")
                return None
            
            # Format timezone data
            timezone = {
                "timezone_id": timezone_data.get("timezoneId"),
                "timezone_name": timezone_data.get("timezoneId").replace("_", " "),
                "gmt_offset": timezone_data.get("gmtOffset"),
                "dst_offset": timezone_data.get("dstOffset"),
                "raw_offset": timezone_data.get("rawOffset"),
                "timestamp": datetime.now().isoformat(),
            }
            
            # Cache timezone data
            self._save_to_cache(cache_key, timezone)
            
            return timezone
        
        except Exception as e:
            self.logger.error(f"Error getting timezone: {e}")
            return None
    
    def get_exchange_rate(self, from_currency: str, to_currency: str, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """Get currency exchange rate
        
        Args:
            from_currency: Source currency code (e.g., "USD")
            to_currency: Target currency code (e.g., "EUR")
            use_cache: Whether to use cached results
            
        Returns:
            Exchange rate information, or None if not available
        """
        if not self.enabled or not REQUESTS_AVAILABLE:
            return None
        
        # Normalize currency codes
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()
        
        # Generate cache key
        cache_key = f"exchange_{from_currency}_{to_currency}"
        
        # Check cache
        if use_cache:
            cached_rate = self._get_from_cache(cache_key)
            if cached_rate is not None:
                # Check if cache is recent (exchange rates should be more recent than general cache)
                cache_time = datetime.fromisoformat(cached_rate.get("timestamp", "2000-01-01T00:00:00"))
                if (datetime.now() - cache_time).total_seconds() < 3600:  # 1 hour
                    self.logger.info(f"Using cached exchange rate for: {from_currency} to {to_currency}")
                    return cached_rate
        
        try:
            # Get API key
            api_key = self.api_keys.get("exchangerate")
            if not api_key:
                self.logger.error("Exchange Rate API key not found")
                return None
            
            # Make API request
            url = f"https://v6.exchangerate-api.com/v6/{api_key}/pair/{from_currency}/{to_currency}"
            response = self.session.get(url)
            response.raise_for_status()
            
            # Parse response
            rate_data = response.json()
            
            # Check if we got valid data
            if rate_data.get("result") != "success":
                self.logger.error(f"Error getting exchange rate: {rate_data.get('error', 'Unknown error')}")
                return None
            
            # Format exchange rate data
            exchange_rate = {
                "from_currency": from_currency,
                "to_currency": to_currency,
                "rate": rate_data.get("conversion_rate"),
                "timestamp": datetime.now().isoformat(),
            }
            
            # Cache exchange rate data
            self._save_to_cache(cache_key, exchange_rate)
            
            return exchange_rate
        
        except Exception as e:
            self.logger.error(f"Error getting exchange rate: {e}")
            return None
    
    def fetch_url(self, url: str, parse_html: bool = False, use_cache: bool = True) -> Optional[Dict[str, Any]]:
        """Fetch content from a URL
        
        Args:
            url: URL to fetch
            parse_html: Whether to parse HTML content
            use_cache: Whether to use cached results
            
        Returns:
            URL content, or None if not available
        """
        if not self.enabled or not REQUESTS_AVAILABLE:
            return None
        
        # Generate cache key
        cache_key = f"url_{url}_{parse_html}"
        
        # Check cache
        if use_cache:
            cached_content = self._get_from_cache(cache_key)
            if cached_content is not None:
                self.logger.info(f"Using cached content for URL: {url}")
                return cached_content
        
        try:
            # Make HTTP request
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            # Get content type
            content_type = response.headers.get("Content-Type", "").lower()
            
            # Format URL content
            url_content = {
                "url": url,
                "status_code": response.status_code,
                "content_type": content_type,
                "content": response.text,
                "timestamp": datetime.now().isoformat(),
            }
            
            # Parse HTML if requested and content is HTML
            if parse_html and "text/html" in content_type and BS4_AVAILABLE:
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Extract title
                title = soup.title.string if soup.title else ""
                url_content["title"] = title
                
                # Extract meta description
                meta_desc = soup.find("meta", attrs={"name": "description"})
                if meta_desc:
                    url_content["description"] = meta_desc.get("content", "")
                
                # Extract main text content (simplified)
                main_content = ""
                for tag in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6"]):
                    if tag.text.strip():
                        main_content += tag.text.strip() + "\n\n"
                
                url_content["main_content"] = main_content.strip()
            
            # Cache URL content
            self._save_to_cache(cache_key, url_content)
            
            return url_content
        
        except Exception as e:
            self.logger.error(f"Error fetching URL: {e}")
            return None
    
    def shutdown(self):
        """Shutdown the web services"""
        if self.session:
            self.session.close()
            self.session = None
        
        self.logger.info("Web services shut down")