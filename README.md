# 🛒 Mercato Marketplace: Merchant Activation Engine

The high-performance backend infrastructure for the **Mercato** marketplace. This system automates the lifecycle of merchant listings in Rwanda, bridging the gap between Mobile Money (MoMo) payments and real-time business visibility.

## 🚀 Core Functionality

### ⚡ Automated Merchant Activation
* **MoMo SMS Gateway:** Integrated with SMSSync to process incoming transaction messages instantly through a hardened webhook.
* **Smart Matching Engine:** Advanced regex-based logic that links Transaction IDs and Phone Numbers to specific Provider accounts for zero-touch activation.
* **Subscription Management:** Automated tracking of payment status, subscription expiry, and listing lifecycle.

### 💬 Official Meta WhatsApp Integration
* **Enterprise Messaging:** Leverages the **Official Meta WhatsApp Business API** for high-reliability, secure message delivery.
* **Real-time Confirmation:** Instant, template-based WhatsApp notifications sent to merchants upon successful business activation.
* **Session Persistence:** High-integrity message logging and state management for buyer/seller interactions.

### 🛡️ System Integrity
* **Anti-Duplicate Check:** UUID-based verification to prevent double-processing of payment signals.
* **Failure Resilience:** Hardened error handling for chat notifications to ensure database updates persist even if the Meta API experiences latency.

## 🛠️ Technical Stack

* **Language:** Python 3.10+
* **Framework:** Django 4.x
* **Messaging API:** **Meta WhatsApp Business API**
* **Integration:** SMSSync (Android SMS Gateway)
* **Infrastructure:** AWS EC2 (Ubuntu 22.04)

## 📦 Getting Started

1. **Clone the repository:**
   \`\`\`bash
   git clone git@github.com:kabertin/Whatsapp_automation.git
   cd Whatsapp_automation
   \`\`\`

2. **Environment Setup:**
   Create a \`.env\` file for your \`SECRET_KEY\`, \`META_ACCESS_TOKEN\`, and \`WHATSAPP_PHONE_ID\`.

3. **Install Dependencies:**
   \`\`\`bash
   pip install -r requirements.txt
   \`\`\`

4. **Run Migrations:**
   \`\`\`bash
   python manage.py migrate
   \`\`\`

---

**Developed with 💡 in Kigali, Rwanda.**
*Lead Engineer: Bertin Karinda*
