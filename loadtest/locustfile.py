"""
ERP Suite 부하 테스트

실행 방법:
  pip install locust
  cd loadtest
  locust -f locustfile.py --host http://localhost:8000

웹 UI: http://localhost:8089

헤드리스 실행 (벤치마크):
  locust -f locustfile.py --host http://localhost:8000 \
    --headless -u 50 -r 5 --run-time 60s \
    --csv=results --html=report.html
"""
import os
import re

from locust import HttpUser, task, between, tag


class ERPUser(HttpUser):
    """일반 ERP 사용자 시나리오"""
    wait_time = between(1, 5)

    def on_start(self):
        """로그인"""
        resp = self.client.get('/accounts/login/')
        match = re.search(
            r'name="csrfmiddlewaretoken" value="([^"]+)"',
            resp.text,
        )
        csrf = match.group(1) if match else ''

        self.client.post('/accounts/login/', {
            'username': 'admin',
            'password': os.environ.get('LOADTEST_PASSWORD', 'changeme'),
            'csrfmiddlewaretoken': csrf,
        }, headers={'Referer': f'{self.host}/accounts/login/'})

    def _get_csrf(self, url):
        """페이지에서 CSRF 토큰 추출"""
        resp = self.client.get(url)
        match = re.search(
            r'name="csrfmiddlewaretoken" value="([^"]+)"',
            resp.text,
        )
        return match.group(1) if match else ''

    # === 읽기 작업 (높은 빈도) ===

    @tag('dashboard')
    @task(10)
    def view_dashboard(self):
        """대시보드 조회 (가장 빈번)"""
        self.client.get('/')

    @tag('inventory')
    @task(5)
    def view_product_list(self):
        """제품 목록 조회"""
        self.client.get('/inventory/products/')

    @tag('inventory')
    @task(3)
    def view_stock_status(self):
        """재고 현황 조회"""
        self.client.get('/inventory/stock-status/')

    @tag('inventory')
    @task(2)
    def view_movement_list(self):
        """입출고 내역 조회"""
        self.client.get('/inventory/movements/')

    @tag('inventory')
    @task(2)
    def view_warehouse_stock(self):
        """창고별 재고 현황 조회"""
        self.client.get('/inventory/warehouse-stock/')

    @tag('inventory')
    @task(1)
    def view_stock_count_list(self):
        """재고실사 목록 조회"""
        self.client.get('/inventory/stock-count/')

    @tag('sales')
    @task(5)
    def view_order_list(self):
        """주문 목록 조회"""
        self.client.get('/sales/orders/')

    @tag('sales')
    @task(3)
    def view_partner_list(self):
        """거래처 목록 조회"""
        self.client.get('/sales/partners/')

    @tag('sales')
    @task(2)
    def view_quotation_list(self):
        """견적 목록 조회"""
        self.client.get('/sales/quotations/')

    @tag('production')
    @task(3)
    def view_plan_list(self):
        """생산계획 목록 조회"""
        self.client.get('/production/plans/')

    @tag('production')
    @task(2)
    def view_workorder_list(self):
        """작업지시 목록 조회"""
        self.client.get('/production/workorders/')

    @tag('production')
    @task(2)
    def view_bom_list(self):
        """BOM 목록 조회"""
        self.client.get('/production/bom/')

    @tag('production')
    @task(1)
    def view_qc_list(self):
        """품질검수 목록 조회"""
        self.client.get('/production/qc/')

    @tag('accounting')
    @task(2)
    def view_accounting_dashboard(self):
        """회계 대시보드 조회"""
        self.client.get('/accounting/')

    @tag('accounting')
    @task(1)
    def view_voucher_list(self):
        """전표 목록 조회"""
        self.client.get('/accounting/vouchers/')

    @tag('accounting')
    @task(1)
    def view_taxinvoice_list(self):
        """세금계산서 목록 조회"""
        self.client.get('/accounting/tax-invoices/')

    @tag('accounting')
    @task(1)
    def view_bank_reconciliation(self):
        """은행 대사 조회"""
        self.client.get('/accounting/bank-reconciliation/')

    @tag('accounting')
    @task(1)
    def view_account_ledger(self):
        """계정별 원장 조회"""
        self.client.get('/accounting/ledger/')

    @tag('accounting')
    @task(1)
    def view_trial_balance(self):
        """시산표 조회"""
        self.client.get('/accounting/trial-balance/')

    @tag('accounting')
    @task(1)
    def view_budget_list(self):
        """예산관리 조회"""
        self.client.get('/accounting/budget/')

    @tag('purchase')
    @task(2)
    def view_purchase_order_list(self):
        """발주서 목록 조회"""
        self.client.get('/purchase/orders/')

    @tag('service')
    @task(1)
    def view_service_list(self):
        """AS 목록 조회"""
        self.client.get('/service/requests/')

    @tag('hr')
    @task(1)
    def view_employee_list(self):
        """직원 목록 조회"""
        self.client.get('/hr/employees/')

    @tag('hr')
    @task(1)
    def view_org_chart(self):
        """조직도 조회"""
        self.client.get('/hr/org-chart/')

    @tag('board')
    @task(2)
    def view_board_list(self):
        """게시판 목록 조회"""
        self.client.get('/board/')

    @tag('attendance')
    @task(1)
    def view_attendance_dashboard(self):
        """근태 현황 조회"""
        self.client.get('/attendance/')

    # === API 엔드포인트 ===

    @tag('api')
    @task(3)
    def api_product_list(self):
        """API 제품 목록 조회"""
        self.client.get('/api/products/?format=json')

    @tag('api')
    @task(2)
    def api_order_list(self):
        """API 주문 목록 조회"""
        self.client.get('/api/orders/?format=json')

    @tag('api')
    @task(1)
    def api_stock_movements(self):
        """API 재고이동 조회"""
        self.client.get('/api/stock-movements/?format=json')

    # === Excel 다운로드 ===

    @tag('excel')
    @task(1)
    def download_product_excel(self):
        """제품 목록 Excel 다운로드"""
        self.client.get('/inventory/products/excel/')

    @tag('excel')
    @task(1)
    def download_order_excel(self):
        """주문 목록 Excel 다운로드"""
        self.client.get('/sales/orders/excel/')


class APIUser(HttpUser):
    """API 전용 사용자 (JWT 인증)"""
    wait_time = between(0.5, 2)

    def on_start(self):
        """JWT 토큰 획득"""
        resp = self.client.post('/api/token/', json={
            'username': 'admin',
            'password': os.environ.get('LOADTEST_PASSWORD', 'changeme'),
        })
        if resp.status_code == 200:
            self.token = resp.json().get('access', '')
            self.client.headers.update({
                'Authorization': f'Bearer {self.token}',
            })
        else:
            self.token = ''

    @task(5)
    def api_products(self):
        self.client.get('/api/products/?format=json')

    @task(3)
    def api_orders(self):
        self.client.get('/api/orders/?format=json')

    @task(2)
    def api_stock_movements(self):
        self.client.get('/api/stock-movements/?format=json')

    @task(2)
    def api_production_plans(self):
        self.client.get('/api/production-plans/?format=json')

    @task(1)
    def api_partners(self):
        self.client.get('/api/partners/?format=json')

    @task(1)
    def api_products_search(self):
        """API 제품 검색"""
        self.client.get('/api/products/?format=json&search=테스트')

    @task(1)
    def api_products_filter(self):
        """API 제품 타입 필터"""
        self.client.get('/api/products/?format=json&product_type=FINISHED')

    @task(1)
    def api_orders_pagination(self):
        """API 주문 페이지네이션"""
        self.client.get('/api/orders/?format=json&page=1&page_size=10')
