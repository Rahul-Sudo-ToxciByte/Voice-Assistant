#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Vision System for Jarvis Assistant

This module handles the computer vision capabilities of the Jarvis assistant,
including face recognition, object detection, and scene analysis.
"""

import os
import logging
import threading
import time
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime
import json
import numpy as np

# Import for computer vision
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# Import for face recognition
try:
    import face_recognition
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False

# Import for object detection (YOLOv8)
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False


class VisionSystem:
    """Computer vision system for Jarvis Assistant"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the vision system
        
        Args:
            config: Configuration dictionary for vision settings
        """
        self.logger = logging.getLogger("jarvis.vision")
        self.config = config
        
        # Check if OpenCV is available
        if not CV2_AVAILABLE:
            self.logger.error("OpenCV not available. Vision capabilities will be disabled.")
            self.enabled = False
            return
        
        # Set up vision system configuration
        self.enabled = config.get("enable_camera", False)
        self.camera_index = config.get("camera_index", 0)
        self.enable_face_recognition = config.get("face_recognition", False)
        self.enable_object_detection = config.get("object_detection", False)
        self.detection_model_path = config.get("detection_model", "yolov8n.pt")
        self.detection_confidence = config.get("detection_confidence", 0.5)
        
        # Initialize camera
        self.camera = None
        self.frame = None
        self.last_frame_time = 0
        self.camera_lock = threading.RLock()
        
        # Initialize face recognition if enabled
        self.known_faces = {}
        self.known_face_encodings = []
        self.known_face_names = []
        if self.enable_face_recognition:
            self._initialize_face_recognition()
        
        # Initialize object detection if enabled
        self.detection_model = None
        if self.enable_object_detection:
            self._initialize_object_detection()
        
        # Start camera if enabled
        if self.enabled:
            self._start_camera()
        
        self.logger.info(f"Vision system initialized (enabled: {self.enabled})")
    
    def _initialize_face_recognition(self):
        """Initialize face recognition"""
        if not FACE_RECOGNITION_AVAILABLE:
            self.logger.error("Face recognition package not available. Face recognition will be disabled.")
            self.enable_face_recognition = False
            return
        
        # Load known faces from data directory
        faces_dir = os.path.join("data", "faces")
        if not os.path.exists(faces_dir):
            os.makedirs(faces_dir, exist_ok=True)
            self.logger.info(f"Created faces directory: {faces_dir}")
        
        # Load face database if it exists
        face_db_path = os.path.join(faces_dir, "face_db.json")
        if os.path.exists(face_db_path):
            try:
                with open(face_db_path, 'r') as f:
                    self.known_faces = json.load(f)
                self.logger.info(f"Loaded {len(self.known_faces)} known faces from database")
            except Exception as e:
                self.logger.error(f"Error loading face database: {e}")
                self.known_faces = {}
        
        # Load face images and create encodings
        for filename in os.listdir(faces_dir):
            if filename.endswith(".jpg") or filename.endswith(".png"):
                try:
                    # Extract name from filename (remove extension)
                    name = os.path.splitext(filename)[0]
                    
                    # Load image and create encoding
                    image_path = os.path.join(faces_dir, filename)
                    image = face_recognition.load_image_file(image_path)
                    encoding = face_recognition.face_encodings(image)[0]
                    
                    # Add to known faces
                    self.known_face_encodings.append(encoding)
                    self.known_face_names.append(name)
                    
                    self.logger.debug(f"Loaded face: {name}")
                except Exception as e:
                    self.logger.error(f"Error loading face image {filename}: {e}")
        
        self.logger.info(f"Face recognition initialized with {len(self.known_face_encodings)} faces")
    
    def _initialize_object_detection(self):
        """Initialize object detection"""
        if not YOLO_AVAILABLE:
            self.logger.error("YOLOv8 package not available. Object detection will be disabled.")
            self.enable_object_detection = False
            return
        
        try:
            # Check if model file exists
            if not os.path.exists(self.detection_model_path):
                # Try to find in models directory
                models_dir = os.path.join("data", "models")
                model_path = os.path.join(models_dir, self.detection_model_path)
                
                if os.path.exists(model_path):
                    self.detection_model_path = model_path
                else:
                    # Model will be downloaded automatically by YOLO
                    self.logger.info(f"Model file not found locally. Will download: {self.detection_model_path}")
            
            # Load YOLO model
            self.detection_model = YOLO(self.detection_model_path)
            self.logger.info(f"Loaded object detection model: {self.detection_model_path}")
        
        except Exception as e:
            self.logger.error(f"Error initializing object detection: {e}")
            self.enable_object_detection = False
    
    def _start_camera(self):
        """Initialize and start the camera"""
        try:
            self.camera = cv2.VideoCapture(self.camera_index)
            
            # Check if camera opened successfully
            if not self.camera.isOpened():
                self.logger.error(f"Failed to open camera at index {self.camera_index}")
                self.enabled = False
                return
            
            # Start camera thread
            self.camera_thread = threading.Thread(target=self._camera_loop, daemon=True)
            self.camera_thread.start()
            
            self.logger.info(f"Camera started at index {self.camera_index}")
        
        except Exception as e:
            self.logger.error(f"Error starting camera: {e}")
            self.enabled = False
    
    def _camera_loop(self):
        """Main camera processing loop"""
        while self.enabled and self.camera and self.camera.isOpened():
            try:
                # Read a frame from the camera
                ret, frame = self.camera.read()
                
                if not ret:
                    self.logger.warning("Failed to read frame from camera")
                    time.sleep(0.1)
                    continue
                
                # Store the frame with thread safety
                with self.camera_lock:
                    self.frame = frame
                    self.last_frame_time = time.time()
            
            except Exception as e:
                self.logger.error(f"Error in camera loop: {e}")
                time.sleep(0.1)
    
    def get_current_frame(self) -> Optional[np.ndarray]:
        """Get the current camera frame
        
        Returns:
            The current frame as a numpy array, or None if not available
        """
        if not self.enabled or self.frame is None:
            return None
        
        with self.camera_lock:
            return self.frame.copy()
    
    def detect_faces(self, frame: Optional[np.ndarray] = None) -> List[Dict[str, Any]]:
        """Detect and recognize faces in the current frame
        
        Args:
            frame: Optional frame to use instead of the current frame
            
        Returns:
            List of detected faces with their locations and names
        """
        if not self.enabled or not self.enable_face_recognition:
            return []
        
        if not FACE_RECOGNITION_AVAILABLE:
            return []
        
        # Get frame if not provided
        if frame is None:
            frame = self.get_current_frame()
            if frame is None:
                return []
        
        try:
            # Resize frame for faster processing
            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            
            # Convert from BGR to RGB (face_recognition uses RGB)
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
            
            # Find face locations and encodings
            face_locations = face_recognition.face_locations(rgb_small_frame)
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)
            
            detected_faces = []
            
            for i, (face_encoding, face_location) in enumerate(zip(face_encodings, face_locations)):
                # Scale back up face locations
                top, right, bottom, left = face_location
                top *= 4
                right *= 4
                bottom *= 4
                left *= 4
                
                # See if the face is a match for known faces
                matches = face_recognition.compare_faces(self.known_face_encodings, face_encoding)
                name = "Unknown"
                
                # Use the known face with the smallest distance to the new face
                face_distances = face_recognition.face_distance(self.known_face_encodings, face_encoding)
                if len(face_distances) > 0:
                    best_match_index = np.argmin(face_distances)
                    if matches[best_match_index]:
                        name = self.known_face_names[best_match_index]
                
                # Add to detected faces
                detected_faces.append({
                    "name": name,
                    "confidence": 1.0 - face_distances[best_match_index] if len(face_distances) > 0 else 0.0,
                    "location": {
                        "top": int(top),
                        "right": int(right),
                        "bottom": int(bottom),
                        "left": int(left)
                    }
                })
            
            return detected_faces
        
        except Exception as e:
            self.logger.error(f"Error detecting faces: {e}")
            return []
    
    def detect_objects(self, frame: Optional[np.ndarray] = None) -> List[Dict[str, Any]]:
        """Detect objects in the current frame
        
        Args:
            frame: Optional frame to use instead of the current frame
            
        Returns:
            List of detected objects with their locations and classes
        """
        if not self.enabled or not self.enable_object_detection:
            return []
        
        if not YOLO_AVAILABLE or self.detection_model is None:
            return []
        
        # Get frame if not provided
        if frame is None:
            frame = self.get_current_frame()
            if frame is None:
                return []
        
        try:
            # Run inference with YOLOv8
            results = self.detection_model(frame, conf=self.detection_confidence)
            
            detected_objects = []
            
            # Process results
            for result in results:
                boxes = result.boxes
                
                for i, box in enumerate(boxes):
                    # Get box coordinates
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    
                    # Get class and confidence
                    cls = int(box.cls[0].item())
                    conf = float(box.conf[0].item())
                    
                    # Get class name
                    class_name = result.names[cls]
                    
                    # Add to detected objects
                    detected_objects.append({
                        "class": class_name,
                        "confidence": conf,
                        "location": {
                            "x1": int(x1),
                            "y1": int(y1),
                            "x2": int(x2),
                            "y2": int(y2)
                        }
                    })
            
            return detected_objects
        
        except Exception as e:
            self.logger.error(f"Error detecting objects: {e}")
            return []
    
    def analyze_scene(self) -> Dict[str, Any]:
        """Analyze the current scene
        
        Returns:
            Dictionary with scene analysis results
        """
        if not self.enabled:
            return {"error": "Vision system not enabled"}
        
        # Get current frame
        frame = self.get_current_frame()
        if frame is None:
            return {"error": "No frame available"}
        
        # Analyze the scene
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "faces": [],
            "objects": [],
            "scene_description": ""
        }
        
        # Detect faces if enabled
        if self.enable_face_recognition:
            analysis["faces"] = self.detect_faces(frame)
        
        # Detect objects if enabled
        if self.enable_object_detection:
            analysis["objects"] = self.detect_objects(frame)
        
        # Generate scene description
        analysis["scene_description"] = self._generate_scene_description(analysis["faces"], analysis["objects"])
        
        return analysis
    
    def _generate_scene_description(self, faces: List[Dict[str, Any]], objects: List[Dict[str, Any]]) -> str:
        """Generate a natural language description of the scene
        
        Args:
            faces: List of detected faces
            objects: List of detected objects
            
        Returns:
            Natural language description of the scene
        """
        description = ""
        
        # Describe faces
        if faces:
            if len(faces) == 1:
                face = faces[0]
                if face["name"] == "Unknown":
                    description += "I can see one unrecognized person. "
                else:
                    description += f"I can see {face['name']}. "
            else:
                known_faces = [face for face in faces if face["name"] != "Unknown"]
                unknown_count = len(faces) - len(known_faces)
                
                if known_faces:
                    names = [face["name"] for face in known_faces]
                    if len(names) == 1:
                        description += f"I can see {names[0]}"
                    elif len(names) == 2:
                        description += f"I can see {names[0]} and {names[1]}"
                    else:
                        description += f"I can see {', '.join(names[:-1])}, and {names[-1]}"
                    
                    if unknown_count > 0:
                        description += f" along with {unknown_count} unrecognized {'person' if unknown_count == 1 else 'people'}"
                    
                    description += ". "
                else:
                    description += f"I can see {len(faces)} unrecognized people. "
        
        # Describe objects
        if objects:
            # Count objects by class
            object_counts = {}
            for obj in objects:
                cls = obj["class"]
                if cls in object_counts:
                    object_counts[cls] += 1
                else:
                    object_counts[cls] = 1
            
            # Generate description
            object_descriptions = []
            for cls, count in object_counts.items():
                if count == 1:
                    object_descriptions.append(f"a {cls}")
                else:
                    object_descriptions.append(f"{count} {cls}s")
            
            if object_descriptions:
                if len(object_descriptions) == 1:
                    description += f"I can see {object_descriptions[0]}. "
                elif len(object_descriptions) == 2:
                    description += f"I can see {object_descriptions[0]} and {object_descriptions[1]}. "
                else:
                    description += f"I can see {', '.join(object_descriptions[:-1])}, and {object_descriptions[-1]}. "
        
        # If nothing detected
        if not faces and not objects:
            description = "I don't see any people or recognizable objects in the current scene."
        
        return description
    
    def save_frame(self, filename: Optional[str] = None) -> Optional[str]:
        """Save the current frame to a file
        
        Args:
            filename: Optional filename to save to
            
        Returns:
            Path to the saved file, or None if failed
        """
        if not self.enabled:
            return None
        
        # Get current frame
        frame = self.get_current_frame()
        if frame is None:
            return None
        
        try:
            # Create screenshots directory if it doesn't exist
            screenshots_dir = os.path.join("data", "screenshots")
            os.makedirs(screenshots_dir, exist_ok=True)
            
            # Generate filename if not provided
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{timestamp}.jpg"
            
            # Ensure filename has extension
            if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
                filename += ".jpg"
            
            # Create full path
            filepath = os.path.join(screenshots_dir, filename)
            
            # Save the image
            cv2.imwrite(filepath, frame)
            
            self.logger.info(f"Saved screenshot to {filepath}")
            return filepath
        
        except Exception as e:
            self.logger.error(f"Error saving screenshot: {e}")
            return None
    
    def add_face(self, name: str, frame: Optional[np.ndarray] = None) -> bool:
        """Add a face to the known faces database
        
        Args:
            name: Name of the person
            frame: Optional frame to use instead of the current frame
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.enable_face_recognition:
            return False
        
        if not FACE_RECOGNITION_AVAILABLE:
            return False
        
        # Get frame if not provided
        if frame is None:
            frame = self.get_current_frame()
            if frame is None:
                return False
        
        try:
            # Convert from BGR to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Detect faces in the frame
            face_locations = face_recognition.face_locations(rgb_frame)
            
            if not face_locations:
                self.logger.warning("No faces detected in the frame")
                return False
            
            # Use the first face found
            face_location = face_locations[0]
            face_encoding = face_recognition.face_encodings(rgb_frame, [face_location])[0]
            
            # Add to known faces
            self.known_face_encodings.append(face_encoding)
            self.known_face_names.append(name)
            
            # Save face image
            faces_dir = os.path.join("data", "faces")
            os.makedirs(faces_dir, exist_ok=True)
            
            # Extract face from frame
            top, right, bottom, left = face_location
            face_image = frame[top:bottom, left:right]
            
            # Save face image
            face_filename = f"{name}.jpg"
            face_path = os.path.join(faces_dir, face_filename)
            cv2.imwrite(face_path, face_image)
            
            # Update face database
            self.known_faces[name] = {
                "added": datetime.now().isoformat(),
                "file": face_filename
            }
            
            # Save face database
            face_db_path = os.path.join(faces_dir, "face_db.json")
            with open(face_db_path, 'w') as f:
                json.dump(self.known_faces, f, indent=2)
            
            self.logger.info(f"Added face for {name}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error adding face: {e}")
            return False
    
    def shutdown(self):
        """Shutdown the vision system"""
        self.enabled = False
        
        # Release camera resources
        if self.camera:
            self.camera.release()
            self.camera = None
        
        self.logger.info("Vision system shut down")