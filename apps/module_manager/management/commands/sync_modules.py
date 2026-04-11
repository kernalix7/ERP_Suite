from django.core.management.base import BaseCommand

from apps.module_manager.models import InstalledModule
from apps.module_manager.registry import module_registry


class Command(BaseCommand):
    help = '레지스트리에 등록된 모듈을 DB와 동기화합니다'

    def handle(self, *args, **options):
        all_modules = module_registry.get_all()
        created = 0
        updated = 0

        for module_id, module in all_modules.items():
            obj, was_created = InstalledModule.all_objects.get_or_create(
                module_id=module_id,
                defaults={
                    'name': module.name,
                    'description': module.description,
                    'category': module.category,
                    'country_code': module.country_code,
                    'version': module.version,
                    'icon': module.icon,
                    'dependencies': module.dependencies,
                },
            )
            if was_created:
                created += 1
                self.stdout.write(f'  생성: {module_id}')
            else:
                changed = False
                for attr in ('name', 'description', 'version', 'icon', 'dependencies'):
                    new_val = getattr(module, attr)
                    if getattr(obj, attr) != new_val:
                        setattr(obj, attr, new_val)
                        changed = True
                if changed:
                    obj.save()
                    updated += 1
                    self.stdout.write(f'  업데이트: {module_id}')

        self.stdout.write(self.style.SUCCESS(
            f'동기화 완료: {created}개 생성, {updated}개 업데이트 (전체 {len(all_modules)}개 모듈)'
        ))
