#!/usr/bin/env python3
"""
Staging Validation Setup
실제 운영 환경 테스트를 위한 샘플 리뷰 항목 생성
"""

import sqlite3
import json
import uuid
from pathlib import Path
from datetime import datetime, timedelta
import random

DB_PATH = Path(__file__).parent / "data" / "approval_queue.db"

# 실제 상품 샘플 데이터 (한국 쇼핑몰 스타일)
SAMPLE_PRODUCTS = [
    {
        "source_title": "프리미엄 스테인리스 텀블러 500ml 보온보냉",
        "category": "주방용품",
        "source_price_cny": 35.00,
        "korean_price": 15900,
        "images": [
            "https://example.com/tumbler/main.jpg",
            "https://example.com/tumbler/detail1.jpg",
            "https://example.com/tumbler/detail2.jpg",
            "https://example.com/tumbler/package.jpg"
        ],
        "naver_title": "[특가] 프리미엄 스테인리스 텀블러 500ml 보온보냉 진공단열",
        "naver_desc": "고급 스테인리스 소재로 제작된 진공단열 텀블러입니다.\n\n✓ 500ml 넉넉한 용량\n✓ 보온 6시간 / 보냉 12시간\n✓ 진공단열 설계\n✓ 세척 편리한 구조",
        "naver_tags": ["텀블러", "보온보냉", "스테인리스", "500ml", "진공단열", "보냉컵"],
        "coupang_title": "프리미엄 진공단열 텀블러 500ml",
        "coupang_desc": "진공단열 설계로 장시간 온도 유지\n스테인리스 소재로 위생적\n500ml 넉넉한 용량\n휴대 간편한 디자인",
        "score": 85,
        "decision": "PASS"
    },
    {
        "source_title": "무선 블루투스 이어폰 노이즈캔슬링",
        "category": "전자제품",
        "source_price_cny": 89.00,
        "korean_price": 39900,
        "images": [
            "https://example.com/earphone/main.jpg",
            "https://example.com/earphone/case.jpg",
            "https://example.com/earphone/wear.jpg"
        ],
        "naver_title": "[신상] 무선 블루투스 이어폰 노이즈캔슬링 TWS 고음질",
        "naver_desc": "프리미엄 블루투스 5.3 무선 이어폰\n\n✓ 액티브 노이즈캔슬링 지원\n✓ 최대 24시간 재생 (케이스 포함)\n✓ IPX4 생활방수\n✓ 터치 컨트롤",
        "naver_tags": ["블루투스이어폰", "무선이어폰", "노이즈캔슬링", "TWS", "이어폰"],
        "coupang_title": "블루투스 5.3 무선 이어폰 노이즈캔슬링",
        "coupang_desc": "액티브 노이즈캔슬링 기능\n24시간 재생 (케이스 포함)\nIPX4 생활방수\n터치 컨트롤 지원",
        "score": 78,
        "decision": "PASS"
    },
    {
        "source_title": "LED 스탠드 조명 무선충전 스마트",
        "category": "가구/인테리어",
        "source_price_cny": 45.00,
        "korean_price": 24900,
        "images": [
            "https://example.com/lamp/main.jpg",
            "https://example.com/lamp/detail.jpg",
            "https://example.com/lamp/charging.jpg",
            "https://example.com/lamp/night.jpg"
        ],
        "naver_title": "LED 스탠드 조명 무선충전 3단 밝기조절 독서등",
        "naver_desc": "스마트한 LED 스탠드 조명\n\n✓ 무선충전 패드 내장 (10W)\n✓ 3단계 밝기 조절\n✓ 색온도 조절 가능\n✓ USB 포트 추가 충전",
        "naver_tags": ["LED스탠드", "무선충전", "독서등", "스탠드조명", "밝기조절"],
        "coupang_title": "LED 스탠드 무선충전 밝기조절",
        "coupang_desc": "무선충전 패드 내장 (10W)\n3단계 밝기 조절\n색온도 조절 가능\nUSB 추가 충전 포트",
        "score": 82,
        "decision": "PASS"
    },
    {
        "source_title": "프리미엄 요가매트 10mm TPE 친환경",
        "category": "스포츠/레저",
        "source_price_cny": 38.00,
        "korean_price": 19900,
        "images": [
            "https://example.com/yoga/main.jpg",
            "https://example.com/yoga/detail.jpg",
            "https://example.com/yoga/use.jpg"
        ],
        "naver_title": "[베스트] 프리미엄 요가매트 10mm TPE 친환경 논슬립",
        "naver_desc": "고밀도 TPE 친환경 요가매트\n\n✓ 10mm 두께로 쿠션감 우수\n✓ 논슬립 양면 처리\n✓ 무독성 TPE 소재\n✓ 수납 스트랩 포함",
        "naver_tags": ["요가매트", "TPE", "친환경", "논슬립", "운동매트", "홈트"],
        "coupang_title": "TPE 요가매트 10mm 논슬립",
        "coupang_desc": "10mm 두께 고밀도 TPE\n논슬립 양면 처리\n무독성 친환경 소재\n수납 스트랩 포함",
        "score": 88,
        "decision": "PASS"
    },
    {
        "source_title": "전기 그릴 가정용 무연 실내 BBQ",
        "category": "주방가전",
        "source_price_cny": 68.00,
        "korean_price": 34900,
        "images": [
            "https://example.com/grill/main.jpg",
            "https://example.com/grill/cooking.jpg",
            "https://example.com/grill/clean.jpg"
        ],
        "naver_title": "전기 그릴 가정용 무연 실내 BBQ 구이팬 1200W",
        "naver_desc": "집에서 즐기는 무연 전기 그릴\n\n✓ 1200W 강력 화력\n✓ 무연 설계로 연기 최소화\n✓ 논스틱 코팅 플레이트\n✓ 분리형 세척 편리",
        "naver_tags": ["전기그릴", "무연그릴", "실내그릴", "BBQ", "구이팬"],
        "coupang_title": "무연 전기 그릴 1200W",
        "coupang_desc": "1200W 강력 화력\n무연 설계\n논스틱 코팅 플레이트\n분리형 세척 간편",
        "score": 75,
        "decision": "HOLD"
    },
    {
        "source_title": "USB 미니 가습기 초음파 휴대용",
        "category": "생활가전",
        "source_price_cny": 22.00,
        "korean_price": 12900,
        "images": [
            "https://example.com/humidifier/main.jpg",
            "https://example.com/humidifier/use.jpg"
        ],
        "naver_title": "USB 미니 가습기 초음파 휴대용 차량용 사무실",
        "naver_desc": "컴팩트한 USB 미니 가습기\n\n✓ 초음파 방식 조용한 작동\n✓ USB 전원으로 어디서나 사용\n✓ 300ml 용량\n✓ 자동 전원 차단",
        "naver_tags": ["미니가습기", "USB가습기", "휴대용가습기", "차량용", "사무실"],
        "coupang_title": "USB 미니 가습기 초음파",
        "coupang_desc": "초음파 방식 조용한 작동\nUSB 전원 어디서나 사용\n300ml 용량\n자동 전원 차단",
        "score": 80,
        "decision": "PASS"
    },
    {
        "source_title": "스마트 체중계 블루투스 체지방 측정",
        "category": "건강/의료용품",
        "source_price_cny": 42.00,
        "korean_price": 21900,
        "images": [
            "https://example.com/scale/main.jpg",
            "https://example.com/scale/app.jpg",
            "https://example.com/scale/detail.jpg"
        ],
        "naver_title": "스마트 체중계 블루투스 체지방 측정 앱 연동",
        "naver_desc": "스마트 체성분 분석 체중계\n\n✓ 체중/체지방/근육량/BMI 등 12가지 측정\n✓ 블루투스 앱 연동\n✓ 강화유리 안전 설계\n✓ 가족 모드 지원",
        "naver_tags": ["체중계", "스마트체중계", "체지방측정", "블루투스", "체성분"],
        "coupang_title": "블루투스 스마트 체중계 체지방",
        "coupang_desc": "12가지 체성분 측정\n블루투스 앱 연동\n강화유리 안전 설계\n가족 모드 지원",
        "score": 72,
        "decision": "HOLD"
    },
    {
        "source_title": "휴대용 손선풍기 USB 충전식 미니",
        "category": "계절가전",
        "source_price_cny": 18.00,
        "korean_price": 9900,
        "images": [
            "https://example.com/fan/main.jpg",
            "https://example.com/fan/portable.jpg"
        ],
        "naver_title": "휴대용 손선풍기 USB 충전식 미니 핸디 목걸이",
        "naver_desc": "휴대 간편한 미니 손선풍기\n\n✓ USB 충전식 (2000mAh)\n✓ 3단 풍속 조절\n✓ 최대 8시간 사용\n✓ 초경량 디자인",
        "naver_tags": ["손선풍기", "휴대용선풍기", "미니선풍기", "충전식", "핸디선풍기"],
        "coupang_title": "USB 충전식 휴대용 손선풍기",
        "coupang_desc": "USB 충전식 (2000mAh)\n3단 풍속 조절\n최대 8시간 사용\n초경량 휴대 간편",
        "score": 83,
        "decision": "PASS"
    },
    {
        "source_title": "무선 마우스 블루투스 충전식 저소음",
        "category": "컴퓨터/주변기기",
        "source_price_cny": 28.00,
        "korean_price": 14900,
        "images": [
            "https://example.com/mouse/main.jpg",
            "https://example.com/mouse/side.jpg",
            "https://example.com/mouse/use.jpg"
        ],
        "naver_title": "무선 마우스 블루투스 충전식 저소음 3단 DPI",
        "naver_desc": "조용하고 편안한 무선 마우스\n\n✓ 블루투스 5.0 무선 연결\n✓ 저소음 클릭 설계\n✓ 3단 DPI 조절 (800/1200/1600)\n✓ 충전식 배터리 (1개월 사용)",
        "naver_tags": ["무선마우스", "블루투스마우스", "저소음", "충전식", "마우스"],
        "coupang_title": "블루투스 무선 마우스 저소음",
        "coupang_desc": "블루투스 5.0 무선\n저소음 클릭 설계\n3단 DPI 조절\n충전식 1개월 사용",
        "score": 86,
        "decision": "PASS"
    },
    {
        "source_title": "방수 블루투스 스피커 휴대용 IPX7",
        "category": "음향기기",
        "source_price_cny": 52.00,
        "korean_price": 27900,
        "images": [
            "https://example.com/speaker/main.jpg",
            "https://example.com/speaker/water.jpg",
            "https://example.com/speaker/outdoor.jpg"
        ],
        "naver_title": "방수 블루투스 스피커 휴대용 IPX7 고음질 중저음",
        "naver_desc": "완전 방수 아웃도어 스피커\n\n✓ IPX7 완전 방수 (물속 사용 가능)\n✓ 블루투스 5.0 안정 연결\n✓ 20시간 재생 (5000mAh)\n✓ 중저음 강화 설계",
        "naver_tags": ["블루투스스피커", "방수스피커", "휴대용스피커", "IPX7", "아웃도어"],
        "coupang_title": "IPX7 방수 블루투스 스피커",
        "coupang_desc": "IPX7 완전 방수\n블루투스 5.0\n20시간 재생\n중저음 강화",
        "score": 79,
        "decision": "PASS"
    },
    {
        "source_title": "프리미엄 텀블러 보온병 진공 스테인리스 1L",
        "category": "주방용품",
        "source_price_cny": 58.00,
        "korean_price": 29900,
        "images": [
            "https://example.com/bottle/main.jpg",
            "https://example.com/bottle/capacity.jpg",
            "https://example.com/bottle/detail.jpg",
            "https://example.com/bottle/package.jpg"
        ],
        "naver_title": "[대용량] 프리미엄 보온병 1L 진공 스테인리스 텀블러",
        "naver_desc": "대용량 진공 보온병\n\n✓ 1000ml 대용량\n✓ 보온 12시간 / 보냉 24시간\n✓ 이중 진공 단열 설계\n✓ 304 스테인리스 소재",
        "naver_tags": ["보온병", "텀블러", "1L", "대용량", "스테인리스", "진공"],
        "coupang_title": "진공 보온병 1L 스테인리스",
        "coupang_desc": "1000ml 대용량\n보온 12시간 보냉 24시간\n이중 진공 단열\n304 스테인리스",
        "score": 84,
        "decision": "PASS"
    },
    {
        "source_title": "스마트폰 거치대 차량용 송풍구 마그네틱",
        "category": "자동차용품",
        "source_price_cny": 15.00,
        "korean_price": 8900,
        "images": [
            "https://example.com/holder/main.jpg",
            "https://example.com/holder/car.jpg"
        ],
        "naver_title": "차량용 스마트폰 거치대 송풍구 마그네틱 360도 회전",
        "naver_desc": "편리한 마그네틱 차량용 거치대\n\n✓ 강력 자석 안정 고정\n✓ 송풍구 클립 장착\n✓ 360도 자유 회전\n✓ 원터치 탈부착",
        "naver_tags": ["차량용거치대", "스마트폰거치대", "마그네틱", "송풍구", "거치대"],
        "coupang_title": "마그네틱 차량용 거치대",
        "coupang_desc": "강력 자석 고정\n송풍구 클립 장착\n360도 회전\n원터치 탈부착",
        "score": 81,
        "decision": "PASS"
    },
    {
        "source_title": "LED 무드등 수면등 침실 터치 조명",
        "category": "조명",
        "source_price_cny": 32.00,
        "korean_price": 16900,
        "images": [
            "https://example.com/mood/main.jpg",
            "https://example.com/mood/night.jpg",
            "https://example.com/mood/colors.jpg"
        ],
        "naver_title": "LED 무드등 수면등 침실 터치 조명 RGB 밝기조절",
        "naver_desc": "분위기 있는 LED 무드등\n\n✓ RGB 컬러 모드 (16가지)\n✓ 터치 컨트롤 간편 조작\n✓ 밝기 무단 조절\n✓ 수면 타이머 기능",
        "naver_tags": ["무드등", "수면등", "LED조명", "침실조명", "터치조명", "RGB"],
        "coupang_title": "LED 무드등 RGB 터치 조명",
        "coupang_desc": "RGB 16가지 컬러\n터치 컨트롤\n밝기 무단 조절\n수면 타이머",
        "score": 77,
        "decision": "PASS"
    },
    {
        "source_title": "실리콘 폴더블 물병 접이식 휴대용",
        "category": "스포츠/레저",
        "source_price_cny": 12.00,
        "korean_price": 7900,
        "images": [
            "https://example.com/bottle2/main.jpg",
            "https://example.com/bottle2/fold.jpg"
        ],
        "naver_title": "실리콘 폴더블 물병 600ml 접이식 휴대용 등산",
        "naver_desc": "휴대 간편한 접이식 물병\n\n✓ 600ml 용량\n✓ 접었을 때 1/3 크기\n✓ 식품등급 실리콘\n✓ 내열 -40~200도",
        "naver_tags": ["접이식물병", "실리콘물병", "휴대용", "폴더블", "등산용품"],
        "coupang_title": "실리콘 접이식 물병 600ml",
        "coupang_desc": "600ml 용량\n접으면 1/3 크기\n식품등급 실리콘\n내열 -40~200도",
        "score": 85,
        "decision": "PASS"
    },
    {
        "source_title": "USB 허브 7포트 멀티 고속 충전",
        "category": "컴퓨터/주변기기",
        "source_price_cny": 25.00,
        "korean_price": 13900,
        "images": [
            "https://example.com/hub/main.jpg",
            "https://example.com/hub/ports.jpg"
        ],
        "naver_title": "USB 3.0 허브 7포트 멀티 고속 충전 개별 스위치",
        "naver_desc": "다용도 USB 확장 허브\n\n✓ USB 3.0 고속 전송 (5Gbps)\n✓ 7개 포트 동시 사용\n✓ 개별 스위치 전원 제어\n✓ 과전류 보호",
        "naver_tags": ["USB허브", "멀티허브", "7포트", "USB3.0", "고속충전"],
        "coupang_title": "USB 3.0 허브 7포트",
        "coupang_desc": "USB 3.0 고속 5Gbps\n7포트 동시 사용\n개별 스위치\n과전류 보호",
        "score": 82,
        "decision": "PASS"
    },
    {
        "source_title": "키보드 마우스 세트 무선 게이밍",
        "category": "컴퓨터/주변기기",
        "source_price_cny": 75.00,
        "korean_price": 38900,
        "images": [
            "https://example.com/keyboard/main.jpg",
            "https://example.com/keyboard/rgb.jpg",
            "https://example.com/keyboard/mouse.jpg"
        ],
        "naver_title": "키보드 마우스 세트 무선 게이밍 RGB 기계식",
        "naver_desc": "프리미엄 게이밍 키보드 마우스 세트\n\n✓ 2.4GHz 무선 안정 연결\n✓ RGB 백라이트 (16가지)\n✓ 기계식 스위치 키감\n✓ 6400 DPI 게이밍 마우스",
        "naver_tags": ["키보드", "마우스", "게이밍", "무선", "RGB", "기계식"],
        "coupang_title": "무선 게이밍 키보드 마우스 세트",
        "coupang_desc": "2.4GHz 무선 연결\nRGB 백라이트\n기계식 스위치\n6400 DPI 마우스",
        "score": 68,
        "decision": "HOLD"
    },
    {
        "source_title": "멀티탭 USB 충전 개별 스위치 4구",
        "category": "생활용품",
        "source_price_cny": 28.00,
        "korean_price": 14900,
        "images": [
            "https://example.com/outlet/main.jpg",
            "https://example.com/outlet/switch.jpg"
        ],
        "naver_title": "멀티탭 4구 USB 충전 개별 스위치 과부하 차단",
        "naver_desc": "안전한 USB 충전 멀티탭\n\n✓ 4구 콘센트 + 4포트 USB\n✓ 개별 스위치 전원 제어\n✓ 과부하 자동 차단\n✓ 2.5m 긴 선 길이",
        "naver_tags": ["멀티탭", "USB충전", "4구", "개별스위치", "과부하차단"],
        "coupang_title": "멀티탭 4구 USB 충전",
        "coupang_desc": "4구 콘센트 + 4포트 USB\n개별 스위치\n과부하 차단\n2.5m 긴 선",
        "score": 87,
        "decision": "PASS"
    },
    {
        "source_title": "무선 충전 패드 고속 15W 스마트폰",
        "category": "전자제품",
        "source_price_cny": 35.00,
        "korean_price": 18900,
        "images": [
            "https://example.com/charger/main.jpg",
            "https://example.com/charger/charging.jpg"
        ],
        "naver_title": "무선 충전 패드 고속 15W 스마트폰 거치대 접이식",
        "naver_desc": "편리한 무선 고속 충전기\n\n✓ 15W 고속 무선 충전\n✓ 접이식 거치대 기능\n✓ Qi 인증 안전 충전\n✓ 과열 방지 보호",
        "naver_tags": ["무선충전", "고속충전", "15W", "충전패드", "무선충전기"],
        "coupang_title": "15W 고속 무선 충전 패드",
        "coupang_desc": "15W 고속 무선 충전\n접이식 거치대\nQi 인증\n과열 방지",
        "score": 80,
        "decision": "PASS"
    },
    {
        "source_title": "전동 칫솔 음파 충전식 IPX7 방수",
        "category": "건강/미용",
        "source_price_cny": 48.00,
        "korean_price": 24900,
        "images": [
            "https://example.com/brush/main.jpg",
            "https://example.com/brush/modes.jpg",
            "https://example.com/brush/heads.jpg"
        ],
        "naver_title": "전동 칫솔 음파 충전식 IPX7 방수 5가지 모드",
        "naver_desc": "프리미엄 음파 전동칫솔\n\n✓ 분당 31,000회 음파 진동\n✓ 5가지 세정 모드\n✓ IPX7 완전 방수\n✓ 4주 사용 (1회 충전)",
        "naver_tags": ["전동칫솔", "음파칫솔", "충전식", "방수", "칫솔"],
        "coupang_title": "음파 전동칫솔 IPX7 방수",
        "coupang_desc": "31,000회 음파 진동\n5가지 모드\nIPX7 방수\n4주 사용",
        "score": 76,
        "decision": "PASS"
    },
    {
        "source_title": "전기 포트 무선 주전자 1.7L 자동차단",
        "category": "주방가전",
        "source_price_cny": 38.00,
        "korean_price": 19900,
        "images": [
            "https://example.com/kettle/main.jpg",
            "https://example.com/kettle/capacity.jpg"
        ],
        "naver_title": "전기 포트 무선 주전자 1.7L 자동차단 온도 표시",
        "naver_desc": "편리한 무선 전기 주전자\n\n✓ 1.7L 대용량\n✓ 빠른 끓임 (3-5분)\n✓ 자동 전원 차단\n✓ 온도 LED 표시",
        "naver_tags": ["전기포트", "전기주전자", "무선", "1.7L", "자동차단"],
        "coupang_title": "무선 전기 주전자 1.7L",
        "coupang_desc": "1.7L 대용량\n3-5분 빠른 끓임\n자동 전원 차단\n온도 LED 표시",
        "score": 83,
        "decision": "PASS"
    }
]

def create_staging_reviews():
    """실제 운영 검증용 리뷰 항목 생성"""

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    created_reviews = []

    for idx, product in enumerate(SAMPLE_PRODUCTS, 1):
        review_id = f"review-{uuid.uuid4().hex[:12]}"
        now = datetime.now()

        # 생성 시간 약간씩 다르게 (최근 1-3일 내)
        days_ago = random.randint(1, 3)
        created_at = (now - timedelta(days=days_ago)).isoformat()
        updated_at = created_at

        # approval_queue 삽입 (모든 NOT NULL 컬럼 포함)
        raw_agent_output = json.dumps({
            "generated_content": {
                "naver_title": product["naver_title"],
                "naver_description": product["naver_desc"],
                "coupang_title": product["coupang_title"]
            }
        }, ensure_ascii=False)

        cursor.execute("""
            INSERT INTO approval_queue (
                review_id, source_type, source_title, registration_status, needs_human_review,
                raw_agent_output, reviewer_status,
                score, decision,
                generated_naver_title, generated_naver_description, generated_naver_tags,
                generated_coupang_title, generated_coupang_description, generated_price,
                review_status,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            review_id,
            "taobao",
            product["source_title"],
            "pending",  # registration_status (NOT NULL)
            True,  # needs_human_review (NOT NULL)
            raw_agent_output,  # raw_agent_output (NOT NULL)
            "pending",  # reviewer_status (NOT NULL)
            product["score"],
            product["decision"],
            product["naver_title"],
            product["naver_desc"],
            json.dumps(product["naver_tags"], ensure_ascii=False),
            product["coupang_title"],
            product["coupang_desc"],
            product["korean_price"],
            "draft",
            created_at,
            updated_at
        ))

        # image_review 삽입
        image_review_id = f"imgrev-{uuid.uuid4().hex[:12]}"
        original_images = product["images"]

        reviewed_images = []
        for i, url in enumerate(original_images):
            reviewed_images.append({
                "url": url,
                "order": i,
                "is_primary": (i == 0),  # 첫 번째 이미지를 primary로
                "excluded": False,
                "warnings": []
            })

        cursor.execute("""
            INSERT INTO image_review (
                image_review_id, review_id,
                original_images_json, reviewed_images_json,
                primary_image_index,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            image_review_id,
            review_id,
            json.dumps(original_images),
            json.dumps(reviewed_images, ensure_ascii=False),
            0,
            created_at,
            updated_at
        ))

        created_reviews.append({
            "review_id": review_id,
            "product_name": product["source_title"],
            "score": product["score"],
            "decision": product["decision"],
            "status": "draft",
            "image_count": len(original_images)
        })

        print(f"  {idx:2d}. {product['source_title'][:40]:40} | Score: {product['score']:2d} | {product['decision']:6} | Images: {len(original_images)}")

    conn.commit()
    conn.close()

    return created_reviews

if __name__ == "__main__":
    print("\n" + "="*80)
    print("🔧 Phase 4 Staging Validation Setup")
    print("="*80)
    print("\n📦 실제 운영 검증용 리뷰 항목 생성 중...\n")

    reviews = create_staging_reviews()

    print("\n" + "="*80)
    print(f"✅ {len(reviews)}개 리뷰 항목 생성 완료")
    print("="*80)
    print(f"\n데이터베이스: {DB_PATH}")
    print(f"\n다음 단계:")
    print(f"  1. http://localhost:8000/review/list 접속")
    print(f"  2. 10-20개 항목 실제 검수 수행")
    print(f"  3. Naver/Coupang CSV 내보내기 테스트")
    print(f"  4. 실제 마켓플레이스 업로드 호환성 검증")
    print()
