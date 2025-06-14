# Voice Assistant Jarvis
A voice assistant is an AI-powered tool that understands and responds to spoken commands, enabling hands-free interaction with devices and services.

## 📌 Tech Stack
Python, Jupyter Notebook

## Some Glimpse 🤩 :
<table>
 <tr>
  <td><img src = "https://res.cloudinary.com/phantomping/image/upload/v1747317708/Github%20Project/x7jcfhfvnpb4m30ba1fe.webp" width="500"></td>
<!--   <td><img src = "https://res.cloudinary.com/phantomping/image/upload/v1747317074/Github%20Project/rvexadx1tufo2ioaspnc.png" width="500"></td> -->
 </tr>
</table>
<div align="center">
<table>
<tr>
<!-- <td><img src = "(https://user-images.githubusercontent.com/108818360/188401020-69357d33-7c60-445e-a438-658bf77fd415.png](https://res.cloudinary.com/phantomping/image/upload/v1747293303/t36qsxbqov58sxkojtmc.png)" width="200"></td>
<!-- <td><img src = "https://user-images.githubusercontent.com/108818360/188401033-e5e8a295-d27e-4a86-a3b5-cc90a1ac4460.png" width="200"></td> --> -->
</table>
</tr>
</div>

<h2>📬 Contact</h2>

Can reach me through the handles below. If you want to contact me

&nbsp;&nbsp;<a href="https://www.linkedin.com/in/g-rahul-871002255/"><img src="https://www.felberpr.com/wp-content/uploads/linkedin-logo.png" width="30"></img></a>

© 2023 Rahul

[![forthebadge](https://forthebadge.com/images/badges/built-with-love.svg)](https://forthebadge.com)











# Project Jarvis - Advanced AI Assistant

A powerful AI assistant with multi-device support, voice commands, Google services integration, and enhanced security features.

## Features

### Core Features
- Voice command system with wake word detection
- Multi-device connectivity and synchronization
- Secure communication and data encryption
- Database integration for persistent storage
- Google Services integration (Gmail, Calendar, Drive, Vision, etc.)
- RESTful API for external integrations

### Security Features
- End-to-end encryption for all communications
- JWT-based authentication
- Secure password hashing
- Device authentication and authorization
- Rate limiting and request validation

### Voice Command System
- Wake word detection using Whisper
- Natural language command processing
- Text-to-speech with multiple voice options
- Command sentiment analysis
- Voice activity detection

### Multi-Device Support
- WebSocket-based real-time communication
- Device registration and management
- State synchronization
- Cross-device command execution
- Device capability discovery

### Google Services Integration
- Gmail integration for email management
- Google Calendar for scheduling
- Google Drive for file storage
- Google Cloud Vision for image analysis
- Google Cloud Text-to-Speech and Speech-to-Text

### Database Integration
- SQLAlchemy ORM for database operations
- Support for multiple database backends
- Automatic schema migrations
- Data encryption at rest
- Backup and restore functionality

## Setup Instructions

1. Clone the repository:
```bash
git clone https://github.com/yourusername/project-jarvis.git
cd project-jarvis
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

5. Set up Google Cloud credentials:
- Create a project in Google Cloud Console
- Enable required APIs
- Download credentials and save as `config/google_credentials.json`

6. Initialize the database:
```bash
python scripts/init_db.py
```

7. Start the application:
```bash
python main.py
```

## Configuration

### Environment Variables
Create a `.env` file with the following variables:
- Database configuration (DB_USER, DB_PASSWORD, etc.)
- Security settings (SECRET_KEY, JWT_SECRET_KEY)
- Google Services credentials
- Redis cache settings
- API configuration
- Voice command settings
- Device management settings
- Logging configuration
- Feature flags

### Google Services Setup
1. Create a project in Google Cloud Console
2. Enable required APIs:
   - Gmail API
   - Google Calendar API
   - Google Drive API
   - Google Cloud Vision API
   - Google Cloud Text-to-Speech API
   - Google Cloud Speech-to-Text API
3. Create service account credentials
4. Download and save credentials

## Usage

### Voice Commands
1. Start the voice command system:
```python
from modules.voice_commands import VoiceCommandSystem

voice_system = VoiceCommandSystem()
voice_system.start()
```

2. Register custom commands:
```python
def handle_weather_command(command, sentiment):
    # Implement weather command logic
    pass

voice_system.register_command("weather", handle_weather_command)
```

### Multi-Device Setup
1. Initialize device manager:
```python
from modules.device_manager import DeviceManager

device_manager = DeviceManager()
await device_manager.start_server()
```

2. Register device handlers:
```python
async def handle_device_connected(device_info):
    print(f"Device connected: {device_info.name}")

device_manager.register_handler("device_connected", handle_device_connected)
```

### Google Services
1. Initialize Google services:
```python
from modules.google_services import GoogleServicesManager

google_manager = GoogleServicesManager("path/to/credentials.json")
```

2. Use Google services:
```python
# Send email
await google_manager.send_email("recipient@example.com", "Subject", "Body")

# Create calendar event
await google_manager.create_calendar_event("Meeting", start_time, end_time)

# Analyze image
result = await google_manager.analyze_image("path/to/image.jpg")
```

## Security

### Authentication
- JWT-based authentication for API access
- Device authentication using secure tokens
- Password hashing using PBKDF2

### Encryption
- End-to-end encryption for all communications
- Data encryption at rest
- Secure key management

### Access Control
- Role-based access control
- Device capability restrictions
- Rate limiting and request validation

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- OpenAI for Whisper model
- Google Cloud Platform
- SQLAlchemy
- FastAPI
- PyTorch
- Hugging Face Transformers
