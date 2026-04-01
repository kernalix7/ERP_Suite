"""
결재 모델을 accounting에서 approval 앱으로 이동.
SeparateDatabaseAndState를 사용하여 DB 테이블은 rename하고
Django state에서는 새 앱으로 생성.
"""
from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion
import simple_history.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0002_remove_content_type_name'),
        ('accounting', '0010_bankaccount_balance_transfer_distribution'),
    ]

    operations = [
        # Step 1: Rename the DB tables
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    'ALTER TABLE accounting_approvalrequest RENAME TO approval_approvalrequest;',
                    'ALTER TABLE approval_approvalrequest RENAME TO accounting_approvalrequest;',
                ),
                migrations.RunSQL(
                    'ALTER TABLE accounting_approvalstep RENAME TO approval_approvalstep;',
                    'ALTER TABLE approval_approvalstep RENAME TO accounting_approvalstep;',
                ),
                migrations.RunSQL(
                    'ALTER TABLE accounting_historicalapprovalrequest RENAME TO approval_historicalapprovalrequest;',
                    'ALTER TABLE approval_historicalapprovalrequest RENAME TO accounting_historicalapprovalrequest;',
                ),
                migrations.RunSQL(
                    'ALTER TABLE accounting_historicalapprovalstep RENAME TO approval_historicalapprovalstep;',
                    'ALTER TABLE approval_historicalapprovalstep RENAME TO accounting_historicalapprovalstep;',
                ),
            ],
            state_operations=[
                migrations.CreateModel(
                    name='ApprovalRequest',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='생성일')),
                        ('updated_at', models.DateTimeField(auto_now=True, verbose_name='수정일')),
                        ('is_active', models.BooleanField(default=True, verbose_name='활성')),
                        ('notes', models.TextField(blank=True, verbose_name='비고')),
                        ('request_number', models.CharField(max_length=30, unique=True, verbose_name='결재번호')),
                        ('category', models.CharField(choices=[
                            ('PURCHASE', '구매품의'), ('EXPENSE', '지출품의'),
                            ('BUDGET', '예산신청'), ('CONTRACT', '계약체결'),
                            ('GENERAL', '일반결재'), ('LEAVE', '휴가신청'),
                            ('OVERTIME', '초과근무'), ('TRAVEL', '출장신청'),
                            ('IT_REQUEST', 'IT요청'),
                        ], max_length=20, verbose_name='문서종류')),
                        ('title', models.CharField(max_length=200, verbose_name='제목')),
                        ('content', models.TextField(verbose_name='내용')),
                        ('amount', models.DecimalField(decimal_places=0, default=0, max_digits=15, validators=[django.core.validators.MinValueValidator(0)], verbose_name='금액')),
                        ('status', models.CharField(choices=[('DRAFT', '작성중'), ('SUBMITTED', '결재요청'), ('APPROVED', '승인'), ('REJECTED', '반려'), ('CANCELLED', '취소')], default='DRAFT', max_length=20, verbose_name='상태')),
                        ('submitted_at', models.DateTimeField(blank=True, null=True, verbose_name='제출일')),
                        ('approved_at', models.DateTimeField(blank=True, null=True, verbose_name='결재일')),
                        ('reject_reason', models.TextField(blank=True, verbose_name='반려사유')),
                        ('current_step', models.PositiveIntegerField(default=1, verbose_name='현재 결재단계')),
                        ('object_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='문서ID')),
                        ('approver', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approval_assigned', to=settings.AUTH_USER_MODEL, verbose_name='결재자')),
                        ('content_type', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='contenttypes.contenttype', verbose_name='문서유형')),
                        ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='생성자')),
                        ('requester', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='approval_requests', to=settings.AUTH_USER_MODEL, verbose_name='요청자')),
                    ],
                    options={
                        'verbose_name': '결재/품의',
                        'verbose_name_plural': '결재/품의',
                        'ordering': ['-created_at'],
                    },
                ),
                migrations.CreateModel(
                    name='ApprovalStep',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='생성일')),
                        ('updated_at', models.DateTimeField(auto_now=True, verbose_name='수정일')),
                        ('is_active', models.BooleanField(default=True, verbose_name='활성')),
                        ('notes', models.TextField(blank=True, verbose_name='비고')),
                        ('step_order', models.PositiveIntegerField(verbose_name='단계순서')),
                        ('status', models.CharField(choices=[('PENDING', '대기'), ('APPROVED', '승인'), ('REJECTED', '반려')], default='PENDING', max_length=20, verbose_name='상태')),
                        ('comment', models.TextField(blank=True, verbose_name='의견')),
                        ('acted_at', models.DateTimeField(blank=True, null=True, verbose_name='처리일시')),
                        ('approver', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='approval_steps', to=settings.AUTH_USER_MODEL, verbose_name='결재자')),
                        ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='생성자')),
                        ('request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='steps', to='approval.approvalrequest', verbose_name='결재요청')),
                    ],
                    options={
                        'verbose_name': '결재단계',
                        'verbose_name_plural': '결재단계',
                        'ordering': ['step_order'],
                        'unique_together': {('request', 'step_order')},
                    },
                ),
            ],
        ),
        # Step 2: Add status index (GFK index moved to 0002 after columns are added)
        migrations.AddIndex(
            model_name='approvalrequest',
            index=models.Index(fields=['status'], name='idx_appr_status'),
        ),
    ]
