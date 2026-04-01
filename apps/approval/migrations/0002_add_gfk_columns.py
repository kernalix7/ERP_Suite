"""
approval_approvalrequest 테이블에 content_type_id, object_id 컬럼을 실제로 추가.
0001_initial에서는 SeparateDatabaseAndState로 state만 선언했고
DB 컬럼은 추가되지 않았으므로 여기서 보완.
GFK 인덱스도 컬럼 추가 후 여기서 생성 (0001에서 하면 컬럼 미존재로 실패).
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('approval', '0001_initial'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=[
                        "ALTER TABLE approval_approvalrequest ADD COLUMN content_type_id INTEGER NULL REFERENCES django_content_type(id);",
                        "ALTER TABLE approval_approvalrequest ADD COLUMN object_id INTEGER NULL;",
                        "ALTER TABLE approval_historicalapprovalrequest ADD COLUMN content_type_id INTEGER NULL;",
                        "ALTER TABLE approval_historicalapprovalrequest ADD COLUMN object_id INTEGER NULL;",
                    ],
                    reverse_sql=[
                        "ALTER TABLE approval_approvalrequest DROP COLUMN content_type_id;",
                        "ALTER TABLE approval_approvalrequest DROP COLUMN object_id;",
                        "ALTER TABLE approval_historicalapprovalrequest DROP COLUMN content_type_id;",
                        "ALTER TABLE approval_historicalapprovalrequest DROP COLUMN object_id;",
                    ],
                ),
            ],
            state_operations=[],  # State already declared in 0001
        ),
        # GFK index: created here after columns exist (moved from 0001)
        migrations.AddIndex(
            model_name='approvalrequest',
            index=models.Index(fields=['content_type', 'object_id'], name='idx_appr_gfk'),
        ),
    ]
