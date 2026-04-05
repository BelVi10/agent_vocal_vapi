from flask import Flask, request, jsonify
import os
from datetime import datetime
from dotenv import load_dotenv
from calendar_utils import find_available_slots, create_restaurant_booking

load_dotenv()
app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "message": "Serveur réservations restaurant"})

@app.route('/checkAvailability', methods=['POST'])
def check_availability():
    """
    Vérifie les créneaux disponibles pour une date et un nombre de couverts.
    """
    try:
        data = request.get_json()
        
        date_str = data.get('date') or data.get('preferredDate')
        guests = data.get('guests', 2)
        
        if not date_str:
            return jsonify({"status": "error", "message": "Date manquante"}), 400
        
        available_slots = find_available_slots(date_str, guests)
        
        return jsonify({
            "status": "success",
            "date": date_str,
            "guests": guests,
            "availableSlots": available_slots
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/bookRestaurant', methods=['POST'])
def book_restaurant():
    """
    Crée une réservation restaurant.
    """
    try:
        data = request.get_json()
        
        customer_name = data.get('name')
        customer_phone = data.get('phone')
        customer_email = data.get('email')
        start_datetime = data.get('startDateTime')
        guests = data.get('guests', 2)
        
        if not customer_name:
            return jsonify({"status": "error", "message": "Nom manquant"}), 400
        if not start_datetime:
            return jsonify({"status": "error", "message": "Date et heure manquantes"}), 400
        
        start_iso = start_datetime + '+02:00'
        
        result = create_restaurant_booking(
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email=customer_email,
            start_datetime_iso=start_iso,
            guests=guests
        )
        
        if result['success']:
            return jsonify({
                "status": "success",
                "message": f"Réservation confirmée pour {customer_name} le {start_datetime}",
                "eventId": result['event_id']
            })
        else:
            return jsonify({"status": "error", "message": result.get('error')}), 400
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)