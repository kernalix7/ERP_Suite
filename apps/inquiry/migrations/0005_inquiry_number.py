"""Add inquiry_number field to Inquiry model."""
from django.db import migrations, models


def populate_inquiry_numbers(apps, schema_editor):
    """기존 문의에 inquiry_number 자동 할당."""
    Inquiry = apps.get_model('inquiry', 'Inquiry')
    HistoricalInquiry = apps.get_model('inquiry', 'HistoricalInquiry')

    for inq in Inquiry.objects.all():
        inq.inquiry_number = f'INQ-{inq.pk:06d}'
        inq.save(update_fields=['inquiry_number'])

    for hc in HistoricalInquiry.objects.filter(inquiry_number__isnull=True):
        hc.inquiry_number = f'INQ-H{hc.history_id:06d}'
        hc.save(update_fields=['inquiry_number'])


class Migration(migrations.Migration):

    dependencies = [
        ('inquiry', '0004_alter_historicalinquiry_customer_contact_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='inquiry',
            name='inquiry_number',
            field=models.CharField(verbose_name='문의번호', max_length=30, null=True, editable=False),
        ),
        migrations.AddField(
            model_name='historicalinquiry',
            name='inquiry_number',
            field=models.CharField(verbose_name='문의번호', max_length=30, null=True, editable=False),
        ),
        migrations.RunPython(populate_inquiry_numbers, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='inquiry',
            name='inquiry_number',
            field=models.CharField(verbose_name='문의번호', max_length=30, unique=True, editable=False),
        ),
        migrations.AlterField(
            model_name='historicalinquiry',
            name='inquiry_number',
            field=models.CharField(verbose_name='문의번호', max_length=30, db_index=True, editable=False),
        ),
    ]
