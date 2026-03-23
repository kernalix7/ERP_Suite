"""
데이터 입력 가이드 리포트 시스템.

AI가 임포트한 데이터를 JSON으로 기록 → HTML로 렌더링하여
Prod 환경에서 수동 입력할 때 참고 가이드로 사용.
"""
import json
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

REPORT_FILE = Path(settings.BASE_DIR) / 'local' / 'data_report.json'


def load_report():
    """리포트 JSON 로드"""
    if REPORT_FILE.exists():
        return json.loads(REPORT_FILE.read_text(encoding='utf-8'))
    return {'updated_at': None, 'sections': []}


def save_report(data):
    """리포트 JSON 저장"""
    data['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def update_report_section(section_id, title, description, items):
    """
    리포트에 섹션 추가/업데이트.

    Args:
        section_id: 고유 식별자 (예: 'bom_import_20260320')
        title: 섹션 제목 (예: 'BOM 데이터 임포트')
        description: 섹션 설명
        items: [{group, label, fields: [{name, value, help}]}]
    """
    report = load_report()
    sections = report.get('sections', [])

    # 기존 섹션 업데이트 또는 새 섹션 추가
    found = False
    for i, sec in enumerate(sections):
        if sec.get('id') == section_id:
            sections[i] = {
                'id': section_id,
                'title': title,
                'description': description,
                'items': items,
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
            found = True
            break

    if not found:
        sections.append({
            'id': section_id,
            'title': title,
            'description': description,
            'items': items,
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        })

    report['sections'] = sections
    save_report(report)


class DataReportView(LoginRequiredMixin, TemplateView):
    template_name = 'core/data_report.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['report'] = load_report()
        return ctx
