#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Voice Engine for Jarvis Assistant

This module handles the voice processing capabilities of the Jarvis assistant,
including speech recognition and text-to-speech functionality.
"""

import os
import logging
import threading
import queue
import time
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime

# Import for speech recognition
try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False

# Import for text-to-speech
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

# Import for OpenAI Whisper (if available)
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

# Import for wake word detection
try:
    import pvporcupine
    PORCUPINE_AVAILABLE = True
except ImportError:
    PORCUPINE_AVAILABLE = False


class VoiceEngine:
    """Voice processing engine for Jarvis Assistant"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the voice engine
        
        Args:
            config: Configuration dictionary for voice settings
        """
        self.logger = logging.getLogger("jarvis.voice")
        self.config = config
        
        # Set up voice engine configuration
        self.stt_engine = config.get("stt_engine", "google")
        self.tts_engine = config.get("tts_engine", "pyttsx3")
        self.wake_word = config.get("wake_word", "jarvis")
        self.voice_id = config.get("voice_id", None)  # Voice ID for TTS
        self.speaking_rate = config.get("speaking_rate", 175)  # Words per minute
        self.speaking_volume = config.get("speaking_volume", 1.0)  # 0.0 to 1.0
        
        # Thread control
        self.running = False
        self.listening = False
        self.speaking = False
        self.wake_word_detected = False
        
        # Threads
        self.wake_word_thread = None
        self.listen_thread = None
        
        # Callback for wake word detection
        self.wake_word_callback = None
        
        # Audio processing queues
        self.audio_queue = queue.Queue()
        self.speech_queue = queue.Queue()
        
        # Initialize speech recognition
        self._initialize_speech_recognition()
        
        # Initialize text-to-speech
        self._initialize_text_to_speech()
        
        # Initialize wake word detection
        self._initialize_wake_word_detection()
        
        self.logger.info("Voice engine initialized")
    
    def _initialize_speech_recognition(self):
        """Initialize speech recognition based on configuration"""
        if not SPEECH_RECOGNITION_AVAILABLE:
            self.logger.error("SpeechRecognition package not available. Please install with 'pip install SpeechRecognition'")
            raise ImportError("SpeechRecognition package not available")
        
        self.recognizer = sr.Recognizer()
        
        # Configure speech recognition based on selected engine
        if self.stt_engine == "google":
            # Google Speech Recognition (default)
            self.logger.info("Using Google Speech Recognition")
            
            # Adjust recognition parameters
            self.recognizer.energy_threshold = self.config.get("energy_threshold", 300)
            self.recognizer.dynamic_energy_threshold = self.config.get("dynamic_energy_threshold", True)
            self.recognizer.pause_threshold = self.config.get("pause_threshold", 0.8)
        
        elif self.stt_engine == "whisper":
            # OpenAI Whisper
            if not WHISPER_AVAILABLE:
                self.logger.error("Whisper package not available. Please install with 'pip install whisper'")
                raise ImportError("Whisper package not available")
            
            self.logger.info("Using OpenAI Whisper for speech recognition")
            
            # Load Whisper model
            model_size = self.config.get("whisper_model_size", "base")
            self.whisper_model = whisper.load_model(model_size)
            self.logger.info(f"Loaded Whisper model: {model_size}")
        
        else:
            self.logger.error(f"Unsupported speech recognition engine: {self.stt_engine}")
            raise ValueError(f"Unsupported speech recognition engine: {self.stt_engine}")
    
    def _initialize_text_to_speech(self):
        """Initialize text-to-speech based on configuration"""
        if self.tts_engine == "pyttsx3":
            if not PYTTSX3_AVAILABLE:
                self.logger.error("pyttsx3 package not available. Please install with 'pip install pyttsx3'")
                raise ImportError("pyttsx3 package not available")
            
            self.logger.info("Using pyttsx3 for text-to-speech")
            
            # Initialize pyttsx3
            self.tts = pyttsx3.init()
            
            # Configure voice properties
            self.tts.setProperty("rate", self.speaking_rate)
            self.tts.setProperty("volume", self.speaking_volume)
            
            # Set voice if specified
            if self.voice_id:
                self.tts.setProperty("voice", self.voice_id)
            else:
                # Try to find a British English voice if available
                voices = self.tts.getProperty("voices")
                british_voice = None
                for voice in voices:
                    if "british" in voice.name.lower() or "en-gb" in voice.id.lower():
                        british_voice = voice.id
                        break
                
                if british_voice:
                    self.tts.setProperty("voice", british_voice)
                    self.logger.info(f"Set British English voice: {british_voice}")
                elif voices:  # Set any available voice if no British voice found
                    self.tts.setProperty("voice", voices[0].id)
        
        else:
            self.logger.error(f"Unsupported text-to-speech engine: {self.tts_engine}")
            raise ValueError(f"Unsupported text-to-speech engine: {self.tts_engine}")
    
    def _initialize_wake_word_detection(self):
        """Initialize wake word detection based on configuration"""
        # Check if wake word detection is enabled
        if not self.config.get("use_wake_word", True):
            self.logger.info("Wake word detection disabled")
            return
        
        wake_word_config = self.config.get("wake_word_detection", {})
        engine = wake_word_config.get("engine", "basic")
        
        if engine == "porcupine" and PORCUPINE_AVAILABLE:
            self.logger.info("Using Porcupine for wake word detection")
            
            # Get Porcupine access key
            porcupine_access_key = self.config.get("porcupine_access_key") or os.environ.get("PORCUPINE_ACCESS_KEY")
            if not porcupine_access_key:
                self.logger.warning("Porcupine access key not found. Using basic wake word detection.")
                engine = "basic"
            else:
                try:
                    # Initialize Porcupine with the wake word
                    self.porcupine = pvporcupine.create(
                        access_key=porcupine_access_key,
                        keywords=[self.wake_word]
                    )
                    self.logger.info(f"Porcupine initialized with wake word: {self.wake_word}")
                    return
                except Exception as e:
                    self.logger.error(f"Failed to initialize Porcupine: {e}")
                    engine = "basic"
        
        if engine == "basic":
            self.logger.info("Using basic wake word detection")
            self.porcupine = None
            # Configure basic wake word detection
            self.wake_word_sensitivity = wake_word_config.get("sensitivity", 0.5)
            self.wake_word_threshold = int(3000 * (1 - self.wake_word_sensitivity))  # Adjust threshold based on sensitivity
            self.recognizer.energy_threshold = self.wake_word_threshold
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = 0.5  # Shorter pause threshold for wake word detection
        else:
            self.logger.warning(f"Unsupported wake word detection engine: {engine}. Using basic detection.")
            self.porcupine = None
    
    def start(self):
        """Start the voice engine"""
        if self.running:
            self.logger.warning("Voice engine is already running")
            return
        
        self.running = True
        
        # Start wake word detection thread if enabled
        if self.config.get("use_wake_word", True):
            self.wake_word_thread = threading.Thread(target=self._wake_word_detection_loop, daemon=True)
            self.wake_word_thread.start()
            self.logger.info("Wake word detection started")
        
        self.logger.info("Voice engine started")
    
    def stop(self):
        """Stop the voice engine"""
        self.running = False
        self.listening = False
        self.speaking = False
        self.wake_word_detected = False
        
        # Clear queues
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
        
        while not self.speech_queue.empty():
            try:
                self.speech_queue.get_nowait()
            except queue.Empty:
                break
        
        # Wait for threads to finish
        if self.wake_word_thread and self.wake_word_thread.is_alive():
            self.wake_word_thread.join(timeout=1.0)
        
        if self.listen_thread and self.listen_thread.is_alive():
            self.listen_thread.join(timeout=1.0)
        
        # Clean up resources
        if hasattr(self, "porcupine") and self.porcupine:
            self.porcupine.delete()
        
        self.logger.info("Voice engine stopped")
    
    def set_wake_word_callback(self, callback: Callable):
        """Set the callback function for wake word detection
        
        Args:
            callback: Function to call when wake word is detected
        """
        self.wake_word_callback = callback
    
    def _wake_word_detection_loop(self):
        """Main loop for wake word detection"""
        try:
            # Initialize audio stream for wake word detection
            audio = sr.Microphone()
            
            with audio as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                
                while self.running:
                    try:
                        # Listen for audio
                        audio_data = self.recognizer.listen(source, timeout=1.0, phrase_time_limit=5.0)
                        
                        if self.porcupine:
                            # Process with Porcupine
                            pcm = self._convert_audio_to_pcm(audio_data)
                            if pcm is not None:
                                keyword_index = self.porcupine.process(pcm)
                                if keyword_index >= 0:
                                    self._handle_wake_word_detected()
                        else:
                            # Basic wake word detection using speech recognition
                            try:
                                text = self.recognizer.recognize_google(audio_data).lower()
                                if self.wake_word.lower() in text:
                                    self._handle_wake_word_detected()
                            except sr.UnknownValueError:
                                pass  # No speech detected
                            except sr.RequestError as e:
                                self.logger.error(f"Error with speech recognition service: {e}")
                    
                    except sr.WaitTimeoutError:
                        # Timeout, continue listening
                        continue
                    except Exception as e:
                        self.logger.error(f"Error in wake word detection: {e}")
                        time.sleep(0.1)  # Prevent tight loop on error
        
        except Exception as e:
            self.logger.error(f"Error initializing wake word detection: {e}")
    
    def _handle_wake_word_detected(self):
        """Handle wake word detection"""
        self.logger.info("Wake word detected!")
        self.wake_word_detected = True
        
        # Call the callback if set
        if self.wake_word_callback:
            threading.Thread(target=self.wake_word_callback).start()
    
    def _convert_audio_to_pcm(self, audio_data):
        """Convert audio data to PCM format for Porcupine
        
        Args:
            audio_data: Audio data from speech_recognition
            
        Returns:
            PCM audio data or None if conversion fails
        """
        try:
            # Convert audio data to raw PCM
            # This is a simplified implementation and may need adjustment
            # based on the actual audio format from speech_recognition
            import numpy as np
            from array import array
            
            # Get raw audio data as int16 array
            raw_data = audio_data.get_raw_data(convert_rate=16000, convert_width=2)
            
            # Convert to numpy array of int16
            pcm = np.frombuffer(raw_data, dtype=np.int16)
            
            return pcm
        
        except Exception as e:
            self.logger.error(f"Error converting audio to PCM: {e}")
            return None
    
    def listen_for_command(self, callback: Callable[[str], None]):
        """Listen for a voice command and process it
        
        Args:
            callback: Function to call with the recognized command
        """
        if self.listening:
            self.logger.warning("Already listening for a command")
            return
        
        self.listening = True
        self.listen_thread = threading.Thread(
            target=self._listen_and_process,
            args=(callback,),
            daemon=True
        )
        self.listen_thread.start()
    
    def _listen_and_process(self, callback: Callable[[str], None]):
        """Listen for audio and process it to extract a command
        
        Args:
            callback: Function to call with the recognized command
        """
        try:
            # Initialize audio source
            audio = sr.Microphone()
            
            with audio as source:
                self.logger.info("Listening for command...")
                
                # Adjust for ambient noise if needed
                if self.config.get("adjust_for_ambient_noise", True):
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                
                # Listen for audio
                audio_data = self.recognizer.listen(
                    source,
                    timeout=self.config.get("listen_timeout", 5.0),
                    phrase_time_limit=self.config.get("phrase_time_limit", 10.0)
                )
                
                self.logger.info("Processing audio...")
                
                # Process audio based on selected engine
                if self.stt_engine == "google":
                    try:
                        # Use Google Speech Recognition
                        text = self.recognizer.recognize_google(audio_data)
                        self.logger.info(f"Recognized: {text}")
                        
                        # Call the callback with the recognized text
                        if callback:
                            callback(text)
                    
                    except sr.UnknownValueError:
                        self.logger.info("Google Speech Recognition could not understand audio")
                        if callback:
                            callback("")
                    
                    except sr.RequestError as e:
                        self.logger.error(f"Could not request results from Google Speech Recognition service: {e}")
                        if callback:
                            callback("")
                
                elif self.stt_engine == "whisper":
                    try:
                        # Use OpenAI Whisper
                        # Convert audio to format expected by Whisper
                        import numpy as np
                        audio_np = np.frombuffer(audio_data.get_raw_data(), np.int16).flatten().astype(np.float32) / 32768.0
                        
                        # Process with Whisper
                        result = self.whisper_model.transcribe(audio_np, fp16=False)
                        text = result["text"].strip()
                        
                        self.logger.info(f"Whisper recognized: {text}")
                        
                        # Call the callback with the recognized text
                        if callback:
                            callback(text)
                    
                    except Exception as e:
                        self.logger.error(f"Error processing audio with Whisper: {e}")
                        if callback:
                            callback("")
        
        except sr.WaitTimeoutError:
            self.logger.info("Listening timed out")
            if callback:
                callback("")
        
        except Exception as e:
            self.logger.error(f"Error in listen_and_process: {e}")
            if callback:
                callback("")
        
        finally:
            self.listening = False
    
    def speak(self, text: str):
        """Convert text to speech and speak it
        
        Args:
            text: The text to speak
        """
        if not text:
            return
        
        self.logger.info(f"Speaking: {text}")
        
        # Set speaking flag
        self.speaking = True
        
        try:
            if self.tts_engine == "pyttsx3":
                # Use pyttsx3 for text-to-speech
                self.tts.say(text)
                self.tts.runAndWait()
            
            # Add other TTS engines here as needed
        
        except Exception as e:
            self.logger.error(f"Error in text-to-speech: {e}")
        
        finally:
            self.speaking = False
    
    def is_speaking(self) -> bool:
        """Check if the assistant is currently speaking
        
        Returns:
            True if speaking, False otherwise
        """
        return self.speaking
        
    def set_low_power_mode(self, enabled):
        """Set the voice engine to low power mode
        
        In low power mode, the voice engine will use less resources
        but still detect wake words.
        
        Args:
            enabled: Whether to enable low power mode
        """
        self.logger.info(f"Setting low power mode to {enabled}")
        
        if enabled:
            # Reduce resource usage in wake word detection
            if hasattr(self, "porcupine") and self.porcupine and hasattr(self.porcupine, 'set_sensitivity'):
                # Lower sensitivity to reduce false positives and save CPU
                self.porcupine.set_sensitivity(0.4)
            
            # Increase pause threshold to reduce processing frequency
            if self.stt_engine == "google":
                self.recognizer.pause_threshold = 1.5
                self.recognizer.energy_threshold = 4000  # Higher threshold in low power mode
        else:
            # Restore normal settings
            if hasattr(self, "porcupine") and self.porcupine and hasattr(self.porcupine, 'set_sensitivity'):
                # Normal sensitivity
                self.porcupine.set_sensitivity(0.5)
            
            # Normal pause threshold
            if self.stt_engine == "google":
                self.recognizer.pause_threshold = 0.8
                self.recognizer.energy_threshold = 3000  # Normal threshold
    
    def is_wake_word_detection_running(self):
        """Check if wake word detection is running
        
        Returns:
            bool: True if wake word detection is running
        """
        return self.running and hasattr(self, "wake_word_thread") and self.wake_word_thread is not None and self.wake_word_thread.is_alive()
    
    def is_listening(self) -> bool:
        """Check if the assistant is currently listening
        
        Returns:
            True if listening, False otherwise
        """
        return self.listening