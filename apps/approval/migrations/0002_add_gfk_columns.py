"""
approval_approvalrequest 테이블에 content_type_id, object_id 컬럼을 실제로 추가.
0001_initial에서는 SeparateDatabaseAndState로 state만 선언했고
DB 컬럼은 추가되지 않았으므로 여기서 보완.
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
                        # SQLite doesn't support DROP COLUMN before 3.35
                        # but Django 5.x requires SQLite 3.27+, and most have 3.35+
                        "ALTER TABLE approval_approvalrequest DROP COLUMN content_type_id;",
                        "ALTER TABLE approval_approvalrequest DROP COLUMN object_id;",
                        "ALTER TABLE approval_historicalapprovalrequest DROP COLUMN content_type_id;",
                        "ALTER TABLE approval_historicalapprovalrequest DROP COLUMN object_id;",
                    ],
                ),
            ],
            state_operations=[],  # State already declared in 0001
        ),
    ]
