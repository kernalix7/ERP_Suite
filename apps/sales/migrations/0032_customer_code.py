"""Add code field to Customer model."""
from django.db import migrations, models


def populate_customer_codes(apps, schema_editor):
    """기존 고객에 code 자동 할당."""
    Customer = apps.get_model('sales', 'Customer')
    HistoricalCustomer = apps.get_model('sales', 'HistoricalCustomer')

    for cat in Customer.objects.all():
        cat.code = f'CUST-{cat.pk:03d}'
        cat.save(update_fields=['code'])

    for hc in HistoricalCustomer.objects.filter(code__isnull=True):
        hc.code = f'CUST-H{hc.history_id:04d}'
        hc.save(update_fields=['code'])


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0031_alter_customer_address_alter_customer_email_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='code',
            field=models.CharField(verbose_name='고객코드', max_length=30, null=True),
        ),
        migrations.AddField(
            model_name='historicalcustomer',
            name='code',
            field=models.CharField(verbose_name='고객코드', max_length=30, null=True),
        ),
        migrations.RunPython(populate_customer_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='customer',
            name='code',
            field=models.CharField(verbose_name='고객코드', max_length=30, unique=True),
        ),
        migrations.AlterField(
            model_name='historicalcustomer',
            name='code',
            field=models.CharField(verbose_name='고객코드', max_length=30, db_index=True),
        ),
        migrations.AlterModelOptions(
            name='customer',
            options={'ordering': ['code'], 'verbose_name': '고객', 'verbose_name_plural': '고객'},
        ),
    ]
