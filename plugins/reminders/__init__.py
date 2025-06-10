import re
import os
import json
import time
import datetime
import threading
import traceback
from typing import Dict, List, Any, Optional, Tuple, Union
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

from core.plugin_base import PluginBase
from core.notification import Notification
from core.utils import extract_entities, extract_datetime, format_datetime, get_datetime_obj
from core.logger import get_logger

logger = get_logger(__name__)

class RemindersPlugin(PluginBase):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.name = "reminders"
        self.reminders_file = os.path.join(self.config.get("data_dir", "data"), "reminders.json")
        self.reminders = self._load_reminders()
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        self._schedule_reminders()

    def _load_reminders(self) -> List[Dict[str, Any]]:
        """Load reminders from file"""
        if os.path.exists(self.reminders_file):
            try:
                with open(self.reminders_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading reminders: {e}")
                return []
        return []

    def _save_reminders(self) -> None:
        """Save reminders to file"""
        try:
            with open(self.reminders_file, "w") as f:
                json.dump(self.reminders, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving reminders: {e}")

    def _schedule_reminders(self) -> None:
        """Schedule all reminders"""
        for reminder in self.reminders:
            if not reminder.get("completed", False):
                self._schedule_reminder(reminder)

    def _schedule_reminder(self, reminder: Dict[str, Any]) -> None:
        """Schedule a single reminder"""
        reminder_id = reminder.get("id")
        reminder_time = reminder.get("time")
        recurrence = reminder.get("recurrence")

        if not reminder_id or not reminder_time:
            return

        # Skip scheduling if the reminder is in the past and doesn't recur
        reminder_dt = get_datetime_obj(reminder_time)
        if not recurrence and reminder_dt < datetime.datetime.now():
            return

        # Remove existing job if it exists
        if self.scheduler.get_job(reminder_id):
            self.scheduler.remove_job(reminder_id)

        # Schedule the reminder
        if recurrence:
            # Handle recurrence patterns
            if recurrence == "daily":
                trigger = IntervalTrigger(days=1, start_date=reminder_dt)
            elif recurrence == "weekly":
                trigger = IntervalTrigger(weeks=1, start_date=reminder_dt)
            elif recurrence == "monthly":
                # For monthly, we need to reschedule after each occurrence
                # because IntervalTrigger doesn't handle month intervals well
                trigger = DateTrigger(run_date=reminder_dt)
            elif recurrence == "yearly":
                # Similar to monthly, we'll reschedule after each occurrence
                trigger = DateTrigger(run_date=reminder_dt)
            else:
                # Default to one-time reminder if recurrence is unknown
                trigger = DateTrigger(run_date=reminder_dt)
        else:
            # One-time reminder
            trigger = DateTrigger(run_date=reminder_dt)

        self.scheduler.add_job(
            self._reminder_callback,
            trigger=trigger,
            args=[reminder],
            id=reminder_id,
            replace_existing=True
        )

    def _reminder_callback(self, reminder: Dict[str, Any]) -> None:
        """Callback function when a reminder is triggered"""
        reminder_id = reminder.get("id")
        title = reminder.get("title", "Reminder")
        recurrence = reminder.get("recurrence")

        # Send notification
        notification = Notification(
            title="Reminder",
            message=title,
            source=self.name,
            priority=reminder.get("priority", "normal"),
            actions=[{"name": "Complete", "value": f"complete_reminder {reminder_id}"}]
        )
        self.send_notification(notification)

        # Handle recurrence
        if recurrence:
            if recurrence == "monthly":
                # Reschedule for next month
                next_time = get_datetime_obj(reminder.get("time")) + relativedelta(months=1)
                reminder["time"] = next_time.isoformat()
                self._schedule_reminder(reminder)
            elif recurrence == "yearly":
                # Reschedule for next year
                next_time = get_datetime_obj(reminder.get("time")) + relativedelta(years=1)
                reminder["time"] = next_time.isoformat()
                self._schedule_reminder(reminder)
            # For daily and weekly, the IntervalTrigger handles rescheduling
        else:
            # Mark one-time reminder as completed
            reminder["completed"] = True

        # Save changes
        self._save_reminders()

    def _generate_reminder_id(self) -> str:
        """Generate a unique ID for a reminder"""
        return f"reminder_{int(time.time())}_{len(self.reminders)}"

    def _find_reminder_by_id(self, reminder_id: str) -> Optional[Dict[str, Any]]:
        """Find a reminder by its ID"""
        for reminder in self.reminders:
            if reminder.get("id") == reminder_id:
                return reminder
        return None

    def _find_reminders_by_title(self, title: str) -> List[Dict[str, Any]]:
        """Find reminders by title (partial match)"""
        return [r for r in self.reminders if title.lower() in r.get("title", "").lower()]

    def _check_reminders(self) -> List[Dict[str, Any]]:
        """Check for reminders that are due today"""
        today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + datetime.timedelta(days=1)
        
        today_reminders = []
        for reminder in self.reminders:
            if reminder.get("completed", False):
                continue
                
            reminder_time = get_datetime_obj(reminder.get("time", ""))
            if today <= reminder_time < tomorrow:
                today_reminders.append(reminder)
                
        return today_reminders

    def _format_reminder_time(self, reminder: Dict[str, Any]) -> str:
        """Format the reminder time for display"""
        reminder_time = get_datetime_obj(reminder.get("time", ""))
        return format_datetime(reminder_time)

    def _format_reminder(self, reminder: Dict[str, Any]) -> str:
        """Format a reminder for display"""
        title = reminder.get("title", "Untitled")
        time_str = self._format_reminder_time(reminder)
        recurrence = reminder.get("recurrence", "")
        priority = reminder.get("priority", "normal")
        completed = "✓" if reminder.get("completed", False) else "⏰"
        
        recurrence_str = ""
        if recurrence:
            recurrence_str = f" (Repeats: {recurrence})"
            
        priority_icon = "🔴" if priority == "high" else "🔵" if priority == "normal" else "⚪"
        
        return f"{completed} {priority_icon} {title} - {time_str}{recurrence_str}"

    def _format_reminders_list(self, reminders: List[Dict[str, Any]], filter_type: str = "all") -> str:
        """Format a list of reminders for display"""
        if not reminders:
            return "No reminders found."
            
        # Filter reminders based on filter_type
        filtered_reminders = reminders
        if filter_type == "today":
            today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow = today + datetime.timedelta(days=1)
            filtered_reminders = [
                r for r in reminders 
                if not r.get("completed", False) and 
                today <= get_datetime_obj(r.get("time", "")) < tomorrow
            ]
        elif filter_type == "upcoming":
            now = datetime.datetime.now()
            filtered_reminders = [
                r for r in reminders 
                if not r.get("completed", False) and 
                get_datetime_obj(r.get("time", "")) >= now
            ]
        elif filter_type == "completed":
            filtered_reminders = [r for r in reminders if r.get("completed", False)]
        elif filter_type == "active":
            filtered_reminders = [r for r in reminders if not r.get("completed", False)]
            
        if not filtered_reminders:
            return f"No {filter_type} reminders found."
            
        # Sort reminders by time
        sorted_reminders = sorted(
            filtered_reminders, 
            key=lambda r: get_datetime_obj(r.get("time", ""))
        )
        
        # Format each reminder
        formatted_reminders = [self._format_reminder(r) for r in sorted_reminders]
        
        # Add header based on filter type
        header = f"{filter_type.capitalize()} Reminders:" if filter_type != "all" else "All Reminders:"
        
        return f"{header}\n" + "\n".join(formatted_reminders)

    def _get_birthday_reminders(self) -> List[Dict[str, Any]]:
        """Get all birthday reminders"""
        return [r for r in self.reminders if r.get("type") == "birthday"]

    def _find_birthday_reminder_by_person(self, person: str) -> Optional[Dict[str, Any]]:
        """Find a birthday reminder by person name"""
        birthday_reminders = self._get_birthday_reminders()
        for reminder in birthday_reminders:
            if reminder.get("person", "").lower() == person.lower():
                return reminder
        return None

    def _check_birthdays(self) -> List[Dict[str, Any]]:
        """Check for birthdays that are today"""
        today = datetime.datetime.now().date()
        
        today_birthdays = []
        for reminder in self._get_birthday_reminders():
            birth_date = get_datetime_obj(reminder.get("birth_date", "")).date()
            if birth_date.month == today.month and birth_date.day == today.day:
                today_birthdays.append(reminder)
                
        return today_birthdays

    def _format_birthday_reminder(self, reminder: Dict[str, Any]) -> str:
        """Format a birthday reminder for display"""
        person = reminder.get("person", "Unknown")
        birth_date = get_datetime_obj(reminder.get("birth_date", ""))
        
        # Calculate age
        today = datetime.datetime.now().date()
        age = today.year - birth_date.year
        if (birth_date.month, birth_date.day) > (today.month, today.day):
            age -= 1
            
        return f"🎂 {person}'s Birthday - {birth_date.strftime('%B %d')} (Age: {age})"

    def _format_birthday_list(self, reminders: List[Dict[str, Any]]) -> str:
        """Format a list of birthday reminders for display"""
        if not reminders:
            return "No birthday reminders found."
            
        # Sort birthdays by month and day
        sorted_reminders = sorted(
            reminders, 
            key=lambda r: (
                get_datetime_obj(r.get("birth_date", "")).month,
                get_datetime_obj(r.get("birth_date", "")).day
            )
        )
        
        # Format each birthday reminder
        formatted_reminders = [self._format_birthday_reminder(r) for r in sorted_reminders]
        
        return "Birthday Reminders:\n" + "\n".join(formatted_reminders)

    def _sync_contacts_birthdays(self, contacts: List[Dict[str, Any]]) -> Tuple[int, int, int]:
        """Sync birthday reminders with contacts"""
        added = 0
        updated = 0
        unchanged = 0
        
        for contact in contacts:
            name = contact.get("name")
            birth_date = contact.get("birth_date")
            
            if not name or not birth_date:
                continue
                
            # Check if we already have a birthday reminder for this person
            existing_reminder = self._find_birthday_reminder_by_person(name)
            
            if existing_reminder:
                # Update existing reminder if birth date has changed
                existing_birth_date = existing_reminder.get("birth_date")
                if existing_birth_date != birth_date:
                    existing_reminder["birth_date"] = birth_date
                    updated += 1
                else:
                    unchanged += 1
            else:
                # Create new birthday reminder
                reminder_id = self._generate_reminder_id()
                
                # Parse the birth date to create a recurring yearly reminder
                birth_dt = get_datetime_obj(birth_date)
                
                # Set reminder for this year's birthday
                this_year = datetime.datetime.now().year
                birthday_this_year = birth_dt.replace(year=this_year)
                
                # If birthday already passed this year, set for next year
                if birthday_this_year < datetime.datetime.now():
                    birthday_this_year = birthday_this_year.replace(year=this_year + 1)
                
                new_reminder = {
                    "id": reminder_id,
                    "type": "birthday",
                    "person": name,
                    "birth_date": birth_date,
                    "title": f"{name}'s Birthday",
                    "time": birthday_this_year.isoformat(),
                    "recurrence": "yearly",
                    "priority": "normal",
                    "completed": False
                }
                
                self.reminders.append(new_reminder)
                self._schedule_reminder(new_reminder)
                added += 1
        
        # Save changes
        self._save_reminders()
        
        return added, updated, unchanged

    def _send_birthday_wishes(self, person: str, message: Optional[str] = None) -> bool:
        """Send birthday wishes to a person"""
        # Find the birthday reminder for this person
        birthday_reminder = self._find_birthday_reminder_by_person(person)
        if not birthday_reminder:
            return False
            
        # Check if we have the Gmail plugin available
        gmail_plugin = self.get_plugin("gmail")
        if not gmail_plugin:
            return False
            
        # Get the person's email from contacts
        contacts_plugin = self.get_plugin("contacts")
        if not contacts_plugin:
            return False
            
        # Find the contact
        contact = contacts_plugin.find_contact_by_name(person)
        if not contact or not contact.get("email"):
            return False
            
        email = contact.get("email")
        
        # Prepare the birthday message
        if not message:
            message = f"Happy Birthday, {person}! 🎂🎉 Hope you have a wonderful day!"
            
        subject = f"Happy Birthday, {person}!"
        
        # Send the email
        try:
            gmail_plugin.send_email(email, subject, message)
            return True
        except Exception as e:
            logger.error(f"Error sending birthday wishes: {e}")
            return False

    def execute_command(self, command: str, args: Dict[str, Any]) -> str:
        """Execute a command with the given arguments"""
        if command == "add_reminder":
            title = args.get("title")
            time_str = args.get("time")
            recurrence = args.get("recurrence")
            priority = args.get("priority", "normal")
            
            if not title or not time_str:
                return "Error: Title and time are required for adding a reminder."
                
            # Parse the time string to a datetime object
            try:
                reminder_time = extract_datetime(time_str)
                if not reminder_time:
                    return f"Error: Could not parse time '{time_str}'."
            except Exception as e:
                return f"Error parsing time: {str(e)}"
                
            # Create a new reminder
            reminder_id = self._generate_reminder_id()
            new_reminder = {
                "id": reminder_id,
                "title": title,
                "time": reminder_time.isoformat(),
                "priority": priority,
                "completed": False
            }
            
            if recurrence:
                new_reminder["recurrence"] = recurrence
                
            self.reminders.append(new_reminder)
            self._schedule_reminder(new_reminder)
            self._save_reminders()
            
            time_str = format_datetime(reminder_time)
            recurrence_str = f" (Repeats: {recurrence})" if recurrence else ""
            return f"Reminder added: {title} - {time_str}{recurrence_str}"
            
        elif command == "list_reminders":
            filter_type = args.get("filter_type", "all")
            return self._format_reminders_list(self.reminders, filter_type)
            
        elif command == "complete_reminder":
            reminder_id = args.get("reminder_id")
            title = args.get("title")
            
            if reminder_id:
                # Find reminder by ID
                reminder = self._find_reminder_by_id(reminder_id)
                if not reminder:
                    return f"Error: Reminder with ID {reminder_id} not found."
                    
                reminder["completed"] = True
                
                # Remove the scheduled job
                if self.scheduler.get_job(reminder_id):
                    self.scheduler.remove_job(reminder_id)
                    
                self._save_reminders()
                return f"Marked reminder as completed: {reminder.get('title')}"
                
            elif title:
                # Find reminders by title
                matching_reminders = self._find_reminders_by_title(title)
                if not matching_reminders:
                    return f"Error: No reminders found with title containing '{title}'."
                    
                # If multiple matches, complete the earliest one that's not already completed
                active_reminders = [r for r in matching_reminders if not r.get("completed", False)]
                if not active_reminders:
                    return f"Error: All matching reminders are already completed."
                    
                # Sort by time and complete the earliest
                sorted_reminders = sorted(
                    active_reminders, 
                    key=lambda r: get_datetime_obj(r.get("time", ""))
                )
                
                reminder = sorted_reminders[0]
                reminder_id = reminder.get("id")
                reminder["completed"] = True
                
                # Remove the scheduled job
                if self.scheduler.get_job(reminder_id):
                    self.scheduler.remove_job(reminder_id)
                    
                self._save_reminders()
                return f"Marked reminder as completed: {reminder.get('title')}"
            else:
                return "Error: Either reminder_id or title is required to complete a reminder."
                
        elif command == "delete_reminder":
            reminder_id = args.get("reminder_id")
            title = args.get("title")
            
            if reminder_id:
                # Find reminder by ID
                reminder = self._find_reminder_by_id(reminder_id)
                if not reminder:
                    return f"Error: Reminder with ID {reminder_id} not found."
                    
                # Remove the reminder
                self.reminders.remove(reminder)
                
                # Remove the scheduled job
                if self.scheduler.get_job(reminder_id):
                    self.scheduler.remove_job(reminder_id)
                    
                self._save_reminders()
                return f"Deleted reminder: {reminder.get('title')}"
                
            elif title:
                # Find reminders by title
                matching_reminders = self._find_reminders_by_title(title)
                if not matching_reminders:
                    return f"Error: No reminders found with title containing '{title}'."
                    
                # If multiple matches, delete the earliest one
                sorted_reminders = sorted(
                    matching_reminders, 
                    key=lambda r: get_datetime_obj(r.get("time", ""))
                )
                
                reminder = sorted_reminders[0]
                reminder_id = reminder.get("id")
                
                # Remove the reminder
                self.reminders.remove(reminder)
                
                # Remove the scheduled job
                if self.scheduler.get_job(reminder_id):
                    self.scheduler.remove_job(reminder_id)
                    
                self._save_reminders()
                return f"Deleted reminder: {reminder.get('title')}"
            else:
                return "Error: Either reminder_id or title is required to delete a reminder."
                
        elif command == "create_birthday_reminder":
            person = args.get("person")
            birth_date_str = args.get("birth_date")
            
            if not person or not birth_date_str:
                return "Error: Person name and birth date are required."
                
            # Check if we already have a birthday reminder for this person
            existing_reminder = self._find_birthday_reminder_by_person(person)
            if existing_reminder:
                return f"Error: Birthday reminder for {person} already exists."
                
            # Parse the birth date
            try:
                birth_date = date_parser.parse(birth_date_str)
            except Exception as e:
                return f"Error parsing birth date: {str(e)}"
                
            # Create a new birthday reminder
            reminder_id = self._generate_reminder_id()
            
            # Set reminder for this year's birthday
            this_year = datetime.datetime.now().year
            birthday_this_year = birth_date.replace(year=this_year)
            
            # If birthday already passed this year, set for next year
            if birthday_this_year < datetime.datetime.now():
                birthday_this_year = birthday_this_year.replace(year=this_year + 1)
            
            new_reminder = {
                "id": reminder_id,
                "type": "birthday",
                "person": person,
                "birth_date": birth_date.isoformat(),
                "title": f"{person}'s Birthday",
                "time": birthday_this_year.isoformat(),
                "recurrence": "yearly",
                "priority": "normal",
                "completed": False
            }
            
            self.reminders.append(new_reminder)
            self._schedule_reminder(new_reminder)
            self._save_reminders()
            
            return f"Birthday reminder created for {person} (born {birth_date.strftime('%B %d, %Y')})"
            
        elif command == "list_birthdays":
            birthday_reminders = self._get_birthday_reminders()
            return self._format_birthday_list(birthday_reminders)
            
        elif command == "sync_contacts":
            contacts_plugin = self.get_plugin("contacts")
            if not contacts_plugin:
                return "Error: Contacts plugin not available."
                
            contacts = contacts_plugin.get_contacts_with_birthdays()
            added, updated, unchanged = self._sync_contacts_birthdays(contacts)
            
            return f"Synced birthday reminders with contacts: {added} added, {updated} updated, {unchanged} unchanged."
            
        elif command == "send_birthday_wishes":
            person = args.get("person")
            message = args.get("message")
            
            if not person:
                return "Error: Person name is required."
                
            success = self._send_birthday_wishes(person, message)
            if success:
                return f"Birthday wishes sent to {person}."
            else:
                return f"Error: Could not send birthday wishes to {person}."
                
        else:
            return f"Error: Unknown command '{command}'."

    def get_intents(self) -> Dict[str, List[str]]:
        """Get the intents supported by this plugin"""
        return {
            "add_reminder": [
                "remind me to {title} at {time}",
                "add a reminder to {title} at {time}",
                "create a reminder to {title} at {time}",
                "set a reminder to {title} at {time}",
                "remind me to {title} on {time}",
                "remind me to {title} every {recurrence}",
                "add a {priority} priority reminder to {title} at {time}",
                "remind me about {title} at {time}"
            ],
            "list_reminders": [
                "show my reminders",
                "list my reminders",
                "what are my reminders",
                "show me my reminders",
                "show my {filter_type} reminders",
                "list my {filter_type} reminders",
                "what are my {filter_type} reminders"
            ],
            "complete_reminder": [
                "mark reminder {title} as complete",
                "complete reminder {title}",
                "mark reminder {title} as done",
                "finish reminder {title}",
                "i completed reminder {title}",
                "i finished reminder {title}"
            ],
            "create_birthday_reminder": [
                "add {person}'s birthday on {birth_date}",
                "create a birthday reminder for {person} on {birth_date}",
                "remember {person}'s birthday on {birth_date}",
                "add a birthday for {person} on {birth_date}",
                "{person}'s birthday is on {birth_date}"
            ],
            "list_birthdays": [
                "show birthdays",
                "list birthdays",
                "show birthday reminders",
                "list birthday reminders",
                "what birthdays do i have saved"
            ],
            "sync_contacts": [
                "sync birthdays with contacts",
                "update birthdays from contacts",
                "import birthdays from contacts",
                "sync contact birthdays"
            ],
            "send_birthday_wishes": [
                "send birthday wishes to {person}",
                "wish {person} happy birthday",
                "send {person} birthday greetings",
                "email birthday wishes to {person}",
                "send birthday message to {person}",
                "send birthday wishes to {person} with message {message}",
                "wish {person} happy birthday saying {message}",
                "send {person} birthday wishes that says {message}"
            ],
            "delete_reminder": [
                "delete reminder {title}",
                "remove reminder {title}",
                "cancel reminder {title}",
                "delete the reminder for {title}",
                "remove the reminder about {title}"
            ]
        }

    def handle_intent(self, intent: str, text: str, entities: Dict[str, Any]) -> str:
        """Handle an intent with the given text and entities"""
        if intent == "add_reminder":
            # Extract title, time, recurrence, and priority from entities or text
            title = entities.get("title", "")
            time_str = entities.get("time", "")
            recurrence = entities.get("recurrence", "")
            priority = entities.get("priority", "normal")
            
            # If title or time is missing, try to extract from text
            if not title or not time_str:
                # Try to extract title using regex if not in entities
                if not title:
                    title_match = re.search(r"remind me to (.+?) (at|on|every)", text, re.IGNORECASE)
                    if title_match:
                        title = title_match.group(1).strip()
                
                # Try to extract time using regex if not in entities
                if not time_str:
                    time_match = re.search(r"(at|on) (.+?)( |$)", text, re.IGNORECASE)
                    if time_match:
                        time_str = time_match.group(2).strip()
                        
                # Try to extract recurrence using regex if not in entities
                if not recurrence:
                    recurrence_match = re.search(r"every (day|week|month|year|daily|weekly|monthly|yearly)", text, re.IGNORECASE)
                    if recurrence_match:
                        recurrence = recurrence_match.group(1).strip().lower()
                        # Normalize recurrence terms
                        if recurrence == "day":
                            recurrence = "daily"
                        elif recurrence == "week":
                            recurrence = "weekly"
                        elif recurrence == "month":
                            recurrence = "monthly"
                        elif recurrence == "year":
                            recurrence = "yearly"
                
                # Try to extract priority using regex if not in entities
                if priority == "normal":
                    priority_match = re.search(r"(high|low) priority", text, re.IGNORECASE)
                    if priority_match:
                        priority = priority_match.group(1).strip().lower()
            
            # Execute command
            return self.execute_command("add_reminder", {
                "title": title,
                "time": time_str,
                "recurrence": recurrence,
                "priority": priority
            })
            
        elif intent == "list_reminders":
            # Extract filter type from entities or text
            filter_type = entities.get("filter_type", "all")
            
            # If filter type is missing, try to extract from text
            if filter_type == "all":
                filter_match = re.search(r"(today|upcoming|completed|active) reminders", text, re.IGNORECASE)
                if filter_match:
                    filter_type = filter_match.group(1).strip().lower()
            
            # Execute command
            return self.execute_command("list_reminders", {
                "filter_type": filter_type
            })
            
        elif intent == "complete_reminder":
            # Extract reminder title from entities or text
            title = entities.get("title", "")
            
            # If title is missing, try to extract from text
            if not title:
                title_match = re.search(r"reminder (.+?) as (complete|done|finished)", text, re.IGNORECASE)
                if not title_match:
                    title_match = re.search(r"(complete|finish) reminder (.+?)( |$)", text, re.IGNORECASE)
                    if title_match:
                        title = title_match.group(2).strip()
                else:
                    title = title_match.group(1).strip()
            
            # Execute command
            return self.execute_command("complete_reminder", {
                "title": title
            })
            
        elif intent == "create_birthday_reminder":
            # Extract person name and birth date from entities or text
            person = entities.get("person", "")
            birth_date = entities.get("birth_date", "")
            
            # If person or birth date is missing, try to extract from text
            if not person or not birth_date:
                # Try to extract person using regex if not in entities
                if not person:
                    person_match = re.search(r"add (.+?)'s birthday", text, re.IGNORECASE)
                    if not person_match:
                        person_match = re.search(r"birthday reminder for (.+?) on", text, re.IGNORECASE)
                        if not person_match:
                            person_match = re.search(r"remember (.+?)'s birthday", text, re.IGNORECASE)
                            if not person_match:
                                person_match = re.search(r"(.+?)'s birthday is on", text, re.IGNORECASE)
                    if person_match:
                        person = person_match.group(1).strip()
                
                # Try to extract birth date using regex if not in entities
                if not birth_date:
                    date_match = re.search(r"birthday (on|is on|is) (.+?)( |$)", text, re.IGNORECASE)
                    if date_match:
                        birth_date = date_match.group(2).strip()
            
            # Execute command
            return self.execute_command("create_birthday_reminder", {
                "person": person,
                "birth_date": birth_date
            })
            
        elif intent == "list_birthdays":
            # No parameters needed
            return self.execute_command("list_birthdays", {})
            
        elif intent == "sync_contacts":
            # No parameters needed
            return self.execute_command("sync_contacts", {})
            
        elif intent == "send_birthday_wishes":
            # Extract person name and custom message from entities or text
            person = entities.get("person", "")
            
            # Extract custom message from entities or text
            message = entities.get("message", "")
            if not message:
                # Try to extract custom message from text
                match = re.search(r"(with message|saying|that says)\s+[\'\"](.*?)[\'\"]", text, re.IGNORECASE)
                if match:
                    message = match.group(2).strip()
                    
            # If person is provided, send birthday wishes
            if person:
                return self.execute_command("send_birthday_wishes", {"person": person, "message": message})
            else:
                return {"error": "No person specified for birthday wishes."}