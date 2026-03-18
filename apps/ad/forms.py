from django import forms

from apps.core.forms import BaseForm
from .models import (
    ADDomain, ADOrganizationalUnit, ADGroup,
    ADUserMapping, ADGroupPolicy,
)


class ADDomainForm(BaseForm):
    class Meta:
        model = ADDomain
        fields = [
            'name', 'domain', 'ldap_server', 'ldap_bind_dn',
            'ldap_bind_password', 'base_dn', 'user_search_base',
            'group_search_base', 'use_ssl', 'use_start_tls',
            'sync_enabled', 'sync_interval_minutes', 'notes',
        ]
        widgets = {
            'ldap_bind_password': forms.PasswordInput(
                attrs={'autocomplete': 'new-password'},
            ),
        }


class ADOrganizationalUnitForm(BaseForm):
    class Meta:
        model = ADOrganizationalUnit
        fields = [
            'domain', 'distinguished_name', 'name',
            'parent', 'description', 'mapped_department',
        ]


class ADGroupForm(BaseForm):
    class Meta:
        model = ADGroup
        fields = [
            'domain', 'distinguished_name', 'sam_account_name',
            'display_name', 'description', 'group_type',
            'group_scope', 'mapped_role', 'ou',
        ]


class ADUserMappingForm(BaseForm):
    class Meta:
        model = ADUserMapping
        fields = [
            'user', 'domain', 'distinguished_name',
            'sam_account_name', 'user_principal_name',
            'object_guid', 'ad_groups', 'ou',
        ]


class ADGroupPolicyForm(BaseForm):
    class Meta:
        model = ADGroupPolicy
        fields = [
            'name', 'domain', 'ad_group', 'action',
            'action_value', 'priority', 'notes',
        ]


class ADConnectionTestForm(forms.Form):
    """AD 연결 테스트 폼"""
    domain = forms.ModelChoiceField(
        queryset=ADDomain.objects.all(),
        label='도메인',
    )


class ADManualSyncForm(forms.Form):
    """수동 동기화 폼"""
    SYNC_CHOICES = [
        ('FULL', '전체 동기화'),
        ('INCREMENTAL', '증분 동기화'),
    ]
    domain = forms.ModelChoiceField(
        queryset=ADDomain.objects.all(),
        label='도메인',
    )
    sync_type = forms.ChoiceField(
        choices=SYNC_CHOICES,
        label='동기화 유형',
    )
