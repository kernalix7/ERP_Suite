"""Add code field to Category model with data migration for existing records."""
from django.db import migrations, models


def populate_category_codes(apps, schema_editor):
    """기존 카테고리 + 히스토리에 code 자동 할당."""
    Category = apps.get_model('inventory', 'Category')
    HistoricalCategory = apps.get_model('inventory', 'HistoricalCategory')

    # 한글 카테고리명 → 코드 매핑
    name_to_code = {
        '기타': 'CAT-ETC',
        '라벨': 'CAT-LBL',
        '보드': 'CAT-BRD',
        '상자': 'CAT-PKG',
        '종이': 'CAT-PPR',
        '케이블': 'CAT-CBL',
    }

    # Category 테이블
    for cat in Category.objects.all():
        code = name_to_code.get(cat.name, f'CAT-{cat.pk:03d}')
        cat.code = code
        cat.save(update_fields=['code'])

    # HistoricalCategory 테이블 — name 기반 매핑 + fallback
    for hc in HistoricalCategory.objects.filter(code__isnull=True):
        code = name_to_code.get(hc.name, f'CAT-H{hc.history_id:04d}')
        hc.code = code
        hc.save(update_fields=['code'])


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0019_product_reserved_stock_non_negative'),
    ]

    operations = [
        # 1. code 필드 추가 (nullable)
        migrations.AddField(
            model_name='category',
            name='code',
            field=models.CharField(
                verbose_name='카테고리코드',
                max_length=30,
                null=True,
            ),
        ),
        # HistoricalCategory에도 추가
        migrations.AddField(
            model_name='historicalcategory',
            name='code',
            field=models.CharField(
                verbose_name='카테고리코드',
                max_length=30,
                null=True,
            ),
        ),
        # 2. 기존 데이터에 code 할당
        migrations.RunPython(
            populate_category_codes,
            reverse_code=migrations.RunPython.noop,
        ),
        # 3. NOT NULL + unique 제약조건 적용
        migrations.AlterField(
            model_name='category',
            name='code',
            field=models.CharField(
                verbose_name='카테고리코드',
                max_length=30,
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name='historicalcategory',
            name='code',
            field=models.CharField(
                verbose_name='카테고리코드',
                max_length=30,
                db_index=True,
            ),
        ),
        # 4. ordering 변경
        migrations.AlterModelOptions(
            name='category',
            options={
                'ordering': ['code'],
                'verbose_name': '카테고리',
                'verbose_name_plural': '카테고리',
            },
        ),
    ]
