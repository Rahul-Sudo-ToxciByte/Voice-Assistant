#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Google Services Integration Module for Jarvis Assistant

This module provides integration with various Google services including:
- Gmail for email access
- Calendar for event management
- Contacts for contact management
- Drive for file storage and access
- Photos for image access and management

It handles authentication, token management, and provides a unified interface
for accessing these services from other modules.
"""

import os
import json
import logging
import threading
import time
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime, timedelta
import pickle

# Google API imports
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False


class GoogleServicesManager:
    """Manager for Google services integration"""
    
    # Define scopes for different services
    SCOPES = {
        "gmail": ["https://www.googleapis.com/auth/gmail.readonly", 
                 "https://www.googleapis.com/auth/gmail.send"],
        "calendar": ["https://www.googleapis.com/auth/calendar"],
        "contacts": ["https://www.googleapis.com/auth/contacts"],
        "drive": ["https://www.googleapis.com/auth/drive"],
        "photos": ["https://www.googleapis.com/auth/photoslibrary.readonly"]
    }
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the Google services manager
        
        Args:
            config: Configuration dictionary
        """
        self.logger = logging.getLogger("jarvis.google_services")
        self.config = config
        
        # Check if required libraries are available
        if not GOOGLE_API_AVAILABLE:
            self.logger.error("Google API libraries not available. Please install with 'pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib'")
            raise ImportError("Google API libraries not available")
        
        # Configuration
        self.credentials_file = config.get("credentials_file", "credentials.json")
        self.token_dir = os.path.join(config.get("data_dir", "data"), "google_tokens")
        os.makedirs(self.token_dir, exist_ok=True)
        
        # Services configuration
        self.enabled_services = config.get("enabled_services", ["gmail", "calendar", "contacts", "drive"])
        
        # Service instances
        self.services = {}
        self.credentials = {}
        
        # Initialize services
        for service_name in self.enabled_services:
            if service_name in self.SCOPES:
                self._initialize_service(service_name)
            else:
                self.logger.warning(f"Unknown service: {service_name}")
        
        self.logger.info(f"Google services manager initialized with services: {', '.join(self.services.keys())}")
    
    def _initialize_service(self, service_name: str):
        """Initialize a Google service
        
        Args:
            service_name: Name of the service to initialize
        """
        try:
            # Get credentials for the service
            creds = self._get_credentials(service_name)
            if not creds:
                self.logger.warning(f"Failed to get credentials for {service_name}")
                return
            
            self.credentials[service_name] = creds
            
            # Build the service
            if service_name == "gmail":
                self.services[service_name] = build("gmail", "v1", credentials=creds)
            elif service_name == "calendar":
                self.services[service_name] = build("calendar", "v3", credentials=creds)
            elif service_name == "contacts":
                self.services[service_name] = build("people", "v1", credentials=creds)
            elif service_name == "drive":
                self.services[service_name] = build("drive", "v3", credentials=creds)
            elif service_name == "photos":
                self.services[service_name] = build("photoslibrary", "v1", credentials=creds)
            
            self.logger.info(f"Initialized {service_name} service")
        
        except Exception as e:
            self.logger.error(f"Error initializing {service_name} service: {e}")
    
    def _get_credentials(self, service_name: str) -> Optional[Credentials]:
        """Get credentials for a Google service
        
        Args:
            service_name: Name of the service
            
        Returns:
            Credentials object or None if not available
        """
        token_file = os.path.join(self.token_dir, f"{service_name}_token.pickle")
        creds = None
        
        # Get scopes for the service
        scopes = self.SCOPES.get(service_name, [])
        if not scopes:
            self.logger.error(f"No scopes defined for {service_name}")
            return None
        
        # Load existing token if available
        if os.path.exists(token_file):
            try:
                with open(token_file, "rb") as token:
                    creds = pickle.load(token)
            except Exception as e:
                self.logger.error(f"Error loading token for {service_name}: {e}")
        
        # Refresh token if expired
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                # Save refreshed token
                with open(token_file, "wb") as token:
                    pickle.dump(creds, token)
            except Exception as e:
                self.logger.error(f"Error refreshing token for {service_name}: {e}")
                creds = None
        
        # If no valid credentials, need to authenticate
        if not creds:
            try:
                if not os.path.exists(self.credentials_file):
                    self.logger.error(f"Credentials file not found: {self.credentials_file}")
                    return None
                
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, scopes)
                creds = flow.run_local_server(port=0)
                
                # Save token
                with open(token_file, "wb") as token:
                    pickle.dump(creds, token)
            except Exception as e:
                self.logger.error(f"Error authenticating for {service_name}: {e}")
                return None
        
        return creds
    
    def get_service(self, service_name: str) -> Any:
        """Get a Google service instance
        
        Args:
            service_name: Name of the service
            
        Returns:
            Service instance or None if not available
        """
        if service_name not in self.services:
            self.logger.warning(f"Service not initialized: {service_name}")
            return None
        
        return self.services.get(service_name)
    
    def refresh_service(self, service_name: str) -> bool:
        """Refresh a Google service
        
        Args:
            service_name: Name of the service
            
        Returns:
            True if service was refreshed successfully, False otherwise
        """
        if service_name not in self.enabled_services:
            self.logger.warning(f"Service not enabled: {service_name}")
            return False
        
        try:
            # Close existing service if any
            if service_name in self.services:
                del self.services[service_name]
            
            # Re-initialize service
            self._initialize_service(service_name)
            
            return service_name in self.services
        
        except Exception as e:
            self.logger.error(f"Error refreshing {service_name} service: {e}")
            return False
    
    def is_service_available(self, service_name: str) -> bool:
        """Check if a service is available
        
        Args:
            service_name: Name of the service
            
        Returns:
            True if service is available, False otherwise
        """
        return service_name in self.services
    
    def get_enabled_services(self) -> List[str]:
        """Get a list of enabled services
        
        Returns:
            List of enabled service names
        """
        return list(self.services.keys())


class GmailService:
    """Gmail service for email access and sending"""
    
    def __init__(self, google_services_manager: GoogleServicesManager):
        """Initialize the Gmail service
        
        Args:
            google_services_manager: Google services manager instance
        """
        self.logger = logging.getLogger("jarvis.google_services.gmail")
        self.manager = google_services_manager
        self.service = google_services_manager.get_service("gmail")
        
        if not self.service:
            self.logger.error("Gmail service not available")
            raise ValueError("Gmail service not available")
    
    def get_unread_messages(self, max_results: int = 10) -> List[Dict[str, Any]]:
        """Get unread messages from Gmail
        
        Args:
            max_results: Maximum number of messages to retrieve
            
        Returns:
            List of message dictionaries
        """
        try:
            # Get list of unread messages
            results = self.service.users().messages().list(
                userId="me",
                q="is:unread",
                maxResults=max_results
            ).execute()
            
            messages = results.get("messages", [])
            
            # Get message details
            detailed_messages = []
            for message in messages:
                msg = self.service.users().messages().get(
                    userId="me",
                    id=message["id"],
                    format="metadata",
                    metadataHeaders=["From", "Subject", "Date"]
                ).execute()
                
                # Extract headers
                headers = {}
                for header in msg["payload"]["headers"]:
                    headers[header["name"]] = header["value"]
                
                detailed_messages.append({
                    "id": msg["id"],
                    "threadId": msg["threadId"],
                    "from": headers.get("From", ""),
                    "subject": headers.get("Subject", "(No Subject)"),
                    "date": headers.get("Date", ""),
                    "snippet": msg.get("snippet", "")
                })
            
            return detailed_messages
        
        except Exception as e:
            self.logger.error(f"Error getting unread messages: {e}")
            return []
    
    def get_message(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific message from Gmail
        
        Args:
            message_id: ID of the message to retrieve
            
        Returns:
            Message dictionary or None if not found
        """
        try:
            # Get message details
            msg = self.service.users().messages().get(
                userId="me",
                id=message_id,
                format="full"
            ).execute()
            
            # Extract headers
            headers = {}
            for header in msg["payload"]["headers"]:
                headers[header["name"]] = header["value"]
            
            # Extract body
            body = ""
            if "parts" in msg["payload"]:
                for part in msg["payload"]["parts"]:
                    if part["mimeType"] == "text/plain" and "data" in part["body"]:
                        import base64
                        body_data = part["body"]["data"]
                        body += base64.urlsafe_b64decode(body_data).decode("utf-8")
            elif "body" in msg["payload"] and "data" in msg["payload"]["body"]:
                import base64
                body_data = msg["payload"]["body"]["data"]
                body = base64.urlsafe_b64decode(body_data).decode("utf-8")
            
            return {
                "id": msg["id"],
                "threadId": msg["threadId"],
                "from": headers.get("From", ""),
                "to": headers.get("To", ""),
                "subject": headers.get("Subject", "(No Subject)"),
                "date": headers.get("Date", ""),
                "body": body,
                "snippet": msg.get("snippet", "")
            }
        
        except Exception as e:
            self.logger.error(f"Error getting message {message_id}: {e}")
            return None
    
    def send_message(self, to: str, subject: str, body: str) -> bool:
        """Send an email message
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body
            
        Returns:
            True if message was sent successfully, False otherwise
        """
        try:
            import base64
            from email.mime.text import MIMEText
            
            # Create message
            message = MIMEText(body)
            message["to"] = to
            message["subject"] = subject
            
            # Encode message
            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            
            # Send message
            self.service.users().messages().send(
                userId="me",
                body={"raw": encoded_message}
            ).execute()
            
            self.logger.info(f"Sent email to {to}: {subject}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error sending email: {e}")
            return False
    
    def mark_as_read(self, message_id: str) -> bool:
        """Mark a message as read
        
        Args:
            message_id: ID of the message to mark as read
            
        Returns:
            True if message was marked as read successfully, False otherwise
        """
        try:
            self.service.users().messages().modify(
                userId="me",
                id=message_id,
                body={"removeLabelIds": ["UNREAD"]}
            ).execute()
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error marking message {message_id} as read: {e}")
            return False


class CalendarService:
    """Calendar service for event management"""
    
    def __init__(self, google_services_manager: GoogleServicesManager):
        """Initialize the Calendar service
        
        Args:
            google_services_manager: Google services manager instance
        """
        self.logger = logging.getLogger("jarvis.google_services.calendar")
        self.manager = google_services_manager
        self.service = google_services_manager.get_service("calendar")
        
        if not self.service:
            self.logger.error("Calendar service not available")
            raise ValueError("Calendar service not available")
    
    def get_upcoming_events(self, days: int = 7, max_results: int = 10) -> List[Dict[str, Any]]:
        """Get upcoming events from Calendar
        
        Args:
            days: Number of days to look ahead
            max_results: Maximum number of events to retrieve
            
        Returns:
            List of event dictionaries
        """
        try:
            # Calculate time range
            now = datetime.utcnow().isoformat() + "Z"  # 'Z' indicates UTC time
            end_time = (datetime.utcnow() + timedelta(days=days)).isoformat() + "Z"
            
            # Get events
            events_result = self.service.events().list(
                calendarId="primary",
                timeMin=now,
                timeMax=end_time,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime"
            ).execute()
            
            events = events_result.get("items", [])
            
            # Format events
            formatted_events = []
            for event in events:
                start = event["start"].get("dateTime", event["start"].get("date"))
                end = event["end"].get("dateTime", event["end"].get("date"))
                
                formatted_events.append({
                    "id": event["id"],
                    "summary": event.get("summary", "(No Title)"),
                    "start": start,
                    "end": end,
                    "location": event.get("location", ""),
                    "description": event.get("description", ""),
                    "link": event.get("htmlLink", "")
                })
            
            return formatted_events
        
        except Exception as e:
            self.logger.error(f"Error getting upcoming events: {e}")
            return []
    
    def get_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific event from Calendar
        
        Args:
            event_id: ID of the event to retrieve
            
        Returns:
            Event dictionary or None if not found
        """
        try:
            event = self.service.events().get(
                calendarId="primary",
                eventId=event_id
            ).execute()
            
            start = event["start"].get("dateTime", event["start"].get("date"))
            end = event["end"].get("dateTime", event["end"].get("date"))
            
            return {
                "id": event["id"],
                "summary": event.get("summary", "(No Title)"),
                "start": start,
                "end": end,
                "location": event.get("location", ""),
                "description": event.get("description", ""),
                "link": event.get("htmlLink", ""),
                "attendees": event.get("attendees", [])
            }
        
        except Exception as e:
            self.logger.error(f"Error getting event {event_id}: {e}")
            return None
    
    def create_event(self, summary: str, start_time: str, end_time: str, 
                     description: str = "", location: str = "") -> Optional[str]:
        """Create a new event in Calendar
        
        Args:
            summary: Event title
            start_time: Start time (ISO format)
            end_time: End time (ISO format)
            description: Event description
            location: Event location
            
        Returns:
            Event ID if created successfully, None otherwise
        """
        try:
            event = {
                "summary": summary,
                "location": location,
                "description": description,
                "start": {
                    "dateTime": start_time,
                    "timeZone": "UTC"
                },
                "end": {
                    "dateTime": end_time,
                    "timeZone": "UTC"
                }
            }
            
            event = self.service.events().insert(
                calendarId="primary",
                body=event
            ).execute()
            
            self.logger.info(f"Created event: {summary}")
            return event["id"]
        
        except Exception as e:
            self.logger.error(f"Error creating event: {e}")
            return None


class ContactsService:
    """Contacts service for contact management"""
    
    def __init__(self, google_services_manager: GoogleServicesManager):
        """Initialize the Contacts service
        
        Args:
            google_services_manager: Google services manager instance
        """
        self.logger = logging.getLogger("jarvis.google_services.contacts")
        self.manager = google_services_manager
        self.service = google_services_manager.get_service("contacts")
        
        if not self.service:
            self.logger.error("Contacts service not available")
            raise ValueError("Contacts service not available")
    
    def get_contacts(self, max_results: int = 100) -> List[Dict[str, Any]]:
        """Get contacts from Google Contacts
        
        Args:
            max_results: Maximum number of contacts to retrieve
            
        Returns:
            List of contact dictionaries
        """
        try:
            # Get contacts
            results = self.service.people().connections().list(
                resourceName="people/me",
                pageSize=max_results,
                personFields="names,emailAddresses,phoneNumbers,birthdays"
            ).execute()
            
            connections = results.get("connections", [])
            
            # Format contacts
            contacts = []
            for person in connections:
                names = person.get("names", [])
                emails = person.get("emailAddresses", [])
                phones = person.get("phoneNumbers", [])
                birthdays = person.get("birthdays", [])
                
                name = names[0].get("displayName", "") if names else ""
                email = emails[0].get("value", "") if emails else ""
                phone = phones[0].get("value", "") if phones else ""
                
                # Extract birthday if available
                birthday = None
                if birthdays:
                    date = birthdays[0].get("date", {})
                    if date:
                        month = date.get("month", 0)
                        day = date.get("day", 0)
                        year = date.get("year", 0)
                        
                        if month and day:
                            birthday = {
                                "month": month,
                                "day": day,
                                "year": year
                            }
                
                contacts.append({
                    "resourceName": person["resourceName"],
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "birthday": birthday
                })
            
            return contacts
        
        except Exception as e:
            self.logger.error(f"Error getting contacts: {e}")
            return []
    
    def get_contact(self, resource_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific contact from Google Contacts
        
        Args:
            resource_name: Resource name of the contact to retrieve
            
        Returns:
            Contact dictionary or None if not found
        """
        try:
            person = self.service.people().get(
                resourceName=resource_name,
                personFields="names,emailAddresses,phoneNumbers,birthdays,addresses"
            ).execute()
            
            names = person.get("names", [])
            emails = person.get("emailAddresses", [])
            phones = person.get("phoneNumbers", [])
            birthdays = person.get("birthdays", [])
            addresses = person.get("addresses", [])
            
            name = names[0].get("displayName", "") if names else ""
            email = emails[0].get("value", "") if emails else ""
            phone = phones[0].get("value", "") if phones else ""
            address = addresses[0].get("formattedValue", "") if addresses else ""
            
            # Extract birthday if available
            birthday = None
            if birthdays:
                date = birthdays[0].get("date", {})
                if date:
                    month = date.get("month", 0)
                    day = date.get("day", 0)
                    year = date.get("year", 0)
                    
                    if month and day:
                        birthday = {
                            "month": month,
                            "day": day,
                            "year": year
                        }
            
            return {
                "resourceName": person["resourceName"],
                "name": name,
                "email": email,
                "phone": phone,
                "address": address,
                "birthday": birthday
            }
        
        except Exception as e:
            self.logger.error(f"Error getting contact {resource_name}: {e}")
            return None
    
    def create_contact(self, name: str, email: str = "", phone: str = "", 
                       birthday: Dict[str, int] = None) -> Optional[str]:
        """Create a new contact in Google Contacts
        
        Args:
            name: Contact name
            email: Contact email
            phone: Contact phone number
            birthday: Contact birthday (dict with month, day, year keys)
            
        Returns:
            Resource name if created successfully, None otherwise
        """
        try:
            contact = {
                "names": [
                    {
                        "givenName": name
                    }
                ]
            }
            
            if email:
                contact["emailAddresses"] = [
                    {
                        "value": email
                    }
                ]
            
            if phone:
                contact["phoneNumbers"] = [
                    {
                        "value": phone
                    }
                ]
            
            if birthday:
                contact["birthdays"] = [
                    {
                        "date": {
                            "month": birthday.get("month", 1),
                            "day": birthday.get("day", 1),
                            "year": birthday.get("year", 0)
                        }
                    }
                ]
            
            person = self.service.people().createContact(
                body=contact
            ).execute()
            
            self.logger.info(f"Created contact: {name}")
            return person["resourceName"]
        
        except Exception as e:
            self.logger.error(f"Error creating contact: {e}")
            return None


class DriveService:
    """Drive service for file storage and access"""
    
    def __init__(self, google_services_manager: GoogleServicesManager):
        """Initialize the Drive service
        
        Args:
            google_services_manager: Google services manager instance
        """
        self.logger = logging.getLogger("jarvis.google_services.drive")
        self.manager = google_services_manager
        self.service = google_services_manager.get_service("drive")
        
        if not self.service:
            self.logger.error("Drive service not available")
            raise ValueError("Drive service not available")
    
    def list_files(self, max_results: int = 10, query: str = None) -> List[Dict[str, Any]]:
        """List files from Google Drive
        
        Args:
            max_results: Maximum number of files to retrieve
            query: Search query (e.g., "name contains 'report'")
            
        Returns:
            List of file dictionaries
        """
        try:
            # Prepare query
            params = {
                "pageSize": max_results,
                "fields": "files(id, name, mimeType, webViewLink, createdTime, modifiedTime, size)"
            }
            
            if query:
                params["q"] = query
            
            # Get files
            results = self.service.files().list(**params).execute()
            
            files = results.get("files", [])
            
            # Format files
            formatted_files = []
            for file in files:
                formatted_files.append({
                    "id": file["id"],
                    "name": file["name"],
                    "mimeType": file["mimeType"],
                    "webViewLink": file.get("webViewLink", ""),
                    "createdTime": file.get("createdTime", ""),
                    "modifiedTime": file.get("modifiedTime", ""),
                    "size": file.get("size", "0")
                })
            
            return formatted_files
        
        except Exception as e:
            self.logger.error(f"Error listing files: {e}")
            return []
    
    def get_file(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific file from Google Drive
        
        Args:
            file_id: ID of the file to retrieve
            
        Returns:
            File dictionary or None if not found
        """
        try:
            file = self.service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, webViewLink, createdTime, modifiedTime, size, description"
            ).execute()
            
            return {
                "id": file["id"],
                "name": file["name"],
                "mimeType": file["mimeType"],
                "webViewLink": file.get("webViewLink", ""),
                "createdTime": file.get("createdTime", ""),
                "modifiedTime": file.get("modifiedTime", ""),
                "size": file.get("size", "0"),
                "description": file.get("description", "")
            }
        
        except Exception as e:
            self.logger.error(f"Error getting file {file_id}: {e}")
            return None
    
    def download_file(self, file_id: str, destination_path: str) -> bool:
        """Download a file from Google Drive
        
        Args:
            file_id: ID of the file to download
            destination_path: Path where the file should be saved
            
        Returns:
            True if file was downloaded successfully, False otherwise
        """
        try:
            from googleapiclient.http import MediaIoBaseDownload
            import io
            
            request = self.service.files().get_media(fileId=file_id)
            fh = io.FileIO(destination_path, "wb")
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            self.logger.info(f"Downloaded file {file_id} to {destination_path}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error downloading file {file_id}: {e}")
            return False
    
    def upload_file(self, file_path: str, name: str = None, 
                    mime_type: str = None, folder_id: str = None) -> Optional[str]:
        """Upload a file to Google Drive
        
        Args:
            file_path: Path to the file to upload
            name: Name for the uploaded file (defaults to filename)
            mime_type: MIME type of the file (auto-detected if not provided)
            folder_id: ID of the folder to upload to (root if not provided)
            
        Returns:
            File ID if uploaded successfully, None otherwise
        """
        try:
            from googleapiclient.http import MediaFileUpload
            import mimetypes
            import os
            
            # Get file name if not provided
            if not name:
                name = os.path.basename(file_path)
            
            # Get MIME type if not provided
            if not mime_type:
                mime_type, _ = mimetypes.guess_type(file_path)
                if not mime_type:
                    mime_type = "application/octet-stream"
            
            # Prepare file metadata
            file_metadata = {
                "name": name
            }
            
            # Set parent folder if provided
            if folder_id:
                file_metadata["parents"] = [folder_id]
            
            # Upload file
            media = MediaFileUpload(file_path, mimetype=mime_type)
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id"
            ).execute()
            
            self.logger.info(f"Uploaded file {name} to Drive")
            return file.get("id")
        
        except Exception as e:
            self.logger.error(f"Error uploading file {file_path}: {e}")
            return None


class PhotosService:
    """Photos service for image access and management"""
    
    def __init__(self, google_services_manager: GoogleServicesManager):
        """Initialize the Photos service
        
        Args:
            google_services_manager: Google services manager instance
        """
        self.logger = logging.getLogger("jarvis.google_services.photos")
        self.manager = google_services_manager
        self.service = google_services_manager.get_service("photos")
        
        if not self.service:
            self.logger.error("Photos service not available")
            raise ValueError("Photos service not available")
    
    def list_albums(self, max_results: int = 10) -> List[Dict[str, Any]]:
        """List albums from Google Photos
        
        Args:
            max_results: Maximum number of albums to retrieve
            
        Returns:
            List of album dictionaries
        """
        try:
            # Get albums
            results = self.service.albums().list(
                pageSize=max_results
            ).execute()
            
            albums = results.get("albums", [])
            
            # Format albums
            formatted_albums = []
            for album in albums:
                formatted_albums.append({
                    "id": album["id"],
                    "title": album.get("title", "(No Title)"),
                    "productUrl": album.get("productUrl", ""),
                    "mediaItemsCount": album.get("mediaItemsCount", "0"),
                    "coverPhotoUrl": album.get("coverPhotoBaseUrl", "")
                })
            
            return formatted_albums
        
        except Exception as e:
            self.logger.error(f"Error listing albums: {e}")
            return []
    
    def search_photos(self, query: str = None, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search photos in Google Photos
        
        Args:
            query: Search query
            max_results: Maximum number of photos to retrieve
            
        Returns:
            List of photo dictionaries
        """
        try:
            # Prepare search body
            body = {
                "pageSize": max_results
            }
            
            if query:
                body["filters"] = {
                    "contentFilter": {
                        "includedContentCategories": [query]
                    }
                }
            
            # Search media items
            results = self.service.mediaItems().search(
                body=body
            ).execute()
            
            media_items = results.get("mediaItems", [])
            
            # Format media items
            formatted_items = []
            for item in media_items:
                formatted_items.append({
                    "id": item["id"],
                    "productUrl": item.get("productUrl", ""),
                    "baseUrl": item.get("baseUrl", ""),
                    "mimeType": item.get("mimeType", ""),
                    "filename": item.get("filename", "")
                })
            
            return formatted_items
        
        except Exception as e:
            self.logger.error(f"Error searching photos: {e}")
            return []
    
    def get_photo(self, photo_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific photo from Google Photos
        
        Args:
            photo_id: ID of the photo to retrieve
            
        Returns:
            Photo dictionary or None if not found
        """
        try:
            item = self.service.mediaItems().get(
                mediaItemId=photo_id
            ).execute()
            
            return {
                "id": item["id"],
                "productUrl": item.get("productUrl", ""),
                "baseUrl": item.get("baseUrl", ""),
                "mimeType": item.get("mimeType", ""),
                "filename": item.get("filename", ""),
                "description": item.get("description", "")
            }
        
        except Exception as e:
            self.logger.error(f"Error getting photo {photo_id}: {e}")
            return None
    
    def download_photo(self, photo_id: str, destination_path: str) -> bool:
        """Download a photo from Google Photos
        
        Args:
            photo_id: ID of the photo to download
            destination_path: Path where the photo should be saved
            
        Returns:
            True if photo was downloaded successfully, False otherwise
        """
        try:
            import requests
            
            # Get photo details
            photo = self.get_photo(photo_id)
            if not photo:
                return False
            
            # Download photo
            response = requests.get(photo["baseUrl"] + "=d", stream=True)
            if response.status_code != 200:
                self.logger.error(f"Error downloading photo {photo_id}: HTTP {response.status_code}")
                return False
            
            with open(destination_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
            
            self.logger.info(f"Downloaded photo {photo_id} to {destination_path}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error downloading photo {photo_id}: {e}")
            return False