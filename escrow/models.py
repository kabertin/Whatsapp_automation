from django.db import models
import os
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone

def validate_video_length(value):
    # 1. First check the extension (No library needed)
    ext = os.path.splitext(str(value))[1].lower()
    if ext not in ['.mp4', '.mov', '.webm', '.avi']:
        raise ValidationError("File must be a video (MP4, MOV, etc.). Photos are not allowed.")

    # 2. Check duration ONLY if moviepy is actually installed
    try:
        # We import it here inside the function so it doesn't crash the server
        from moviepy.video.io.VideoFileClip import VideoFileClip

        full_path = os.path.join(settings.MEDIA_ROOT, str(value))
        if os.path.exists(full_path):
            with VideoFileClip(full_path) as video:
                if video.duration < 5:
                    raise ValidationError(f"Video is too short ({round(video.duration, 1)}s). Min 5s.")
                if video.duration > 15:
                    raise ValidationError(f"Video is too long ({round(video.duration, 1)}s). Max 15s.")
    except (ImportError, ModuleNotFoundError):
        # If the library is missing, we just skip the duration check for now
        # so the server stays online.
        pass

class UserProfile(models.Model):
    phone_number = models.CharField(max_length=100, unique=True)
    is_provider = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.phone_number

class CategoryConfig(models.Model):
    name = models.CharField(max_length=100)
    monthly_fee_rwf = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    # NEW FIELDS for Hierarchy
    group = models.CharField(max_length=50, default="General", db_index=True)
    icon = models.CharField(max_length=10, default="🛠️")

    def __str__(self):
        return f"{self.icon} {self.name} - {self.group} ({self.monthly_fee_rwf} RWF)"

class Provider(models.Model):
    ENTITY_TYPE_CHOICES = [
        ('INDIVIDUAL', 'Individual'),
        ('COMPANY', 'Company'),
    ]

    # Account Linking
    user = models.OneToOneField(UserProfile, on_delete=models.CASCADE, related_name='business')
    business_name = models.CharField(max_length=255)
    category = models.ForeignKey(CategoryConfig, on_delete=models.PROTECT)
    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPE_CHOICES)

    # Location
    district = models.CharField(max_length=50)
    sector = models.CharField(max_length=50)

    # KYC Documents (Stored as local paths)
    id_front = models.CharField(max_length=255, blank=True, null=True)
    id_back = models.CharField(max_length=255, blank=True, null=True)
    face_scan = models.CharField(max_length=255, blank=True, null=True, validators=[validate_video_length])
    rdb_doc = models.CharField(max_length=255, blank=True, null=True)

    # --- NEW: Visibility & Deletion ---
    is_visible = models.BooleanField(default=True, help_text="Allows provider to hide/show themselves in search")
    is_deleted = models.BooleanField(default=False, help_text="Soft delete to free up phone number for new service")

    # --- NEW: Automated Payment Tracking ---
    is_paid = models.BooleanField(default=False)
    payment_reference = models.CharField(max_length=100, blank=True, null=True, unique=True)

    # Portfolio & Stats
    portfolio_images = models.JSONField(default=list)
    is_verified = models.BooleanField(default=False)
    trust_score = models.DecimalField(max_digits=3, decimal_places=1, default=5.0)
    review_count = models.IntegerField(default=0)

    # Status & Subscriptions
    is_active = models.BooleanField(default=False) # Admin approval status
    subscription_expiry = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_badge(self):
        """Returns the verification status badge"""
        return "✅ Verified" if self.is_verified else "⏳ Pending"

    def get_stars(self):
        """Converts trust_score (e.g., 4.8) into visual stars (⭐⭐⭐⭐)"""
        return "⭐" * int(self.trust_score)

    def __str__(self):
        return f"{self.business_name} ({self.entity_type})"

class Review(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name='reviews')
    reviewer_phone = models.CharField(max_length=20)
    rating = models.IntegerField()
    text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class ChatSession(models.Model):
    phone_number = models.CharField(max_length=100, unique=True)
    state = models.CharField(max_length=50, default="START")
    temp_data = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.phone_number} - {self.state}"

class MomoTransaction(models.Model):
    tx_id = models.CharField(max_length=50, unique=True, verbose_name="Transaction ID")
    amount = models.IntegerField(verbose_name="Amount Received")
    payer_name = models.CharField(max_length=255, blank=True, null=True)
    full_text = models.TextField(help_text="The original SMS content")
    is_used = models.BooleanField(default=False, help_text="Checked if a provider has already claimed this money")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tx_id} - {self.amount} RWF"

    class Meta:
        verbose_name = "MoMo Bank Record"
        ordering = ['-created_at']
