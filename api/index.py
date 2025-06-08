# api/index.py - 원본 HTML 파일을 사용하도록 수정

from flask import Flask, jsonify, request, send_from_directory, render_template_string
from flask_cors import CORS
import time
import os
import requests
from datetime import datetime, timedelta
import logging
import sys

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# ============================================
# Flask 앱 초기화
# ============================================

app = Flask(__name__)

# CORS 설정
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# ============================================
# 환경 설정
# ============================================

IS_VERCEL = os.environ.get('VERCEL_ENV') is not None
FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"
FMP_STABLE_URL = "https://financialmodelingprep.com/stable"
FMP_API_KEY = os.environ.get('FMP_API_KEY', 'demo')

# 글로벌 저장소
strategies = {}
cache = {}
CACHE_DURATION = 300

# API 설정
API_TIMEOUT = 8
MAX_RETRIES = 2
RETRY_DELAY = 0.5
RATE_LIMIT = 0.3
last_api_request = 0

# ============================================
# 원본 HTML 파일 읽기 (Vercel 환경용)
# ============================================

def get_index_html():
    """원본 HTML 파일 내용을 반환"""
    try:
        # Vercel에서는 루트 디렉토리에서 index.html 찾기
        html_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'index.html')
        
        if os.path.exists(html_path):
            with open(html_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            # 파일이 없으면 기본 HTML 반환
            logger.warning("index.html 파일을 찾을 수 없습니다")
            return get_fallback_html()
            
    except Exception as e:
        logger.error(f"HTML 파일 읽기 오류: {e}")
        return get_fallback_html()

def get_fallback_html():
    """원본 HTML이 없을 때 사용할 대체 HTML"""
    return '''
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>스마트 투자 전략</title>
        <style>
            body { 
                font-family: -apple-system, BlinkMacSystemFont, sans-serif; 
                margin: 0; padding: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }
            .container { 
                max-width: 1200px; margin: 0 auto; 
                padding: 40px 20px; color: white; text-align: center;
            }
            .card {
                background: rgba(255,255,255,0.95); 
                padding: 40px; border-radius: 16px; 
                box-shadow: 0 8px 32px rgba(0,0,0,0.1);
                color: #1a2332; margin: 20px 0;
            }
            .btn {
                display: inline-block; margin: 10px;
                padding: 16px 32px; background: #4a90e2;
                color: white; text-decoration: none;
                border-radius: 8px; font-weight: 600;
                transition: all 0.2s ease; border: none;
                cursor: pointer; font-size: 16px;
            }
            .btn:hover { transform: translateY(-2px); background: #357abd; }
            .status { 
                background: #10b981; color: white; 
                padding: 16px; border-radius: 8px; margin: 20px 0;
            }
            input, select {
                width: 100%; padding: 12px; margin: 10px 0;
                border: 2px solid #e2e8f0; border-radius: 8px;
                font-size: 16px;
            }
            .grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; }
            @media (max-width: 768px) { .grid { grid-template-columns: 1fr; } }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📊 스마트 투자 전략</h1>
            <p>체계적인 분할매수와 수익실현으로 안정적인 투자 수익을 추구하세요</p>
            
            <div class="card">
                <h2>🔍 종목 조회</h2>
                <div style="display: flex; gap: 10px; align-items: center;">
                    <input type="text" id="stockSymbol" placeholder="주식명 또는 심볼 입력 (예: AAPL, TSLA)" style="flex: 1;">
                    <button class="btn" onclick="searchStock()">조회</button>
                </div>
                <div id="stockInfo" style="display: none; margin-top: 20px; padding: 20px; background: #1a2332; color: white; border-radius: 8px;">
                    <h3 id="stockName">-</h3>
                    <div style="font-size: 24px; font-weight: bold;">
                        $<span id="currentPrice">-</span>
                        <span id="priceChange" style="margin-left: 10px;">-</span>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h2>💰 투자 설정</h2>
                <div class="grid">
                    <div>
                        <label>기준 매수 가격</label>
                        <input type="number" id="basePrice" placeholder="100">
                    </div>
                    <div>
                        <label>차수별 투입 금액</label>
                        <input type="number" id="investmentAmount" placeholder="1000">
                    </div>
                    <div>
                        <label>차수간 하락률 (%)</label>
                        <input type="number" id="dropRate" value="5">
                    </div>
                </div>
            </div>
            
            <div class="card">
                <h2>📈 매도 전략</h2>
                <div class="grid">
                    <div>
                        <label>1차 매수 목표 수익률 (%)</label>
                        <input type="number" id="firstTargetProfit" value="10">
                    </div>
                    <div>
                        <label>2차 이후 목표 수익률 (%)</label>
                        <input type="number" id="otherTargetProfit" value="3">
                    </div>
                    <div style="display: flex; align-items: end;">
                        <button class="btn" onclick="calculateStrategy()" style="width: 100%;">전략 계산</button>
                    </div>
                </div>
            </div>
            
            <div id="results" class="card" style="display: none;">
                <h2>📊 계산 결과</h2>
                <div id="resultContent"></div>
            </div>
        </div>
        
        <script>
            const API_BASE_URL = window.location.origin;
            
            async function searchStock() {
                const symbol = document.getElementById('stockSymbol').value.trim();
                if (!symbol) return;
                
                try {
                    const response = await fetch(`${API_BASE_URL}/api/stock/${symbol}`);
                    const data = await response.json();
                    
                    if (response.ok) {
                        document.getElementById('stockName').textContent = data.name;
                        document.getElementById('currentPrice').textContent = data.price.toFixed(2);
                        document.getElementById('priceChange').textContent = 
                            `${data.change >= 0 ? '+' : ''}${data.change.toFixed(2)} (${data.changePercent.toFixed(2)}%)`;
                        document.getElementById('priceChange').style.color = data.change >= 0 ? '#10b981' : '#ef4444';
                        document.getElementById('stockInfo').style.display = 'block';
                        
                        // 현재 가격을 기준 가격에 자동 입력
                        document.getElementById('basePrice').value = data.price.toFixed(2);
                    } else {
                        alert('주식 정보를 찾을 수 없습니다: ' + data.error);
                    }
                } catch (error) {
                    alert('주식 조회 중 오류가 발생했습니다: ' + error.message);
                }
            }
            
            function calculateStrategy() {
                const basePrice = parseFloat(document.getElementById('basePrice').value) || 0;
                const investmentAmount = parseFloat(document.getElementById('investmentAmount').value) || 0;
                const dropRate = parseFloat(document.getElementById('dropRate').value) || 5;
                const firstTargetProfit = parseFloat(document.getElementById('firstTargetProfit').value) || 10;
                const otherTargetProfit = parseFloat(document.getElementById('otherTargetProfit').value) || 3;
                
                if (basePrice <= 0 || investmentAmount <= 0) {
                    alert('기준 가격과 투입 금액을 입력해주세요.');
                    return;
                }
                
                let html = '<table style="width: 100%; border-collapse: collapse;">';
                html += '<tr style="background: #f8fafc;"><th style="padding: 12px; border: 1px solid #e2e8f0;">차수</th><th style="padding: 12px; border: 1px solid #e2e8f0;">매수가</th><th style="padding: 12px; border: 1px solid #e2e8f0;">매수량</th><th style="padding: 12px; border: 1px solid #e2e8f0;">목표 수익률</th><th style="padding: 12px; border: 1px solid #e2e8f0;">목표 매도가</th></tr>';
                
                for (let i = 0; i < 4; i++) {
                    const orderNum = i + 1;
                    const cumulativeDropRate = i * dropRate;
                    const buyPrice = basePrice * (1 - cumulativeDropRate / 100);
                    const quantity = Math.floor(investmentAmount / buyPrice);
                    const targetProfit = orderNum === 1 ? firstTargetProfit : otherTargetProfit;
                    const sellPrice = buyPrice * (1 + targetProfit / 100);
                    
                    html += `<tr>
                        <td style="padding: 12px; border: 1px solid #e2e8f0; text-align: center;">${orderNum}차</td>
                        <td style="padding: 12px; border: 1px solid #e2e8f0; text-align: center;">$${buyPrice.toFixed(2)}</td>
                        <td style="padding: 12px; border: 1px solid #e2e8f0; text-align: center;">${quantity}주</td>
                        <td style="padding: 12px; border: 1px solid #e2e8f0; text-align: center;">${targetProfit}%</td>
                        <td style="padding: 12px; border: 1px solid #e2e8f0; text-align: center;">$${sellPrice.toFixed(2)}</td>
                    </tr>`;
                }
                
                html += '</table>';
                document.getElementById('resultContent').innerHTML = html;
                document.getElementById('results').style.display = 'block';
            }
            
            // Enter 키로 검색
            document.getElementById('stockSymbol').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') searchStock();
            });
        </script>
    </body>
    </html>
    '''

# ============================================
# 메인 페이지 - 원본 HTML 사용
# ============================================

@app.route('/')
def index():
    """메인 페이지 - 원본 HTML 파일 반환"""
    try:
        html_content = get_index_html()
        return html_content
    except Exception as e:
        logger.error(f"Index page error: {e}")
        return get_fallback_html()

# ============================================
# 헬퍼 함수들
# ============================================

def rate_limit():
    """API 요청 간격 조절"""
    global last_api_request
    current_time = time.time()
    elapsed = current_time - last_api_request
    
    if elapsed < RATE_LIMIT:
        time.sleep(RATE_LIMIT - elapsed)
    
    last_api_request = time.time()

def make_fmp_request(endpoint, params=None):
    """FMP API 요청"""
    try:
        rate_limit()
        
        if params is None:
            params = {}
        
        params['apikey'] = FMP_API_KEY
        url = f"{FMP_BASE_URL}/{endpoint}"
        
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.get(url, params=params, timeout=API_TIMEOUT)
                response.raise_for_status()
                data = response.json()
                
                if isinstance(data, dict) and 'Error Message' in data:
                    raise Exception(data['Error Message'])
                
                return data
                
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    raise e
                time.sleep(RETRY_DELAY)
                
    except Exception as e:
        logger.error(f"FMP API request failed: {str(e)}")
        raise e

# ============================================
# API 엔드포인트들 (기존과 동일)
# ============================================

@app.route('/api/status')
def api_status():
    """API 상태 확인"""
    try:
        status = {
            'status': 'ok',
            'timestamp': datetime.utcnow().isoformat(),
            'environment': 'vercel' if IS_VERCEL else 'local',
            'fmp_key': '설정됨' if FMP_API_KEY != 'demo' else '데모키',
            'python_version': f"{sys.version_info.major}.{sys.version_info.minor}",
            'cache_size': len(cache)
        }
        
        if IS_VERCEL:
            status['vercel_info'] = {
                'region': os.environ.get('VERCEL_REGION', 'unknown'),
                'env': os.environ.get('VERCEL_ENV', 'unknown')
            }
        
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Status check error: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

@app.route('/api/health')
def health_check():
    """헬스체크"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/api/search/<query>')
def search_stocks(query):
    """주식 검색"""
    try:
        if not query or len(query.strip()) < 1:
            return jsonify({
                'query': query,
                'results': [],
                'count': 0,
                'error': '검색어를 입력해주세요'
            }), 400
        
        # 캐시 확인
        cache_key = f"search_{query.lower()}"
        current_time = time.time()
        
        if cache_key in cache and (current_time - cache[cache_key]['time']) < CACHE_DURATION:
            return jsonify({
                'query': query,
                'results': cache[cache_key]['data'][:10],
                'count': len(cache[cache_key]['data']),
                'source': 'cache'
            })
        
        # FMP API 검색
        try:
            search_data = make_fmp_request("search", {"query": query, "limit": 10})
            
            results = []
            if search_data:
                for item in search_data[:10]:
                    results.append({
                        'symbol': item['symbol'],
                        'name': item['name'],
                        'exchange': item.get('exchangeShortName', 'Unknown'),
                        'currency': item.get('currency', 'USD'),
                        'type': 'stock'
                    })
            
            # 캐시 저장
            cache[cache_key] = {
                'data': results,
                'time': current_time
            }
            
            return jsonify({
                'query': query,
                'results': results,
                'count': len(results),
                'source': 'api'
            })
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return jsonify({
                'query': query,
                'results': [],
                'count': 0,
                'error': '검색 중 오류가 발생했습니다'
            }), 500
            
    except Exception as e:
        logger.error(f"Search endpoint error: {e}")
        return jsonify({
            'error': '서버 오류가 발생했습니다',
            'details': str(e)
        }), 500

@app.route('/api/stock/<symbol>')
def get_stock_data(symbol):
    """주식 정보 조회"""
    try:
        if not symbol:
            return jsonify({'error': '주식 심볼을 입력해주세요'}), 400
        
        # 캐시 확인
        cache_key = f"stock_{symbol.upper()}"
        current_time = time.time()
        
        if cache_key in cache and (current_time - cache[cache_key]['time']) < CACHE_DURATION:
            return jsonify(cache[cache_key]['data'])
        
        # 주식 정보 조회
        try:
            quote_data = make_fmp_request(f"quote/{symbol.upper()}")
            
            if not quote_data or len(quote_data) == 0:
                return jsonify({'error': f'주식 정보를 찾을 수 없습니다: {symbol}'}), 404
            
            quote = quote_data[0]
            
            stock_data = {
                'symbol': quote['symbol'],
                'name': quote.get('name', symbol),
                'price': float(quote['price']),
                'change': float(quote.get('change', 0)),
                'changePercent': float(quote.get('changesPercentage', 0)),
                'currency': 'USD',
                'timestamp': datetime.now().isoformat(),
                'source': 'fmp_api'
            }
            
            # 캐시 저장
            cache[cache_key] = {
                'data': stock_data,
                'time': current_time
            }
            
            return jsonify(stock_data)
            
        except Exception as e:
            logger.error(f"Stock data error: {e}")
            return jsonify({
                'error': '주식 정보를 가져올 수 없습니다',
                'details': str(e)
            }), 500
            
    except Exception as e:
        logger.error(f"Stock endpoint error: {e}")
        return jsonify({
            'error': '서버 오류가 발생했습니다',
            'details': str(e)
        }), 500

@app.route('/api/exchange-rate')
def get_exchange_rate():
    """환율 정보"""
    try:
        cache_key = 'exchange_rate'
        current_time = time.time()
        
        if cache_key in cache and (current_time - cache[cache_key]['time']) < CACHE_DURATION:
            return jsonify(cache[cache_key]['data'])
        
        default_rate = 1300.0
        
        try:
            response = requests.get(
                'https://api.exchangerate-api.com/v4/latest/USD',
                timeout=5
            )
            response.raise_for_status()
            data = response.json()
            rate = data['rates'].get('KRW', default_rate)
        except:
            rate = default_rate
        
        result = {
            'rate': rate,
            'timestamp': datetime.now().isoformat(),
            'source': 'API' if rate != default_rate else 'Default'
        }
        
        cache[cache_key] = {'data': result, 'time': current_time}
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Exchange rate error: {e}")
        return jsonify({
            'rate': 1300.0,
            'timestamp': datetime.now().isoformat(),
            'source': 'Error Fallback'
        })

@app.route('/api/strategy', methods=['GET', 'POST'])
def manage_strategy():
    """전략 관리"""
    try:
        if request.method == 'GET':
            return jsonify({
                'strategies': list(strategies.values()),
                'count': len(strategies)
            })
        
        elif request.method == 'POST':
            data = request.get_json()
            if not data:
                return jsonify({'error': '데이터가 필요합니다'}), 400
            
            strategy_id = f"strategy_{int(time.time())}"
            strategy_data = {
                'id': strategy_id,
                'name': data.get('name', '새 전략'),
                'timestamp': datetime.now().isoformat(),
                **data
            }
            
            strategies[strategy_id] = strategy_data
            
            return jsonify({
                'message': '전략이 저장되었습니다',
                'strategy': strategy_data
            })
            
    except Exception as e:
        logger.error(f"Strategy error: {e}")
        return jsonify({
            'error': '전략 관리 중 오류가 발생했습니다',
            'details': str(e)
        }), 500

# ============================================
# 에러 핸들러
# ============================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'error': 'Not Found',
        'message': '요청하신 리소스를 찾을 수 없습니다'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'error': 'Internal Server Error',
        'message': '서버 내부 오류가 발생했습니다'
    }), 500

# ============================================
# Vercel 핸들러
# ============================================

if __name__ != '__main__':
    application = app
else:
    if __name__ == '__main__':
        app.run(debug=True, port=5000)
