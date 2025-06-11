from typing import Dict
from openai import OpenAI
import logging
import os

class OpenAIIntegration:
    def __init__(self):
        self.logger = logging.getLogger("jarvis.openai")
        self.client = None
        self.api_key = None
        # Try to load API key from environment variable
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            self.set_api_key(api_key)

    def analyze_text(self, text: str) -> str:
        """Analyze text with improved error handling"""
        try:
            if not self.api_key:
                return "I'm sorry, but I need an OpenAI API key to analyze text. Please set it up first."
            
            try:
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that analyzes text."},
                        {"role": "user", "content": f"Analyze this text and provide insights: {text}"}
                    ],
                    temperature=0.7,
                    max_tokens=150
                )
                
                return response.choices[0].message.content
                
            except Exception as e:
                self.logger.error(f"Error analyzing text: {str(e)}")
                return "I'm sorry, I encountered an error while analyzing the text."
                
        except Exception as e:
            self.logger.error(f"Error in analyze_text: {str(e)}")
            return "I'm sorry, I encountered an error while analyzing the text."

    def summarize_text(self, text: str) -> str:
        """Summarize text with improved error handling"""
        try:
            if not self.api_key:
                return "I'm sorry, but I need an OpenAI API key to summarize text. Please set it up first."
            
            try:
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that summarizes text."},
                        {"role": "user", "content": f"Summarize this text concisely: {text}"}
                    ],
                    temperature=0.7,
                    max_tokens=100
                )
                
                return response.choices[0].message.content
                
            except Exception as e:
                self.logger.error(f"Error summarizing text: {str(e)}")
                return "I'm sorry, I encountered an error while summarizing the text."
                
        except Exception as e:
            self.logger.error(f"Error in summarize_text: {str(e)}")
            return "I'm sorry, I encountered an error while summarizing the text."

    def extract_keywords(self, text: str) -> Dict:
        """Extract keywords with improved error handling"""
        try:
            if not self.api_key:
                self.logger.error("OpenAI API key not set")
                return {}
            
            try:
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that extracts keywords from text."},
                        {"role": "user", "content": f"Extract the main keywords from this text: {text}"}
                    ],
                    temperature=0.7,
                    max_tokens=50
                )
                
                keywords = response.choices[0].message.content
                return {
                    'keywords': keywords,
                    'success': True
                }
                
            except Exception as e:
                self.logger.error(f"Error extracting keywords: {str(e)}")
                return {
                    'error': str(e),
                    'success': False
                }
                
        except Exception as e:
            self.logger.error(f"Error in extract_keywords: {str(e)}")
            return {
                'error': str(e),
                'success': False
            }

    def set_api_key(self, api_key: str) -> bool:
        """Set OpenAI API key with improved error handling"""
        try:
            if not api_key:
                self.logger.error("Invalid API key")
                return False
            
            try:
                self.client = OpenAI(api_key=api_key)
                self.api_key = api_key
                self.logger.info("OpenAI API key set successfully")
                return True
                
            except Exception as e:
                self.logger.error(f"Error setting API key: {str(e)}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error in set_api_key: {str(e)}")
            return False

def openai_integration():
    """Create and return an instance of OpenAIIntegration"""
    return OpenAIIntegration() 