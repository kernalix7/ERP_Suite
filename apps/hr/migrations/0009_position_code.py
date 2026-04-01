"""Add code field to Position model."""
from django.db import migrations, models


def populate_position_codes(apps, schema_editor):
    """기존 직급에 code 자동 할당."""
    Position = apps.get_model('hr', 'Position')
    HistoricalPosition = apps.get_model('hr', 'HistoricalPosition')

    name_to_code = {
        'CEO': 'POS-CEO',
        '사장': 'POS-CEO',
        '부사장': 'POS-VP',
        '전무': 'POS-EVP',
        '상무': 'POS-SVP',
        '이사': 'POS-DIR',
        '부장': 'POS-GM',
        '차장': 'POS-DM',
        '과장': 'POS-MGR',
        '대리': 'POS-AM',
        '주임': 'POS-SR',
        '사원': 'POS-STF',
        '인턴': 'POS-INT',
    }
    for pos in Position.objects.all():
        code = name_to_code.get(pos.name, f'POS-{pos.pk:03d}')
        pos.code = code
        pos.save(update_fields=['code'])

    for hc in HistoricalPosition.objects.filter(code__isnull=True):
        hc.code = f'POS-H{hc.history_id:04d}'
        hc.save(update_fields=['code'])


class Migration(migrations.Migration):

    dependencies = [
        ('hr', '0008_employeeprofile_base_salary_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='position',
            name='code',
            field=models.CharField(verbose_name='직급코드', max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='historicalposition',
            name='code',
            field=models.CharField(verbose_name='직급코드', max_length=20, null=True),
        ),
        migrations.RunPython(populate_position_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='position',
            name='code',
            field=models.CharField(verbose_name='직급코드', max_length=20, unique=True),
        ),
        migrations.AlterField(
            model_name='historicalposition',
            name='code',
            field=models.CharField(verbose_name='직급코드', max_length=20, db_index=True),
        ),
    ]
