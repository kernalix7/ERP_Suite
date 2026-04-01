/**
 * 주소검색 Alpine.js 컴포넌트 (팝업 API 방식)
 * 사용: x-data="addressSearch('field_id', 'domestic')"
 *
 * 국내: juso.go.kr 팝업 → localStorage 이벤트로 결과 수신
 * 해외: AJAX 검색
 */
function addressSearch(fieldId, searchType) {
    var initialType = (!searchType || searchType === 'auto') ? 'domestic' : searchType;
    var isAutoMode = searchType === 'auto';

    return {
        query: '',
        results: [],
        loading: false,
        error: '',
        manualMode: false,
        selectedAddress: '',
        searchType: initialType,
        autoMode: isAutoMode,
        debounceTimer: null,

        init() {
            var field = document.getElementById(fieldId);
            if (field && field.value) {
                this.selectedAddress = field.value;
            }

            // localStorage 'storage' 이벤트로 팝업 결과 수신
            var self = this;
            window.addEventListener('storage', function(e) {
                if (e.key === 'juso_result' && e.newValue) {
                    try {
                        var data = JSON.parse(e.newValue);
                        if (data && data.address) {
                            self.selectedAddress = data.address;
                            var f = document.getElementById(fieldId);
                            if (f) {
                                f.value = data.address;
                                f.dispatchEvent(new Event('input', { bubbles: true }));
                            }
                            self.results = [];
                            self.query = '';
                        }
                    } catch (err) {}
                    // 정리
                    localStorage.removeItem('juso_result');
                }
            });
        },

        openPopup() {
            if (this.searchType === 'domestic') {
                window.open('/juso-popup/', 'jusoPopup', 'width=570,height=420,scrollbars=yes,resizable=yes');
            } else {
                this.searchInternational();
            }
        },

        onInput() {
            if (this.searchType !== 'domestic') {
                clearTimeout(this.debounceTimer);
                if (this.query.length < 2) {
                    this.results = [];
                    return;
                }
                this.debounceTimer = setTimeout(() => this.searchInternational(), 300);
            }
        },

        async searchInternational() {
            this.loading = true;
            this.error = '';
            try {
                var params = new URLSearchParams({
                    q: this.query,
                    type: 'international',
                });
                var resp = await fetch('/address-search/?' + params);
                var data = await resp.json();
                if (data.error) {
                    this.error = data.message || '검색 실패';
                    this.results = [];
                } else {
                    this.results = data.results || [];
                }
            } catch (e) {
                this.error = 'API 연결 실패. 직접 입력해주세요.';
                this.manualMode = true;
                this.results = [];
            }
            this.loading = false;
        },

        selectAddress(item) {
            var addr = item.displayName || '';
            this.selectedAddress = addr;
            var field = document.getElementById(fieldId);
            if (field) {
                field.value = addr;
                field.dispatchEvent(new Event('input', { bubbles: true }));
            }
            this.results = [];
            this.query = '';
        },

        clearAddress() {
            this.selectedAddress = '';
            var field = document.getElementById(fieldId);
            if (field) field.value = '';
        },

        toggleManual() {
            this.manualMode = !this.manualMode;
            this.results = [];
            this.query = '';
            this.error = '';
        },
    };
}
