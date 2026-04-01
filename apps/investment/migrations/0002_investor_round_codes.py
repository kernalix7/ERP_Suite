"""Add code field to Investor and InvestmentRound models."""
from django.db import migrations, models


def populate_investor_codes(apps, schema_editor):
    """기존 투자자/라운드에 code 자동 할당."""
    Investor = apps.get_model('investment', 'Investor')
    HistoricalInvestor = apps.get_model('investment', 'HistoricalInvestor')
    InvestmentRound = apps.get_model('investment', 'InvestmentRound')
    HistoricalInvestmentRound = apps.get_model('investment', 'HistoricalInvestmentRound')

    for inv in Investor.objects.all():
        inv.code = f'INV-{inv.pk:03d}'
        inv.save(update_fields=['code'])
    for hc in HistoricalInvestor.objects.filter(code__isnull=True):
        hc.code = f'INV-H{hc.history_id:04d}'
        hc.save(update_fields=['code'])

    for rd in InvestmentRound.objects.all():
        rd.code = f'RND-{rd.pk:03d}'
        rd.save(update_fields=['code'])
    for hc in HistoricalInvestmentRound.objects.filter(code__isnull=True):
        hc.code = f'RND-H{hc.history_id:04d}'
        hc.save(update_fields=['code'])


class Migration(migrations.Migration):

    dependencies = [
        ('investment', '0001_initial'),
    ]

    operations = [
        # Investor
        migrations.AddField(
            model_name='investor',
            name='code',
            field=models.CharField(verbose_name='투자자코드', max_length=30, null=True),
        ),
        migrations.AddField(
            model_name='historicalinvestor',
            name='code',
            field=models.CharField(verbose_name='투자자코드', max_length=30, null=True),
        ),
        # InvestmentRound
        migrations.AddField(
            model_name='investmentround',
            name='code',
            field=models.CharField(verbose_name='라운드코드', max_length=30, null=True),
        ),
        migrations.AddField(
            model_name='historicalinvestmentround',
            name='code',
            field=models.CharField(verbose_name='라운드코드', max_length=30, null=True),
        ),
        # Data migration
        migrations.RunPython(populate_investor_codes, migrations.RunPython.noop),
        # Investor constraints
        migrations.AlterField(
            model_name='investor',
            name='code',
            field=models.CharField(verbose_name='투자자코드', max_length=30, unique=True),
        ),
        migrations.AlterField(
            model_name='historicalinvestor',
            name='code',
            field=models.CharField(verbose_name='투자자코드', max_length=30, db_index=True),
        ),
        migrations.AlterModelOptions(
            name='investor',
            options={'ordering': ['code'], 'verbose_name': '투자자', 'verbose_name_plural': '투자자'},
        ),
        # InvestmentRound constraints
        migrations.AlterField(
            model_name='investmentround',
            name='code',
            field=models.CharField(verbose_name='라운드코드', max_length=30, unique=True),
        ),
        migrations.AlterField(
            model_name='historicalinvestmentround',
            name='code',
            field=models.CharField(verbose_name='라운드코드', max_length=30, db_index=True),
        ),
    ]
