from django.core.management.base import BaseCommand
from escrow.utils import initialize_new_trade
from escrow.whatsapp_client import send_whatsapp_message
from escrow.tasks import monitor_trade  # 👈 This is the "Brain" import

class Command(BaseCommand):
    help = 'Tests the full flow: Wallet Generation -> WhatsApp -> Background Watcher'

    def add_arguments(self, parser):
        parser.add_argument('phone', type=str, help='Your WhatsApp phone number with country code')

    def handle(self, *args, **options):
        phone = options['phone']
        amount = 1  # Setting it to 1 as you requested

        self.stdout.write(f"🚀 Initializing 1 USDT Trade for {phone}...")

        # 1. Generate the Blockchain Wallet
        trade = initialize_new_trade(buyer_wa=phone, seller_wa="SYSTEM_TEST", amount=amount)

        # 2. TRIGGER THE WATCHER (Crucial Step!)
        # .delay() pushes this task to Redis so Celery can pick it up
        monitor_trade.delay(trade.trade_id)
        self.stdout.write(f"🕵️ Watcher assigned to Trade ID: {trade.trade_id}")

        # 3. Format the message
        message = (
            f"✅ *New Trade Initialized*\n\n"
            f"Trade ID: `{trade.trade_id}`\n"
            f"Amount: {amount} USDT\n\n"
            f"Please send USDT to this Polygon address:\n"
            f"`{trade.escrow_address}`\n\n"
            f"I am now watching the blockchain. I will notify you the moment the payment hits."
        )

        # 4. Send via WhatsApp
        response = send_whatsapp_message(phone, message)
        self.stdout.write(f"Response from Meta: {response}")
