from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget

from .models import Department, Position


class DepartmentResource(resources.ModelResource):
    parent_code = fields.Field(
        column_name='parent_code',
        attribute='parent',
        widget=ForeignKeyWidget(Department, field='code'),
    )

    class Meta:
        model = Department
        fields = ('code', 'name', 'parent_code')
        import_id_fields = ('code',)
        skip_unchanged = True
        report_skipped = True


class PositionResource(resources.ModelResource):
    class Meta:
        model = Position
        fields = ('name', 'level')
        import_id_fields = ('name',)
        skip_unchanged = True
        report_skipped = True
