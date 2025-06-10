#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Gmail Integration Plugin for Jarvis Assistant

This plugin provides Gmail integration using OAuth2 authentication,
allowing the assistant to send and receive emails.
"""

import os
import json
import logging
import threading
import time
import base64
import re
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Import for Gmail API
try:
    from googleapiclient.discovery import build
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.errors import HttpError
    GMAIL_API_AVAILABLE = True
except ImportError:
    GMAIL_API_AVAILABLE = False

# Import Plugin base class
from core.plugin import Plugin


class GmailPlugin(Plugin):
    """Gmail Integration Plugin for Jarvis Assistant"""
    
    def __init__(self, assistant):
        """Initialize the Gmail plugin
        
        Args:
            assistant: The Jarvis assistant instance
        """
        super().__init__(assistant)
        self.logger = logging.getLogger("jarvis.plugins.gmail")
        
        # Check if Gmail API is available
        if not GMAIL_API_AVAILABLE:
            self.logger.error("Gmail API libraries not available. Please install with 'pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib'")
            self.enabled = False
            return
        
        # Get plugin configuration
        self.config = self.assistant.config.get("plugins", {}).get("gmail", {})
        
        # Set up Gmail API configuration
        self.credentials_file = os.path.join(self.assistant.config.get("data_dir", "data"), 
                                           "gmail", 
                                           self.config.get("credentials_file", "credentials.json"))
        self.token_file = os.path.join(self.assistant.config.get("data_dir", "data"), 
                                     "gmail", 
                                     self.config.get("token_file", "token.json"))
        self.scopes = self.config.get("scopes", [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.compose",
            "https://www.googleapis.com/auth/gmail.modify"
        ])
        
        # Email checking configuration
        self.check_interval = self.config.get("check_interval", 300)  # seconds
        self.max_emails = self.config.get("max_emails", 10)
        self.notify_new_emails = self.config.get("notify_new_emails", True)
        self.important_senders = self.config.get("important_senders", [])
        
        # Gmail API service
        self.service = None
        
        # Thread control
        self.running = False
        self.check_thread = None
        
        # Last email check timestamp
        self.last_check_time = datetime.now().timestamp()
        
        # Create data directory
        os.makedirs(os.path.dirname(self.credentials_file), exist_ok=True)
        
        self.logger.info("Gmail plugin initialized")
    
    def activate(self):
        """Activate the Gmail plugin"""
        if not GMAIL_API_AVAILABLE:
            self.logger.error("Cannot activate Gmail plugin: Gmail API libraries not available")
            return False
        
        # Check if credentials file exists
        if not os.path.exists(self.credentials_file):
            self.logger.error(f"Credentials file not found: {self.credentials_file}")
            self.logger.info("Please download OAuth credentials from Google Cloud Console and save to the credentials file")
            return False
        
        # Authenticate with Gmail API
        try:
            self._authenticate()
        except Exception as e:
            self.logger.error(f"Failed to authenticate with Gmail API: {e}")
            return False
        
        # Start email checking thread
        self.running = True
        self.check_thread = threading.Thread(target=self._email_check_loop, daemon=True)
        self.check_thread.start()
        
        # Register commands
        self._register_commands()
        
        # Register intents
        self._register_intents()
        
        self.logger.info("Gmail plugin activated")
        return True
    
    def _authenticate(self):
        """Authenticate with Gmail API using OAuth2"""
        creds = None
        
        # Check if token file exists
        if os.path.exists(self.token_file):
            try:
                creds = Credentials.from_authorized_user_file(self.token_file, self.scopes)
            except Exception as e:
                self.logger.error(f"Error loading credentials from token file: {e}")
        
        # If no valid credentials available, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    self.logger.error(f"Error refreshing credentials: {e}")
                    creds = None
            
            if not creds:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(self.credentials_file, self.scopes)
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    self.logger.error(f"Error in authentication flow: {e}")
                    raise
            
            # Save the credentials for the next run
            try:
                with open(self.token_file, 'w') as token:
                    token.write(creds.to_json())
                self.logger.info(f"Saved authentication token to {self.token_file}")
            except Exception as e:
                self.logger.error(f"Error saving credentials to token file: {e}")
        
        # Build the Gmail API service
        try:
            self.service = build('gmail', 'v1', credentials=creds)
            self.logger.info("Successfully authenticated with Gmail API")
        except Exception as e:
            self.logger.error(f"Error building Gmail API service: {e}")
            raise
    
    def _email_check_loop(self):
        """Background thread to periodically check for new emails"""
        while self.running:
            try:
                # Check for new emails
                if self.notify_new_emails:
                    self._check_new_emails()
                
                # Sleep until next check
                time.sleep(self.check_interval)
            
            except Exception as e:
                self.logger.error(f"Error in email check loop: {e}")
                time.sleep(60)  # Wait a minute before retrying on error
    
    def _check_new_emails(self):
        """Check for new emails and send notifications"""
        try:
            # Get current time
            current_time = datetime.now().timestamp()
            
            # Create query for emails received after last check
            query = f"after:{int(self.last_check_time)}"
            
            # Add important senders to query if configured
            if self.important_senders:
                sender_query = " OR ".join([f"from:{sender}" for sender in self.important_senders])
                query = f"({query}) AND ({sender_query})"
            
            # Call Gmail API to get messages
            results = self.service.users().messages().list(userId='me', q=query, maxResults=self.max_emails).execute()
            messages = results.get('messages', [])
            
            # Process new messages
            for message in messages:
                msg = self.service.users().messages().get(userId='me', id=message['id']).execute()
                
                # Extract email details
                headers = msg['payload']['headers']
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
                
                # Send notification
                self._send_email_notification(sender, subject, message['id'])
            
            # Update last check time
            self.last_check_time = current_time
            
            if messages:
                self.logger.info(f"Found {len(messages)} new emails")
        
        except HttpError as e:
            self.logger.error(f"Error checking emails: {e}")
            # If authentication error, try to re-authenticate
            if e.resp.status in [401, 403]:
                try:
                    self._authenticate()
                except Exception as auth_error:
                    self.logger.error(f"Failed to re-authenticate: {auth_error}")
        
        except Exception as e:
            self.logger.error(f"Unexpected error checking emails: {e}")
    
    def _send_email_notification(self, sender, subject, message_id):
        """Send a notification for a new email
        
        Args:
            sender: Email sender
            subject: Email subject
            message_id: Gmail message ID
        """
        # Get notification manager from assistant
        notification_manager = self.assistant.get_module("notifications")
        
        if notification_manager:
            # Send notification using notification manager
            notification_manager.notify(
                title=f"New Email from {sender}",
                message=f"Subject: {subject}",
                level="info",
                channel="all",
                data={"type": "email", "message_id": message_id}
            )
        else:
            self.logger.warning("Notification manager not available")
    
    def _register_commands(self):
        """Register Gmail commands"""
        self.register_command(
            "check_email",
            self._cmd_check_email,
            "Check for new emails",
            "Check for new emails in your Gmail inbox",
            "check_email [count]",
            ["check_email", "check_email 5"],
            {
                "count": {
                    "type": "integer",
                    "description": "Number of emails to retrieve",
                    "default": 5
                }
            }
        )
        
        self.register_command(
            "send_email",
            self._cmd_send_email,
            "Send an email",
            "Send an email through your Gmail account",
            "send_email <to> <subject> <message>",
            ["send_email john@example.com 'Meeting tomorrow' 'Hi John, just a reminder about our meeting tomorrow.'"],
            {
                "to": {
                    "type": "string",
                    "description": "Recipient email address",
                    "required": True
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject",
                    "required": True
                },
                "message": {
                    "type": "string",
                    "description": "Email message body",
                    "required": True
                }
            }
        )
        
        self.register_command(
            "read_email",
            self._cmd_read_email,
            "Read an email",
            "Read the content of a specific email",
            "read_email <email_id>",
            ["read_email 1"],
            {
                "email_id": {
                    "type": "string",
                    "description": "Email ID or index",
                    "required": True
                }
            }
        )
    
    def _register_intents(self):
        """Register Gmail intents"""
        self.register_intent(
            "check_email",
            self._intent_check_email,
            [
                "check my email",
                "check my gmail",
                "do I have any new emails",
                "check for new emails",
                "any new messages in my inbox"
            ]
        )
        
        self.register_intent(
            "send_email",
            self._intent_send_email,
            [
                "send an email to {person} about {subject}",
                "email {person} saying {message}",
                "send a message to {person}",
                "compose an email"
            ],
            {
                "person": "PERSON",
                "subject": "TEXT",
                "message": "TEXT"
            }
        )
        
        self.register_intent(
            "read_email",
            self._intent_read_email,
            [
                "read my latest email",
                "read my recent emails",
                "what's in my inbox",
                "read email from {person}"
            ],
            {
                "person": "PERSON"
            }
        )
    
    def _cmd_check_email(self, count=5):
        """Command to check for emails
        
        Args:
            count: Number of emails to retrieve
            
        Returns:
            Command result
        """
        try:
            # Call Gmail API to get messages
            results = self.service.users().messages().list(userId='me', maxResults=count).execute()
            messages = results.get('messages', [])
            
            if not messages:
                return {"success": True, "message": "No emails found."}
            
            # Process messages
            email_list = []
            for message in messages:
                msg = self.service.users().messages().get(userId='me', id=message['id']).execute()
                
                # Extract email details
                headers = msg['payload']['headers']
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
                date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown Date')
                
                email_list.append({
                    "id": message['id'],
                    "sender": sender,
                    "subject": subject,
                    "date": date
                })
            
            return {
                "success": True,
                "message": f"Found {len(email_list)} emails.",
                "emails": email_list
            }
        
        except Exception as e:
            self.logger.error(f"Error checking emails: {e}")
            return {"success": False, "message": f"Error checking emails: {str(e)}"}
    
    def _cmd_send_email(self, to, subject, message):
        """Command to send an email
        
        Args:
            to: Recipient email address
            subject: Email subject
            message: Email message body
            
        Returns:
            Command result
        """
        try:
            # Create email message
            email_message = MIMEMultipart()
            email_message['to'] = to
            email_message['subject'] = subject
            
            # Add message body
            email_message.attach(MIMEText(message, 'plain'))
            
            # Encode message
            encoded_message = base64.urlsafe_b64encode(email_message.as_bytes()).decode()
            
            # Create message object
            create_message = {
                'raw': encoded_message
            }
            
            # Send message
            send_message = self.service.users().messages().send(userId="me", body=create_message).execute()
            
            return {
                "success": True,
                "message": f"Email sent successfully to {to}.",
                "message_id": send_message['id']
            }
        
        except Exception as e:
            self.logger.error(f"Error sending email: {e}")
            return {"success": False, "message": f"Error sending email: {str(e)}"}
    
    def _cmd_read_email(self, email_id):
        """Command to read an email
        
        Args:
            email_id: Email ID or index
            
        Returns:
            Command result
        """
        try:
            # If email_id is a number (index), get the actual message ID
            if email_id.isdigit():
                # Get list of messages
                results = self.service.users().messages().list(userId='me', maxResults=int(email_id) + 1).execute()
                messages = results.get('messages', [])
                
                if not messages or int(email_id) >= len(messages):
                    return {"success": False, "message": f"Email index {email_id} not found."}
                
                # Get the message ID at the specified index
                email_id = messages[int(email_id)]['id']
            
            # Get the email
            message = self.service.users().messages().get(userId='me', id=email_id).execute()
            
            # Extract email details
            headers = message['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown Date')
            
            # Extract email body
            body = ""
            if 'parts' in message['payload']:
                for part in message['payload']['parts']:
                    if part['mimeType'] == 'text/plain':
                        body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                        break
            elif 'body' in message['payload'] and 'data' in message['payload']['body']:
                body = base64.urlsafe_b64decode(message['payload']['body']['data']).decode('utf-8')
            
            return {
                "success": True,
                "message": f"Email retrieved successfully.",
                "email": {
                    "id": message['id'],
                    "sender": sender,
                    "subject": subject,
                    "date": date,
                    "body": body
                }
            }
        
        except Exception as e:
            self.logger.error(f"Error reading email: {e}")
            return {"success": False, "message": f"Error reading email: {str(e)}"}
    
    def _intent_check_email(self, text, entities):
        """Handle check email intent
        
        Args:
            text: Intent text
            entities: Extracted entities
            
        Returns:
            Response text
        """
        # Extract count from text if present
        count_match = re.search(r'\b(\d+)\b', text)
        count = int(count_match.group(1)) if count_match else 5
        
        # Call check email command
        result = self._cmd_check_email(count)
        
        if result["success"]:
            if "emails" in result and result["emails"]:
                response = f"I found {len(result['emails'])} emails. Here are the most recent:\n"
                
                for i, email in enumerate(result["emails"]):
                    sender_name = email["sender"].split('<')[0].strip()
                    response += f"{i+1}. From: {sender_name}, Subject: {email['subject']}\n"
                
                return response
            else:
                return "You don't have any new emails."
        else:
            return f"Sorry, I couldn't check your emails. {result['message']}"
    
    def _intent_send_email(self, text, entities):
        """Handle send email intent
        
        Args:
            text: Intent text
            entities: Extracted entities
            
        Returns:
            Response text or None to start conversation flow
        """
        # Check if we have all required entities
        if 'person' in entities:
            # Start a conversation flow to get the rest of the information
            self.assistant.start_conversation_flow(
                "send_email",
                {
                    "person": entities.get('person'),
                    "subject": entities.get('subject', ''),
                    "message": entities.get('message', '')
                },
                self._complete_send_email
            )
            
            # Return None to indicate that a conversation flow has been started
            return None
        else:
            # Start a conversation flow to get all information
            self.assistant.start_conversation_flow(
                "send_email",
                {},
                self._complete_send_email
            )
            
            # Return None to indicate that a conversation flow has been started
            return None
    
    def _complete_send_email(self, data):
        """Complete the send email conversation flow
        
        Args:
            data: Collected conversation data
            
        Returns:
            Response text
        """
        # Send the email
        result = self._cmd_send_email(data["to"], data["subject"], data["message"])
        
        if result["success"]:
            return f"Email sent successfully to {data['to']}."
        else:
            return f"Sorry, I couldn't send the email. {result['message']}"
    
    def _intent_read_email(self, text, entities):
        """Handle read email intent
        
        Args:
            text: Intent text
            entities: Extracted entities
            
        Returns:
            Response text
        """
        # Check if we're looking for emails from a specific person
        if 'person' in entities:
            person = entities['person']
            
            try:
                # Search for emails from the person
                query = f"from:{person}"
                results = self.service.users().messages().list(userId='me', q=query, maxResults=1).execute()
                messages = results.get('messages', [])
                
                if not messages:
                    return f"I couldn't find any emails from {person}."
                
                # Read the most recent email
                result = self._cmd_read_email(messages[0]['id'])
                
                if result["success"]:
                    email = result["email"]
                    return f"Here's the most recent email from {person}:\nSubject: {email['subject']}\n\n{email['body']}"
                else:
                    return f"Sorry, I couldn't read the email. {result['message']}"
            
            except Exception as e:
                self.logger.error(f"Error reading email from person: {e}")
                return f"Sorry, I couldn't read emails from {person}. An error occurred."
        
        else:
            # Read the most recent email
            result = self._cmd_read_email("0")
            
            if result["success"]:
                email = result["email"]
                sender_name = email["sender"].split('<')[0].strip()
                return f"Here's your most recent email:\nFrom: {sender_name}\nSubject: {email['subject']}\n\n{email['body']}"
            else:
                return f"Sorry, I couldn't read your latest email. {result['message']}"
    
    def shutdown(self):
        """Shutdown the Gmail plugin"""
        self.running = False
        
        if self.check_thread and self.check_thread.is_alive():
            self.check_thread.join(timeout=2.0)
        
        self.logger.info("Gmail plugin shut down")