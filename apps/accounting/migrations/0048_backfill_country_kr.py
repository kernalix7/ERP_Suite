"""모든 AccountCode/TaxRate 행에 country=KR 자동 backfill.

prod 데이터 보존 원칙: KR 단일 행만 생성. 다른 country 절대 생성 안 함.
미설치 환경(localizations 마이그 미적용 시점) 보호를 위해 try/except.
"""
from django.db import migrations


def backfill_kr(apps, schema_editor):
    Country = apps.get_model('localizations', 'Country')
    AccountCode = apps.get_model('accounting', 'AccountCode')
    TaxRate = apps.get_model('accounting', 'TaxRate')
    try:
        kr = Country.objects.get(code='KR')
    except Country.DoesNotExist:
        return  # localizations 0002 미적용 — 후속 마이그에서 처리
    AccountCode.objects.filter(country__isnull=True).update(country=kr)
    TaxRate.objects.filter(country__isnull=True).update(country=kr)


def reverse(apps, schema_editor):
    AccountCode = apps.get_model('accounting', 'AccountCode')
    TaxRate = apps.get_model('accounting', 'TaxRate')
    AccountCode.objects.update(country=None)
    TaxRate.objects.update(country=None)


class Migration(migrations.Migration):
    dependencies = [
        ('accounting', '0047_accountcode_country_historicalaccountcode_country_and_more'),
        ('localizations', '0002_seed_kr_country'),
    ]
    operations = [
        migrations.RunPython(backfill_kr, reverse),
    ]
