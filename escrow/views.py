import os
import re
import json
import requests
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import ChatSession, Provider, UserProfile, CategoryConfig, MomoTransaction
from django.shortcuts import render, HttpResponse, get_object_or_404
from django.db.models import Q
import urllib.parse
from .validators import validate_rwanda_id
from django.utils import timezone
from datetime import timedelta


# --- CONFIGURATION (Move these to settings.py later) ---
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN") # The one you set in Meta Dashboard
MY_PERSONAL_NUMBER = "250789512989" # Put your number here

def send_whatsapp_message(to, text):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    response = requests.post(url, headers=headers, json=payload)
    return response.json()

def handle_back_command(session, sender):
    state = session.state
    data = session.temp_data

    # Map current state to the previous one
    mapping = {
        "AWAITING_NAME": "START",
        "AWAITING_FRONT_ID": "AWAITING_NAME",
        "AWAITING_BACK_ID": "AWAITING_FRONT_ID",
        "AWAITING_FACE_SCAN": "AWAITING_BACK_ID",
        "AWAITING_RDB": "AWAITING_BACK_ID",
        "AWAITING_CATEGORY": "AWAITING_FACE_SCAN" if data.get('entity_type') == "INDIVIDUAL" else "AWAITING_RDB",
        "AWAITING_DISTRICT": "AWAITING_CATEGORY",
        "AWAITING_SECTOR": "AWAITING_DISTRICT",
        "AWAITING_PORTFOLIO": "AWAITING_SECTOR",
        "AWAITING_CONFIRMATION": "AWAITING_PORTFOLIO",
    }

    new_state = mapping.get(state, "START")
    session.state = new_state
    session.save()

    # Special handling for states that require buttons instead of just text
    if new_state == "START":
        return send_welcome_message(sender)

    if new_state == "AWAITING_CATEGORY":
        return trigger_category_selection(session, sender)

    # General prompt for text/media states
    prompts = {
        "AWAITING_NAME": "🔙 Back to Name. Please enter your name again:",
        "AWAITING_FRONT_ID": "🔙 Back to ID. Please upload the **FRONT** of your ID:",
        "AWAITING_BACK_ID": "🔙 Back to ID. Please upload the **BACK** of your ID:",
        "AWAITING_FACE_SCAN": "🔙 Back to Face Scan. Please send the 5-15 seconds video of your face, remember to turn left and right in the video:",
        "AWAITING_RDB": "🔙 Back to RDB. Please upload your RDB Company Registration Certificate or Tax Declaration Receipt document(In PDF, PNG or JPG):",
        "AWAITING_DISTRICT": "🔙 Back to Location. What is your **District**?",
        "AWAITING_SECTOR": "🔙 Back to Location. What is your **Sector**?",
        "AWAITING_PORTFOLIO": "🔙 Back to Portfolio. You can upload more photos showcasing your Business or type 'DONE':"
    }

    msg = prompts.get(new_state, "Where would you like to go?")
    send_interactive_buttons(sender, msg, [("back", "🔙 Go Back More"), ("reset", "🗑️ Reset")])
    return HttpResponse("OK")

def open_whatsapp_window(to):
    """Sends the approved one-liner to unlock the 24-hour window"""
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "template",
        "template": {
            "name": "mercato_welcome",  # The name you just got approved
            "language": {"code": "en_US"}
        }
    }
    return requests.post(url, headers=headers, json=payload)

def send_welcome_message(to):
    """The Smart Hub: Dynamic menu for Browsing, Registering, or Managing Profile"""
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}

    # 1. Logic Check: Does this user already have a profile?
    provider = Provider.objects.filter(user__phone_number=to, is_deleted=False).first()

    # 2. Dynamic Button Selection
    if provider:
        # If they are a provider, swap 'Register' for 'Manage'
        middle_button = {"type": "reply", "reply": {"id": "manage_profile", "title": "⚙️ Manage Business"}}
        registration_text = (
            "⚙️ *Manage Your Business*\n"
            "Update your visibility or manage your Mercato account settings.\n\n"
        )
    else:
        # If they are a new user, show the standard Register button
        middle_button = {"type": "reply", "reply": {"id": "nav_register_hub", "title": "🏢 Register Service"}}
        registration_text = (
            "🏢 *Register Your Service*\n"
            "Promote your business on Mercato and connect with new clients.\n\n"
        )

    # 3. Construct Payload (Preserving all your original features)
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {
                "type": "image",
                "image": {"link": "https://www.mercato.rw/static/images/mercato_logo.png"}
            },

            "body": {
                "text": (
                    "🌟 *Welcome to Mercato Platform* 🌟\n"
                    "🤝 Rwanda's Professional Service Network 🇷🇼\n\n"
                    "Find trusted professionals near you\n"
                    "or promote your services to reach more clients.\n\n"
                    "*How can we help you today?*\n\n"
                    "🔍 *Find a Service*\n"
                    "Search for services, businesses, or experts near you.\n\n"
                    f"{registration_text}"  # Injected dynamic text
                    "📞 *Contact Admin*\n"
                    "Get direct assistance and support from our team.\n\n"
                    "───────────────\n"
                    "*Mercato Platform*\n"
                    "Company: Heimat50 Ltd\n"
                    "🌐 Website: https://www.mercato.rw\n"
                    "📧 Email: admin@mercato.rw\n"
                    "📍 Address: Gasabo, Kigali, Rwanda\n"
                    "📱 Phone: +250795464615"
                )
            },

            "footer": {"text": "Type 'reset' at any time to return here."},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "nav_browse", "title": "🔍 Find Service"}},
                    middle_button,  # Dynamic Button (Register or Manage)
                    {"type": "reply", "reply": {"id": "nav_admin", "title": "📞 Contact Admin"}}
                ]
            }
        }
    }

    return requests.post(url, headers=headers, json=payload)


def send_whatsapp_list(to, body, options, header="Mercato Services", footer="Select an option", button_label="View Options"):
    """
    A reusable engine for all your menus.
    options: list of tuples [("id", "title"), ...]
    """
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}

    # Automatically format rows and truncate titles to 24 chars (Meta requirement)
    rows = [{"id": str(opt[0]), "title": str(opt[1])[:24], "description": "Select to continue"} for opt in options]

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": header},
            "body": {"text": body},
            "footer": {"text": footer},
            "action": {
                "button": button_label,
                "sections": [{"title": "Results", "rows": rows}]
            }
        }
    }

    # 1. Trigger the actual WhatsApp message
    requests.post(url, headers=headers, json=payload)

    # 2. RETURN THIS TO DJANGO TO STOP THE RETRY LOOP
    # This must be the ONLY return statement at the end of the function
    return HttpResponse("OK")

def send_super_categories(sender):
    # 1. Fetch UNIQUE groups from your 70+ categories
    # values_list('group', 'icon').distinct() is the magic line
    groups = CategoryConfig.objects.filter(is_active=True).values_list('group', 'icon').distinct()[:10]

    # 2. DEBUG: Add this line to see what's happening in your logs
    print(f"DEBUG: Found groups: {list(groups)}")

    if not groups:
        # If no groups found, we'll see this in the logs
        send_whatsapp_message(sender, "⚠️ No categories organized yet. Pleease contact Admin.")
        return HttpResponse("OK")

    # 3. Create the buttons
    # IMPORTANT: ID must start with 'super_' for our router to catch it later
    options = [(f"super_{g[0]}", f"{g[1]} {g[0]}") for g in groups]

    header = "Mercato Services"
    body = "Choose a service category."
    footer = "Rwanda's Trusted Service Hub"

    return send_whatsapp_list(sender, body, options, header=header, footer=footer)

def handle_group_selection(sender, group_name):
    # Fetch categories belonging to the selected group
    categories = CategoryConfig.objects.filter(group=group_name, is_active=True).order_by('name')[:10]

    if not categories:
        send_whatsapp_message(sender, f"No specific services found in {group_name}.")
        return HttpResponse("OK")

    # Create options using the CategoryConfig ID
    options = [(f"cat_{c.id}", c.name) for c in categories]

    msg = f"Choose a specific service in *{group_name}*:"

    return send_whatsapp_list(sender, msg, options)

def send_interactive_buttons(to, text, buttons, footer="Type 'reset' to start over"):
    """
    buttons: list of tuples [("id", "Title")] - Max 3 buttons total.
    """
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}

    formatted_buttons = [{"type": "reply", "reply": {"id": b[0], "title": b[1]}} for b in buttons]

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": text},
            "footer": {"text": footer},
            "action": {"buttons": formatted_buttons}
        }
    }
    requests.post(url, headers=headers, json=payload)

# Inside your webhook function:
@csrf_exempt
def whatsapp_webhook(request):

    # -------------------------
    # 1. WEBHOOK VERIFICATION
    # -------------------------
    if request.method == "GET":
        verify_token = settings.VERIFY_TOKEN
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        if mode == "subscribe" and token == verify_token:
            return HttpResponse(challenge, status=200)

        return HttpResponse("Forbidden", status=403)

    # -------------------------
    # 2. MESSAGE PROCESSING
    # -------------------------
    if request.method == "POST":
        try:
            data = json.loads(request.body)

            for entry in data.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})

                    if "messages" not in value:
                        continue

                    for message in value.get("messages", []):
                        sender = message.get("from")

                        if not sender:
                            continue

                        # --- NEW INTEGRATION START ---
                        # Force open/refresh the 24h window using your approved template
                        # This allows 'interactive' messages to bypass the Meta block.
                        open_whatsapp_window(sender)
                        # --- NEW INTEGRATION END ---

                        session, _ = ChatSession.objects.get_or_create(
                            phone_number=sender
                        )

                        msg_type = message.get("type")

                        # -------------------------
                        # A. INTERACTIVE HANDLING
                        # -------------------------
                        if msg_type == "interactive":
                            interactive = message.get("interactive", {})
                            button_id = None

                            if interactive.get("type") == "button_reply":
                                button_id = interactive["button_reply"].get("id")

                            elif interactive.get("type") == "list_reply":
                                button_id = interactive["list_reply"].get("id")

                            if button_id:
                                handle_button_reply(session, sender, button_id)

                        # -------------------------
                        # B. TEXT HANDLING
                        # -------------------------
                        elif msg_type == "text":
                            text = message["text"]["body"].strip().lower()

                            if text == "reset":
                                session.state = "START"
                                session.temp_data = {}
                                session.save()

                                send_welcome_message(sender)
                                continue

                            if text == "back":
                                handle_back_command(session, sender)
                                continue

                            handle_text_reply(session, sender, text)

                        # -------------------------
                        # C. MEDIA HANDLING
                        # -------------------------
                        elif msg_type in ["image", "document", "video"]:
                            media_object = message.get(msg_type, {})
                            media_id = media_object.get("id")

                            if not media_id:
                                continue

                            # Restrict PDFs to RDB upload step
                            if msg_type == "document" and session.state != "AWAITING_RDB":
                                send_whatsapp_message(
                                    sender,
                                    "⚠️ Only the RDB Certificate can be uploaded as a PDF."
                                )
                                continue

                            handle_media_upload(
                                session,
                                sender,
                                media_id,
                                msg_type
                            )

        except Exception as e:
            print(f"WEBHOOK CRITICAL ERROR: {e}")

        return HttpResponse("OK", status=200)

    return HttpResponse("OK")


def send_review_step(session, sender):
    data = session.temp_data
    # Fetch Category name for the summary
    cat_id = data.get('selected_category_id')
    cat = CategoryConfig.objects.filter(id=cat_id).first()
    cat_name = cat.name if cat else "Not Selected"
    review_msg = (
        "📝 *Registration Summary*\n"
        "Please confirm your details:\n\n"
        f"👤 *Type:* {data.get('entity_type', 'N/A').title()}\n"
        f"🏢 *Name:* {data.get('business_name', 'N/A')}\n"
        f"📂 *Category:* {cat_name}\n"
        f"📍 *Location:* {data.get('district')}, {data.get('sector')}\n"
        f"🖼️ *Portfolio:* {len(data.get('portfolio', []))} photos uploaded\n\n"
        "Is this information correct?"
    )
    buttons = [
        ("confirm_final", "✅ Confirm & Submit"),
        ("back", "🔙 Go Back"),
        ("reset", "🗑️ Reset")
    ]
    send_interactive_buttons(sender, review_msg, buttons)
    return HttpResponse("OK")

def handle_unsubscribe_and_reset(sender):
    try:
        # 1. Find the active provider for this phone number
        provider = Provider.objects.filter(user__phone_number=sender, is_deleted=False).first()

        if provider:
            # 2. Mark as deleted (Soft Delete)
            # This hides them from all searches and Admin "Active" lists
            provider.is_deleted = True
            provider.is_active = False
            provider.is_visible = False
            provider.save()

            # 3. CRITICAL: Reset the Chat Session
            # This allows the user to start the registration flow from scratch
            session = ChatSession.objects.filter(phone_number=sender).first()
            if session:
                session.state = "START"
                session.temp_data = {} # Clear all cached registration data
                session.save()

            return (
                "🗑️ *Account Successfully Deleted.*\n\n"
                "Your business has been removed from Mercato Platform. "
                "If you'd like to register a different service, just type *'reset'* to start over."
            )
        return "❌ No active provider profile was found for this number."

    except Exception as e:
        print(f"Unsubscribe Error: {e}")
        return "❌ An error occurred while deleting your account. Please try again or contact support."


def handle_text_reply(session, sender, text):
    state = session.state

    # 1. Initial Greeting -> Show Logo & Person/Company Buttons
    if state == "START" or text.lower() in ["hi", "hello", "mercato"]:
        # If they are already mid-registration, ask if they want to reset or continue
        if state != "START" and state != "COMPLETED":
            msg = "It looks like you have a registration in progress. Would you like to continue or start over?"
            buttons = [
                ("continue", "➡️ Continue"),
                ("reset", "🗑️ Start Over")
            ]
            send_interactive_buttons(sender, msg, buttons)
            return HttpResponse("OK")

        # If it's a fresh start or they are finished
        session.state = "AWAITING_ENTITY_TYPE"
        session.temp_data = {} # Clear any old data
        session.save()
        send_welcome_message(sender) # Sends Logo + Individual/Company buttons
        return HttpResponse("OK")

    # 2. Capture the Name AFTER they chose Entity Type
    elif state == "AWAITING_NAME":
        session.temp_data['business_name'] = text
        session.state = "AWAITING_FRONT_ID"
        session.save()
        # Friendly confirmation based on their choice (Individual vs Company)
        entity_label = "Individual" if session.temp_data.get('entity_type') == "INDIVIDUAL" else "Company"
        msg = (
            f"✅ *{entity_label} Confirmed*\n"
            f"Name: _{text}_\n"
            "──────────────────\n\n"
            "🛡️ *Identity Verification*\n"
            "To secure your account, please upload a clear photo of the **FRONT** of your National ID card.\n\n"
            "💡 *Tip:* Ensure the text is readable and the corners are visible."
        )
        # Include navigation buttons so they can go back if the name has a typo
        buttons = [
            ("back", "🔙 Edit Name"),
            ("reset", "🗑️ Reset")
        ]
        send_interactive_buttons(sender, msg, buttons)
        return HttpResponse("OK")

    # 3. Existing Location Logic
    elif state == "AWAITING_DISTRICT":
        session.temp_data['district'] = text.capitalize()
        session.state = "AWAITING_SECTOR"
        session.save()

        msg = (
            f"📍 *Location Fixed: {text.capitalize()}*\n"
            "──────────────────\n\n"
            "Wonderful! Now, let's get more specific.\n\n"
            "🏡 Please enter your **Sector**:\n"
            "_(e.g., Remera, Kimironko, or Gisozi)_"
        )

        buttons = [
            ("back", "🔙 Edit District"),
            ("reset", "🗑️ Reset")
        ]

        send_interactive_buttons(sender, msg, buttons)
        return HttpResponse("OK")

    elif state == "AWAITING_SECTOR":
        session.temp_data['sector'] = text.capitalize()
        session.state = "AWAITING_PORTFOLIO"
        session.save()

        # Formatting the location string for a clean look
        district = session.temp_data.get('district', 'Unknown')
        location_display = f"{district}, {text.capitalize()}"

        msg = (
            f"📍 *Location Confirmed*\n"
            f"{location_display}\n"
            "──────────────────\n\n"
            "📸 *Showcase Your Work*\n"
            "First impressions matter! Please upload **2 to 5 photos** that best represent your services or business.\n\n"
            "💡 *Note:* These images will be displayed on your public profile for customers to see."
        )

        buttons = [
            ("back", "🔙 Edit Sector"),
            ("reset", "🗑️ Reset")
        ]

        send_interactive_buttons(sender, msg, buttons)
        return HttpResponse("OK")


    elif state == "AWAITING_PAYMENT_ID":
        # 1. Look for an 11-digit number anywhere in their message (FT Id)
        # This works even if they paste the whole "You have received..." SMS
        id_match = re.search(r'(\d{11})', text)

        if not id_match:
            msg = (
                "⚠️ *Transaction ID Not Recognized*\n"
                "──────────────────\n\n"
                "We couldn't find a valid Transaction ID in your message. To verify your payment, please:\n\n"
                "📋 *Copy & Paste* the full confirmation SMS you received,\n"
                "OR\n"
                "🔢 *Type the 11-digit ID* manually.\n\n"
                "💡 *Example:* `20289722206`\n\n"
                "🛡️ _Your payment is safe. We just need this ID to link it to your account._"
            )
            buttons = [
                ("back", "🔙 Try Again"),
                ("nav_admin", "📞 Get Help")
            ]
            send_interactive_buttons(sender, msg, buttons)
            return HttpResponse("OK")

        tx_id = id_match.group(1)
        provider = Provider.objects.filter(user__phone_number=sender, is_deleted=False).first()

        if not provider:
            return send_whatsapp_message(sender, "❌ Error: Could not find your profile. Please try again.")

        # 2. Store the ID they claimed so the Webhook can match it if it's slow
        provider.payment_reference = tx_id
        provider.save()

        # 3. Check if the Bank Webhook already received this ID
        bank_record = MomoTransaction.objects.filter(tx_id=tx_id, is_used=False).first()

        if bank_record:
            # MATCH FOUND: The bank already notified the server
            # Use your existing activate_provider function from views.py
            result_text = activate_provider(provider, bank_record)

            # Reset state so the bot returns to normal AI mode
            session.state = "COMPLETED"
            session.save()

            return send_whatsapp_message(sender, result_text)

        else:
            # NO MATCH YET: User was faster than the bank SMS
            session.state = "COMPLETED"  # Reset state so they aren't stuck
            session.save()

            msg = (
                f"📝 *Transaction Logged*\n"
                f"ID: `{tx_id}`\n"
                "──────────────────\n\n"
                "I have successfully recorded your ID. 📥\n\n"
                "The bank confirmation is still processing. I will notify you here the second "
                "the verification is complete (usually within 60 seconds). ⏳\n\n"
                "🛡️ _You may continue browsing while we handle the rest._"
            )
            return send_whatsapp_message(sender, msg)

    elif state == "AWAITING_PORTFOLIO":
        if text.upper() == "DONE":
            portfolio = session.temp_data.get('portfolio', [])
            if len(portfolio) < 2:
                send_whatsapp_message(sender, "⚠️ You need at least 2 photos of your work. Please upload more.")
            else:
                # Move to Review Step
                session.state = "AWAITING_CONFIRMATION"
                session.save()
                return send_review_step(session, sender)
        else:
            # If they type something else during portfolio upload
            send_whatsapp_message(sender, "📸 Please upload photos of your work, or type *'DONE'* if you are finished (min 2 photos).")

    return HttpResponse("OK")

def handle_button_reply(session, sender, button_id):
    # 1. ENHANCED: Allow Settings for COMPLETED users without blocking them
    if session.state == "COMPLETED":
        # Check if the button belongs to the management flow
        if button_id in ["manage_profile", "toggle_hide", "delete_account_start", "confirm_delete_account"]:
            pass # Continue to the management logic below
        else:
            # If they are already registered and click a generic button, offer the Management Menu
            msg = "✅ Your registration is active and under review.\n\nWould you like to manage your profile visibility or account?"
            btns = [("manage_profile", "⚙️ Profile Settings"), ("nav_browse", "📂 Browse Mercato")]
            send_interactive_buttons(sender, msg, btns)
            return HttpResponse("OK")

    # 2. NEW: Profile Management & Visibility Handlers
    if button_id == "manage_profile":
        provider = Provider.objects.filter(user__phone_number=sender, is_deleted=False).first()
        if not provider:
            send_whatsapp_message(sender, "❌ No active profile found. Type 'Hi' to start.")
            return HttpResponse("OK")

        # 1. Determine Subscription Status & Expiry
        if provider.is_paid and provider.subscription_expiry:
            days_left = (provider.subscription_expiry - timezone.now()).days

            if days_left > 0:
                sub_status = f"ACTIVE ✅ ({days_left} days remaining)"
                pay_btn_label = "🔄 Renew Early"
            else:
                # Subscription expired but Janitor hasn't flipped is_paid yet
                sub_status = "EXPIRED ⚠️ (Activation Required)"
                pay_btn_label = "💳 Pay Subscription"
        else:
            sub_status = "INACTIVE ❌ (Payment Required)"
            pay_btn_label = "💳 Pay Subscription"

        # 2. Determine Visibility Status
        visibility_text = "VISIBLE 🌍" if provider.is_visible else "HIDDEN 🙈"

        # 3. Construct the Message
        msg = (
            f"⚙️ *Manage Your Business*\n"
            f"━━━━━━━━━━━━━━\n"
            f"🏢 Business: *{provider.business_name}*\n"
            f"💳 Subscription: *{sub_status}*\n"
            f"👁️ Visibility: *{visibility_text}*\n"
            f"━━━━━━━━━━━━━━\n\n"
            "Select an option below to manage your profile:"
        )

        # 4. Dynamic Buttons
        btns = [
            ("pay_sub", pay_btn_label),
            ("toggle_hide", "👁️ Show/Hide Profile"),
            ("delete_account_start", "🛑 Delete Account")
        ]

        return send_interactive_buttons(sender, msg, btns)

    elif button_id == "pay_sub":
        # 1. Update session state to "listen" for the ID
        session.state = "AWAITING_PAYMENT_ID"
        session.save()

        provider = Provider.objects.filter(user__phone_number=sender, is_deleted=False).first()

        # 2. Get the specific fee for their category (default to 1000 if not set)
        fee = provider.category.monthly_fee_rwf if provider.category else 1000

        # 3. Send instructions
        msg = (
            "💳 *Subscription Activation*\n"
            "━━━━━━━━━━━━━━\n"
            f"Business: *{provider.business_name}*\n"
            f"Amount to Pay: *{fee:,} RWF*\n"
            "━━━━━━━━━━━━━━\n\n"
            "1️⃣ Send the payment to MTN MoMopay Code: *2656360* Company Name: *HEIMAT50 Ltd*).\n"
            "2️⃣ Once you receive the MTN Mobile Money payment notifiation SMS.\n"
            "3️⃣ **Please Copy and Paste the entire message(SMS) right here** in this chat to activate your profile."
        )

        return send_whatsapp_message(sender, msg)


    elif button_id == "toggle_hide":
        provider = Provider.objects.filter(user__phone_number=sender, is_deleted=False).first()
        if provider:
            provider.is_visible = not provider.is_visible
            provider.save()
            new_status = "VISIBLE ✅" if provider.is_visible else "HIDDEN 🙈"
            send_whatsapp_message(sender, f"👁️ Status updated: Your profile is now **{new_status}**.")
            # Re-show management menu for better UX
            return handle_button_reply(session, sender, "manage_profile")

    elif button_id == "delete_account_start":
        msg = (
            "🗑️ *Account Deletion Request*\n"
            "────────────────────────\n\n"
            "This action will immediately hide your business and remove your profile "
            "from all Mercato search results.\n\n"
            "💡 *Note:* You can always register a new service with this number in the future, "
            "but your current ratings and portfolio will be lost.\n\n"
            "**Are you absolutely sure you want to proceed?**"
        )
        btns = [
            ("confirm_delete_account", "⚠️ Delete My Account"),
            ("manage_profile", "🔙 No, Keep It")
        ]
        return send_interactive_buttons(sender, msg, btns)

    elif button_id == "confirm_delete_account":
        # This calls the reset function we are about to define in the next step
        response = handle_unsubscribe_and_reset(sender)
        send_whatsapp_message(sender, response)
        return HttpResponse("OK")

    # 3. PRIORITY: Global Navigation & Infrastructure Handlers
    if button_id == "reset":
        session.state = "START"
        session.temp_data = {}
        session.save()
        send_welcome_message(sender)
        return HttpResponse("OK")

    if button_id in ["explore_services", "nav_browse", "nav_sectors"]:
        # If they aren't registering, assume they are browsing
        if session.state not in ["AWAITING_NAME", "AWAITING_CATEGORY", "AWAITING_DISTRICT", "AWAITING_PORTFOLIO"]:
            session.state = "BROWSING"
            session.save()
        return send_super_categories(sender)

    if button_id.startswith("super_"):
        group_name = button_id.replace("super_", "").strip()
        return handle_group_selection(sender, group_name)

    if button_id == "nav_register_hub":
        msg = (
            "🚀 *Join the Mercato Marketplace*\n"
            "────────────────────────\n\n"
            "Grow your business and reach thousands of customers. To get started, "
            "how will you be joining us today?\n\n"
            "👤 **Individual**\n"
            "Select this if you are a freelance professional or solo service provider.\n\n"
            "🏢 **Company**\n"
            "Select this if you are a registered business, shop, or agency."
        )
        btns = [
            ("type_individual", "👤 Individual"),
            ("type_company", "🏢 Company")
        ]
        send_interactive_buttons(sender, msg, btns)
        return HttpResponse("OK")

    if button_id == "nav_admin":
        admin_msg = (
            "📞 *Mercato Support Center*\n"
            "──────────────────────\n\n"
            "Need help with your account or looking for a specific service? Our team is here to assist you.\n\n"
            "💬 *WhatsApp:* https://wa.me/250789512989\n"
            "📧 *Email:* admin@mercato.rw\n"
            "⏰ *Working Hours:* Mon - Fri (4:00 AM - 11:59 PM)\n\n"
            "🛡️ _Simply click the link above to chat with a real person._"
        )
        send_whatsapp_message(sender, admin_msg)
        return HttpResponse("OK")

    # 4. REGISTRATION STATE LOGIC (Prioritized by state)

    # --- Category Selection State ---
    if session.state == "AWAITING_CATEGORY":
        # 1. Handle Sector Selection (Level 1)
        if button_id.startswith("super_"):
            group_name = button_id.replace("super_", "").strip()
            return handle_group_selection(sender, group_name)

        # 2. Handle Specific Category Selection (Level 2)
        if button_id.startswith("cat_"):
            clean_id = button_id.replace("cat_", "").strip()
            cat = CategoryConfig.objects.filter(id=clean_id).first() if clean_id.isdigit() else None

            if cat:
                session.temp_data['selected_category_id'] = cat.id
                session.state = "AWAITING_DISTRICT"
                session.save()

                msg = (
                    f"✅ *Category Selected:* {cat.name}\n"
                    f"💳 *Subscription:* {cat.monthly_fee_rwf:,} RWF / month\n"
                    "──────────────────\n\n"
                    "📍 *Location Setup*\n"
                    "To help customers find you easily, please enter the **District** where your business is located.\n\n"
                    "_(e.g., Gasabo, Nyarugenge, or Kicukiro)_"
                )

                buttons = [
                    ("nav_sectors", "⬅️ Back to Categories"),
                    ("reset", "🗑️ Reset")
                ]
                return send_interactive_buttons(sender, msg, buttons)

        # 3. Fallback: If they click "Back to Sectors" or something else
        if button_id == "nav_sectors":
            return send_super_categories(sender)

        # 4. Error Catch: If they typed something random instead of clicking
        msg = "⚠️ Please select a Category from the menu to continue."
        send_whatsapp_message(sender, msg)
        return send_super_categories(sender)


    # --- Registration Type & Portfolio States ---
    if button_id == "type_individual":
        session.temp_data['entity_type'] = "INDIVIDUAL"
        session.state = "AWAITING_NAME"
        session.save()

        msg = (
            "👤 *Profile Type: Individual*\n"
            "──────────────────\n\n"
            "Please enter your **Full Name** as it appears on your National ID.\n\n"
            "🛡️ _This helps us maintain a trusted network._"
        )
        send_interactive_buttons(sender, msg, [("back", "🔙 Change Type"), ("reset", "🗑️ Reset")])
        return HttpResponse("OK")

    elif button_id == "type_company":
        session.temp_data['entity_type'] = "COMPANY"
        session.state = "AWAITING_NAME"
        session.save()

        msg = (
            "🏢 *Profile Type: Company*\n"
            "──────────────────\n\n"
            "Please enter your **Official Company Name**.\n\n"
            "📋 _This name will be displayed on your business profile._"
        )
        send_interactive_buttons(sender, msg, [("back", "🔙 Change Type"), ("reset", "🗑️ Reset")])
        return HttpResponse("OK")

    if button_id == "done_portfolio":
        portfolio = session.temp_data.get('portfolio', [])

        if len(portfolio) < 2:
            msg = (
                "⚠️ *Gallery Minimum Not Met*\n"
                "────────────────────────\n\n"
                f"You've shared **{len(portfolio)}** photo(s) so far. To help you stand out "
                "to customers, we need at least **2 high-quality photos** of your work.\n\n"
                "📸 _Please upload just one more to unlock the next step!_"
            )
            send_whatsapp_message(sender, msg)
            return HttpResponse("OK")

        # Success: Move to the final confirmation phase
        session.state = "AWAITING_CONFIRMATION"
        session.save()

        # We don't just send a message; we trigger the full review summary
        return send_review_step(session, sender)

    # 5. SEARCH & PROVIDER INTERACTION (The cat_ prefix used in browsing)
    if button_id.startswith("cat_"):
        category_id = button_id.replace("cat_", "").strip()
        cat = CategoryConfig.objects.filter(id=category_id).first()
        category_query = cat.name if cat else category_id

        # Smart Search provides a seamless transition to results
        return handle_smart_search(session, sender, category_query)

    if button_id.startswith("chat_"):
        provider_id = button_id.replace("chat_", "").strip()
        try:
            provider = Provider.objects.get(id=provider_id)
            raw_phone = "".join(filter(str.isdigit, str(provider.user.phone_number)))

            # Crafting a professional pre-filled message for the user
            welcome_text = f"Hello! I found your business ({provider.business_name}) on Mercato. I'm interested in your services."
            encoded_text = urllib.parse.quote(welcome_text)
            wa_link = f"https://wa.me/{raw_phone}?text={encoded_text}"

            msg = (
                f"🤝 *Connect with {provider.business_name}*\n"
                "──────────────────\n\n"
                "We’ve generated a direct chat link for you. Click below to start your conversation with the service provider:\n\n"
                f"🚀 *Start Chat:* {wa_link}\n\n"
                "🛡️ _Mercato: Connecting you to trusted professionals._"
            )

            send_interactive_buttons(sender, msg, [("nav_browse", "📂 Back to Search")])
            return HttpResponse("OK")

        except Provider.DoesNotExist:
            msg = (
                "🧐 *Listing No Longer Available*\n"
                "────────────────────────\n\n"
                "It looks like this business has recently updated its profile or "
                "moved off the marketplace.\n\n"
                "📂 *What can you do?*\n"
                "Please try searching for a different provider or browse our "
                "categories to find exactly what you need. 🚀"
            )
            send_whatsapp_message(sender, msg)
            return HttpResponse("OK")

    if button_id.startswith("more_"):
        p_id = button_id.replace("more_", "")
        # This handles the visual transition to the business portfolio
        return handle_view_more_portfolio(sender, p_id)

    # 6. BACK / CONFIRM Logic
    if button_id == "back" and session.state == "AWAITING_PORTFOLIO":
        portfolio = session.temp_data.get('portfolio', [])
        if portfolio:
            portfolio.pop()
            session.temp_data['portfolio'] = portfolio
            session.save()

            count = len(portfolio)
            msg = (
                "🗑️ *Photo Removed*\n"
                "──────────────────\n\n"
                f"Your last upload has been deleted. You currently have **{count}** photo(s) in your gallery.\n\n"
                "📸 _You can upload more or use the buttons below to continue._"
            )

            btns = [("back", "🔙 Undo Another"), ("reset", "🗑️ Reset")]

            # Smart button logic: Only show 'DONE' if the minimum requirement is met
            if count >= 2:
                btns.insert(0, ("done_portfolio", "✅ Proceed to Review"))

            send_interactive_buttons(sender, msg, btns)
            return HttpResponse("OK")

    if button_id == "back":
        # Global back logic
        return handle_back_command(session, sender)

    if button_id == "confirm_final":
        # Finalizing the registration process
        return finalize_registration(session, sender)

    if button_id == "continue":
        # Simple prompt to keep the flow moving
        return trigger_current_state_prompt(session, sender)

    return HttpResponse("OK")


def trigger_current_state_prompt(session, sender):
    """Helper to remind the user what we are waiting for when they click 'Continue'"""
    state = session.state
    prompts = {
        "AWAITING_NAME": (
            "👤 *Name Required*\n"
            "Please type your **Full Name** or **Company Name** below to continue:"
        ),
        "AWAITING_FRONT_ID": (
            "🆔 *Identity Verification (1/2)*\n"
            "Please upload a clear photo of the **FRONT** of your National ID."
        ),
        "AWAITING_BACK_ID": (
            "🆔 *Identity Verification (2/2)*\n"
            "Please upload a clear photo of the **BACK** of your National ID."
        ),
        "AWAITING_FACE_SCAN": (
            "🤳 *Security Check*\n"
            "Please record and send a short **5-15 seconds Video** of your face for verification, Include the left and right of your head in the video."
        ),
        "AWAITING_RDB": (
            "📄 *Business Registration*\n"
            "Please upload your **RDB Registration Certificate** OR **Tax Declaration Receipt** (as a PDF or Image)."
        ),
        "AWAITING_DISTRICT": (
            "📍 *Location: District*\n"
            "Which **District** is your business or service located in?"
        ),
        "AWAITING_SECTOR": (
            "🏡 *Location: Sector*\n"
            "Almost there! Please enter your **Sector** (e.g., Remera, Kacyiru):"
        ),
        "AWAITING_PORTFOLIO": (
            "📸 *Work Gallery*\n"
            "Please upload photos of your work, or click the **'DONE'** button if you are finished."
        ),
        "AWAITING_CONFIRMATION": (
            "📝 *Final Review*\n"
            "We are waiting for your final confirmation. Please review your details and click **'Confirm'**."
        )
    }
    msg = prompts.get(state, "How can I help you today?")
    if state == "AWAITING_CATEGORY":
        # Re-fetch categories to show buttons again
        categories = CategoryConfig.objects.filter(is_active=True)[:3]
        category_buttons = [(str(cat.id), cat.name) for cat in categories]
        send_interactive_buttons(sender, "Please select your business category:", category_buttons)
    elif state == "AWAITING_CONFIRMATION":
        from .views import send_review_step
        send_review_step(session, sender)
    else:
        send_interactive_buttons(sender, msg, [("back", "🔙 Back"), ("reset", "🗑️ Reset")])
    return HttpResponse("OK")

def validate_video_duration(relative_path):
    """Returns (is_valid, error_message)"""
    try:
        from moviepy.video.io.VideoFileClip import VideoFileClip
        full_path = os.path.join(settings.MEDIA_ROOT, relative_path)

        with VideoFileClip(full_path) as video:
            duration = video.duration

            if duration < 5:
                msg = (
                    f"⚠️ *Video Too Short* ({round(duration, 1)}s)\n\n"
                    "To ensure a successful face scan, please record a video between **5 and 15 seconds**.\n\n"
                    "📸 _Tip: Move your head slightly so we can verify it's really you!_"
                )
                return False, msg

            if duration > 15:
                msg = (
                    f"⚠️ *Video Too Long* ({round(duration, 1)}s)\n\n"
                    "Our system prefers shorter clips for faster verification. Please keep your video **under 15 seconds**.\n\n"
                    "✂️ _Please try recording a slightly shorter version._"
                )
                return False, msg

        return True, None

    except Exception as e:
        print(f"MoviePy Error: {e}")
        msg = (
            "🔍 *Verification Interrupted*\n"
            "──────────────────\n\n"
            "We encountered a small technical glitch while checking your video. "
            "This usually happens due to a file format issue.\n\n"
            "✅ *Please try one of the following:*\n"
            "1. Record a fresh video directly in WhatsApp.\n"
            "2. Ensure you have a stable internet connection.\n"
            "3. Send the video again.\n\n"
            "📞 _If this persists, please contact Mercato Support._"
        )
        return False, msg

def download_whatsapp_media(media_id, folder='uploads'):
    if not media_id: return None
    try:
        # Use WHATSAPP_TOKEN as defined in your .env/settings
        url = f"https://graph.facebook.com/v18.0/{media_id}"
        headers = {"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}"}

        # Step 1: Get the temporary download URL
        res = requests.get(url, headers=headers, timeout=15).json()
        download_url = res.get('url')
        mime_type = res.get('mime_type', '')

        if not download_url: return None

        # Determine extension
        if 'video' in mime_type: extension = ".mp4"
        elif 'pdf' in mime_type: extension = ".pdf"
        elif 'png' in mime_type: extension = ".png"
        else: extension = ".jpg"

        # Step 2: Download the binary file (Double-try for Meta CDN)
        media_res = requests.get(download_url, headers=headers, timeout=30)
        if media_res.status_code != 200:
            media_res = requests.get(download_url, timeout=30)

        if media_res.status_code != 200: return None

        # Step 3: Save to AWS Disk
        filename = f"{media_id}{extension}"
        relative_path = f"{folder}/{filename}"
        full_path = os.path.join(settings.MEDIA_ROOT, folder, filename)

        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'wb') as f:
            f.write(media_res.content)

        return relative_path # Returns string: "uploads/123.jpg"
    except Exception as e:
        print(f"Download Error: {e}")
        return None


def handle_media_upload(session, sender, media_id, media_type):
    state = session.state
    data = session.temp_data or {}
    nav_buttons = [("back", "🔙 Back"), ("reset", "🗑️ Reset")]

    # --- 1. ID PHOTO HANDLING ---
    if state in ["AWAITING_FRONT_ID", "AWAITING_BACK_ID"]:
        if media_type != "image":
            side = "FRONT" if state == "AWAITING_FRONT_ID" else "BACK"
            msg = (
                f"📸 *Photo Required: {side} of ID*\n"
                "──────────────────\n\n"
                f"It looks like you sent a {media_type}, but we need a **clear photo** (Image) "
                f"of the **{side}** of your National ID.\n\n"
                "✅ *Please:* \n"
                "1. Take a picture using your camera.\n"
                "2. Send it as a 'Gallery' or 'Camera' attachment.\n\n"
                "🛡️ _This ensures our verification system can read your details clearly._"
            )
            send_whatsapp_message(sender, msg)
            return HttpResponse("OK")

        send_whatsapp_message(sender, "📥 *Receiving your file...* \n_Please wait a moment while we process the image._")
        path = download_whatsapp_media(media_id, folder='uploads')

        if not path:
            msg = (
                "❌ *Upload Failed*\n"
                "──────────────────\n\n"
                "We couldn't securely download your photo. This is usually due to a temporary connection issue.\n\n"
                "🔄 Please try uploading the photo again."
            )
            send_whatsapp_message(sender, msg)
            return HttpResponse("OK")

        if state == "AWAITING_FRONT_ID":
            data['id_front_path'] = path
            session.temp_data = data
            session.state = "AWAITING_BACK_ID"
            session.save()

            msg = (
                "✅ *Front ID Captured*\n"
                "──────────────────\n\n"
                "Great! The front of your ID is saved. Now, please upload the **BACK** of your ID."
            )
            send_interactive_buttons(sender, msg, [("back", "🔙 Re-upload Front"), ("reset", "🗑️ Reset")])

        else:
            data['id_back_path'] = path
            session.temp_data = data

            if data.get('entity_type') != "COMPANY":
                session.state = "AWAITING_FACE_SCAN"
                msg = (
                    "✅ *ID Verification Complete*\n"
                    "──────────────────\n\n"
                    "Both sides of your ID have been recorded. To finish your security profile, "
                    "please send a **short Video (5-15 seconds)** of your face including left and right of your head for verification."
                )
            else:
                session.state = "AWAITING_RDB"
                msg = (
                    "✅ *ID Verification Complete*\n"
                    "──────────────────\n\n"
                    "Your ID photos are saved. Since you are registering a company, "
                    "please upload your **RDB Registration Certificate** OR **Tax Declaration Receipt** Document (PDF or Image) to proceed."
                )

            session.save()
            send_interactive_buttons(sender, msg, nav_buttons)

        return HttpResponse("OK")

    # --- 2. FACE SCAN ---
    elif state == "AWAITING_FACE_SCAN":
        if media_type != "video":
            send_whatsapp_message(sender, "please send a **short Video (5-15 seconds)** of your face including left and right of your head for verification.")
            return HttpResponse("OK")

        path = download_whatsapp_media(media_id, folder='uploads')
        if path:
            is_valid, error_msg = validate_video_duration(path)
            if not is_valid:
                send_whatsapp_message(sender, error_msg)
                return HttpResponse("OK")

            data['face_scan'] = path
            session.temp_data = data
            session.save()
            return trigger_category_selection(session, sender)

    # --- 3. RDB CERTIFICATE ---
    elif state == "AWAITING_RDB":
        path = download_whatsapp_media(media_id, folder='uploads')
        if path:
            data['rdb_doc'] = path
            session.temp_data = data
            session.save()
            return trigger_category_selection(session, sender)

    # --- 4. PORTFOLIO ---
    elif state == "AWAITING_PORTFOLIO":
        portfolio = data.get('portfolio', [])
        if len(portfolio) < 5 and media_type == "image":
            path = download_whatsapp_media(media_id, folder='portfolio')
            if path:
                portfolio.append(path)
                data['portfolio'] = portfolio
                session.temp_data = data
                session.save()
                count = len(portfolio)
                msg = (
                    f"📸 *Gallery Update: {count}/5 Photos*\n"
                    "──────────────────\n\n"
                    "Photo received and added to your business profile! ✅\n\n"
                    f"{'💡 *You can now finish or add more.*' if count >= 2 else '⏳ *Please upload at least ' + str(2-count) + ' more photo(s) to proceed.*'}"
                )

                # Logic for buttons remains clean and functional
                if count >= 2:
                    btns = [
                        ("done_portfolio", "✅ Finish & Review"),
                        ("back", "🔙 Undo Last"),
                        ("reset", "🗑️ Reset")
                    ]
                else:
                    btns = [
                        ("back", "🔙 Undo Last"),
                        ("reset", "🗑️ Reset")
                    ]

                send_interactive_buttons(sender, msg, btns)

        return HttpResponse("OK")

    return HttpResponse("OK")
def trigger_category_selection(session, sender):
    """Helper to show sectors once docs are uploaded"""
    # 1. Update the state first
    session.state = "AWAITING_CATEGORY"
    session.save()

    # 2. Check if any sectors/groups exist
    groups_exist = CategoryConfig.objects.filter(is_active=True).exists()

    if groups_exist:
        # Send a brief confirmation message first
        send_whatsapp_message(sender, "✅ *Documents verified.*")

        # 3. CALL THE NEW SECTOR MENU (Level 1)
        # This will show 'Accommodation', 'General', etc.
        return send_super_categories(sender)

    else:
        # Fallback if no categories are configured in the Admin
        session.state = "AWAITING_DISTRICT"
        session.save()

        msg = (
            "✅ *Documents Verified*\n"
            "──────────────────\n\n"
            "Your files have been successfully uploaded. Now, let's set up your business location.\n\n"
            "📍 What **District** is your business located in?\n"
            "_(e.g., Gasabo, Kicukiro, or Musanze)_"
        )
        nav_buttons = [
            ("back", "🔙 Back"),
            ("reset", "🗑️ Reset")
        ]
        return send_interactive_buttons(sender, msg, nav_buttons)

def finalize_registration(session, sender):
    try:
        user_profile, _ = UserProfile.objects.get_or_create(phone_number=sender)
        data = session.temp_data or {}

        # Fetch category based on what was selected in the flow
        cat = CategoryConfig.objects.filter(id=data.get('selected_category_id')).first()

        # Save to Provider Model using paths from session
        # We explicitly set the new tracking fields to their starting states
        Provider.objects.create(
            user=user_profile,
            business_name=data.get('business_name', 'Unnamed Business'),
            entity_type=data.get('entity_type'),
            category=cat,
            district=data.get('district'),
            sector=data.get('sector'),
            id_front=data.get('id_front_path'),
            id_back=data.get('id_back_path'),
            face_scan=data.get('face_scan'),
            rdb_doc=data.get('rdb_doc'),
            portfolio_images=data.get('portfolio', []),

            # --- Status & Feature Alignment ---
            is_active=False,       # Original feature: Wait for admin review
            is_visible=True,      # New: Visible by default upon approval
            is_paid=False,         # New: Start as unpaid until webhook triggers
            is_deleted=False       # New: Mark as an active account
        )

        # Update Session State
        session.state = "COMPLETED"
        session.save()

        # Original confirmation message
        send_whatsapp_message(
            sender,
            "🎉 *Congratulations! Registration Submitted*\n"
            "──────────────────────\n\n"
            "Your profile has been successfully sent to the **Mercato Verification Team**. 🛡️\n\n"
            "🕒 *What’s next?*\n"
            "Our team will review your documents. You will receive a notification right here "
            "as soon as your account is approved and live on the marketplace.\n\n"
            "✨ _Thank you for choosing Mercato!_"
        )
    except Exception as e:
        print(f"Finalize Error: {e}")
        error_msg = (
            "⚠️ *Submission Issue*\n\n"
            "We encountered a technical problem while saving your profile. "
            "Don't worry—your progress is safe.\n\n"
            "Please try clicking **'Confirm'** again, or contact our support team if this persists."
        )
        send_whatsapp_message(sender, error_msg)

def provider_detail(request, provider_id):
    from .models import Provider
    from django.shortcuts import render, get_object_or_404

    provider = get_object_or_404(Provider, id=provider_id)

    # Force portfolio_images to be a list if it's currently None or a string
    if not isinstance(provider.portfolio_images, list):
        provider.portfolio_images = []

    return render(request, 'escrow/provider_detail.html', {'provider': provider})

# 3 functions for the mercato.rw pages
def home(request):
    return render(request, 'escrow/home.html')

def privacy_policy(request):
    return render(request, 'escrow/privacy.html')

def terms_of_service(request):
    return render(request, 'escrow/terms.html')


# --- 1. THE SEARCH ENGINE (Typing & List selection) ---
def handle_smart_search(session, sender, query):
    """Finds providers and displays them only if Active, Visible, Paid, and Not Deleted"""
    # We add the new safety and business rules to the filter
    providers = Provider.objects.filter(
        # 1. Search Criteria
        Q(business_name__icontains=query) |
        Q(category__name__icontains=query) |
        Q(district__icontains=query) |
        Q(sector__icontains=query),

        # 2. Business Logic Filters
        is_active=True,    # Admin has approved them
        is_visible=True,   # User has NOT hidden their profile
        is_paid=True,      # User has a current subscription
        is_deleted=False   # User has NOT deleted their account
    ).select_related('category', 'user')[:3]

    if not providers.exists():
        # Check if they exist but are just hidden/unpaid for internal debugging (optional)
        msg = f"🔍 No active results for '{query}' at the moment."
        return send_interactive_buttons(sender, msg, [("nav_browse", "📂 Browse Categories")])

    send_whatsapp_message(sender, f"🔎 *Results for '{query}':*")

    for p in providers:
        send_provider_card(sender, p)

    return HttpResponse("OK")


def send_simple_image(recipient_number, image_url, caption=""):
    """Sends a single image with an optional caption via WhatsApp API"""
    url = f"https://graph.facebook.com/v18.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "messaging_product": "whatsapp",
        "to": recipient_number,
        "type": "image",
        "image": {
            "link": image_url,
            "caption": caption
        }
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        return response.json()
    except Exception as e:
        print(f"Failed to send image: {e}")
        return None

# --- 2. THE VISUAL CARD (Image + Details + Buttons) ---
def send_provider_card(to, provider):
    """Sends a single image card with verification badge, stars, and 3 action buttons"""
    # 1. Image Logic
    image_url = "https://www.mercato.rw/static/images/default_provider.png"
    if provider.portfolio_images and len(provider.portfolio_images) > 0:
        image_path = str(provider.portfolio_images[0]).lstrip('/')
        image_url = f"https://mercato.rw/media/{image_path}"

    # 2. Building the smart caption
    caption = (
        f"{provider.get_badge()} | {provider.get_stars()}\n"
        f"🏢 *{provider.business_name}*\n"
        f"🛠️ {provider.category.name if provider.category else 'Service'} \n"
        f"📍 {provider.district}, {provider.sector}\n\n"
        "Click below to start a secure trade or see more photos."
    )

    # 3. API Config
    url = f"https://graph.facebook.com/v18.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    # 4. The Interactive Payload (Limited to 3 buttons)
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {
                "type": "image",
                "image": {"link": image_url}
            },
            "body": {"text": caption},
            "footer": {"text": "Mercato Trusted Services 🛡️"},
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {"id": f"chat_{provider.id}", "title": "💬 Chat Now"}
                    },
                    {
                        "type": "reply",
                        "reply": {"id": f"more_{provider.id}", "title": "📸 View More"}
                    },
                    {
                        "type": "reply",
                        "reply": {"id": "nav_browse", "title": "📂 Back to Search"} # Added 3rd Button
                    }
                ]
            }
        }
    }

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        print(f"META API ERROR: {response.text}")

    return response


def handle_view_more_portfolio(sender, provider_id):
    try:
        provider = Provider.objects.get(id=provider_id)
        # Assuming portfolio_images is a list of paths
        images = provider.portfolio_images

        if not images or len(images) <= 1:
            send_whatsapp_message(sender, "📝 This provider has no additional photos.")
            return HttpResponse("OK")

        send_whatsapp_message(sender, f"📸 *More from {provider.business_name}:*")

        # Skip the first image (already seen) and send the next 3
        for img_path in images[1:4]:
            full_url = f"https://mercato.rw/media/{str(img_path).lstrip('/')}"
            # THIS IS THE CALL THAT WAS CRASHING:
            send_simple_image(sender, full_url)

        # Give them the action buttons back
        send_interactive_buttons(sender, "Ready to proceed?", [
            (f"chat_{provider.id}", "💬 Chat Now"),
            ("nav_browse", "📂 Back to Search")
        ])

    except Provider.DoesNotExist:
        send_whatsapp_message(sender, "❌ Provider data error.")

    return HttpResponse("OK")


def toggle_visibility(sender):
    # Find the active provider (ignoring soft-deleted accounts)
    provider = Provider.objects.filter(user__phone_number=sender, is_deleted=False).first()
    if not provider:
        return (
            "🔍 *Profile Not Found*\n"
            "──────────────────\n\n"
            "We couldn't find an active business profile linked to this phone number.\n\n"
            "✨ *Want to get started?*\n"
            "Type **'Register'** to create your business account and join the Mercato marketplace today! 🚀"
        )

    # Flip the boolean: True becomes False, False becomes True
    provider.is_visible = not provider.is_visible
    provider.save()

    if provider.is_visible:
        return (
            "✅ *Status: GO LIVE*\n"
            "──────────────────\n\n"
            "👁️ **Your profile is now VISIBLE.**\n\n"
            "Customers can now discover your business and contact you for services. "
            "Good luck with your sales! 🚀"
        )
    else:
        return (
            "💤 *Status: ON BREAK*\n"
            "──────────────────\n\n"
            "🙈 **Your profile is now HIDDEN.**\n\n"
            "You are currently invisible to new customers. Your existing clients can still "
            "reach you, but you won't appear in search results until you go live again."
        )

def extract_momo_details(text):
    """
    Unified Parser for Heimat50 Ltd.
    """
    data = {"amount": 0, "tx_id": None, "payer_name": None}
    if not text: return data

    # 1. Extract 11-digit ID (FT Id: or TxId:)
    id_match = re.search(r"(?:FT\s*Id:|TxId:)\s*(\d{11})", text)
    if id_match:
        data["tx_id"] = id_match.group(1)

    # 2. Extract Amount (handles commas)
    amount_match = re.search(r"(?:received|payment of)\s+([\d,]+)\s*RWF", text, re.IGNORECASE)
    if amount_match:
        clean_amt = amount_match.group(1).replace(",", "")
        data["amount"] = int(float(clean_amt))

    # 3. Extract Name
    name_match = re.search(r"from\s+(.*?)\s+\(", text)
    if name_match:
        data["payer_name"] = name_match.group(1).strip()

    return data

@csrf_exempt
def momo_sms_webhook(request):
    if request.method == "POST":
        raw_text = request.POST.get("message", "")
        sender_title = request.POST.get("from", "")
        msg_uuid = request.POST.get("uuid", "test")

        # 1. Smssync handshake
        if "test" in raw_text.lower() and "smssync" in raw_text.lower():
            return JsonResponse({"payload": {"success": True, "error": None}})

        # 2. Filter for MoMo messages only
        if "M-Money" not in sender_title and "MoMo" not in sender_title:
            return JsonResponse({"payload": {"success": True, "error": None, "note": "Ignored non-MoMo"}})

        momo = extract_momo_details(raw_text)
        tx_id = momo.get("tx_id")

        if tx_id:
            # 3. Anti-Duplicate Check
            full_text_with_uuid = f"{raw_text} | UUID:{msg_uuid}"
            if MomoTransaction.objects.filter(full_text__contains=msg_uuid).exists():
                return JsonResponse({"payload": {"success": True, "error": None, "note": "Duplicate"}})

            # 4. Save Bank Record
            transaction, created = MomoTransaction.objects.get_or_create(
                tx_id=tx_id,
                defaults={
                    'amount': momo["amount"],
                    'payer_name': momo["payer_name"],
                    'full_text': full_text_with_uuid
                }
            )

            # 5. THE MATCHING ENGINE
            provider = Provider.objects.filter(payment_reference=tx_id, is_paid=False).first()

            if not provider:
                phone_match = re.search(r"\((\*\*\*.*?\d{3,4}|07\d{8}|250\d{9})\)", raw_text)
                if phone_match:
                    last_4 = phone_match.group(1)[-4:]
                    provider = Provider.objects.filter(user__phone_number__endswith=last_4, is_paid=False).first()

            # 6. ACTIVATION & NOTIFICATION
            if provider and not transaction.is_used:
                required_fee = provider.category.monthly_fee_rwf if provider.category else 0

                if transaction.amount >= required_fee:
                    # --- DATABASE UPDATES ---
                    from datetime import timedelta
                    expiry_date = timezone.now() + timedelta(days=30)

                    provider.is_paid = True
                    provider.payment_reference = tx_id
                    provider.subscription_expiry = expiry_date
                    provider.save()

                    transaction.is_used = True
                    transaction.save()

                    # --- INTEGRATED CHAT NOTIFICATION (HARDENED) ---
                    try:
                        session = ChatSession.objects.filter(
                            phone_number=provider.user.phone_number
                        ).order_by('-id').first()

                        if session:
                            expiry_str = expiry_date.strftime("%d %b %Y")
                            success_msg = (
                                f"🚀 *BUSINESS ACTIVATED: {provider.business_name}*\n"
                                "────────────────────────\n\n"
                                f"✅ **Payment Confirmed**\n"
                                f"💰 Amount: {transaction.amount:,} RWF\n"
                                f"🆔 TxID: `{tx_id}`\n\n"
                                f"📅 **Subscription Status**\n"
                                f"Your listing is officially active until: **{expiry_str}**\n\n"
                                "🌟 Your business is now live and visible to thousands of customers on Mercato. "
                                "Get ready for your next big opportunity! ✨"
                            )
                            # Standardize messages as a list to avoid JSON errors
                            current_messages = session.messages if isinstance(session.messages, list) else []

                            # Use a plain string for the timestamp
                            current_messages.append({
                                "role": "assistant",
                                "content": success_msg,
                                "timestamp": timezone.now().strftime("%Y-%m-%dT%H:%M:%S")
                            })

                            session.messages = current_messages
                            session.save()
                    except Exception as e:
                        print(f"Chat Notification Error: {str(e)}")
                    # ------------------------------------

                    return JsonResponse({
                        "payload": {
                            "success": True,
                            "error": None,
                            "chat_confirm": f"Activated: {provider.business_name}"
                        }
                    })

        # Return standard SMSSync success payload for all other processed cases
        return JsonResponse({"payload": {"success": True, "error": None, "note": "Recorded"}})

    return JsonResponse({"error": "Method not allowed"}, status=405)

def handle_subscriber_paste(sender_phone, text):
    """
    Handles the manual paste of MTN MoMo confirmation messages.
    Syncs the user's claim with the banking backend.
    """
    momo = extract_momo_details(text)
    tx_id = momo.get("tx_id")

    if not tx_id:
        return (
            "⚠️ *Transaction ID Not Found*\n"
            "──────────────────\n\n"
            "I couldn't detect a valid 11-digit Transaction ID in your message. "
            "Please paste the **entire** SMS you received from MTN or just the ID number (e.g., 20289722206)."
        )

    # 1. Find the Provider
    provider = Provider.objects.filter(user__phone_number=sender_phone, is_deleted=False).first()
    if not provider:
        return "❌ *Profile Not Found*\nPlease complete your business registration before making a payment."

    # 2. Store the ID (Bridge for the Webhook)
    provider.payment_reference = tx_id
    provider.save()

    # 3. Check for existing bank confirmation
    bank_record = MomoTransaction.objects.filter(tx_id=tx_id, is_used=False).first()

    if bank_record:
        # MATCH FOUND: Instant activation
        return activate_provider(provider, bank_record)
    else:
        # PENDING: The "Fast User" scenario
        return (
            f"📥 *Transaction Logged*\n"
            f"ID: `{tx_id}`\n"
            "──────────────────\n\n"
            "Your payment claim has been received! ⚡\n\n"
            "I am currently waiting for the bank's network to confirm the transfer. "
            "Your profile will **auto-activate** the second we receive the green light (usually under 60 seconds). ⏳\n\n"
            "🛡️ _You don't need to stay on this screen._"
        )


def activate_provider(provider, bank_record):
    """
    Final activation logic used by BOTH the Webhook and the Manual Paste.
    Ensures payment meets category requirements before unlocking profile.
    """
    from datetime import timedelta
    from django.utils import timezone

    required_fee = provider.category.monthly_fee_rwf if provider.category else 0

    if bank_record.amount >= required_fee:
        # 1. Update Provider Status
        provider.is_paid = True
        provider.is_visible = True  # Auto-show them when they pay
        provider.subscription_expiry = timezone.now() + timedelta(days=30)
        provider.save()

        # 2. Mark bank record as used
        bank_record.is_used = True
        bank_record.save()

        expiry_str = provider.subscription_expiry.strftime('%d %b %Y')

        return (
            f"🎊 *Business Activated!*\n"
            f"──────────────────\n\n"
            f"🚀 **{provider.business_name}** is now LIVE.\n\n"
            f"💰 *Payment:* {bank_record.amount:,} RWF\n"
            f"📅 *Valid Until:* {expiry_str}\n\n"
            "Your business is now visible to all customers on the Mercato marketplace. "
            "Get ready for new opportunities! ✨"
        )
    else:
        return (
            f"⚠️ *Payment Amount Mismatch*\n"
            f"──────────────────\n\n"
            f"We received your payment of **{bank_record.amount:,} RWF**, but the "
            f"required fee for the *{provider.category.name}* category is **{required_fee:,} RWF**.\n\n"
            "🛠️ *How to fix this:* \n"
            "Please contact our support team to settle the balance or adjust your category."
        )
