from apps.core.forms import BaseForm
from .models import VisitorPurpose, Visitor, VisitRequest, VisitLog


class VisitorPurposeForm(BaseForm):
    class Meta:
        model = VisitorPurpose
        fields = ['name', 'code', 'requires_escort', 'notes']


class VisitorForm(BaseForm):
    class Meta:
        model = Visitor
        fields = ['name', 'company', 'phone', 'email', 'id_type', 'photo', 'notes']


class VisitRequestForm(BaseForm):
    class Meta:
        model = VisitRequest
        fields = [
            'visitor', 'host', 'purpose', 'department',
            'scheduled_at', 'expected_duration_minutes',
            'visitor_count', 'description', 'notes',
        ]


class VisitCheckInForm(BaseForm):
    class Meta:
        model = VisitLog
        fields = ['visit_request', 'visitor', 'badge_number', 'temperature', 'remarks']


class VisitCheckOutForm(BaseForm):
    class Meta:
        model = VisitLog
        fields = ['check_out_at', 'remarks']
