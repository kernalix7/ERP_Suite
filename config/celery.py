import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')

app = Celery('erp_suite')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'check-certification-expiry-daily': {
        'task': 'apps.asset.tasks.check_certification_expiry',
        'schedule': crontab(hour=9, minute=0),
    },
    'generate-lease-vouchers-monthly': {
        'task': 'apps.asset.tasks.generate_lease_monthly_vouchers',
        'schedule': crontab(day_of_month=1, hour=6, minute=0),
    },
    'run-depreciation-monthly': {
        'task': 'apps.asset.tasks.run_monthly_depreciation',
        'schedule': crontab(day_of_month=1, hour=7, minute=0),
    },
    'check-safety-stock-daily': {
        'task': 'apps.inventory.tasks.check_safety_stock',
        'schedule': crontab(hour=7, minute=0),
    },
    'check-reorder-point-daily': {
        'task': 'apps.inventory.tasks.check_reorder_point',
        'schedule': crontab(hour=8, minute=0),
    },
    'check-overdue-po-daily': {
        'task': 'apps.purchase.tasks.check_overdue_purchase_orders',
        'schedule': crontab(hour=7, minute=30),
    },
    'expire-quotations-daily': {
        'task': 'apps.sales.tasks.expire_quotations',
        'schedule': crontab(hour=0, minute=30),
    },
    'update-overdue-receivables-daily': {
        'task': 'apps.accounting.tasks.update_overdue_receivables',
        'schedule': crontab(hour=1, minute=0),
    },
    'reset-card-used-amount-monthly': {
        'task': 'apps.accounting.tasks.reset_card_used_amount',
        'schedule': crontab(day_of_month=1, hour=0, minute=30),
    },
    'create-card-billing-monthly': {
        'task': 'apps.accounting.tasks.create_monthly_card_billing',
        'schedule': crontab(day_of_month=1, hour=2, minute=0),
    },
    'check-labor-compliance-weekly': {
        'task': 'apps.hr.tasks.check_labor_compliance_weekly',
        'schedule': crontab(day_of_week=1, hour=9, minute=0),  # 매주 월요일 09:00
    },
    'backup-database-daily': {
        'task': 'apps.core.tasks.backup_database',
        'schedule': crontab(hour=3, minute=0),  # 매일 03:00
    },
    'check-preventive-maintenance-daily': {
        'task': 'apps.cmms.tasks.check_preventive_maintenance',
        'schedule': crontab(hour=6, minute=30),  # 매일 06:30
    },
    'check-sla-breaches': {
        'task': 'apps.helpdesk.tasks.check_sla_breaches',
        'schedule': crontab(minute='*/30'),  # 매 30분
    },
    'auto-settle-marketplace-weekly': {
        'task': 'apps.sales.tasks.auto_settle_marketplace_orders',
        'schedule': crontab(day_of_week=1, hour=4, minute=0),  # 매주 월요일 04:00
    },
}
