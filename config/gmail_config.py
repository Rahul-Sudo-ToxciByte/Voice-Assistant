from pathlib import Path
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

# Gmail API scopes
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.modify'
]

# Your Gmail address
GMAIL_ADDRESS = ""

# Paths for credentials
BASE_DIR = Path(__file__).resolve().parent.parent
CREDENTIALS_PATH = BASE_DIR / "config" / "credentials.json"
TOKEN_PATH = BASE_DIR / "config" / "token.pickle"

def get_gmail_credentials():
    """Get or refresh Gmail API credentials"""
    creds = None
    
    # Load existing token if available
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)
    
    # If credentials are not valid or don't exist, get new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for future use
        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)
    
    return creds

def setup_gmail_integration():
    """Initial setup for Gmail integration"""
    if not os.path.exists(CREDENTIALS_PATH):
        raise FileNotFoundError(
            "Please download your OAuth 2.0 credentials from Google Cloud Console "
            "and save them as 'credentials.json' in the config directory."
        )
    
    # Get credentials
    creds = get_gmail_credentials()
    
    return creds 