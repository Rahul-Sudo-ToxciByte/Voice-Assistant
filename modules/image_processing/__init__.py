#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Image Processing Module for Jarvis Assistant

This module provides image search, analysis, and processing capabilities including:
- Web image search via various APIs
- Image recognition and classification
- Object detection
- Image manipulation and editing
- OCR (Optical Character Recognition)

It enables Jarvis to understand, process, and retrieve visual information.
"""

import os
import io
import json
import logging
import threading
import time
import base64
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime
import requests
from urllib.parse import urlencode, quote_plus

# Try to import image processing libraries
try:
    from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


class ImageManager:
    """Manager for image processing and search capabilities"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the image manager
        
        Args:
            config: Configuration dictionary
        """
        self.logger = logging.getLogger("jarvis.image_processing")
        self.config = config
        
        # Configuration
        self.search_provider = config.get("search_provider", "google")
        self.api_keys = config.get("api_keys", {})
        self.max_results = config.get("max_results", 10)
        self.safe_search = config.get("safe_search", True)
        
        # Image storage directory
        self.image_dir = os.path.join(
            config.get("data_dir", "data"),
            "image_processing",
            "images"
        )
        os.makedirs(self.image_dir, exist_ok=True)
        
        # Initialize components
        self.search_engine = self._initialize_search_engine()
        self.image_processor = self._initialize_image_processor()
        self.ocr_engine = self._initialize_ocr_engine()
        
        self.logger.info("Image manager initialized")
    
    def _initialize_search_engine(self) -> Optional["ImageSearchEngine"]:
        """Initialize the image search engine
        
        Returns:
            ImageSearchEngine instance or None if initialization failed
        """
        try:
            return ImageSearchEngine(self.config)
        except Exception as e:
            self.logger.error(f"Error initializing image search engine: {e}")
            return None
    
    def _initialize_image_processor(self) -> Optional["ImageProcessor"]:
        """Initialize the image processor
        
        Returns:
            ImageProcessor instance or None if initialization failed
        """
        if not PIL_AVAILABLE and not OPENCV_AVAILABLE:
            self.logger.warning("No image processing libraries available")
            return None
        
        try:
            return ImageProcessor(self.config)
        except Exception as e:
            self.logger.error(f"Error initializing image processor: {e}")
            return None
    
    def _initialize_ocr_engine(self) -> Optional["OCREngine"]:
        """Initialize the OCR engine
        
        Returns:
            OCREngine instance or None if initialization failed
        """
        if not TESSERACT_AVAILABLE:
            self.logger.warning("Tesseract OCR not available")
            return None
        
        try:
            return OCREngine(self.config)
        except Exception as e:
            self.logger.error(f"Error initializing OCR engine: {e}")
            return None
    
    def search_images(self, query: str, max_results: int = None, 
                      safe_search: bool = None) -> List[Dict[str, Any]]:
        """Search for images using the configured search engine
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return (uses config default if None)
            safe_search: Whether to enable safe search (uses config default if None)
            
        Returns:
            List of image results with metadata
        """
        if not self.search_engine:
            self.logger.error("Image search engine not available")
            return []
        
        if max_results is None:
            max_results = self.max_results
        
        if safe_search is None:
            safe_search = self.safe_search
        
        return self.search_engine.search(query, max_results, safe_search)
    
    def download_image(self, url: str, filename: str = None) -> Optional[str]:
        """Download an image from a URL
        
        Args:
            url: URL of the image
            filename: Filename to save the image as (generated if None)
            
        Returns:
            Path to the downloaded image or None if download failed
        """
        try:
            # Generate filename if not provided
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                ext = os.path.splitext(url.split("?")[0])[1] or ".jpg"
                filename = f"image_{timestamp}{ext}"
            
            # Ensure filename has an extension
            if not os.path.splitext(filename)[1]:
                filename += ".jpg"
            
            # Download image
            response = requests.get(url, stream=True, timeout=10)
            response.raise_for_status()
            
            # Save image
            image_path = os.path.join(self.image_dir, filename)
            with open(image_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            self.logger.info(f"Downloaded image to {image_path}")
            return image_path
        
        except Exception as e:
            self.logger.error(f"Error downloading image: {e}")
            return None
    
    def analyze_image(self, image_path: str) -> Dict[str, Any]:
        """Analyze an image to extract information
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dictionary with analysis results
        """
        if not self.image_processor:
            self.logger.error("Image processor not available")
            return {"error": "Image processor not available"}
        
        return self.image_processor.analyze(image_path)
    
    def detect_objects(self, image_path: str) -> List[Dict[str, Any]]:
        """Detect objects in an image
        
        Args:
            image_path: Path to the image file
            
        Returns:
            List of detected objects with bounding boxes and confidence scores
        """
        if not self.image_processor:
            self.logger.error("Image processor not available")
            return []
        
        return self.image_processor.detect_objects(image_path)
    
    def extract_text(self, image_path: str) -> str:
        """Extract text from an image using OCR
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Extracted text string
        """
        if not self.ocr_engine:
            self.logger.error("OCR engine not available")
            return ""
        
        return self.ocr_engine.extract_text(image_path)
    
    def resize_image(self, image_path: str, width: int, height: int, 
                     output_path: str = None) -> Optional[str]:
        """Resize an image
        
        Args:
            image_path: Path to the image file
            width: Target width
            height: Target height
            output_path: Path to save the resized image (generated if None)
            
        Returns:
            Path to the resized image or None if resizing failed
        """
        if not self.image_processor:
            self.logger.error("Image processor not available")
            return None
        
        # Generate output path if not provided
        if not output_path:
            filename = os.path.basename(image_path)
            name, ext = os.path.splitext(filename)
            output_filename = f"{name}_resized{ext}"
            output_path = os.path.join(self.image_dir, output_filename)
        
        return self.image_processor.resize(image_path, width, height, output_path)
    
    def crop_image(self, image_path: str, x: int, y: int, width: int, height: int, 
                   output_path: str = None) -> Optional[str]:
        """Crop an image
        
        Args:
            image_path: Path to the image file
            x: X-coordinate of the top-left corner
            y: Y-coordinate of the top-left corner
            width: Width of the crop region
            height: Height of the crop region
            output_path: Path to save the cropped image (generated if None)
            
        Returns:
            Path to the cropped image or None if cropping failed
        """
        if not self.image_processor:
            self.logger.error("Image processor not available")
            return None
        
        # Generate output path if not provided
        if not output_path:
            filename = os.path.basename(image_path)
            name, ext = os.path.splitext(filename)
            output_filename = f"{name}_cropped{ext}"
            output_path = os.path.join(self.image_dir, output_filename)
        
        return self.image_processor.crop(image_path, x, y, width, height, output_path)


class ImageSearchEngine:
    """Engine for searching images on the web"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the image search engine
        
        Args:
            config: Configuration dictionary
        """
        self.logger = logging.getLogger("jarvis.image_processing.search")
        self.config = config
        
        # Configuration
        self.provider = config.get("search_provider", "google")
        self.api_keys = config.get("api_keys", {})
        
        # Validate configuration
        if self.provider not in ["google", "bing", "unsplash", "pexels"]:
            self.logger.warning(f"Unknown search provider: {self.provider}, falling back to Google")
            self.provider = "google"
        
        # Check API keys
        if self.provider in ["google", "bing", "unsplash", "pexels"] and self.provider not in self.api_keys:
            self.logger.warning(f"No API key found for {self.provider}")
        
        self.logger.info(f"Image search engine initialized with provider: {self.provider}")
    
    def search(self, query: str, max_results: int = 10, 
               safe_search: bool = True) -> List[Dict[str, Any]]:
        """Search for images
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            safe_search: Whether to enable safe search
            
        Returns:
            List of image results with metadata
        """
        if self.provider == "google":
            return self._search_google(query, max_results, safe_search)
        elif self.provider == "bing":
            return self._search_bing(query, max_results, safe_search)
        elif self.provider == "unsplash":
            return self._search_unsplash(query, max_results)
        elif self.provider == "pexels":
            return self._search_pexels(query, max_results)
        else:
            self.logger.error(f"Unsupported search provider: {self.provider}")
            return []
    
    def _search_google(self, query: str, max_results: int = 10, 
                       safe_search: bool = True) -> List[Dict[str, Any]]:
        """Search for images using Google Custom Search API
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            safe_search: Whether to enable safe search
            
        Returns:
            List of image results with metadata
        """
        try:
            api_key = self.api_keys.get("google")
            cx = self.config.get("google_cx")
            
            if not api_key or not cx:
                self.logger.error("Google API key or CX not configured")
                return []
            
            results = []
            
            # Google CSE API can return max 10 results per request
            for start_index in range(1, min(max_results + 1, 101), 10):
                params = {
                    "key": api_key,
                    "cx": cx,
                    "q": query,
                    "searchType": "image",
                    "num": min(10, max_results - len(results)),
                    "start": start_index,
                    "safe": "high" if safe_search else "off"
                }
                
                url = f"https://www.googleapis.com/customsearch/v1?{urlencode(params)}"
                response = requests.get(url)
                response.raise_for_status()
                data = response.json()
                
                if "items" not in data:
                    break
                
                for item in data["items"]:
                    results.append({
                        "url": item["link"],
                        "thumbnail": item["image"]["thumbnailLink"],
                        "title": item["title"],
                        "source": item["displayLink"],
                        "width": item["image"]["width"],
                        "height": item["image"]["height"],
                        "mime_type": item.get("mime", "")
                    })
                    
                    if len(results) >= max_results:
                        break
                
                if len(results) >= max_results:
                    break
            
            return results
        
        except Exception as e:
            self.logger.error(f"Error searching Google Images: {e}")
            return []
    
    def _search_bing(self, query: str, max_results: int = 10, 
                     safe_search: bool = True) -> List[Dict[str, Any]]:
        """Search for images using Bing Image Search API
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            safe_search: Whether to enable safe search
            
        Returns:
            List of image results with metadata
        """
        try:
            api_key = self.api_keys.get("bing")
            
            if not api_key:
                self.logger.error("Bing API key not configured")
                return []
            
            headers = {
                "Ocp-Apim-Subscription-Key": api_key
            }
            
            params = {
                "q": query,
                "count": max_results,
                "safeSearch": "Strict" if safe_search else "Off"
            }
            
            url = f"https://api.bing.microsoft.com/v7.0/images/search?{urlencode(params)}"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            results = []
            
            if "value" in data:
                for item in data["value"][:max_results]:
                    results.append({
                        "url": item["contentUrl"],
                        "thumbnail": item["thumbnailUrl"],
                        "title": item["name"],
                        "source": item["hostPageDisplayUrl"],
                        "width": item.get("width", 0),
                        "height": item.get("height", 0),
                        "mime_type": item.get("encodingFormat", "")
                    })
            
            return results
        
        except Exception as e:
            self.logger.error(f"Error searching Bing Images: {e}")
            return []
    
    def _search_unsplash(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search for images using Unsplash API
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            
        Returns:
            List of image results with metadata
        """
        try:
            api_key = self.api_keys.get("unsplash")
            
            if not api_key:
                self.logger.error("Unsplash API key not configured")
                return []
            
            headers = {
                "Authorization": f"Client-ID {api_key}"
            }
            
            params = {
                "query": query,
                "per_page": max_results
            }
            
            url = f"https://api.unsplash.com/search/photos?{urlencode(params)}"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            results = []
            
            if "results" in data:
                for item in data["results"][:max_results]:
                    results.append({
                        "url": item["urls"]["full"],
                        "thumbnail": item["urls"]["thumb"],
                        "title": item.get("description", "") or item.get("alt_description", ""),
                        "source": f"unsplash.com/@{item['user']['username']}",
                        "width": item.get("width", 0),
                        "height": item.get("height", 0),
                        "mime_type": "image/jpeg",
                        "author": item["user"]["name"],
                        "author_url": item["user"]["links"]["html"]
                    })
            
            return results
        
        except Exception as e:
            self.logger.error(f"Error searching Unsplash: {e}")
            return []
    
    def _search_pexels(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search for images using Pexels API
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return
            
        Returns:
            List of image results with metadata
        """
        try:
            api_key = self.api_keys.get("pexels")
            
            if not api_key:
                self.logger.error("Pexels API key not configured")
                return []
            
            headers = {
                "Authorization": api_key
            }
            
            params = {
                "query": query,
                "per_page": max_results
            }
            
            url = f"https://api.pexels.com/v1/search?{urlencode(params)}"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            results = []
            
            if "photos" in data:
                for item in data["photos"][:max_results]:
                    results.append({
                        "url": item["src"]["original"],
                        "thumbnail": item["src"]["medium"],
                        "title": item.get("alt", ""),
                        "source": "pexels.com",
                        "width": item.get("width", 0),
                        "height": item.get("height", 0),
                        "mime_type": "image/jpeg",
                        "author": item["photographer"],
                        "author_url": item["photographer_url"]
                    })
            
            return results
        
        except Exception as e:
            self.logger.error(f"Error searching Pexels: {e}")
            return []


class ImageProcessor:
    """Processor for image analysis and manipulation"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the image processor
        
        Args:
            config: Configuration dictionary
        """
        self.logger = logging.getLogger("jarvis.image_processing.processor")
        self.config = config
        
        # Check available libraries
        self.use_opencv = OPENCV_AVAILABLE and config.get("use_opencv", True)
        self.use_pil = PIL_AVAILABLE and config.get("use_pil", True)
        
        if not self.use_opencv and not self.use_pil:
            raise ValueError("No image processing libraries available")
        
        # Load object detection model if OpenCV is available
        self.object_detection_model = None
        if self.use_opencv and config.get("enable_object_detection", False):
            self._load_object_detection_model()
        
        self.logger.info("Image processor initialized")
    
    def _load_object_detection_model(self):
        """Load the object detection model"""
        try:
            # Load YOLO model
            model_dir = os.path.join(
                self.config.get("data_dir", "data"),
                "image_processing",
                "models"
            )
            os.makedirs(model_dir, exist_ok=True)
            
            # Check if model files exist, download if not
            model_files = {
                "config": "yolov3.cfg",
                "weights": "yolov3.weights",
                "classes": "coco.names"
            }
            
            model_paths = {}
            for key, filename in model_files.items():
                path = os.path.join(model_dir, filename)
                model_paths[key] = path
                
                if not os.path.exists(path):
                    self.logger.warning(f"Model file {filename} not found, please download it manually")
            
            # Load model if all files exist
            if all(os.path.exists(path) for path in model_paths.values()):
                self.object_detection_model = cv2.dnn.readNetFromDarknet(
                    model_paths["config"],
                    model_paths["weights"]
                )
                
                # Load class names
                with open(model_paths["classes"], "r") as f:
                    self.object_classes = f.read().strip().split("\n")
                
                self.logger.info("Object detection model loaded")
            else:
                self.logger.warning("Object detection model not loaded due to missing files")
        
        except Exception as e:
            self.logger.error(f"Error loading object detection model: {e}")
    
    def analyze(self, image_path: str) -> Dict[str, Any]:
        """Analyze an image to extract information
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dictionary with analysis results
        """
        try:
            result = {
                "format": None,
                "width": 0,
                "height": 0,
                "mode": None,
                "has_alpha": False,
                "dominant_colors": [],
                "average_color": None,
                "histogram": None
            }
            
            # Use PIL for basic analysis
            if self.use_pil:
                with Image.open(image_path) as img:
                    result["format"] = img.format
                    result["width"] = img.width
                    result["height"] = img.height
                    result["mode"] = img.mode
                    result["has_alpha"] = img.mode == "RGBA" or "A" in img.mode
                    
                    # Get dominant colors
                    if img.mode == "RGB" or img.mode == "RGBA":
                        # Resize for faster processing
                        small_img = img.resize((100, 100))
                        if small_img.mode == "RGBA":
                            small_img = small_img.convert("RGB")
                        
                        # Get pixel data
                        pixels = list(small_img.getdata())
                        
                        # Count colors
                        color_count = {}
                        for pixel in pixels:
                            if pixel in color_count:
                                color_count[pixel] += 1
                            else:
                                color_count[pixel] = 1
                        
                        # Get dominant colors
                        dominant_colors = sorted(color_count.items(), key=lambda x: x[1], reverse=True)[:5]
                        result["dominant_colors"] = [
                            {"color": f"#{r:02x}{g:02x}{b:02x}", "count": count}
                            for (r, g, b), count in dominant_colors
                        ]
                        
                        # Get average color
                        avg_r = sum(r for (r, g, b), _ in dominant_colors) // len(dominant_colors)
                        avg_g = sum(g for (r, g, b), _ in dominant_colors) // len(dominant_colors)
                        avg_b = sum(b for (r, g, b), _ in dominant_colors) // len(dominant_colors)
                        result["average_color"] = f"#{avg_r:02x}{avg_g:02x}{avg_b:02x}"
                    
                    # Get histogram
                    if img.mode == "RGB":
                        hist_r, hist_g, hist_b = img.histogram()[0:256], img.histogram()[256:512], img.histogram()[512:768]
                        result["histogram"] = {
                            "r": hist_r,
                            "g": hist_g,
                            "b": hist_b
                        }
            
            # Use OpenCV for additional analysis if needed
            elif self.use_opencv:
                img = cv2.imread(image_path)
                if img is not None:
                    result["width"] = img.shape[1]
                    result["height"] = img.shape[0]
                    result["has_alpha"] = img.shape[2] == 4 if len(img.shape) > 2 else False
                    
                    # Get dominant colors
                    small_img = cv2.resize(img, (100, 100))
                    pixels = small_img.reshape(-1, 3)
                    
                    # Convert to RGB for consistent color representation
                    pixels = cv2.cvtColor(pixels.reshape(-1, 1, 3), cv2.COLOR_BGR2RGB).reshape(-1, 3)
                    
                    # Use K-means to find dominant colors
                    if len(pixels) > 0:
                        pixels = np.float32(pixels)
                        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
                        _, labels, centers = cv2.kmeans(pixels, 5, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
                        
                        # Count labels to get color frequency
                        counts = np.bincount(labels.flatten())
                        
                        # Sort colors by frequency
                        colors = []
                        for i in range(len(counts)):
                            color = centers[i].astype(int)
                            colors.append((tuple(color), counts[i]))
                        
                        colors.sort(key=lambda x: x[1], reverse=True)
                        
                        # Format colors
                        result["dominant_colors"] = [
                            {"color": f"#{r:02x}{g:02x}{b:02x}", "count": int(count)}
                            for (r, g, b), count in colors
                        ]
                        
                        # Get average color
                        avg_color = np.mean(centers, axis=0).astype(int)
                        result["average_color"] = f"#{avg_color[0]:02x}{avg_color[1]:02x}{avg_color[2]:02x}"
                    
                    # Get histogram
                    hist_b = cv2.calcHist([img], [0], None, [256], [0, 256]).flatten().tolist()
                    hist_g = cv2.calcHist([img], [1], None, [256], [0, 256]).flatten().tolist()
                    hist_r = cv2.calcHist([img], [2], None, [256], [0, 256]).flatten().tolist()
                    result["histogram"] = {
                        "r": hist_r,
                        "g": hist_g,
                        "b": hist_b
                    }
            
            return result
        
        except Exception as e:
            self.logger.error(f"Error analyzing image: {e}")
            return {"error": str(e)}
    
    def detect_objects(self, image_path: str) -> List[Dict[str, Any]]:
        """Detect objects in an image
        
        Args:
            image_path: Path to the image file
            
        Returns:
            List of detected objects with bounding boxes and confidence scores
        """
        if not self.use_opencv or not self.object_detection_model:
            self.logger.error("Object detection not available")
            return []
        
        try:
            # Load image
            img = cv2.imread(image_path)
            if img is None:
                self.logger.error(f"Failed to load image: {image_path}")
                return []
            
            height, width = img.shape[:2]
            
            # Create blob from image
            blob = cv2.dnn.blobFromImage(img, 1/255.0, (416, 416), swapRB=True, crop=False)
            self.object_detection_model.setInput(blob)
            
            # Get output layer names
            layer_names = self.object_detection_model.getLayerNames()
            output_layers = [layer_names[i - 1] for i in self.object_detection_model.getUnconnectedOutLayers()]
            
            # Run forward pass
            outputs = self.object_detection_model.forward(output_layers)
            
            # Process detections
            class_ids = []
            confidences = []
            boxes = []
            
            for output in outputs:
                for detection in output:
                    scores = detection[5:]
                    class_id = np.argmax(scores)
                    confidence = scores[class_id]
                    
                    if confidence > 0.5:  # Confidence threshold
                        # Object detected
                        center_x = int(detection[0] * width)
                        center_y = int(detection[1] * height)
                        w = int(detection[2] * width)
                        h = int(detection[3] * height)
                        
                        # Rectangle coordinates
                        x = int(center_x - w / 2)
                        y = int(center_y - h / 2)
                        
                        boxes.append([x, y, w, h])
                        confidences.append(float(confidence))
                        class_ids.append(class_id)
            
            # Apply non-maximum suppression
            indices = cv2.dnn.NMSBoxes(boxes, confidences, 0.5, 0.4)
            
            results = []
            for i in indices:
                if isinstance(i, list):
                    i = i[0]  # For older OpenCV versions
                
                box = boxes[i]
                x, y, w, h = box
                
                results.append({
                    "class": self.object_classes[class_ids[i]],
                    "confidence": confidences[i],
                    "box": {
                        "x": max(0, x),
                        "y": max(0, y),
                        "width": w,
                        "height": h
                    }
                })
            
            return results
        
        except Exception as e:
            self.logger.error(f"Error detecting objects: {e}")
            return []
    
    def resize(self, image_path: str, width: int, height: int, 
               output_path: str) -> Optional[str]:
        """Resize an image
        
        Args:
            image_path: Path to the image file
            width: Target width
            height: Target height
            output_path: Path to save the resized image
            
        Returns:
            Path to the resized image or None if resizing failed
        """
        try:
            if self.use_pil:
                with Image.open(image_path) as img:
                    resized_img = img.resize((width, height), Image.LANCZOS)
                    resized_img.save(output_path)
            
            elif self.use_opencv:
                img = cv2.imread(image_path)
                if img is None:
                    self.logger.error(f"Failed to load image: {image_path}")
                    return None
                
                resized_img = cv2.resize(img, (width, height), interpolation=cv2.INTER_LANCZOS4)
                cv2.imwrite(output_path, resized_img)
            
            else:
                self.logger.error("No image processing libraries available")
                return None
            
            self.logger.info(f"Resized image saved to {output_path}")
            return output_path
        
        except Exception as e:
            self.logger.error(f"Error resizing image: {e}")
            return None
    
    def crop(self, image_path: str, x: int, y: int, width: int, height: int, 
             output_path: str) -> Optional[str]:
        """Crop an image
        
        Args:
            image_path: Path to the image file
            x: X-coordinate of the top-left corner
            y: Y-coordinate of the top-left corner
            width: Width of the crop region
            height: Height of the crop region
            output_path: Path to save the cropped image
            
        Returns:
            Path to the cropped image or None if cropping failed
        """
        try:
            if self.use_pil:
                with Image.open(image_path) as img:
                    cropped_img = img.crop((x, y, x + width, y + height))
                    cropped_img.save(output_path)
            
            elif self.use_opencv:
                img = cv2.imread(image_path)
                if img is None:
                    self.logger.error(f"Failed to load image: {image_path}")
                    return None
                
                # Ensure crop region is within image bounds
                img_height, img_width = img.shape[:2]
                x = max(0, x)
                y = max(0, y)
                width = min(width, img_width - x)
                height = min(height, img_height - y)
                
                cropped_img = img[y:y+height, x:x+width]
                cv2.imwrite(output_path, cropped_img)
            
            else:
                self.logger.error("No image processing libraries available")
                return None
            
            self.logger.info(f"Cropped image saved to {output_path}")
            return output_path
        
        except Exception as e:
            self.logger.error(f"Error cropping image: {e}")
            return None


class OCREngine:
    """Engine for optical character recognition"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the OCR engine
        
        Args:
            config: Configuration dictionary
        """
        self.logger = logging.getLogger("jarvis.image_processing.ocr")
        self.config = config
        
        # Configuration
        self.tesseract_path = config.get("tesseract_path")
        self.language = config.get("ocr_language", "eng")
        
        # Set Tesseract path if provided
        if self.tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_path
        
        self.logger.info("OCR engine initialized")
    
    def extract_text(self, image_path: str) -> str:
        """Extract text from an image using OCR
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Extracted text string
        """
        try:
            # Load image
            if PIL_AVAILABLE:
                with Image.open(image_path) as img:
                    # Preprocess image for better OCR results
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    
                    # Enhance image
                    img = ImageEnhance.Contrast(img).enhance(1.5)
                    img = ImageEnhance.Sharpness(img).enhance(1.5)
                    
                    # Extract text
                    text = pytesseract.image_to_string(img, lang=self.language)
                    return text.strip()
            
            elif OPENCV_AVAILABLE:
                # Load image
                img = cv2.imread(image_path)
                if img is None:
                    self.logger.error(f"Failed to load image: {image_path}")
                    return ""
                
                # Preprocess image
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
                
                # Extract text
                text = pytesseract.image_to_string(gray, lang=self.language)
                return text.strip()
            
            else:
                self.logger.error("No image processing libraries available")
                return ""
        
        except Exception as e:
            self.logger.error(f"Error extracting text: {e}")
            return ""