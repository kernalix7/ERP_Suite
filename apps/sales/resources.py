from import_export import resources

from .models import Partner, Customer


class PartnerResource(resources.ModelResource):
    class Meta:
        model = Partner
        fields = (
            'code', 'name', 'partner_type', 'business_number',
            'representative', 'contact_name', 'phone', 'email', 'address',
        )
        import_id_fields = ('code',)
        skip_unchanged = True
        report_skipped = True


class CustomerResource(resources.ModelResource):
    class Meta:
        model = Customer
        fields = ('name', 'phone', 'email', 'address')
        import_id_fields = ('name', 'phone')
        skip_unchanged = True
        report_skipped = True
