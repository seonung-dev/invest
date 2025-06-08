# 스마트 투자 전략 도구

## 로컬 개발 환경 설정

1. Python 3.9 이상 설치

2. 가상환경 생성 및 활성화
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

3. 의존성 설치
```bash
pip install -r requirements.txt
```

4. 서버 실행
```bash
# API 서버 실행
cd api
python index.py

# 또는
python -m flask run --port=3000
```

5. 웹 브라우저에서 접속
- http://localhost:3000

## 주요 기능

- 실시간 주식 시세 조회
- 분할매수 전략 설정
- 매도 전략 시뮬레이션
- 투자 전략 저장/불러오기
- 환율 변환 지원

## 기술 스택

- Frontend: HTML, CSS, JavaScript
- Backend: Python, Flask
- API: yfinance
- 배포: Vercel

## 주의사항

- yfinance API는 일일 요청 제한이 있을 수 있습니다
- 환율 정보는 기본값(1 USD = 1300 KRW)을 사용할 수 있습니다
- 로컬 개발 시 CORS 이슈가 없도록 설정되어 있습니다

## 🚀 빠른 시작

### 로컬 개발
```