/**
 * 전화번호 입력 Alpine.js 컴포넌트
 * 사용: x-data="phoneInput('field_id')"
 */
function phoneInput(fieldId) {
    return {
        countryCode: '+82',
        rawNumber: '',
        formattedDisplay: '',

        countries: [
            { code: '+82', label: 'KR +82', format: 'KR' },
            { code: '+1', label: 'US +1', format: 'US' },
            { code: '+81', label: 'JP +81', format: 'JP' },
            { code: '+86', label: 'CN +86', format: 'CN' },
            { code: '+44', label: 'UK +44', format: 'GB' },
            { code: '+49', label: 'DE +49', format: 'DE' },
            { code: '+33', label: 'FR +33', format: 'FR' },
            { code: '+61', label: 'AU +61', format: 'AU' },
            { code: '+65', label: 'SG +65', format: 'SG' },
            { code: '+852', label: 'HK +852', format: 'HK' },
            { code: '+886', label: 'TW +886', format: 'TW' },
            { code: '+84', label: 'VN +84', format: 'VN' },
        ],

        init() {
            var field = document.getElementById(fieldId);
            if (field && field.value) {
                this._parseExisting(field.value);
            }
        },

        _parseExisting(value) {
            if (!value) return;
            value = value.trim();

            // +XX-번호 또는 +XX 번호 패턴 파싱
            var match = value.match(/^(\+\d{1,4})[-\s]?(.+)$/);
            if (match) {
                var foundCountry = this.countries.find(function(c) { return c.code === match[1]; });
                if (foundCountry) this.countryCode = match[1];
                this.rawNumber = match[2].replace(/[^\d]/g, '');
                // +82 저장 형식에서 leading 0 복원 (DB: +82-10-... → rawNumber: 010...)
                if (this.countryCode === '+82' && this.rawNumber && !this.rawNumber.startsWith('0')) {
                    this.rawNumber = '0' + this.rawNumber;
                }
            } else {
                this.rawNumber = value.replace(/[^\d]/g, '');
            }
            this._format();
        },

        onInput(event) {
            var digits = event.target.value.replace(/[^\d]/g, '');
            this.rawNumber = digits;
            this._format();
            var self = this;
            this.$nextTick(function() {
                event.target.value = self.formattedDisplay;
            });
        },

        onPaste(event) {
            event.preventDefault();
            var pasted = (event.clipboardData || window.clipboardData).getData('text');
            // 붙여넣기된 값에서 국가코드 감지
            var match = pasted.match(/^(\+\d{1,4})[-\s]?(.+)$/);
            if (match) {
                var foundCountry = this.countries.find(function(c) { return c.code === match[1]; });
                if (foundCountry) this.countryCode = match[1];
                this.rawNumber = match[2].replace(/[^\d]/g, '');
            } else {
                this.rawNumber = pasted.replace(/[^\d]/g, '');
            }
            this._format();
            var self = this;
            this.$nextTick(function() {
                event.target.value = self.formattedDisplay;
            });
        },

        _format() {
            var d = this.rawNumber;
            var country = this.countries.find(function(c) { return c.code === this.countryCode; }.bind(this));
            var fmt = country ? country.format : 'DEFAULT';

            if (fmt === 'KR') {
                this.formattedDisplay = this._formatKR(d);
            } else if (fmt === 'US') {
                this.formattedDisplay = this._formatUS(d);
            } else if (fmt === 'JP') {
                this.formattedDisplay = this._formatJP(d);
            } else {
                this.formattedDisplay = this._formatDefault(d);
            }

            this._updateField();
        },

        _formatKR(d) {
            // 서울 지역번호 (02)
            if (d.startsWith('02')) {
                if (d.length <= 2) return d;
                if (d.length <= 5) return d.slice(0, 2) + '-' + d.slice(2);
                if (d.length <= 9) return d.slice(0, 2) + '-' + d.slice(2, 5) + '-' + d.slice(5);
                return d.slice(0, 2) + '-' + d.slice(2, 6) + '-' + d.slice(6, 10);
            }
            // 휴대폰/일반 (010, 031 등)
            if (d.length <= 3) return d;
            if (d.length <= 7) return d.slice(0, 3) + '-' + d.slice(3);
            return d.slice(0, 3) + '-' + d.slice(3, 7) + '-' + d.slice(7, 11);
        },

        _formatUS(d) {
            // (123) 456-7890
            if (d.length <= 3) return d;
            if (d.length <= 6) return '(' + d.slice(0, 3) + ') ' + d.slice(3);
            return '(' + d.slice(0, 3) + ') ' + d.slice(3, 6) + '-' + d.slice(6, 10);
        },

        _formatJP(d) {
            // 일본: 090-1234-5678 또는 03-1234-5678
            if (d.startsWith('0')) {
                if (d.length <= 3) return d;
                if (d.length <= 7) return d.slice(0, 3) + '-' + d.slice(3);
                return d.slice(0, 3) + '-' + d.slice(3, 7) + '-' + d.slice(7, 11);
            }
            return this._formatDefault(d);
        },

        _formatDefault(d) {
            // 4자리씩 하이픈
            if (!d) return '';
            var parts = [];
            for (var i = 0; i < d.length; i += 4) {
                parts.push(d.slice(i, i + 4));
            }
            return parts.join('-');
        },

        _updateField() {
            var field = document.getElementById(fieldId);
            if (!field) return;

            // 저장 형식: +82-10-1234-5678 (국가코드 + 지역번호 leading 0 제거)
            var number = this.rawNumber;
            if (number && number.startsWith('0')) {
                number = number.substring(1);
            }
            var formatted = number ? number.replace(/(\d{1,4})/g, '$1-').replace(/-$/, '') : '';
            // 한국 포맷 유지 (하이픈 위치 보정)
            if (this.countryCode === '+82' && number) {
                if (this.rawNumber.startsWith('02')) {
                    // 서울: 02 → 2, 2-XXXX-XXXX
                    var d = number; // '2...'
                    if (d.length <= 1) formatted = d;
                    else if (d.length <= 4) formatted = d.slice(0, 1) + '-' + d.slice(1);
                    else if (d.length <= 8) formatted = d.slice(0, 1) + '-' + d.slice(1, 5) + '-' + d.slice(5);
                    else formatted = d.slice(0, 1) + '-' + d.slice(1, 5) + '-' + d.slice(5, 9);
                } else {
                    // 휴대폰/지역: 010→10, 10-XXXX-XXXX
                    var d = number;
                    if (d.length <= 2) formatted = d;
                    else if (d.length <= 6) formatted = d.slice(0, 2) + '-' + d.slice(2);
                    else formatted = d.slice(0, 2) + '-' + d.slice(2, 6) + '-' + d.slice(6, 10);
                }
            }
            var val = this.rawNumber ? this.countryCode + '-' + formatted : '';
            field.value = val;
            field.dispatchEvent(new Event('input', { bubbles: true }));
        },

        onCountryChange() {
            this._format();
        },
    };
}
