"""KR (한국) 국가 시드 — prod 데이터 보존을 위해 자동 생성."""
from django.db import migrations


def seed_kr(apps, schema_editor):
    Country = apps.get_model('localizations', 'Country')
    Country.objects.update_or_create(
        code='KR',
        defaults={
            'name': '대한민국',
            'currency_code': 'KRW',
            'locale': 'ko_KR',
            'is_default': True,
            'is_supported': True,
            'is_active': True,
        },
    )


def revert(apps, schema_editor):
    Country = apps.get_model('localizations', 'Country')
    Country.objects.filter(code='KR').delete()


class Migration(migrations.Migration):
    dependencies = [
        ('localizations', '0001_initial'),
    ]
    operations = [
        migrations.RunPython(seed_kr, revert),
    ]
