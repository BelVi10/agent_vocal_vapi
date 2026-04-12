import os
import json
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

CALENDAR_ID = 'primary'
TIMEZONE = 'Europe/Paris'
DEFAULT_MEAL_DURATION = 90
RESTAURANT_CAPACITY = 60

def get_google_calendar_service():
    try:
        credentials_info = json.loads(os.environ.get('GOOGLE_CREDENTIALS'))
        
        SCOPES = [
            'https://www.googleapis.com/auth/calendar',
            'https://www.googleapis.com/auth/calendar.events'
        ]
        
        credentials = Credentials.from_service_account_info(credentials_info, scopes=SCOPES)
        service = build('calendar', 'v3', credentials=credentials)
        return service
        
    except Exception as e:
        print(f"Erreur : {str(e)}")
        return None

def get_events_in_time_range(start_datetime_iso, end_datetime_iso):
    service = get_google_calendar_service()
    if not service:
        return []
    
    try:
        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=start_datetime_iso,
            timeMax=end_datetime_iso,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        return events_result.get('items', [])
        
    except Exception as e:
        print(f"Erreur : {str(e)}")
        return []

def get_total_guests_for_slot(start_datetime_iso, end_datetime_iso):
    events = get_events_in_time_range(start_datetime_iso, end_datetime_iso)
    total_guests = 0
    
    for event in events:
        description = event.get('description', '')
        if 'Nombre de couverts :' in description:
            import re
            match = re.search(r'Nombre de couverts : (\d+)', description)
            if match:
                total_guests += int(match.group(1))
    
    return total_guests

def is_slot_available_with_capacity(start_datetime_iso, end_datetime_iso, requested_guests):
    events = get_events_in_time_range(start_datetime_iso, end_datetime_iso)
    
    if events:
        return False
    
    total_guests = get_total_guests_for_slot(start_datetime_iso, end_datetime_iso)
    return (total_guests + requested_guests) <= RESTAURANT_CAPACITY

def find_available_slots(date_str, guests, duration_minutes=DEFAULT_MEAL_DURATION):
    service = get_google_calendar_service()
    if not service:
        return []
    
    available_slots = []
    possible_times = ["12:00", "12:45", "13:30","19:00","19:45" ,"20:30", "21:15"]
    
    for time_str in possible_times:
        start_datetime = datetime.fromisoformat(f"{date_str}T{time_str}:00")
        end_datetime = start_datetime + timedelta(minutes=duration_minutes)
        
        if time_str < "14:00" and end_datetime.time() > datetime.strptime("14:00", "%H:%M").time():
            continue
        if time_str >= "19:00" and end_datetime.time() > datetime.strptime("22:30", "%H:%M").time():
            continue
        
        start_iso = start_datetime.isoformat() + '+02:00'
        end_iso = end_datetime.isoformat() + '+02:00'
        
        if is_slot_available_with_capacity(start_iso, end_iso, guests):
            available_slots.append(time_str)
    
    return available_slots

def create_restaurant_booking(customer_name, customer_phone, customer_email, 
                               start_datetime_iso, guests, 
                               duration_minutes=DEFAULT_MEAL_DURATION):
    service = get_google_calendar_service()
    if not service:
        return {"success": False, "error": "Service Calendar non disponible"}
    
    end_dt = datetime.fromisoformat(start_datetime_iso) + timedelta(minutes=duration_minutes)
    end_datetime_iso = end_dt.isoformat()
    
    if not is_slot_available_with_capacity(start_datetime_iso, end_datetime_iso, guests):
        return {"success": False, "error": "Plus de places disponibles sur ce créneau"}
    
    try:
        event = {
            'summary': f"Réservation - {customer_name} ({guests} pers.)",
            'description': f"""
Réservation au nom de : {customer_name}
Téléphone : {customer_phone}
Email : {customer_email}
Nombre de couverts : {guests}
Durée : {duration_minutes} minutes
            """.strip(),
            'start': {
                'dateTime': start_datetime_iso,
                'timeZone': TIMEZONE,
            },
            'end': {
                'dateTime': end_datetime_iso,
                'timeZone': TIMEZONE,
            },
            'attendees': [
                {'email': customer_email, 'responseStatus': 'accepted'},
            ],
        }
        
        created_event = service.events().insert(
            calendarId=CALENDAR_ID, 
            body=event,
            sendUpdates='all'
        ).execute()
        
        return {
            "success": True,
            "event_id": created_event.get('id'),
            "event_link": created_event.get('htmlLink'),
            "start": start_datetime_iso,
            "end": end_datetime_iso
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}
