from import_export import resources

from .models import Investor


class InvestorResource(resources.ModelResource):
    class Meta:
        model = Investor
        fields = (
            'name', 'company', 'contact_person',
            'phone', 'email', 'address', 'registration_date',
        )
        import_id_fields = ('name',)
        skip_unchanged = True
        report_skipped = True
