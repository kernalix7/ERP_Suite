"""
accounting 앱에서 ApprovalRequest/ApprovalStep 모델 제거 (state only).
실제 DB 작업은 approval.0001_initial에서 처리.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0010_bankaccount_balance_transfer_distribution'),
        ('approval', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RemoveIndex(
                    model_name='approvalrequest',
                    name='idx_approval_status',
                ),
                migrations.DeleteModel(name='HistoricalApprovalStep'),
                migrations.DeleteModel(name='HistoricalApprovalRequest'),
                migrations.DeleteModel(name='ApprovalStep'),
                migrations.DeleteModel(name='ApprovalRequest'),
            ],
        ),
    ]
