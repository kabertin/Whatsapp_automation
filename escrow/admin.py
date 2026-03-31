from django.contrib import admin
from .models import UserProfile, Provider, ChatSession, CategoryConfig, Review, MomoTransaction
from django.db.models import Sum, Count
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils import timezone


@admin.register(CategoryConfig)
class CategoryConfigAdmin(admin.ModelAdmin):
    # 1. Removed 'base_price' since it doesn't exist in your model
    list_display = ('icon', 'name', 'group', 'monthly_fee_rwf', 'is_active')

    # 2. 'name' is the clickable link to open the record
    list_display_links = ('name',)

    # 3. Sidebar filters
    list_filter = ('group', 'is_active')

    # 4. Search bar
    search_fields = ('name', 'group')

    # 5. Only include fields that actually exist in your CategoryConfig model
    list_editable = ('icon', 'group', 'monthly_fee_rwf', 'is_active')

    # 6. Detailed view organization
    fieldsets = (
        (None, {
            'fields': ('name', 'icon', 'group', 'is_active', 'monthly_fee_rwf')
        }),
    )

@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ('business_name', 'category', 'is_active', 'is_visible', 'is_paid', 'is_deleted', 'created_at')
    list_filter = ('category', 'is_verified', 'is_active', 'is_visible', 'is_paid', 'is_deleted', 'entity_type')
    search_fields = ('business_name', 'user__phone_number', 'district', 'payment_reference')

    fieldsets = (
        ('Account Details', {
            'fields': ('user', 'business_name', 'category', 'entity_type')
        }),
        ('Status & Visibility', {
            'fields': ('is_active', 'is_verified', 'is_visible', 'is_deleted'),
        }),
        ('Location', {
            'fields': ('district', 'sector')
        }),
        ('KYC Verification Media', {
            'fields': ('show_id_front', 'show_id_back', 'show_face_scan', 'show_rdb_doc'),
        }),
        ('Business Portfolio', {
            'fields': ('show_portfolio',),
        }),
        ('Payment & Analytics', {
            'fields': ('is_paid', 'payment_reference', 'subscription_expiry', 'trust_score', 'review_count'),
        }),
    )

    readonly_fields = ('show_id_front', 'show_id_back', 'show_face_scan', 'show_rdb_doc', 'show_portfolio')

    def show_id_front(self, obj):
        if obj.id_front:
            return mark_safe(f'<a href="/media/{obj.id_front}" target="_blank"><img src="/media/{obj.id_front}" width="200" style="border-radius: 8px; border: 1px solid #ccc;"/></a>')
        return "No Front ID uploaded"

    def show_id_back(self, obj):
        if obj.id_back:
            return mark_safe(f'<a href="/media/{obj.id_back}" target="_blank"><img src="/media/{obj.id_back}" width="200" style="border-radius: 8px; border: 1px solid #ccc;"/></a>')
        return "No Back ID uploaded"

    def show_face_scan(self, obj):
        if obj.face_scan:
            return mark_safe(f'<video width="320" height="240" controls style="border-radius: 8px;"><source src="/media/{obj.face_scan}" type="video/mp4">Your browser does not support the video tag.</video>')
        return "No Face Scan uploaded"

    def show_rdb_doc(self, obj):
        if obj.rdb_doc:
            if obj.rdb_doc.endswith('.pdf'):
                return mark_safe(f'<a href="/media/{obj.rdb_doc}" target="_blank">📄 View RDB PDF Certificate</a>')
            return mark_safe(f'<a href="/media/{obj.rdb_doc}" target="_blank"><img src="/media/{obj.rdb_doc}" width="200"/></a>')
        return "No RDB Document"

    def show_portfolio(self, obj):
        images = obj.portfolio_images or []
        if not images: return "No portfolio images"
        html = '<div style="display: flex; flex-wrap: wrap;">'
        for path in images:
            html += f'<div style="margin: 5px;"><a href="/media/{path}" target="_blank"><img src="/media/{path}" width="120" height="120" style="object-fit: cover; border-radius: 4px; border: 1px solid #ddd;"/></a></div>'
        html += '</div>'
        return mark_safe(html)

    show_id_front.short_description = "National ID (Front)"
    show_id_back.short_description = "National ID (Back)"
    show_face_scan.short_description = "Face Verification Video"
    show_rdb_doc.short_description = "RDB Registration"
    show_portfolio.short_description = "Business Portfolio"

@admin.register(MomoTransaction)
class MomoTransactionAdmin(admin.ModelAdmin):
    list_display = ('tx_id', 'amount_display', 'payer_name', 'status_display', 'created_at')
    list_filter = ('is_used', 'created_at')
    search_fields = ('tx_id', 'payer_name', 'full_text')
    readonly_fields = ('tx_id', 'amount', 'payer_name', 'full_text', 'created_at')

    def amount_display(self, obj):
        return f"{obj.amount:,} RWF"
    amount_display.short_description = "Amount"

    # FIXED: Using mark_safe instead of format_html to avoid the "args" error
    def status_display(self, obj):
        if obj.is_used:
            return mark_safe('<span style="color: green; font-weight: bold;">Verified ✅</span>')
        return mark_safe('<span style="color: orange;">Pending ⏳</span>')
    status_display.short_description = "Status"

    def changelist_view(self, request, extra_context=None):
        today = timezone.now().date()
        stats = MomoTransaction.objects.filter(created_at__date=today).aggregate(
            total_money=Sum('amount'),
            total_count=Count('id')
        )

        extra_context = extra_context or {}
        today_rev = stats['total_money'] or 0
        today_cnt = stats['total_count'] or 0

        extra_context['today_revenue'] = today_rev
        extra_context['today_count'] = today_cnt

        # FIXED: Use a plain f-string here. DO NOT use format_html for the title.
        extra_context['title'] = f"MoMo Bank Records (Today: {today_rev:,} RWF | {today_cnt} tx)"

        return super().changelist_view(request, extra_context=extra_context)

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('provider', 'rating', 'reviewer_phone', 'created_at')

admin.site.register(UserProfile)
admin.site.register(ChatSession)
