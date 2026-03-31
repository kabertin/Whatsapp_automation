import requests
from decouple import config

def send_whatsapp_message(to_number, text):
    url = f"https://graph.facebook.com/v21.0/{config('WHATSAPP_PHONE_ID')}/messages"
    headers = {
        "Authorization": f"Bearer {config('WHATSAPP_TOKEN')}",
        "Content-Type": "application/json",
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text}
    }
    response = requests.post(url, headers=headers, json=data)
    return response.json()
