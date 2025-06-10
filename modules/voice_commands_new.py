import pyttsx3
import speech_recognition as sr
import threading
import queue
import time
from typing import Dict, Callable
from core.logger import get_logger
import pyaudio
import wave
import numpy as np
from pystray import Icon, Menu, MenuItem
from PIL import Image
import os
import logging

if __name__ == "__main__":
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    print("Available voices:")
    for idx, voice in enumerate(voices):
        print(f"[{idx}] ID: {voice.id}")
        print(f"    Name: {voice.name}")
        print(f"    Languages: {voice.languages}")
        print(f"    Gender: {getattr(voice, 'gender', 'Unknown')}")
        print(f"    Age: {getattr(voice, 'age', 'Unknown')}")
        print()
    print("To test a voice, set engine.setProperty('voice', voices[IDX].id) and engine.say('Testing voice')")
    print("You can run this file directly: python modules/voice_commands_new.py")
else:
    class VoiceCommandSystem:
        def __init__(self):
            self.logger = logging.getLogger("jarvis.voice")
            self.recognizer = sr.Recognizer()
            
            # Configure speech recognition with extremely sensitive settings
            self.recognizer.energy_threshold = 10  # Very low threshold
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.dynamic_energy_adjustment_damping = 0.15
            self.recognizer.dynamic_energy_ratio = 1.2
            self.recognizer.pause_threshold = 0.3
            self.recognizer.phrase_threshold = 0.3
            self.recognizer.non_speaking_duration = 0.3
            
            # Initialize text-to-speech engine
            try:
                self.engine = pyttsx3.init('sapi5')
                self.engine.setProperty('rate', 150)
                self.engine.setProperty('volume', 1.0)
                
                # Set up voice
                voices = self.engine.getProperty('voices')
                for voice in voices:
                    if "english" in voice.name.lower():
                        self.engine.setProperty('voice', voice.id)
                        break
            except Exception as e:
                self.logger.error(f"Error initializing text-to-speech: {str(e)}")
                raise
            
            # Initialize state
            self.command_handlers = {}
            self.is_listening = False
            self.audio_thread = None
            self.wake_word = "jarvis"
            self.language = "en-US"
            
            # Initialize audio devices
            self._initialize_audio_devices()

        def _initialize_audio_devices(self):
            """Initialize and verify audio devices"""
            try:
                # List all audio devices
                p = pyaudio.PyAudio()
                self.logger.info("Available audio devices:")
                
                # Get default input device
                default_input = p.get_default_input_device_info()
                self.logger.info(f"Default input device: {default_input['name']}")
                
                # List all input devices
                for i in range(p.get_device_count()):
                    dev_info = p.get_device_info_by_index(i)
                    if dev_info['maxInputChannels'] > 0:  # Only input devices
                        self.logger.info(f"Input device {i}: {dev_info['name']}")
                
                p.terminate()
                
                # Test microphone
                with sr.Microphone() as source:
                    self.logger.info("Testing microphone...")
                    self.recognizer.adjust_for_ambient_noise(source, duration=1)
                    self.logger.info("Microphone test successful")
                    
            except Exception as e:
                self.logger.error(f"Error initializing audio devices: {str(e)}")
                raise

        def _capture_audio(self):
            """Continuously capture audio and listen for wake word"""
            try:
                with sr.Microphone() as source:
                    self.logger.info("Adjusting for ambient noise...")
                    self.recognizer.adjust_for_ambient_noise(source, duration=1)
                    self.logger.info("Microphone is ready!")
                    self.speak("Ready")
                    
                    while self.is_listening:
                        try:
                            self.logger.info("Listening...")
                            audio = self.recognizer.listen(source, timeout=None, phrase_time_limit=3)
                            self.logger.info("Audio captured.")
                            
                            try:
                                # Log the audio level
                                audio_data = np.frombuffer(audio.get_raw_data(), dtype=np.int16)
                                audio_level = np.abs(audio_data).mean()
                                self.logger.info(f"Audio level: {audio_level}")
                                
                                text = self.recognizer.recognize_google(audio, language=self.language).lower()
                                self.logger.info(f"Heard: {text}")
                                
                                if self.wake_word in text:
                                    self.logger.info("Wake word detected!")
                                    self._process_command(source)
                                
                            except sr.UnknownValueError:
                                self.logger.info("Could not understand audio (silent or noisy input).")
                            except sr.RequestError as e:
                                self.logger.error(f"Speech recognition service error: {str(e)}")
                                
                        except sr.WaitTimeoutError:
                            self.logger.info("No speech detected within time limit.")
                            continue
                        except Exception as e:
                            self.logger.error(f"Error in audio capture loop: {str(e)}")
                            time.sleep(0.1)
            except Exception as e:
                self.logger.error(f"Critical error in audio capture thread: {str(e)}")
                self.speak("Microphone error. Please check your setup.")

        def _process_command(self, source):
            """Process command after wake word detection"""
            try:
                self.logger.info("Listening for command...")
                self.speak("Yes")
                
                try:
                    audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=5)
                    self.logger.info("Command audio captured.")
                    
                    try:
                        text = self.recognizer.recognize_google(audio, language=self.language).lower()
                        self.logger.info(f"Command recognized: {text}")
                        
                        command_executed = False
                        for command, handler in self.command_handlers.items():
                            if command in text:
                                self.logger.info(f"Executing command: {command}")
                                try:
                                    command_text = text.replace(command, "").strip()
                                    response = handler(command_text)
                                    if response:
                                        self.speak(str(response))
                                    command_executed = True
                                    break
                                except Exception as e:
                                    self.logger.error(f"Command execution error: {str(e)}")
                                    self.speak(f"Error executing {command}")
                                    command_executed = True
                                    break
                        
                        if not command_executed:
                            self.speak("I didn't understand that command")
                        
                    except sr.UnknownValueError:
                        self.speak("I didn't catch that")
                        self.logger.info("Could not understand command audio.")
                    except sr.RequestError as e:
                        self.logger.error(f"Speech recognition service error for command: {str(e)}")
                        self.speak("I'm having trouble understanding")
                    
                except sr.WaitTimeoutError:
                    self.speak("I didn't hear a command")
                    self.logger.info("No command speech detected within time limit.")
                except Exception as e:
                    self.logger.error(f"Error in command processing loop: {str(e)}")
                    self.speak("Error processing command")
                
            except Exception as e:
                self.logger.error(f"Critical error in command processing: {str(e)}")
                self.speak("Error")

        def register_command(self, command: str, handler: Callable):
            """Register a command handler"""
            command = command.lower()
            self.command_handlers[command] = handler
            self.logger.info(f"Registered command: {command}")

        def speak(self, text):
            """Speak the given text"""
            try:
                self.logger.info(f"Speaking: {text}")
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception as e:
                self.logger.error(f"Speech error: {str(e)}")
                try:
                    self.engine = pyttsx3.init('sapi5')
                    self.engine.say(text)
                    self.engine.runAndWait()
                except Exception as e2:
                    self.logger.error(f"Failed to reinitialize speech engine: {str(e2)}")

        async def start(self):
            """Start the voice command system"""
            try:
                self.is_listening = True
                
                # Test microphone
                try:
                    with sr.Microphone() as source:
                        self.logger.info("Testing microphone...")
                        self.recognizer.adjust_for_ambient_noise(source, duration=1)
                        self.logger.info("Microphone test successful")
                except Exception as e:
                    self.logger.error(f"Microphone test failed: {str(e)}")
                    self.speak("Microphone test failed")
                    return False
                
                # Start audio capture thread
                self.audio_thread = threading.Thread(target=self._capture_audio)
                self.audio_thread.daemon = True
                self.audio_thread.start()
                
                return True
                
            except Exception as e:
                self.logger.error(f"Error starting voice system: {str(e)}")
                return False

        async def stop(self):
            """Stop the voice command system"""
            try:
                self.is_listening = False
                if self.audio_thread and self.audio_thread.is_alive():
                    self.audio_thread.join(timeout=1)
                self.logger.info("Voice system stopped")
            except Exception as e:
                self.logger.error(f"Error stopping voice system: {str(e)}")

    # ... rest of the VoiceCommandSystem code ... 