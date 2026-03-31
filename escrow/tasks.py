from celery import shared_task
from .models import Trade
from .whatsapp_client import send_whatsapp_message
from .watcher_logic import check_for_payment
import time
from .utils import refuel_escrow_with_matic, release_funds

@shared_task
def monitor_trade(trade_id):
    try:
        trade = Trade.objects.get(trade_id=trade_id)
        print(f"🕵️ Monitoring {trade.escrow_address} for Trade {trade_id}")

        # Monitor for 1 hour
        for _ in range(360):
            current_balance = check_for_payment(trade.escrow_address)

            if current_balance >= trade.amount_usd:
                trade.status = 'PAID'
                trade.save()

                # ⛽ AUTO-REFUEL: Send 0.1 POL so the escrow wallet can move the USDT
                # We do this now so the "Release" is instant later
                refuel_escrow_with_matic(trade.escrow_address)

                # --- NEW WHATSAPP NOTIFICATIONS ---

                # 1. Notify Buyer
                buyer_msg = (
                    "✅ *Payment Detected!*\n\n"
                    f"Your {trade.amount_usd} USDT is now secured in escrow.\n\n"
                    "Once you receive your goods/service, please reply with:\n"
                    f"👉 *Release {trade.trade_id}*\n\n"
                    "If there is an issue, reply with:\n"
                    f"👉 *Dispute {trade.trade_id}*"
                )
                send_whatsapp_message(trade.buyer_wa, buyer_msg)

                # 2. Notify Seller (Proceed with the deal)
                seller_msg = (
                    "💰 *Funds Secured!*\n\n"
                    f"The buyer has deposited {trade.amount_usd} USDT.\n"
                    "It is now safe to deliver the goods/service.\n\n"
                    "The funds will be released to your wallet as soon as the buyer confirms delivery."
                )
                send_whatsapp_message(trade.seller_wa, seller_msg)

                return f"Trade {trade_id} Paid, Fueled & Notifications Sent"

            time.sleep(10)

        trade.status = 'EXPIRED'
        trade.save()
        send_whatsapp_message(trade.buyer_wa, f"⏰ *Trade Expired*\nTrade {trade_id} timed out before payment was detected.")
        return f"Trade {trade_id} Expired"

    except Exception as e:
        print(f"Error in monitor_trade: {str(e)}")
        return str(e)
