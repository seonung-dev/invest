# api/index.py - 미국 주식만 검색하는 완전한 버전

from flask import Flask, jsonify, request
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
# 메인 페이지 - 원본 HTML
# ============================================

@app.route('/')
def index():
    """메인 페이지 - 완전한 원본 HTML"""
    return '''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>투자 전략 설정</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        :root {
            --primary-navy: #1a2332;
            --secondary-navy: #2d3748;
            --accent-blue: #4a90e2;
            --success-green: #10b981;
            --danger-red: #ef4444;
            --light-gray: #f8fafc;
            --medium-gray: #64748b;
            --dark-gray: #374151;
            --white: #ffffff;
            --border-color: #e2e8f0;
            --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
            --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: var(--light-gray);
            color: var(--primary-navy);
            line-height: 1.6;
        }

        .app-container {
            min-height: 100vh;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
        }

        .main-content {
            max-width: 1400px;
            margin: 0 auto;
            background: var(--white);
            border-radius: 16px;
            box-shadow: var(--shadow-lg);
            overflow: hidden;
        }

        /* Header */
        .app-header {
            background: var(--primary-navy);
            color: var(--white);
            padding: 32px 40px;
            position: relative;
            overflow: hidden;
        }

        .app-header::before {
            content: '';
            position: absolute;
            top: 0;
            right: 0;
            width: 200px;
            height: 200px;
            background: rgba(74, 144, 226, 0.1);
            border-radius: 50%;
            transform: translate(50%, -50%);
        }

        .header-content {
            position: relative;
            z-index: 2;
        }

        .app-title {
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 8px;
            letter-spacing: -0.5px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .header-currency-toggle {
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 14px;
        }

        .header-currency-label {
            font-weight: 500;
            font-size: 14px;
            transition: opacity 0.2s ease;
        }

        .header-currency-label.inactive {
            opacity: 0.5;
        }

        .header-toggle-switch {
            position: relative;
            width: 48px;
            height: 24px;
            background: rgba(255, 255, 255, 0.2);
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .header-toggle-switch.active {
            background: rgba(255, 255, 255, 0.3);
        }

        .header-toggle-slider {
            position: absolute;
            top: 2px;
            left: 2px;
            width: 20px;
            height: 20px;
            background: var(--white);
            border-radius: 50%;
            transition: transform 0.3s ease;
            box-shadow: var(--shadow-sm);
        }

        .header-toggle-switch.active .header-toggle-slider {
            transform: translateX(24px);
        }

        .app-subtitle {
            font-size: 16px;
            opacity: 0.8;
            margin-bottom: 24px;
        }

        .strategy-info {
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 24px;
            padding: 16px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            backdrop-filter: blur(10px);
        }

        .strategy-badge {
            background: var(--accent-blue);
            color: var(--white);
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 600;
        }

        .header-actions {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }

        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .btn-primary {
            background: var(--success-green);
            color: var(--white);
        }

        .btn-secondary {
            background: rgba(255, 255, 255, 0.15);
            color: var(--white);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }

        .btn-danger {
            background: var(--danger-red);
            color: var(--white);
        }

        .btn:hover {
            transform: translateY(-1px);
            box-shadow: var(--shadow-md);
        }

        .strategy-select {
            background: rgba(255, 255, 255, 0.15);
            border: 1px solid rgba(255, 255, 255, 0.2);
            color: var(--white);
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 14px;
        }

        /* Main Layout */
        .content-wrapper {
            padding: 40px;
        }

        .content-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 32px;
            margin-bottom: 32px;
        }

        .full-width {
            grid-column: 1 / -1;
        }

        /* Card Components */
        .card {
            background: var(--white);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            box-shadow: var(--shadow-sm);
            overflow: hidden;
            transition: box-shadow 0.2s ease;
        }

        .card:hover {
            box-shadow: var(--shadow-md);
        }

        .card-header {
            padding: 24px 24px 0;
            border-bottom: none;
        }

        .card-title {
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 20px;
            font-weight: 700;
            color: var(--primary-navy);
            margin-bottom: 8px;
        }

        .card-subtitle {
            color: var(--medium-gray);
            font-size: 14px;
            margin-bottom: 16px;
        }

        .card-content {
            padding: 24px;
        }

        /* Form Elements */
        .form-group {
            margin-bottom: 24px;
        }

        .form-label {
            display: block;
            font-weight: 600;
            font-size: 14px;
            color: var(--dark-gray);
            margin-bottom: 8px;
        }

        .form-input {
            width: 100%;
            padding: 16px;
            border: 2px solid var(--border-color);
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.2s ease;
            background: var(--white);
        }

        .form-input:focus {
            outline: none;
            border-color: var(--accent-blue);
            box-shadow: 0 0 0 3px rgba(74, 144, 226, 0.1);
        }

        .form-hint {
            color: var(--medium-gray);
            font-size: 13px;
            margin-top: 6px;
        }

        .input-group {
            display: flex;
            gap: 12px;
            align-items: stretch;
        }

        .input-group .form-input {
            flex: 1;
        }

        .input-group .btn {
            flex-shrink: 0;
            white-space: nowrap;
        }

        /* 검색 기능 스타일 */
        .search-container {
            position: relative;
        }

        .search-results {
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: var(--white);
            border: 1px solid var(--border-color);
            border-top: none;
            border-radius: 0 0 8px 8px;
            box-shadow: var(--shadow-lg);
            max-height: 400px;
            overflow-y: auto;
            z-index: 1000;
        }

        .search-result-item {
            padding: 16px;
            cursor: pointer;
            border-bottom: 1px solid var(--border-color);
            transition: all 0.2s ease;
        }

        .search-result-item:hover {
            background: rgba(74, 144, 226, 0.08);
            transform: translateX(4px);
        }

        .search-result-item:last-child {
            border-bottom: none;
        }

        .search-result-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 4px;
        }

        .search-result-symbol {
            font-weight: 700;
            color: var(--accent-blue);
            font-size: 16px;
        }

        .search-result-country {
            font-size: 14px;
            opacity: 0.8;
        }

        .search-result-name {
            color: var(--dark-gray);
            font-size: 14px;
            margin-bottom: 6px;
            font-weight: 500;
        }

        .search-result-details {
            display: flex;
            gap: 12px;
            font-size: 12px;
            color: var(--medium-gray);
        }

        .search-result-exchange {
            background: rgba(74, 144, 226, 0.1);
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: 500;
        }

        .search-result-currency {
            background: rgba(16, 185, 129, 0.1);
            color: var(--success-green);
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: 500;
        }

        /* 검색 상태 메시지 */
        .search-loading {
            padding: 16px;
            text-align: center;
            color: var(--medium-gray);
            font-style: italic;
        }

        .search-error {
            padding: 16px;
            text-align: center;
            color: var(--danger-red);
            font-weight: 500;
        }

        .search-no-results {
            padding: 16px;
            text-align: center;
            color: var(--medium-gray);
            font-style: italic;
        }

        /* Stock Info Card */
        .stock-search-section {
            background: var(--white);
        }

        .stock-info-card {
            background: linear-gradient(135deg, var(--primary-navy), var(--secondary-navy));
            color: var(--white);
            padding: 24px;
            border-radius: 12px;
            margin-top: 16px;
            display: none;
        }

        .stock-name {
            font-size: 20px;
            font-weight: 700;
            margin-bottom: 16px;
        }

        .stock-price-container {
            display: flex;
            align-items: baseline;
            gap: 12px;
            margin-bottom: 12px;
        }

        .stock-price {
            font-size: 32px;
            font-weight: 800;
        }

        .stock-currency {
            font-size: 18px;
            opacity: 0.8;
        }

        .stock-change {
            font-size: 16px;
            font-weight: 600;
        }

        .stock-change.positive {
            color: var(--success-green);
        }

        .stock-change.negative {
            color: var(--danger-red);
        }

        .stock-time {
            font-size: 12px;
            opacity: 0.7;
            margin-top: 8px;
        }

        .checkbox-container {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-top: 20px;
            padding: 16px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
        }

        .checkbox {
            width: 20px;
            height: 20px;
            cursor: pointer;
        }

        /* Investment Settings */
        .settings-grid {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 24px;
            margin-bottom: 32px;
        }

        /* Tables */
        .table-container {
            background: var(--white);
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid var(--border-color);
            margin: 24px 0;
        }

        .table {
            width: 100%;
            border-collapse: collapse;
        }

        .table th {
            background: var(--light-gray);
            color: var(--dark-gray);
            font-weight: 600;
            font-size: 14px;
            padding: 16px 12px;
            text-align: center;
            border-bottom: 1px solid var(--border-color);
        }

        .table td {
            padding: 16px 12px;
            text-align: center;
            border-bottom: 1px solid var(--border-color);
            font-size: 14px;
        }

        .table tbody tr:hover {
            background: rgba(74, 144, 226, 0.02);
        }

        .table-input {
            width: 80px;
            padding: 8px;
            border: 1px solid var(--border-color);
            border-radius: 4px;
            text-align: center;
            font-size: 14px;
        }

        .add-row-btn {
            background: var(--success-green);
            color: var(--white);
            border: none;
            padding: 12px 20px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            margin-top: 16px;
            transition: all 0.2s ease;
        }

        .add-row-btn:hover {
            transform: translateY(-1px);
            box-shadow: var(--shadow-md);
        }

        .remove-btn {
            background: var(--danger-red);
            color: var(--white);
            border: none;
            padding: 6px 10px;
            border-radius: 4px;
            font-size: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .remove-btn:hover {
            background: #dc2626;
        }

        /* Profit Settings */
        .profit-settings {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
            margin-bottom: 24px;
        }

        /* Loading Animation */
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 2px solid rgba(255, 255, 255, 0.3);
            border-top: 2px solid var(--white);
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        /* Info boxes */
        .info-box {
            background: rgba(74, 144, 226, 0.1);
            border-left: 4px solid var(--accent-blue);
            padding: 16px;
            border-radius: 8px;
            margin: 16px 0;
        }

        .info-box-text {
            color: var(--dark-gray);
            font-size: 14px;
        }

        /* Save Section */
        .save-section {
            text-align: center;
            padding: 40px;
            border-top: 1px solid var(--border-color);
            background: var(--light-gray);
        }

        .save-btn {
            background: var(--primary-navy);
            color: var(--white);
            padding: 18px 48px;
            border: none;
            border-radius: 12px;
            font-size: 18px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s ease;
            box-shadow: var(--shadow-md);
        }

        .save-btn:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }

        /* Responsive Design */
        @media (max-width: 1024px) {
            .content-grid {
                grid-template-columns: 1fr;
                gap: 24px;
            }
            
            .settings-grid {
                grid-template-columns: 1fr;
            }
            
            .profit-settings {
                grid-template-columns: 1fr;
            }
        }

        @media (max-width: 768px) {
            .app-container {
                padding: 12px;
            }
            
            .app-header {
                padding: 24px 20px;
            }
            
            .content-wrapper {
                padding: 24px 20px;
            }
            
            .header-actions {
                flex-direction: column;
            }
            
            .btn {
                justify-content: center;
            }
        }

        /* Footer Styles */
        .app-footer {
            background: var(--primary-navy);
            color: var(--white);
            margin-top: 40px;
        }

        .footer-content {
            padding: 40px;
            max-width: 1400px;
            margin: 0 auto;
        }

        .footer-info {
            text-align: center;
            margin-bottom: 40px;
        }

        .footer-info h3 {
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 12px;
            color: var(--white);
        }

        .footer-info p {
            font-size: 16px;
            opacity: 0.8;
            max-width: 600px;
            margin: 0 auto;
        }

        .footer-links {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 32px;
            margin-bottom: 32px;
        }

        .footer-section h4 {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 16px;
            color: var(--accent-blue);
        }

        .footer-section p {
            font-size: 14px;
            margin-bottom: 8px;
            opacity: 0.9;
            line-height: 1.5;
        }

        .footer-section a {
            color: var(--accent-blue);
            text-decoration: none;
            transition: color 0.2s ease;
        }

        .footer-section a:hover {
            color: var(--white);
        }

        .footer-bottom {
            text-align: center;
            padding-top: 24px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
        }

        .footer-bottom p {
            font-size: 14px;
            margin-bottom: 8px;
            opacity: 0.7;
        }

        .footer-bottom p:last-child {
            margin-bottom: 0;
        }

        /* Footer Responsive */
        @media (max-width: 768px) {
            .footer-content {
                padding: 24px 20px;
            }
            
            .footer-links {
                grid-template-columns: 1fr;
                gap: 24px;
            }
            
            .footer-section {
                text-align: center;
            }
        }
    </style>
</head>
<body>
    <div class="app-container">
        <div class="main-content">
            <!-- Header -->
            <header class="app-header">
                <div class="header-content">
                    <h1 class="app-title">
                        📊 스마트 투자 전략 (🇺🇸 미국 주식)
                        <div class="header-currency-toggle">
                            <span class="header-currency-label" id="headerKrwLabel">🇰🇷 원화</span>
                            <div class="header-toggle-switch active" id="headerCurrencyToggle" onclick="toggleCurrency()">
                                <div class="header-toggle-slider"></div>
                            </div>
                            <span class="header-currency-label active" id="headerUsdLabel">🇺🇸 달러</span>
                        </div>
                    </h1>
                    <p class="app-subtitle">체계적인 분할매수와 수익실현으로 안정적인 투자 수익을 추구하세요</p>
                    
                    <div class="strategy-info">
                        <span class="strategy-badge">현재 전략</span>
                        <span id="currentStrategyName">기본 전략</span>
                    </div>
                    
                    <div class="header-actions">
                        <button class="btn btn-primary" onclick="saveStrategy()">
                            💾 전략 저장
                        </button>
                        <button class="btn btn-secondary" onclick="saveAsStrategy()">
                            📋 다른 이름으로 저장
                        </button>
                        <select id="strategySelect" onchange="loadStrategy()" class="strategy-select">
                            <option value="">📂 전략 불러오기</option>
                        </select>
                        <button class="btn btn-danger" onclick="resetStrategy()">
                            🔄 초기화
                        </button>
                    </div>
                </div>
            </header>

            <!-- Main Content -->
            <div class="content-wrapper">
                <!-- Currency & Stock Search Section -->
                <div class="content-grid">
                    <!-- Stock Search -->
                    <div class="card stock-search-section">
                        <div class="card-header">
                            <h2 class="card-title">
                                🔍 미국 주식 검색
                            </h2>
                            <p class="card-subtitle">🇺🇸 NYSE, NASDAQ, AMEX 상장 기업만 검색됩니다</p>
                        </div>
                        <div class="card-content">
                            <div class="form-group">
                                <div class="search-container">
                                    <div class="input-group">
                                        <input type="text" id="stockSymbol" placeholder="미국 주식 검색 (예: Apple, AAPL, Tesla)" class="form-input" oninput="searchStocks()" autocomplete="off">
                                        <button class="btn btn-primary search-btn" onclick="searchStock(event)">조회</button>
                                    </div>
                                    
                                    <!-- 검색 결과 드롭다운 -->
                                    <div id="searchResults" class="search-results" style="display: none;">
                                        <!-- 검색 결과가 여기 표시됨 -->
                                    </div>
                                </div>
                                <p class="form-hint">🇺🇸 회사명이나 심볼을 입력하면 미국 주식만 자동으로 검색됩니다</p>
                            </div>
                            
                            <div id="stockInfo" class="stock-info-card">
                                <h3 id="stockName" class="stock-name">-</h3>
                                <div class="stock-price-container">
                                    <span id="currentPrice" class="stock-price">-</span>
                                    <span id="currency" class="stock-currency">USD</span>
                                </div>
                                <div id="priceChange" class="stock-change">
                                    <span id="changeAmount">-</span>
                                    <span id="changePercent">-</span>
                                </div>
                                <div id="lastUpdate" class="stock-time">-</div>
                                
                                <div class="checkbox-container">
                                    <input type="checkbox" id="useCurrentPrice" onchange="toggleCurrentPrice()" class="checkbox">
                                    <label for="useCurrentPrice">현재 가격을 기준 매수 가격으로 설정</label>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Investment Settings -->
                <div class="card full-width">
                    <div class="card-header">
                        <h2 class="card-title">
                            💰 투자 설정
                        </h2>
                        <p class="card-subtitle">기준 가격과 투자 금액, 분할매수 간격을 설정하세요</p>
                    </div>
                    <div class="card-content">
                        <div class="settings-grid">
                            <div class="form-group">
                                <label class="form-label">기준 매수 가격</label>
                                <input type="number" id="basePrice" placeholder="100" class="form-input" oninput="updateInvestmentTable()">
                                <p class="form-hint">1차 매수를 실행할 가격입니다</p>
                            </div>
                            
                            <div class="form-group">
                                <label class="form-label">차수별 투입 금액</label>
                                <input type="number" id="investmentAmount" placeholder="1000" class="form-input" oninput="updateInvestmentTable()">
                                <p class="form-hint">각 차수마다 투입할 금액입니다</p>
                            </div>
                            
                            <div class="form-group">
                                <label class="form-label">차수간 하락률 (%)</label>
                                <input type="number" id="dropRate" value="5" min="0" step="0.1" class="form-input" oninput="updateInvestmentTable()">
                                <p class="form-hint">각 차수 사이의 하락률 간격입니다</p>
                            </div>
                        </div>

                        <div class="info-box">
                            <p class="info-box-text">
                                💡 하락률 5% 설정 시: 1차(0%), 2차(5%), 3차(10%), 4차(15%) 순으로 매수가 실행됩니다
                            </p>
                        </div>

                        <!-- Investment Simulation Table -->
                        <div class="table-container">
                            <table class="table" id="investmentTable">
                                <thead>
                                    <tr>
                                        <th>차수</th>
                                        <th>누적 하락률</th>
                                        <th>매수 가격</th>
                                        <th>매수 수량</th>
                                        <th>실제 투입 금액</th>
                                        <th>관리</th>
                                    </tr>
                                </thead>
                                <tbody id="investmentTableBody">
                                    <tr>
                                        <td><strong>1차</strong></td>
                                        <td class="calculated-drop-rate">0%</td>
                                        <td class="basePrice">-</td>
                                        <td class="calculated-quantity">-</td>
                                        <td class="actual-investment">-</td>
                                        <td>-</td>
                                    </tr>
                                    <tr>
                                        <td><strong>2차</strong></td>
                                        <td class="calculated-drop-rate">5%</td>
                                        <td class="basePrice">-</td>
                                        <td class="calculated-quantity">-</td>
                                        <td class="actual-investment">-</td>
                                        <td><button class="remove-btn" onclick="removeInvestmentRow(this)">삭제</button></td>
                                    </tr>
                                    <tr>
                                        <td><strong>3차</strong></td>
                                        <td class="calculated-drop-rate">10%</td>
                                        <td class="basePrice">-</td>
                                        <td class="calculated-quantity">-</td>
                                        <td class="actual-investment">-</td>
                                        <td><button class="remove-btn" onclick="removeInvestmentRow(this)">삭제</button></td>
                                    </tr>
                                    <tr>
                                        <td><strong>4차</strong></td>
                                        <td class="calculated-drop-rate">15%</td>
                                        <td class="basePrice">-</td>
                                        <td class="calculated-quantity">-</td>
                                        <td class="actual-investment">-</td>
                                        <td><button class="remove-btn" onclick="removeInvestmentRow(this)">삭제</button></td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                        <button class="add-row-btn" onclick="addInvestmentRow()">+ 차수 추가</button>
                    </div>
                </div>

                <!-- Sell Strategy -->
                <div class="card full-width sell-strategy-section" style="margin-top: 32px;">
                    <div class="card-header">
                        <h2 class="card-title">
                            📈 매도 전략
                        </h2>
                        <p class="card-subtitle">차수별 목표 수익률을 설정하여 체계적인 수익실현을 계획하세요</p>
                    </div>
                    <div class="card-content">
                        <div class="profit-settings">
                            <div class="form-group">
                                <label class="form-label">1차 매수 목표 수익률 (%)</label>
                                <input type="number" id="firstTargetProfit" value="10" min="0" step="0.1" class="form-input" oninput="updateSellPreview()">
                                <p class="form-hint">장기 보유를 목적으로 높게 설정하는 것이 일반적입니다</p>
                            </div>
                            
                            <div class="form-group">
                                <label class="form-label">2차 이후 목표 수익률 (%)</label>
                                <input type="number" id="otherTargetProfit" value="3" min="0" step="0.1" class="form-input" oninput="updateSellPreview()">
                                <p class="form-hint">2차 매수부터의 목표 수익률입니다</p>
                            </div>
                        </div>

                        <!-- Sell Preview Table -->
                        <div class="table-container">
                            <table class="table" id="sellPreviewTable">
                                <thead>
                                    <tr>
                                        <th>차수</th>
                                        <th>매수 가격</th>
                                        <th>목표 수익률</th>
                                        <th>목표 매도 가격</th>
                                    </tr>
                                </thead>
                                <tbody id="sellPreviewTableBody">
                                    <!-- 자동 생성 -->
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Save Section -->
            <div class="save-section">
                <button class="save-btn" onclick="saveStrategy(event)">
                    💾 투자 전략 저장하기
                </button>
            </div>
        </div>
    </div>

    <!-- Footer -->
    <footer class="app-footer">
        <div class="footer-content">
            <div class="footer-info">
                <h3>📊 스마트 투자 전략 도구</h3>
                <p>체계적인 분할매수와 수익실현으로 안정적인 투자 수익을 추구하세요</p>
            </div>
            
            <div class="footer-links">
                <div class="footer-section">
                    <h4>개발자 정보</h4>
                    <p>개발자: SEONUNG</p>
                    <p>이메일: seons@kakao.com</p>
                    <p>GitHub: <a href="https://github.com/seonung-dev" target="_blank">https://github.com/seonung-dev</a></p>
                </div>
                
                <div class="footer-section">
                    <h4>기술 스택</h4>
                    <p>• Flask + Python</p>
                    <p>• FMP API</p>
                    <p>• HTML5 + CSS3 + JavaScript</p>
                </div>
                
                <div class="footer-section">
                    <h4>면책 조항</h4>
                    <p>본 도구는 교육 및 참고용입니다.</p>
                    <p>투자 손실에 대한 책임을 지지 않습니다.</p>
                </div>
            </div>
            
            <div class="footer-bottom">
                <p>&copy; 2025 SEONUNG. All rights reserved.</p>
                <p>Made with ❤️ for smart investors</p>
            </div>
        </div>
    </footer>

    <script>
        let investmentRowCount = 4;
        let currentStockPrice = 0;
        let isUSD = false;
        let exchangeRate = 1300;

        // API 기본 URL
        const API_BASE_URL = window.location.hostname === 'localhost' 
            ? 'http://localhost:3000' 
            : window.location.origin;

        // 🇺🇸 미국 주식 검색 함수 (자동완성) - 수정된 버전
        let searchTimeout;
        async function searchStocks() {
            const query = document.getElementById('stockSymbol').value.trim();
            const resultsDiv = document.getElementById('searchResults');
            
            // 입력이 없으면 검색 결과 숨기기
            if (query.length < 1) {
                resultsDiv.style.display = 'none';
                return;
            }
            
            // 이전 검색 취소
            clearTimeout(searchTimeout);
            
            // 300ms 후에 검색 실행 (타이핑 중에는 검색하지 않음)
            searchTimeout = setTimeout(async () => {
                try {
                    console.log(`🇺🇸 미국 주식 검색 시작: ${query}`);
                    
                    // 로딩 표시
                    resultsDiv.innerHTML = '<div class="search-loading">🔍 미국 주식 검색 중...</div>';
                    resultsDiv.style.display = 'block';
                    
                    const response = await fetch(`${API_BASE_URL}/api/search/${encodeURIComponent(query)}`);
                    const data = await response.json();
                    
                    console.log(`✅ 미국 주식 검색 결과: ${data.count}개`);
                    displaySearchResults(data.results, data.filter);
                } catch (error) {
                    console.error('미국 주식 검색 오류:', error);
                    resultsDiv.innerHTML = '<div class="search-error">❌ 검색 중 오류가 발생했습니다</div>';
                }
            }, 300);
        }

        // 검색 결과 표시 - 미국 주식 전용
        function displaySearchResults(results, filter) {
            const resultsDiv = document.getElementById('searchResults');
            
            if (results.length === 0) {
                resultsDiv.innerHTML = '<div class="search-no-results">📭 미국 주식 검색 결과가 없습니다<br><small>NYSE, NASDAQ, AMEX 상장 기업만 검색됩니다</small></div>';
                return;
            }
            
            let html = '';
            
            // 필터 상태 표시
            if (filter === 'US_ONLY') {
                html += '<div style="padding: 12px; background: rgba(74, 144, 226, 0.1); border-bottom: 1px solid var(--border-color); font-size: 12px; color: var(--accent-blue); font-weight: 600;">🇺🇸 미국 주식만 표시 중 (NYSE, NASDAQ, AMEX)</div>';
            }
            
            results.forEach((result, index) => {
                html += `
                    <div class="search-result-item" onclick="selectStock('${result.symbol}', '${result.name.replace(/'/g, "\\'")}')">
                        <div class="search-result-header">
                            <span class="search-result-symbol">${result.symbol}</span>
                            <span class="search-result-country">${result.country}</span>
                        </div>
                        <div class="search-result-name">${result.name}</div>
                        <div class="search-result-details">
                            <span class="search-result-exchange">${result.exchange}</span>
                            <span class="search-result-currency">${result.currency}</span>
                        </div>
                    </div>
                `;
            });
            
            resultsDiv.innerHTML = html;
            resultsDiv.style.display = 'block';
        }

        // 주식 선택
        function selectStock(symbol, name) {
            console.log(`🇺🇸 미국 주식 선택: ${symbol} - ${name}`);
            document.getElementById('stockSymbol').value = symbol;
            document.getElementById('searchResults').style.display = 'none';
            
            // 자동으로 주식 정보 조회
            searchStock();
        }

        // 검색 결과 외부 클릭시 숨기기
        document.addEventListener('click', function(event) {
            const searchContainer = document.querySelector('.search-container');
            if (!searchContainer.contains(event.target)) {
                document.getElementById('searchResults').style.display = 'none';
            }
        });

        // Enter 키로 첫 번째 결과 선택
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Enter') {
                const searchInput = document.getElementById('stockSymbol');
                if (event.target === searchInput) {
                    const firstResult = document.querySelector('.search-result-item');
                    if (firstResult) {
                        firstResult.click();
                    } else {
                        searchStock(); // 검색 결과가 없으면 직접 조회
                    }
                }
            }
        });

        // 환율 정보 가져오기
        async function fetchExchangeRate() {
            try {
                const response = await fetch(`${API_BASE_URL}/api/exchange-rate`);
                const data = await response.json();
                
                if (data.rate) {
                    exchangeRate = data.rate;
                    console.log(`환율 업데이트: 1 USD = ${exchangeRate} KRW`);
                }
            } catch (error) {
                console.error('환율 정보 가져오기 실패:', error);
            }
        }

        // Stock Search - 실제 API 연결
        async function searchStock(event) {
            const symbol = document.getElementById('stockSymbol').value.trim().toUpperCase();
            if (!symbol) {
                alert('미국 주식 심볼을 입력해주세요.');
                return;
            }

            const button = event?.target;
            if (button) {
                const originalText = button.innerHTML;
                button.innerHTML = '<div class="loading"></div>';
                button.disabled = true;
            }

            try {
                const response = await fetch(`${API_BASE_URL}/api/stock/${symbol}`);
                const stockData = await response.json();
                
                if (response.ok) {
                    displayStockInfo(stockData);
                } else {
                    throw new Error(stockData.error || '주식 정보를 가져올 수 없습니다.');
                }
            } catch (error) {
                console.error('주식 조회 오류:', error);
                alert(`주식 정보 조회에 실패했습니다: ${error.message}`);
            } finally {
                if (button) {
                    button.innerHTML = button.textContent.includes('조회') ? '조회' : '조회';
                    button.disabled = false;
                }
            }
        }

        // Currency Toggle
        function toggleCurrency() {
            isUSD = !isUSD;
            const headerToggle = document.getElementById('headerCurrencyToggle');
            const headerKrwLabel = document.getElementById('headerKrwLabel');
            const headerUsdLabel = document.getElementById('headerUsdLabel');
            
            if (isUSD) {
                headerToggle.classList.add('active');
                headerKrwLabel.classList.remove('active');
                headerKrwLabel.classList.add('inactive');
                headerUsdLabel.classList.add('active');
                headerUsdLabel.classList.remove('inactive');
            } else {
                headerToggle.classList.remove('active');
                headerKrwLabel.classList.add('active');
                headerKrwLabel.classList.remove('inactive');
                headerUsdLabel.classList.remove('active');
                headerUsdLabel.classList.add('inactive');
            }
            
            updateInvestmentTable();
            updateSellPreview();
        }

        function formatCurrency(amount) {
            if (isUSD) {
                return ' + amount.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
            } else {
                const roundedAmount = Math.ceil(amount / 10) * 10;
                return roundedAmount.toLocaleString('ko-KR') + '원';
            }
        }

        function displayStockInfo(stockData) {
            document.getElementById('stockName').textContent = stockData.name;
            
            let displayPrice = stockData.price;
            let displayCurrency = stockData.currency;
            let displayChange = stockData.change;
            
            if (isUSD && stockData.currency === 'KRW') {
                displayPrice = stockData.price / exchangeRate;
                displayCurrency = 'USD';
                displayChange = stockData.change / exchangeRate;
            } else if (!isUSD && stockData.currency === 'USD') {
                displayPrice = stockData.price * exchangeRate;
                displayCurrency = 'KRW';
                displayChange = stockData.change * exchangeRate;
            }
            
            document.getElementById('currentPrice').textContent = displayPrice.toLocaleString();
            document.getElementById('currency').textContent = displayCurrency;
            
            const changeElement = document.getElementById('priceChange');
            const changeAmount = document.getElementById('changeAmount');
            const changePercent = document.getElementById('changePercent');
            
            const isPositive = stockData.change >= 0;
            changeElement.className = `stock-change ${isPositive ? 'positive' : 'negative'}`;
            
            changeAmount.textContent = `${isPositive ? '+' : ''}${displayChange.toLocaleString()}`;
            changePercent.textContent = `(${isPositive ? '+' : ''}${stockData.changePercent.toFixed(2)}%)`;
            
            document.getElementById('lastUpdate').textContent = `최종 업데이트: ${new Date().toLocaleString('ko-KR')}`;
            document.getElementById('stockInfo').style.display = 'block';
            
            currentStockPrice = displayPrice;
            document.getElementById('useCurrentPrice').checked = false;
        }

        function toggleCurrentPrice() {
            const checkbox = document.getElementById('useCurrentPrice');
            const basePriceInput = document.getElementById('basePrice');
            
            if (checkbox.checked && currentStockPrice > 0) {
                basePriceInput.value = currentStockPrice;
                updateInvestmentTable();
                
                basePriceInput.style.background = 'rgba(16, 185, 129, 0.1)';
                basePriceInput.style.borderColor = 'var(--success-green)';
                setTimeout(() => {
                    basePriceInput.style.background = '';
                    basePriceInput.style.borderColor = '';
                }, 2000);
            } else if (checkbox.checked && currentStockPrice === 0) {
                checkbox.checked = false;
                alert('먼저 미국 주식 정보를 조회해주세요.');
            }
        }

        // Investment Table Updates
        function updateInvestmentTable() {
            const basePrice = parseFloat(document.getElementById('basePrice').value) || 0;
            const targetInvestment = parseFloat(document.getElementById('investmentAmount').value) || 0;
            const dropRateStep = parseFloat(document.getElementById('dropRate').value) || 5;
            const rows = document.querySelectorAll('#investmentTableBody tr');

            rows.forEach((row, index) => {
                const cumulativeDropRate = index * dropRateStep;
                const buyPrice = basePrice * (1 - cumulativeDropRate / 100);
                
                row.children[1].textContent = cumulativeDropRate + '%';
                row.children[2].textContent = formatCurrency(buyPrice);
                
                const quantity = targetInvestment > 0 && buyPrice > 0 ? Math.floor(targetInvestment / buyPrice) : 0;
                row.children[3].textContent = quantity.toLocaleString('ko-KR') + '주';
                
                const actualInvestment = quantity * buyPrice;
                row.children[4].textContent = formatCurrency(actualInvestment);
            });

            updateSellPreview();
        }

        function updateSellPreview() {
            const sellTableBody = document.getElementById('sellPreviewTableBody');
            const investmentRows = document.querySelectorAll('#investmentTableBody tr');
            const basePrice = parseFloat(document.getElementById('basePrice').value) || 0;
            const dropRateStep = parseFloat(document.getElementById('dropRate').value) || 5;
            const firstTargetProfit = parseFloat(document.getElementById('firstTargetProfit').value) || 0;
            const otherTargetProfit = parseFloat(document.getElementById('otherTargetProfit').value) || 0;
            
            sellTableBody.innerHTML = '';
            
            investmentRows.forEach((row, index) => {
                const tr = document.createElement('tr');
                const orderNum = index + 1;
                const cumulativeDropRate = index * dropRateStep;
                const buyPrice = basePrice * (1 - cumulativeDropRate / 100);
                
                const targetProfit = orderNum === 1 ? firstTargetProfit : otherTargetProfit;
                const sellPrice = buyPrice * (1 + targetProfit / 100);
                
                tr.innerHTML = `
                    <td><strong>${orderNum}차</strong></td>
                    <td>${formatCurrency(buyPrice)}</td>
                    <td>${targetProfit}%</td>
                    <td>${formatCurrency(sellPrice)}</td>
                `;
                sellTableBody.appendChild(tr);
            });
        }

        function addInvestmentRow() {
            investmentRowCount++;
            const tbody = document.getElementById('investmentTableBody');
            const tr = document.createElement('tr');
            const dropRateStep = parseFloat(document.getElementById('dropRate').value) || 5;
            const newDropRate = (investmentRowCount - 1) * dropRateStep;
            
            tr.innerHTML = `
                <td><strong>${investmentRowCount}차</strong></td>
                <td class="calculated-drop-rate">${newDropRate}%</td>
                <td class="basePrice">-</td>
                <td class="calculated-quantity">-</td>
                <td class="actual-investment">-</td>
                <td><button class="remove-btn" onclick="removeInvestmentRow(this)">삭제</button></td>
            `;
            tbody.appendChild(tr);
            updateInvestmentTable();
        }

        function removeInvestmentRow(button) {
            if (document.querySelectorAll('#investmentTableBody tr').length > 1) {
                button.closest('tr').remove();
                
                const rows = document.querySelectorAll('#investmentTableBody tr');
                rows.forEach((row, index) => {
                    row.children[0].innerHTML = `<strong>${index + 1}차</strong>`;
                });
                investmentRowCount = rows.length;
                updateInvestmentTable();
            } else {
                alert('최소 1개의 매수 차수는 유지되어야 합니다.');
            }
        }

        // Strategy Management
        async function saveStrategy(event) {
            const strategyData = {
                name: document.getElementById('currentStrategyName').textContent || '기본 전략',
                currency: isUSD ? 'USD' : 'KRW',
                basePrice: document.getElementById('basePrice').value,
                investmentAmount: document.getElementById('investmentAmount').value,
                dropRate: document.getElementById('dropRate').value,
                firstTargetProfit: document.getElementById('firstTargetProfit').value,
                otherTargetProfit: document.getElementById('otherTargetProfit').value,
                stockSymbol: document.getElementById('stockSymbol').value,
                investmentRows: investmentRowCount
            };
            
            const btn = event.target;
            const originalText = btn.textContent;
            
            try {
                btn.textContent = '저장 중...';
                btn.disabled = true;
                
                const response = await fetch(`${API_BASE_URL}/api/strategy`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(strategyData)
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    btn.textContent = '✅ 저장 완료!';
                    btn.style.background = 'var(--success-green)';
                    
                    setTimeout(() => {
                        btn.textContent = originalText;
                        btn.style.background = '';
                        btn.disabled = false;
                    }, 2000);
                } else {
                    throw new Error(result.error || '저장에 실패했습니다.');
                }
            } catch (error) {
                console.error('전략 저장 오류:', error);
                alert(`전략 저장에 실패했습니다: ${error.message}`);
                btn.textContent = originalText;
                btn.disabled = false;
            }
        }

        async function loadStrategies() {
            try {
                const response = await fetch(`${API_BASE_URL}/api/strategy`);
                const data = await response.json();
                
                const select = document.getElementById('strategySelect');
                
                while (select.children.length > 1) {
                    select.removeChild(select.lastChild);
                }
                
                if (data.strategies && data.strategies.length > 0) {
                    data.strategies.forEach(strategy => {
                        const option = document.createElement('option');
                        option.value = strategy.id;
                        option.textContent = strategy.name;
                        select.appendChild(option);
                    });
                }
            } catch (error) {
                console.error('전략 목록 로딩 오류:', error);
            }
        }

        function saveAsStrategy() {
            const name = prompt('새로운 전략 이름을 입력하세요:');
            if (name) {
                alert(`"${name}" 전략이 저장되었습니다! 📋`);
                document.getElementById('currentStrategyName').textContent = name;
            }
        }

        function loadStrategy() {
            const select = document.getElementById('strategySelect');
            if (select.value) {
                alert(`"${select.options[select.selectedIndex].text}" 전략을 불러왔습니다! 📂`);
                document.getElementById('currentStrategyName').textContent = select.options[select.selectedIndex].text;
            }
        }

        function resetStrategy() {
            if (confirm('모든 설정을 초기화하시겠습니까?')) {
                location.reload();
            }
        }

        // Event Listeners
        document.addEventListener('DOMContentLoaded', async function() {
            document.getElementById('stockSymbol').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    searchStock();
                }
            });
            
            document.getElementById('headerUsdLabel').classList.add('active');
            isUSD = true;
            
            // 초기 데이터 로딩
            await fetchExchangeRate();
            await loadStrategies();
            updateInvestmentTable();
            updateSellPreview();
        });
    </script>
</body>
</html>'''

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
# 🇺🇸 미국 주식 검색 함수 (핵심 수정!)
# ============================================

def search_fmp_stocks(query):
    """FMP API로 주식 검색 - 미국 주식만 필터링"""
    try:
        # FMP 검색 API - 더 많이 가져와서 필터링
        search_data = make_fmp_request("search", {"query": query, "limit": 50})
        
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
            
            # 🔥 미국 주식만 필터링 (NYSE, NASDAQ, AMEX만)
            exchange = item.get('exchangeShortName', '')
            if exchange not in ['NYSE', 'NASDAQ', 'AMEX']:
                continue  # 미국 거래소가 아니면 제외
            
            # 🔥 추가 필터링: 심볼 패턴으로 미국 주식 확인
            # 미국 주식은 보통 1-5자리 알파벳만 사용
            if not symbol.replace('.', '').isalpha() or len(symbol) > 6:
                continue
            
            # 🔥 특정 패턴 제외 (ADR이나 특수 증권 제외)
            # 점(.)이 포함된 심볼들은 대부분 특수 증권이거나 외국 회사
            if '.' in symbol:
                continue
            
            results.append({
                'symbol': symbol,
                'name': item['name'],
                'exchange': exchange,
                'currency': 'USD',  # 미국 주식은 항상 USD
                'displayText': f"{item['name']} ({symbol})",
                'country': '🇺🇸 미국',  # 미국으로 고정
                'type': 'stock'
            })
            
            # 🔥 결과 개수 제한 (성능 향상)
            if len(results) >= 20:
                break
        
        return results
        
    except Exception as e:
        logger.error(f"FMP search error: {str(e)}")
        return []

@app.route('/api/search/<query>')
def search_stocks(query):
    """주식 검색 API - 미국 주식만"""
    try:
        if not query or len(query.strip()) < 1:
            return jsonify({
                'query': query,
                'results': [],
                'count': 0,
                'error': '검색어를 입력해주세요'
            }), 400
        
        # 캐시 확인
        cache_key = f"us_search_{query.lower()}"  # 캐시 키에 us_ 추가
        current_time = time.time()
        
        if cache_key in cache and (current_time - cache[cache_key]['time']) < CACHE_DURATION:
            return jsonify({
                'query': query,
                'results': cache[cache_key]['data'][:10],
                'count': len(cache[cache_key]['data']),
                'source': 'cache',
                'filter': 'US_ONLY'  # 필터 정보 추가
            })
        
        # FMP API 검색 (미국 주식만)
        try:
            logger.info(f"🇺🇸 미국 주식 검색: {query}")
            
            fmp_results = search_fmp_stocks(query)
            
            # 🔥 추가 정렬: 미국 주요 기업 우선
            def sort_key_us(item):
                symbol_exact = item['symbol'].lower() == query.lower()
                name_starts = item['name'].lower().startswith(query.lower())
                symbol_starts = item['symbol'].lower().startswith(query.lower())
                is_nasdaq_nyse = item.get('exchange') in ['NASDAQ', 'NYSE']  # NASDAQ, NYSE 우선
                symbol_length = len(item['symbol'])  # 짧은 심볼 우선 (주요 기업일 가능성)
                
                return (
                    not symbol_exact,     # 심볼 완전 일치 우선
                    not symbol_starts,    # 심볼 시작 일치
                    not name_starts,      # 이름 시작 일치
                    not is_nasdaq_nyse,   # NASDAQ/NYSE 우선
                    symbol_length,        # 짧은 심볼 우선
                    item['symbol']        # 알파벳 순
                )
            
            fmp_results.sort(key=sort_key_us)
            
            # 캐시에 저장
            cache[cache_key] = {
                'data': fmp_results,
                'time': current_time
            }
            
            logger.info(f"✅ 미국 주식 검색 성공: {len(fmp_results)}개 결과")
            return jsonify({
                'query': query,
                'results': fmp_results[:10],  # 최대 10개
                'count': len(fmp_results),
                'source': 'fmp_api',
                'filter': 'US_ONLY'  # 필터 정보 추가
            })
            
        except Exception as e:
            logger.error(f"❌ 미국 주식 검색 실패: {e}")
            return jsonify({
                'query': query,
                'results': [],
                'count': 0,
                'error': '검색 중 오류가 발생했습니다',
                'filter': 'US_ONLY'
            }), 500
            
    except Exception as e:
        logger.error(f"❌ 검색 엔드포인트 오류: {e}")
        return jsonify({
            'error': '서버 오류가 발생했습니다',
            'details': str(e),
            'filter': 'US_ONLY'
        }), 500

# ============================================
# API 상태 확인
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
            'cache_size': len(cache),
            'filter': 'US_STOCKS_ONLY',  # 미국 주식만 검색 표시
            'supported_exchanges': ['NYSE', 'NASDAQ', 'AMEX']
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
        'timestamp': datetime.utcnow().isoformat(),
        'filter': 'US_STOCKS_ONLY'
    })

# ============================================
# 주식 정보 API
# ============================================

@app.route('/api/stock/<symbol>')
def get_stock_data(symbol):
    """주식 데이터 API"""
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
                'source': 'fmp_api',
                'filter': 'US_STOCK'
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

# ============================================
# 환율 정보 API
# ============================================

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

# ============================================
# 전략 관리 API
# ============================================

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
# 🆕 인기 미국 주식 API
# ============================================

@app.route('/api/popular-us-stocks')
def get_popular_us_stocks():
    """인기 미국 주식 목록"""
    try:
        # 인기 미국 주식 리스트
        popular_stocks = [
            {'symbol': 'AAPL', 'name': 'Apple Inc.', 'exchange': 'NASDAQ'},
            {'symbol': 'MSFT', 'name': 'Microsoft Corporation', 'exchange': 'NASDAQ'},
            {'symbol': 'GOOGL', 'name': 'Alphabet Inc.', 'exchange': 'NASDAQ'},
            {'symbol': 'AMZN', 'name': 'Amazon.com Inc.', 'exchange': 'NASDAQ'},
            {'symbol': 'TSLA', 'name': 'Tesla Inc.', 'exchange': 'NASDAQ'},
            {'symbol': 'META', 'name': 'Meta Platforms Inc.', 'exchange': 'NASDAQ'},
            {'symbol': 'NVDA', 'name': 'NVIDIA Corporation', 'exchange': 'NASDAQ'},
            {'symbol': 'NFLX', 'name': 'Netflix Inc.', 'exchange': 'NASDAQ'},
            {'symbol': 'DIS', 'name': 'The Walt Disney Company', 'exchange': 'NYSE'},
            {'symbol': 'JPM', 'name': 'JPMorgan Chase & Co.', 'exchange': 'NYSE'},
            {'symbol': 'JNJ', 'name': 'Johnson & Johnson', 'exchange': 'NYSE'},
            {'symbol': 'V', 'name': 'Visa Inc.', 'exchange': 'NYSE'},
            {'symbol': 'WMT', 'name': 'Walmart Inc.', 'exchange': 'NYSE'},
            {'symbol': 'PG', 'name': 'Procter & Gamble Company', 'exchange': 'NYSE'},
            {'symbol': 'HD', 'name': 'The Home Depot Inc.', 'exchange': 'NYSE'}
        ]
        
        # 각 주식에 추가 정보 붙이기
        formatted_stocks = []
        for stock in popular_stocks:
            formatted_stocks.append({
                'symbol': stock['symbol'],
                'name': stock['name'],
                'exchange': stock['exchange'],
                'currency': 'USD',
                'country': '🇺🇸 미국',
                'displayText': f"{stock['name']} ({stock['symbol']})",
                'type': 'stock',
                'popular': True  # 인기 주식 표시
            })
        
        return jsonify({
            'stocks': formatted_stocks,
            'count': len(formatted_stocks),
            'timestamp': datetime.now().isoformat(),
            'source': 'popular_list',
            'filter': 'US_ONLY'
        })
        
    except Exception as e:
        logger.error(f"인기 주식 목록 오류: {e}")
        return jsonify({
            'error': '인기 주식 목록을 가져올 수 없습니다',
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

if __name__ != '__main__':
    # 서버리스 함수로 실행될 때
    application = app
else:
    # 로컬에서 실행될 때
    if __name__ == '__main__':
        print("\n🇺🇸 미국 주식 전용 투자 전략 도구 시작!")
        print(f"환경: {'Vercel' if IS_VERCEL else '로컬 개발'}")
        print(f"API 키: {'✅ 설정됨' if FMP_API_KEY != 'demo' else '❌ 데모 키'}")
        print("지원 거래소: NYSE, NASDAQ, AMEX")
        print("필터: 미국 주식만 검색")
        app.run(debug=True, port=5000)
