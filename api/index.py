# api/index.py - Vercel 배포용 완전 수정 코드

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from requests.exceptions import RequestException
import time
import os
import requests
from datetime import datetime, timedelta
from functools import wraps
import logging
import sys

# 로깅 설정 - Vercel용 최적화
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# ============================================
# Vercel용 Flask 앱 초기화
# ============================================

app = Flask(__name__, static_folder='..', static_url_path='')

# CORS 설정 - 모든 도메인 허용
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# ============================================
# 환경 변수 및 설정
# ============================================

# Vercel 환경 감지 (여러 방법으로 확인)
IS_VERCEL = (
    os.environ.get('VERCEL_ENV') is not None or 
    os.environ.get('VERCEL') == '1' or
    os.environ.get('NOW_REGION') is not None or
    'vercel' in os.environ.get('DEPLOYMENT_URL', '').lower()
)

# 환경 로깅
if IS_VERCEL:
    logger.info("🚀 Vercel 프로덕션 환경에서 실행 중")
else:
    logger.info("🛠️ 로컬 개발 환경에서 실행 중")

# FMP API 설정
FMP_BASE_URL = "https://financialmodelingprep.com/api/v3"
FMP_STABLE_URL = "https://financialmodelingprep.com/stable"
FMP_API_KEY = os.environ.get('FMP_API_KEY', 'demo')

# API 키 상태 로깅
if FMP_API_KEY == 'demo':
    logger.warning("⚠️ FMP_API_KEY가 설정되지 않음 - 데모 키 사용")
else:
    logger.info("✅ FMP_API_KEY 정상 설정됨")

# 메모리 저장소
strategies = {}
cache = {}
CACHE_DURATION = 300  # 5분

# API 설정
API_TIMEOUT = 10
MAX_RETRIES = 3
RETRY_DELAY = 1
RATE_LIMIT = 0.5

# 마지막 API 요청 시간 추적
last_api_request = 0

# ============================================
# 정적 파일 서빙 - Vercel 최적화
# ============================================

@app.route('/')
def serve_index():
    """메인 페이지 서빙"""
    try:
        return send_from_directory('..', 'index.html')
    except FileNotFoundError:
        logger.error("❌ index.html 파일을 찾을 수 없음")
        return '''
        <!DOCTYPE html>
        <html lang="ko">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>투자 전략 도구</title>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; 
                       max-width: 800px; margin: 50px auto; padding: 20px; 
                       background: #f8fafc; }
                .container { background: white; padding: 40px; border-radius: 12px; 
                            box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; }
                h1 { color: #1a2332; margin-bottom: 20px; }
                .status { background: #10b981; color: white; padding: 12px 24px; 
                         border-radius: 8px; margin: 20px 0; }
                a { color: #4a90e2; text-decoration: none; font-weight: 600; }
                a:hover { text-decoration: underline; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 스마트 투자 전략 도구</h1>
                <div class="status">서버가 정상적으로 실행 중입니다!</div>
                <p>API 상태를 확인하려면 아래 링크를 클릭하세요.</p>
                <p><a href="/api/status">📊 API 상태 확인</a></p>
                <hr style="margin: 30px 0; border: none; border-top: 1px solid #e2e8f0;">
                <p><small>환경: ''' + ('Vercel 프로덕션' if IS_VERCEL else '로컬 개발') + '''</small></p>
            </div>
        </body>
        </html>
        ''', 200
    except Exception as e:
        logger.error(f"❌ 정적 파일 서빙 오류: {e}")
        return f'''
        <html><body style="font-family: sans-serif; text-align: center; padding: 50px;">
            <h1>🚀 스마트 투자 전략 도구</h1>
            <p>파일 로딩 중 오류가 발생했습니다: {str(e)}</p>
            <p><a href="/api/status">API 테스트</a></p>
        </body></html>
        ''', 500

@app.route('/<path:filename>')
def serve_static(filename):
    """정적 파일 서빙"""
    try:
        return send_from_directory('..', filename)
    except Exception as e:
        logger.error(f"❌ 정적 파일 서빙 실패: {filename} - {e}")
        return f"파일을 찾을 수 없습니다: {filename}", 404

# ============================================
# 에러 핸들러
# ============================================

@app.errorhandler(404)
def not_found_error(error):
    logger.warning(f"404 에러: {request.url}")
    return jsonify({
        'error': 'Not Found',
        'message': '요청하신 리소스를 찾을 수 없습니다.',
        'status': 404
    }), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 에러: {error}")
    return jsonify({
        'error': 'Internal Server Error',
        'message': '서버 내부 오류가 발생했습니다.',
        'status': 500
    }), 500

# ============================================
# FMP API 헬퍼 함수들
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
    """FMP API 요청 공통 함수"""
    rate_limit()
    
    if params is None:
        params = {}
    
    params['apikey'] = FMP_API_KEY
    url = f"{FMP_BASE_URL}/{endpoint}"
    
    retries = 0
    while retries < MAX_RETRIES:
        try:
            response = requests.get(url, params=params, timeout=API_TIMEOUT)
            response.raise_for_status()
            
            data = response.json()
            
            # FMP API 에러 체크
            if isinstance(data, dict) and 'Error Message' in data:
                raise Exception(data['Error Message'])
            
            return data
            
        except requests.exceptions.RequestException as e:
            retries += 1
            if retries == MAX_RETRIES:
                raise Exception(f"FMP API request failed: {str(e)}")
            logger.warning(f"⚠️ FMP API 재시도 {retries}/{MAX_RETRIES}: {str(e)}")
            time.sleep(RETRY_DELAY * retries)

def get_fmp_stock_quote(symbol):
    """FMP Stable API로 실시간 주식 시세 조회"""
    try:
        # 실시간 가격 데이터 (Stable API 사용)
        rate_limit()
        params = {'symbol': symbol, 'apikey': FMP_API_KEY}
        url = f"{FMP_STABLE_URL}/quote-short"
        
        response = requests.get(url, params=params, timeout=API_TIMEOUT)
        response.raise_for_status()
        quote_data = response.json()
        
        if not quote_data or len(quote_data) == 0:
            raise Exception(f"No quote data found for {symbol}")
        
        quote = quote_data[0]
        
        # 회사 프로필 정보 (v3 API 사용 - 선택적)
        try:
            profile_data = make_fmp_request(f"profile/{symbol}")
            profile = profile_data[0] if profile_data and len(profile_data) > 0 else {}
        except:
            profile = {}
        
        # 현재 가격과 변동률 계산
        current_price = float(quote['price'])
        previous_close = float(quote.get('previousClose', current_price))
        change = current_price - previous_close
        change_percent = (change / previous_close * 100) if previous_close != 0 else 0
        
        return {
            'symbol': symbol,
            'name': profile.get('companyName') or quote.get('name', symbol),
            'price': current_price,
            'change': round(change, 2),
            'changePercent': round(change_percent, 2),
            'currency': profile.get('currency', 'USD'),
            'exchange': profile.get('exchangeShortName', 'US Market'),
            'timestamp': datetime.now().isoformat(),
            
            # Stable API에서 제공하는 상세 정보
            'open': float(quote.get('open', 0)),
            'dayHigh': float(quote.get('dayHigh', 0)),
            'dayLow': float(quote.get('dayLow', 0)),
            'previousClose': previous_close,
            'volume': int(quote.get('volume', 0)),
            
            # 추가 메트릭 (profile에서)
            'marketCap': profile.get('mktCap'),
            'pe': profile.get('pe'),
            'eps': profile.get('eps'),
            'yearHigh': float(profile.get('range', '0-0').split('-')[1]) if profile.get('range') else None,
            'yearLow': float(profile.get('range', '0-0').split('-')[0]) if profile.get('range') else None,
            'beta': profile.get('beta'),
            'avgVolume': profile.get('volAvg'),
            
            # 회사 정보
            'sector': profile.get('sector'),
            'industry': profile.get('industry'),
            'website': profile.get('website'),
            'description': profile.get('description', '')[:200] + '...' if profile.get('description') else None,
            
            # 데이터 소스 표시
            'source': 'fmp_stable_realtime'
        }
        
    except Exception as e:
        raise Exception(f"FMP stable quote error: {str(e)}")

def search_fmp_stocks(query):
    """FMP API로 주식 검색"""
    try:
        # FMP 검색 API
        search_data = make_fmp_request("search", {"query": query, "limit": 20})
        
        if not search_data:
            return []
        
        results = []
        seen_symbols = set()  # 중복 제거용
        
        for item in search_data:
            symbol = item['symbol']
            
            # 중복 제거
            if symbol in seen_symbols:
                continue
            seen_symbols.add(symbol)
            
            # 거래소 필터링 (주요 거래소만)
            exchange = item.get('exchangeShortName', '')
            if exchange not in ['NYSE', 'NASDAQ', 'AMEX', 'TSX', 'LSE', 'EURONEXT']:
                continue
            
            # 국가 매핑
            country_map = {
                'NYSE': '🇺🇸 미국', 'NASDAQ': '🇺🇸 미국', 'AMEX': '🇺🇸 미국',
                'TSX': '🇨🇦 캐나다', 'LSE': '🇬🇧 영국', 'EURONEXT': '🇪🇺 유럽'
            }
            
            results.append({
                'symbol': symbol,
                'name': item['name'],
                'exchange': exchange,
                'currency': item.get('currency', 'USD'),
                'displayText': f"{item['name']} ({symbol})",
                'country': country_map.get(exchange, '🌍 해외'),
                'type': 'stock'
            })
        
        return results
        
    except Exception as e:
        logger.error(f"FMP search error: {str(e)}")
        return []

def get_fmp_historical_data(symbol, period='1d'):
    """FMP API로 역사적 데이터 조회"""
    try:
        # 기간별 엔드포인트 선택
        if period == '1d':
            # 인트라데이 데이터 (5분 간격)
            endpoint = f"historical-chart/5min/{symbol}"
            params = {}
            url = f"{FMP_BASE_URL}/{endpoint}"
        elif period in ['1mo', '3mo', '1y', '5y', 'max']:
            # End-of-Day 역사적 데이터
            endpoint = f"historical-price-eod/full"
            params = {'symbol': symbol}
            url = f"{FMP_STABLE_URL}/{endpoint}"
            
            if period == '1mo':
                from_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
                params['from'] = from_date
            elif period == '3mo':
                from_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
                params['from'] = from_date
            elif period == '1y':
                from_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
                params['from'] = from_date
        else:
            # 기본값: v3 API 사용
            endpoint = f"historical-price-full/{symbol}"
            params = {}
            url = f"{FMP_BASE_URL}/{endpoint}"
        
        # API 요청
        rate_limit()
        params['apikey'] = FMP_API_KEY
        
        response = requests.get(url, params=params, timeout=API_TIMEOUT)
        response.raise_for_status()
        data = response.json()
        
        # 응답 형식 처리
        if period == '1d':
            return data if isinstance(data, list) else []
        elif period in ['1mo', '3mo', '1y', '5y', 'max']:
            if isinstance(data, dict) and 'eod' in data:
                return data['eod']
            elif isinstance(data, list):
                return data
            else:
                return []
        else:
            return data.get('historical', []) if isinstance(data, dict) else []
            
    except Exception as e:
        logger.error(f"FMP historical data error: {str(e)}")
        return []

# ============================================
# API 상태 확인
# ============================================

@app.route('/api/status')
def api_status():
    """API 상태 확인 엔드포인트"""
    try:
        logger.info("API 상태 확인 요청 수신")
        
        # Vercel 환경 정보 수집
        vercel_info = {}
        if IS_VERCEL:
            vercel_info = {
                'region': os.environ.get('VERCEL_REGION', 'unknown'),
                'env': os.environ.get('VERCEL_ENV', 'unknown'),
                'url': os.environ.get('VERCEL_URL', 'unknown'),
                'git_commit': os.environ.get('VERCEL_GIT_COMMIT_SHA', 'unknown')[:8] if os.environ.get('VERCEL_GIT_COMMIT_SHA') else 'unknown'
            }
        
        status = {
            'status': 'ok',
            'timestamp': datetime.utcnow().isoformat(),
            'environment': 'vercel-production' if IS_VERCEL else 'development',
            'fmp_key_status': '✅ 설정됨' if FMP_API_KEY != 'demo' else '❌ 데모 키 사용',
            'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            'cache_size': len(cache),
            'strategies_count': len(strategies)
        }
        
        if IS_VERCEL:
            status['vercel_info'] = vercel_info
        
        warnings = []
        if FMP_API_KEY == 'demo':
            warnings.append('FMP API 키가 설정되지 않았습니다.')
        
        if warnings:
            status['warnings'] = warnings

        logger.info("API 상태 확인 완료")
        return jsonify(status)

    except Exception as e:
        logger.error(f"API 상태 확인 중 오류: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

# ============================================
# 주식 검색 API
# ============================================

@app.route('/api/search/<query>')
def search_stocks(query):
    """주식 검색 API"""
    try:
        logger.info(f"🔍 주식 검색 시작: '{query}'")
        
        results = []
        query_lower = query.lower().strip()
        
        if len(query_lower) < 1:
            return jsonify({'query': query, 'results': [], 'count': 0})
        
        # 캐시 확인
        cache_key = f"search_{query_lower}"
        current_time = datetime.now().timestamp()
        
        if cache_key in cache and (current_time - cache[cache_key]['time']) < CACHE_DURATION:
            logger.info(f"💾 캐시에서 검색 결과 반환: {query}")
            cached_results = cache[cache_key]['data']
            return jsonify({
                'query': query,
                'results': cached_results[:10],
                'count': len(cached_results),
                'source': 'cache'
            })
        
        # FMP API 검색
        try:
            logger.info(f"🔍 FMP API 검색 시도: {query}")
            
            fmp_results = search_fmp_stocks(query)
            if fmp_results:
                results.extend(fmp_results)
                
                # 성공한 결과 캐시에 저장
                cache[cache_key] = {
                    'data': fmp_results,
                    'time': current_time
                }
                
                logger.info(f"✅ FMP 검색 성공: {len(fmp_results)}개 결과")
            else:
                logger.warning(f"⚠️ FMP 검색 결과 없음: {query}")
            
        except Exception as e:
            logger.error(f"❌ FMP 검색 실패: {e}")
            return jsonify({
                'query': query,
                'results': [],
                'count': 0,
                'error': f'검색 중 오류가 발생했습니다: {str(e)}'
            }), 500
        
        # 결과 정렬
        def sort_key(item):
            symbol_exact = item['symbol'].lower() == query_lower
            name_starts = item['name'].lower().startswith(query_lower)
            symbol_starts = item['symbol'].lower().startswith(query_lower)
            is_major_exchange = item.get('exchange') in ['NYSE', 'NASDAQ', 'AMEX']
            return (not symbol_exact, not symbol_starts, not name_starts, not is_major_exchange, item['symbol'])
        
        results.sort(key=sort_key)
        
        logger.info(f"✅ 검색 결과: {len(results)}개")
        return jsonify({
            'query': query,
            'results': results[:10],
            'count': len(results),
            'source': 'fmp_api'
        })
        
    except Exception as e:
        logger.error(f"❌ 검색 오류: {e}")
        return jsonify({
            'query': query,
            'results': [],
            'count': 0,
            'error': f'검색 중 오류가 발생했습니다: {str(e)}'
        }), 500

# ============================================
# 주식 정보 API
# ============================================

@app.route('/api/stock/<symbol>')
def get_stock_data(symbol):
    """주식 데이터 API"""
    try:
        cache_key = f"stock_{symbol}"
        current_time = datetime.now().timestamp()
        
        # 캐시 확인
        if cache_key in cache and (current_time - cache[cache_key]['time']) < CACHE_DURATION:
            logger.info(f"💾 캐시에서 주식 데이터 반환: {symbol}")
            return jsonify(cache[cache_key]['data'])
        
        logger.info(f"📊 FMP API로 주식 데이터 조회: {symbol}")
        
        # FMP API로 주식 정보 가져오기
        stock_data = get_fmp_stock_quote(symbol)
        
        # 캐시에 저장
        cache[cache_key] = {
            'data': stock_data,
            'time': current_time
        }
        
        logger.info(f"✅ 주식 데이터 조회 성공: {stock_data['name']} - ${stock_data['price']}")
        return jsonify(stock_data)
        
    except Exception as e:
        logger.error(f"❌ 주식 데이터 조회 오류 ({symbol}): {str(e)}")
        return jsonify({
            'error': '주식 정보를 가져올 수 없습니다.',
            'details': str(e)
        }), 500

# ============================================
# 주식 역사적 데이터 API
# ============================================

@app.route('/api/stock/<symbol>/history')
def get_stock_history_data(symbol):
    """주식 장기 역사적 데이터 API"""
    try:
        period = request.args.get('period', '1y')
        
        cache_key = f"history_{symbol}_{period}"
        current_time = datetime.now().timestamp()
        
        # 캐시 확인 (역사적 데이터는 더 긴 캐시)
        cache_duration = 3600  # 1시간
        if cache_key in cache and (current_time - cache[cache_key]['time']) < cache_duration:
            logger.info(f"💾 캐시에서 역사적 데이터 반환: {symbol} ({period})")
            return jsonify(cache[cache_key]['data'])
        
        logger.info(f"📊 FMP API로 역사적 데이터 조회: {symbol} ({period})")
        
        # FMP API로 EOD 데이터 가져오기
        historical_data = get_fmp_historical_data(symbol, period)
        
        # 데이터 가공
        processed_data = []
        for item in historical_data:
            if isinstance(item, dict):
                processed_data.append({
                    'date': item.get('date'),
                    'open': float(item.get('open', 0)),
                    'high': float(item.get('high', 0)),
                    'low': float(item.get('low', 0)),
                    'close': float(item.get('close', 0)),
                    'volume': int(item.get('volume', 0)),
                    'adjClose': float(item.get('adj_close', item.get('close', 0)))
                })
        
        # 날짜순 정렬
        processed_data.sort(key=lambda x: x['date'], reverse=True)
        
        history_data = {
            'symbol': symbol,
            'period': period,
            'data': processed_data,
            'count': len(processed_data),
            'timestamp': datetime.now().isoformat(),
            'source': 'fmp_stable_eod'
        }
        
        # 캐시에 저장
        cache[cache_key] = {
            'data': history_data,
            'time': current_time
        }
        
        logger.info(f"✅ 역사적 데이터 조회 성공: {len(processed_data)}개 데이터")
        return jsonify(history_data)
        
    except Exception as e:
        logger.error(f"❌ 역사적 데이터 조회 오류 ({symbol}): {str(e)}")
        return jsonify({
            'error': '역사적 데이터를 가져올 수 없습니다.',
            'details': str(e)
        }), 500

@app.route('/api/stock/<symbol>/chart')
def get_stock_chart_data(symbol):
    """주식 차트 데이터 API"""
    try:
        period = request.args.get('period', '1d')
        
        cache_key = f"chart_{symbol}_{period}"
        current_time = datetime.now().timestamp()
        
        # 캐시 확인
        cache_duration = 60 if period == '1d' else 300
        if cache_key in cache and (current_time - cache[cache_key]['time']) < cache_duration:
            logger.info(f"💾 캐시에서 차트 데이터 반환: {symbol} ({period})")
            return jsonify(cache[cache_key]['data'])
        
        logger.info(f"📈 FMP API로 차트 데이터 조회: {symbol} ({period})")
        
        # FMP API로 역사적 데이터 가져오기
        historical_data = get_fmp_historical_data(symbol, period)
        
        chart_data = {
            'symbol': symbol,
            'period': period,
            'data': historical_data,
            'timestamp': datetime.now().isoformat()
        }
        
        # 캐시에 저장
        cache[cache_key] = {
            'data': chart_data,
            'time': current_time
        }
        
        logger.info(f"✅ 차트 데이터 조회 성공: {len(historical_data)}개 데이터")
        return jsonify(chart_data)
        
    except Exception as e:
        logger.error(f"❌ 차트 데이터 조회 오류 ({symbol}): {str(e)}")
        return jsonify({
            'error': '차트 데이터를 가져올 수 없습니다.',
            'details': str(e)
        }), 500

# ============================================
# 환율 정보 API
# ============================================

@app.route('/api/exchange-rate')
def get_exchange_rate():
    """환율 정보 API"""
    try:
        cache_key = 'exchange_rate'
        current_time = datetime.now().timestamp()
        
        # 캐시 확인
        if cache_key in cache and (current_time - cache[cache_key]['time']) < CACHE_DURATION:
            logger.info("💾 캐시에서 환율 정보 반환")
            return jsonify(cache[cache_key]['data'])
        
        # 기본 환율
        default_rate = 1300.0
        
        try:
            # 환율 API 호출
            response = requests.get(
                'https://api.exchangerate-api.com/v4/latest/USD',
                timeout=5
            )
            response.raise_for_status()
            data = response.json()
            
            if 'rates' in data and 'KRW' in data['rates']:
                rate = data['rates']['KRW']
            else:
                raise ValueError("환율 데이터 형식 오류")
                
        except Exception as e:
            logger.warning(f"⚠️ 환율 API 호출 실패 (기본값 사용): {e}")
            rate = default_rate
        
        # 결과 데이터
        result = {
            'rate': rate,
            'timestamp': datetime.now().isoformat(),
            'source': 'API' if rate != default_rate else 'Default'
        }
        
        # 캐시에 저장
        cache[cache_key] = {
            'data': result,
            'time': current_time
        }
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"❌ 환율 정보 조회 오류: {e}")
        return jsonify({
            'rate': 1300.0,
            'timestamp': datetime.now().isoformat(),
            'source': 'Error Fallback',
            'error': str(e)
        })

# ============================================
# 투자 전략 관리 API
# ============================================

@app.route('/api/strategy', methods=['GET', 'POST', 'PUT', 'DELETE'])
def manage_strategy():
    """투자 전략 관리 API"""
    try:
        if request.method == 'GET':
            # 전략 목록 조회
            return jsonify({
                'strategies': [
                    {
                        'id': key,
                        'name': value.get('name', 'Unnamed Strategy'),
                        'lastModified': value.get('timestamp', ''),
                        'stockSymbol': value.get('stockSymbol', '')
                    }
                    for key, value in strategies.items()
                ]
            })
            
        elif request.method == 'POST':
            # 새 전략 저장
            data = request.get_json()
            
            # 필수 필드 검증
            required_fields = ['name', 'basePrice', 'investmentAmount', 'dropRate']
            for field in required_fields:
                if field not in data:
                    return jsonify({
                        'error': f'필수 필드 누락: {field}'
                    }), 400
            
            # 데이터 유효성 검증
            try:
                base_price = float(data['basePrice'])
                investment_amount = float(data['investmentAmount'])
                drop_rate = float(data['dropRate'])
                
                if base_price <= 0 or investment_amount <= 0 or drop_rate <= 0:
                    raise ValueError("가격과 금액은 0보다 커야 합니다")
                    
            except ValueError as e:
                return jsonify({
                    'error': f'데이터 유효성 검증 실패: {str(e)}'
                }), 400
            
            # 전략 ID 생성
            strategy_id = f"strategy_{int(time.time())}"
            
            # 전략 데이터 저장
            strategy_data = {
                'name': data['name'],
                'basePrice': base_price,
                'investmentAmount': investment_amount,
                'dropRate': drop_rate,
                'firstTargetProfit': float(data.get('firstTargetProfit', 10)),
                'otherTargetProfit': float(data.get('otherTargetProfit', 5)),
                'stockSymbol': data.get('stockSymbol', ''),
                'currency': data.get('currency', 'KRW'),
                'timestamp': datetime.now().isoformat()
            }
            
            strategies[strategy_id] = strategy_data
            
            logger.info(f"✅ 전략 저장 완료: {data['name']}")
            return jsonify({
                'id': strategy_id,
                'message': '전략이 저장되었습니다',
                'strategy': strategy_data
            })
            
        elif request.method == 'PUT':
            # 전략 수정
            strategy_id = request.args.get('id')
            if not strategy_id or strategy_id not in strategies:
                return jsonify({
                    'error': '존재하지 않는 전략입니다'
                }), 404
            
            data = request.get_json()
            if not data:
                return jsonify({
                    'error': '수정할 데이터가 없습니다'
                }), 400
            
            # 기존 전략 데이터 업데이트
            strategies[strategy_id].update(data)
            strategies[strategy_id]['timestamp'] = datetime.now().isoformat()
            
            logger.info(f"✅ 전략 수정 완료: {strategy_id}")
            return jsonify({
                'message': '전략이 수정되었습니다',
                'strategy': strategies[strategy_id]
            })
            
        elif request.method == 'DELETE':
            # 전략 삭제
            strategy_id = request.args.get('id')
            if not strategy_id or strategy_id not in strategies:
                return jsonify({
                    'error': '존재하지 않는 전략입니다'
                }), 404
            
            del strategies[strategy_id]
            logger.info(f"✅ 전략 삭제 완료: {strategy_id}")
            return jsonify({
                'message': '전략이 삭제되었습니다'
            })
            
    except Exception as e:
        logger.error(f"❌ 전략 관리 오류: {e}")
        return jsonify({
            'error': '전략 관리 중 오류가 발생했습니다',
            'details': str(e)
        }), 500

# ============================================
# 계산 및 분석 API
# ============================================

@app.route('/api/calculate-sell-strategy', methods=['POST'])
def calculate_sell_strategy():
    """매도 전략 계산 API"""
    try:
        data = request.get_json()
        
        base_price = float(data.get('basePrice', 0))
        drop_rate = float(data.get('dropRate', 5))
        first_target_profit = float(data.get('firstTargetProfit', 10))
        other_target_profit = float(data.get('otherTargetProfit', 3))
        num_orders = int(data.get('numOrders', 4))
        
        if base_price <= 0:
            return jsonify({'error': 'Base price must be greater than 0'}), 400
        
        sell_strategy = []
        
        for i in range(num_orders):
            order_num = i + 1
            cumulative_drop_rate = i * drop_rate
            buy_price = base_price * (1 - cumulative_drop_rate / 100)
            
            target_profit = first_target_profit if order_num == 1 else other_target_profit
            sell_price = buy_price * (1 + target_profit / 100)
            
            sell_strategy.append({
                'order': order_num,
                'buyPrice': round(buy_price, 2),
                'targetProfit': target_profit,
                'sellPrice': round(sell_price, 2),
                'dropRate': cumulative_drop_rate
            })
        
        logger.info(f"📈 매도 전략 계산 완료: {len(sell_strategy)}개 차수")
        
        return jsonify({
            'sellStrategy': sell_strategy,
            'count': len(sell_strategy),
            'summary': {
                'basePrice': base_price,
                'dropRate': drop_rate,
                'firstTargetProfit': first_target_profit,
                'otherTargetProfit': other_target_profit,
                'totalOrders': num_orders
            }
        })
        
    except Exception as e:
        logger.error(f"❌ 매도 전략 계산 오류: {e}")
        return jsonify({'error': 'Calculation failed', 'details': str(e)}), 500

# ============================================
# 헬스체크 엔드포인트
# ============================================

@app.route('/health')
@app.route('/api/health')
def health_check():
    """헬스체크 엔드포인트"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'environment': 'vercel' if IS_VERCEL else 'local'
    }), 200

# ============================================
# Vercel Handler (가장 중요!)
# ============================================

# Vercel에서 자동으로 찾는 핸들러들
if __name__ != '__main__':
    # 방법 1: WSGI 앱 노출
    app.wsgi_app = app.wsgi_app
    
    # 방법 2: application 변수로 노출
    application = app
    
    # 방법 3: handler 함수 정의 (서버리스 함수용)
    def handler(event, context):
        return app(event, lambda status, headers: None)

# ============================================
# 로컬 개발 서버 실행
# ============================================

if __name__ == '__main__':
    print("\n" + "="*50)
    print("🚀 스마트 투자 전략 도구 서버 시작")
    print("="*50)
    print(f"🌍 실행 환경: {'Vercel 프로덕션' if IS_VERCEL else '로컬 개발'}")
    print(f"🔑 FMP API 키: {'✅ 정상 설정' if FMP_API_KEY != 'demo' else '❌ 데모 키 사용'}")
    print(f"🐍 Python 버전: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    if FMP_API_KEY == 'demo':
        print("\n⚠️ 주의: FMP API 키가 설정되지 않았습니다!")
        print("환경 변수에 FMP_API_KEY를 설정해주세요.")
    
    print("\n📝 사용 가능한 엔드포인트:")
    endpoints = [
        ("GET", "/", "메인 페이지"),
        ("GET", "/api/status", "API 상태 확인"),
        ("GET", "/api/health", "헬스체크"),
        ("GET", "/api/search/<query>", "주식 검색"),
        ("GET", "/api/stock/<symbol>", "주식 정보"),
        ("GET", "/api/stock/<symbol>/history", "주식 히스토리"),
        ("GET", "/api/stock/<symbol>/chart", "차트 데이터"),
        ("GET", "/api/exchange-rate", "환율 정보"),
        ("GET/POST/PUT/DELETE", "/api/strategy", "전략 관리"),
        ("POST", "/api/calculate-sell-strategy", "매도 전략 계산")
    ]
    
    for method, path, desc in endpoints:
        print(f"   {method:<20} {path:<35} - {desc}")
    
    print("\n" + "="*50)
    print("✨ 서버 실행 완료! 브라우저에서 접속하세요.")
    print("="*50 + "\n")
    
    # 로컬에서만 Flask 개발 서버 실행
    if not IS_VERCEL:
        try:
            port = int(os.environ.get('PORT', 5000))
            app.run(
                host='0.0.0.0',
                port=port,
                debug=True,  # 로컬에서는 디버그 모드
                threaded=True  # 멀티스레딩 지원
            )
        except KeyboardInterrupt:
            print("\n👋 서버를 종료합니다...")
        except Exception as e:
            logger.error(f"❌ 서버 실행 오류: {e}")
    else:
        logger.info("🚀 Vercel 환경에서 실행 중 - 개발 서버 건너뜀")