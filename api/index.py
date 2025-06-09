# api/index.py - Vercel 서버리스 환경 최적화

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import time
import os
import requests
from datetime import datetime, timedelta
import logging
import sys

# 로깅 설정 - Vercel 최적화
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# ============================================
# Flask 앱 초기화 - Vercel 서버리스 최적화
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

# Vercel 환경 감지
IS_VERCEL = os.environ.get('VERCEL_ENV') is not None

# API 설정
FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"
FMP_STABLE_URL = "https://financialmodelingprep.com/stable"
FMP_API_KEY = os.environ.get('FMP_API_KEY', 'demo')

# 글로벌 저장소 (서버리스에서는 요청 간 공유되지 않음)
strategies = {}
cache = {}
CACHE_DURATION = 300

# API 설정
API_TIMEOUT = 8  # Vercel 타임아웃에 맞춰 단축
MAX_RETRIES = 2
RETRY_DELAY = 0.5
RATE_LIMIT = 0.3

last_api_request = 0

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
# 메인 페이지 - 간단한 HTML 반환
# ============================================

@app.route('/')
def index():
    """메인 페이지"""
    return '''
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>스마트 투자 전략 도구</title>
        <style>
            body { 
                font-family: -apple-system, BlinkMacSystemFont, sans-serif; 
                max-width: 800px; margin: 50px auto; padding: 20px; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white; text-align: center; min-height: 100vh;
            }
            .container { 
                background: rgba(255,255,255,0.95); 
                padding: 40px; border-radius: 16px; 
                box-shadow: 0 8px 32px rgba(0,0,0,0.1);
                color: #1a2332;
            }
            h1 { margin-bottom: 20px; }
            .status { 
                background: #10b981; color: white; 
                padding: 16px 24px; border-radius: 8px; 
                margin: 20px 0; font-weight: 600;
            }
            .btn {
                display: inline-block; margin: 10px;
                padding: 12px 24px; background: #4a90e2;
                color: white; text-decoration: none;
                border-radius: 8px; font-weight: 600;
                transition: all 0.2s ease;
            }
            .btn:hover { transform: translateY(-2px); background: #357abd; }
            .endpoints {
                text-align: left; background: #f8fafc;
                padding: 20px; border-radius: 8px; margin: 20px 0;
            }
            .endpoints h3 { margin-top: 0; color: #1a2332; }
            .endpoints code { 
                background: #e2e8f0; padding: 2px 6px; 
                border-radius: 4px; font-size: 14px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 스마트 투자 전략 도구</h1>
            <div class="status">✅ 서버가 정상적으로 실행 중입니다!</div>
            
            <div class="endpoints">
                <h3>📝 사용 가능한 API 엔드포인트:</h3>
                <p><code>GET /api/status</code> - API 상태 확인</p>
                <p><code>GET /api/search/AAPL</code> - 주식 검색</p>
                <p><code>GET /api/stock/AAPL</code> - 주식 정보</p>
                <p><code>GET /api/exchange-rate</code> - 환율 정보</p>
                <p><code>GET /api/health</code> - 헬스체크</p>
            </div>
            
            <a href="/api/status" class="btn">📊 API 상태 확인</a>
            <a href="/api/search/AAPL" class="btn">🔍 검색 테스트</a>
            <a href="/api/health" class="btn">❤️ 헬스체크</a>
            
            <p style="margin-top: 30px; opacity: 0.7; font-size: 14px;">
                환경: ''' + ('Vercel 프로덕션' if IS_VERCEL else '로컬 개발') + '''<br>
                API 키: ''' + ('✅ 설정됨' if FMP_API_KEY != 'demo' else '❌ 데모 키') + '''
            </p>
        </div>
    </body>
    </html>
    '''

# ============================================
# API 엔드포인트들
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
    """간단한 헬스체크"""
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
        
        # 간단한 quote 조회
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
# Vercel 핸들러 (필수!)
# ============================================

# Vercel에서 인식할 수 있도록 앱 노출
if __name__ != '__main__':
    # 서버리스 함수로 실행될 때
    application = app
else:
    # 로컬에서 실행될 때
    if __name__ == '__main__':
        app.run(debug=True, port=5000)
