"""
ERP Suite 부하 테스트

실행 방법:
  pip install locust
  cd loadtest
  locust -f locustfile.py --host http://localhost:8000

웹 UI: http://localhost:8089
"""
from locust import HttpUser, task, between, tag


class ERPUser(HttpUser):
    """일반 ERP 사용자 시나리오"""
    wait_time = between(1, 5)

    def on_start(self):
        """로그인"""
        # CSRF 토큰 획득
        resp = self.client.get('/accounts/login/')
        if 'csrfmiddlewaretoken' in resp.text:
            import re
            match = re.search(
                r'name="csrfmiddlewaretoken" value="([^"]+)"',
                resp.text,
            )
            csrf = match.group(1) if match else ''
        else:
            csrf = ''

        self.client.post('/accounts/login/', {
            'username': 'admin',
            'password': 'admin123!',
            'csrfmiddlewaretoken': csrf,
        }, headers={'Referer': f'{self.host}/accounts/login/'})

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

    @tag('accounting')
    @task(2)
    def view_accounting_dashboard(self):
        """회계 대시보드 조회"""
        self.client.get('/accounting/')

    @tag('service')
    @task(1)
    def view_service_list(self):
        """AS 목록 조회"""
        self.client.get('/service/requests/')

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


class APIUser(HttpUser):
    """API 전용 사용자 (JWT 인증)"""
    wait_time = between(0.5, 2)

    def on_start(self):
        """JWT 토큰 획득"""
        resp = self.client.post('/api/token/', json={
            'username': 'admin',
            'password': 'admin123!',
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
