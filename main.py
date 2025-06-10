import asyncio
import logging
import os
import webbrowser
import pyttsx3
from modules.voice_commands_new import VoiceCommandSystem
from modules.openai_integration import OpenAIIntegration

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("jarvis")

class JarvisAssistant:
    def __init__(self):
        self.logger = logging.getLogger("jarvis")
        self.voice_system = VoiceCommandSystem()
        self.engine = pyttsx3.init('sapi5')
        voices = self.engine.getProperty('voices')
        self.engine.setProperty('voice', voices[1].id)
        # Initialize OpenAI integration
        self.openai = OpenAIIntegration()
        # Register all command handlers
        self._register_commands()

    def speak(self, text):
        """Speak the given text"""
        try:
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as e:
            self.logger.error(f"Speech error: {str(e)}")

    def _register_commands(self):
        """Register all command handlers"""
        # OpenAI commands
        self.voice_system.register_command("ask", self.openai.analyze_text)
        self.voice_system.register_command("summarize", self.openai.summarize_text)
        # Wikipedia command
        self.voice_system.register_command("wikipedia", self.wikipedia_search)
        # Google command
        self.voice_system.register_command("open google", self.open_google)
        # Notepad command
        self.voice_system.register_command("open notepad", self.open_notepad)
        # Introduce command
        self.voice_system.register_command("introduce yourself", self.introduce_yourself)
        # Exit command
        self.voice_system.register_command("exit", self.exit_assistant)
        # Help command
        self.voice_system.register_command("help", self._help_command)

    def wikipedia_search(self, text):
        """Search Wikipedia for information"""
        if not text:
            return "Please provide a topic to search on Wikipedia."
        try:
            import wikipedia
            self.speak('Searching Wikipedia...')
            results = wikipedia.summary(text, sentences=2)
            return f"According to Wikipedia: {results}"
        except Exception as e:
            self.logger.error(f"Wikipedia error: {e}")
            return "Sorry, I could not find information on Wikipedia."

    def open_google(self, text):
        """Open Google in the default browser"""
        try:
            webbrowser.open("https://google.com")
            return "Opening Google."
        except Exception as e:
            self.logger.error(f"Google error: {e}")
            return "Sorry, I could not open Google."

    def open_notepad(self, text):
        """Open Windows Notepad"""
        try:
            os.startfile("C:\\Windows\\notepad.exe")
            return "Opening Notepad."
        except Exception as e:
            self.logger.error(f"Notepad error: {e}")
            return "Sorry, I could not open Notepad."

    def introduce_yourself(self, text):
        """Introduce the assistant"""
        return "Hello everyone, I am Jarvis, a Python-based voice assistant developed by Rahul and team."

    def exit_assistant(self, text):
        """Exit the assistant"""
        self.speak("Thank you. Exiting now.")
        os._exit(0)
        return "Exiting..."

    def _help_command(self, text):
        """Show available commands"""
        help_text = """
        Here are the available commands:
        - "ask [question]" - Ask me any question
        - "summarize [text]" - I'll summarize the text for you
        - "wikipedia [query]" - Search Wikipedia for information
        - "open google" - Open Google in your browser
        - "open notepad" - Open Windows Notepad
        - "introduce yourself" - I'll introduce myself
        - "exit" - Exit the assistant
        - "help" - Show this help message
        """
        return help_text

    async def start(self):
        """Start the assistant"""
        self.speak("Hello, I am Jarvis. How can I help you today?")
        success = await self.voice_system.start()
        if not success:
            self.logger.error("Failed to start voice system")
            return
        while True:
            await asyncio.sleep(1)

    async def stop(self):
        """Stop the assistant"""
        self.speak("Goodbye!")
        await self.voice_system.stop()

async def main():
    assistant = JarvisAssistant()
    try:
        await assistant.start()
    except KeyboardInterrupt:
        await assistant.stop()
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        await assistant.stop()

if __name__ == "__main__":
    asyncio.run(main()) 