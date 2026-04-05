import os
from datetime import datetime, timedelta
from pathlib import Path
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

CALENDAR_ID = 'primary'
TIMEZONE = 'Europe/Paris'
DEFAULT_MEAL_DURATION = 90
RESTAURANT_CAPACITY = 30  # Nombre maximum de couverts par créneau

def get_google_calendar_service():
    try:
        BASE_DIR = Path(__file__).resolve().parent
        CREDENTIALS_FILE = os.path.join(BASE_DIR, 'token.json')
        
        SCOPES = [
            'https://www.googleapis.com/auth/calendar',
            'https://www.googleapis.com/auth/calendar.events'
        ]
        
        credentials = Credentials.from_service_account_file(
            CREDENTIALS_FILE, 
            scopes=SCOPES
        )
        
        service = build('calendar', 'v3', credentials=credentials)
        return service
        
    except Exception as e:
        print(f"Erreur : {str(e)}")
        return None

def get_events_in_time_range(start_datetime_iso, end_datetime_iso):
    """
    Récupère tous les événements dans une plage horaire.
    """
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
    """
    Calcule le nombre total de couverts déjà réservés sur un créneau.
    """
    events = get_events_in_time_range(start_datetime_iso, end_datetime_iso)
    total_guests = 0
    
    for event in events:
        # Chercher le nombre de couverts dans la description
        description = event.get('description', '')
        if 'Nombre de couverts :' in description:
            # Extraire le nombre (ex: "Nombre de couverts : 4")
            import re
            match = re.search(r'Nombre de couverts : (\d+)', description)
            if match:
                total_guests += int(match.group(1))
    
    return total_guests

def is_slot_available_with_capacity(start_datetime_iso, end_datetime_iso, requested_guests):
    """
    Vérifie si un créneau est disponible en termes de temps ET de capacité.
    """
    # D'abord vérifier si le créneau existe déjà dans le calendrier
    # (pour éviter les doublons de temps)
    events = get_events_in_time_range(start_datetime_iso, end_datetime_iso)
    
    # Si des événements existent déjà sur ce créneau, ils sont forcément dans la plage
    # car un restaurant ne peut pas avoir deux réservations qui se chevauchent sans gestion des tables
    if events:
        # On considère que si des événements existent, le créneau est occupé
        # (on pourrait affiner par table, mais on garde simple pour l'instant)
        return False
    
    # Vérifier la capacité pour cette plage horaire
    # Pour l'instant, on vérifie juste qu'on ne dépasse pas la capacité totale
    # Une version plus avancée vérifierait par table
    total_guests = get_total_guests_for_slot(start_datetime_iso, end_datetime_iso)
    
    return (total_guests + requested_guests) <= RESTAURANT_CAPACITY

def find_available_slots(date_str, guests, duration_minutes=DEFAULT_MEAL_DURATION):
    """
    Trouve les créneaux disponibles pour une date et un nombre de couverts donnés.
    """
    service = get_google_calendar_service()
    if not service:
        return []
    
    available_slots = []
    
    # Créneaux possibles
    possible_times = ["12:00", "12:30", "13:00", "13:30", "19:00", "19:30", "20:00", "20:30", "21:00"]
    
    for time_str in possible_times:
        start_datetime = datetime.fromisoformat(f"{date_str}T{time_str}:00")
        end_datetime = start_datetime + timedelta(minutes=duration_minutes)
        
        # Vérifier les limites horaires
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
    """
    Crée une réservation restaurant dans Google Calendar.
    """
    service = get_google_calendar_service()
    if not service:
        return {"success": False, "error": "Service Calendar non disponible"}
    
    # Vérifier la disponibilité AVANT de créer
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