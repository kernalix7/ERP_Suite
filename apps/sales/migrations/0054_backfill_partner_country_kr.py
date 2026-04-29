"""모든 Partner 행에 country=KR 자동 backfill.

prod 데이터 보존: KR 1건 외 다른 country 절대 생성 안 함.
"""
from django.db import migrations


def backfill_kr(apps, schema_editor):
    Country = apps.get_model('localizations', 'Country')
    Partner = apps.get_model('sales', 'Partner')
    try:
        kr = Country.objects.get(code='KR')
    except Country.DoesNotExist:
        return
    Partner.objects.filter(country__isnull=True).update(country=kr)


def reverse(apps, schema_editor):
    Partner = apps.get_model('sales', 'Partner')
    Partner.objects.update(country=None)


class Migration(migrations.Migration):
    dependencies = [
        ('sales', '0053_historicalpartner_country_partner_country'),
        ('localizations', '0002_seed_kr_country'),
    ]
    operations = [
        migrations.RunPython(backfill_kr, reverse),
    ]
