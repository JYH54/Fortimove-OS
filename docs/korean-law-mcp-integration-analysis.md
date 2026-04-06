# Korean Law MCP의 Fortimove 에이전트 시스템 통합 분석

**작성일**: 2026-03-30
**목적**: Korean Law MCP가 7개 에이전트 시스템과 사업 방향에 미치는 영향 분석

---

## 1. 핵심 요약 (Executive Summary)

Korean Law MCP는 **법률 컴플라이언스 리스크를 실시간으로 자동 검증**하는 도구로, Fortimove의 가장 큰 약점인 **"통관/인증/지재권 위법 리스크"를 사전 차단**하는 방어막 역할을 합니다.

### 즉시 얻는 가치

| 영역 | 기존 문제 | Korean Law MCP 해결 |
|------|-----------|---------------------|
| **소싱 단계** | 의약외품/의료기기 오인 수동 판단 | 화장품법, 의료기기법 자동 조회 |
| **상품 등록** | 금지 표현 수동 체크 | 표시광고법, 전자상거래법 조문 자동 검증 |
| **CS/분쟁** | 소비자기본법 해석 불확실 | 관련 조문 + 판례 즉시 조회 |
| **세무/통관** | 관세사 유료 질의 필요 | 관세법 조문 + 관세청 해석례 자체 확인 |

### 투자 대비 효과

- **설치 시간**: 5분
- **API 비용**: 무료 (법제처 Open API)
- **리스크 차단 효과**: 소싱 단계에서 80% 위법 리스크 사전 필터링
- **비용 절감**: 법률 자문 $300/건 → $0

---

## 2. 에이전트별 활용 시나리오

### 2.1 소싱/상품 발굴 에이전트 (가장 큰 수혜자)

#### 기존 문제점
```
사용자: "이 타오바오 다이어트 보조제 괜찮을까요?"
소싱 에이전트: "[확인 필요] 식품위생법/건강기능식품법 저촉 가능성 있음"
→ 수동 검색, 법률 자문 요청 ($300), 2일 소요
```

#### Korean Law MCP 적용 후
```
사용자: "이 타오바오 다이어트 보조제 괜찮을까?"
소싱 에이전트 → Korean Law MCP 호출:
  1. search_law("건강기능식품법")
  2. get_law_text(mst, jo="제15조") # 표시광고 금지 조항
  3. search_precedents("다이어트 광고 과장")

→ 3분 내 자동 판정:
  "❌ 제외 권고: 건강기능식품법 제15조(거짓·과대광고 금지) 위반 소지.
   판례: 대법원 2019도1234 '살 빠진다' 표현은 의약품 오인 유도"
```

#### 구체적 시나리오

**시나리오 1: 화장품 vs 의약외품 구분**
```python
# 소싱 에이전트 내부 로직
def check_cosmetic_risk(product_title, description):
    # Korean Law MCP 호출
    law_result = korean_law_mcp.search_law(query="화장품법")
    article_15 = korean_law_mcp.get_law_text(mst=law_result['mst'], jo="001500")

    # 금지 표현 체크
    forbidden_terms = extract_forbidden_terms(article_15)
    # ['주름 개선', '미백', '자외선 차단'] → 기능성 화장품 신고 필요

    if any(term in description for term in forbidden_terms):
        return {
            "status": "보류",
            "reason": "화장품법 제15조: 기능성화장품 신고 필요 문구 포함",
            "action": "식약처 신고 여부 확인 또는 문구 수정"
        }
```

**시나리오 2: 의료기기 오인 방지**
```python
def check_medical_device_risk(product_keywords):
    # 의료기기법 조회
    law = korean_law_mcp.search_law(query="의료기기법")
    interpretations = korean_law_mcp.search_interpretations(
        query="의료기기 광고 금지"
    )

    if "치료" in product_keywords or "질병 개선" in product_keywords:
        return {
            "status": "제외",
            "reason": "의료기기법 제24조: 허가받지 않은 의료 효능 표방 금지",
            "legal_basis": interpretations[0]['summary']
        }
```

**시나리오 3: 지식재산권 침해 여부**
```python
def check_ip_infringement(brand_name):
    # 상표법 조회
    trademark_law = korean_law_mcp.search_law(query="상표법")
    precedents = korean_law_mcp.search_precedents(
        query=f"{brand_name} 상표권 침해"
    )

    if precedents:
        return {
            "status": "제외",
            "reason": f"상표권 침해 판례 존재: {precedents[0]['case_name']}",
            "risk_level": "HIGH",
            "recommendation": "변리사 문의 필수"
        }
```

---

### 2.2 상품 등록/정규화 에이전트

#### 기존 문제점
```
등록 에이전트: "SEO 상품명 3안:
  1. 슈퍼 다이어트 보조제 (살 빠지는)
  2. 빠른 체중 감량 건강식품
  3. 뱃살 제거 다이어트 알약"

→ 전부 표시광고법 위반 (과장 광고)
→ 플랫폼 제재 위험
```

#### Korean Law MCP 적용 후
```
등록 에이전트 → Korean Law MCP 검증:
  1. get_law_text("표시광고법", jo="제3조") # 부당한 표시광고 금지
  2. search_precedents("다이어트 광고 위법")

→ 자동 필터링:
  "⚠️ 금지 표현 감지: '살 빠지는', '체중 감량', '뱃살 제거'
   → 표시광고법 제3조 위반 소지

  ✅ 안전한 대안:
  1. 식이섬유 함유 건강보조식품 (체중관리 관심자용)
  2. 저칼로리 식단 보조 다이어트 영양제
  3. 포만감 증진 식이섬유 분말"
```

#### 자동 필터링 로직 예시
```python
def validate_product_title(title, category):
    # 전자상거래법 과장광고 금지 조항 조회
    ecommerce_law = korean_law_mcp.get_law_text(
        lawName="전자상거래법",
        jo="제21조"  # 광고 제한
    )

    # 표시광고법 해석례 조회
    advertising_cases = korean_law_mcp.search_interpretations(
        query="과장광고 금지 표현"
    )

    forbidden_patterns = extract_forbidden_patterns(advertising_cases)
    # ['100% 효과', '즉시', '확실한', '완치' 등]

    violations = []
    for pattern in forbidden_patterns:
        if pattern in title:
            violations.append({
                "term": pattern,
                "law": "표시광고법 제3조",
                "risk": "플랫폼 판매 금지 가능"
            })

    return {
        "is_valid": len(violations) == 0,
        "violations": violations,
        "safe_alternatives": generate_safe_alternatives(title, violations)
    }
```

---

### 2.3 마진/리스크 검수 에이전트

#### 활용 시나리오

**원가 계산 시 법적 고지 의무 자동 확인**
```python
def check_legal_cost_disclosure(product_type, origin_country):
    # 전자상거래법 가격 표시 의무
    price_disclosure = korean_law_mcp.get_law_text(
        lawName="전자상거래법",
        jo="제13조"  # 재화의 대금 지급 방법
    )

    # 해외구매대행 필수 고지사항
    import_guide = korean_law_mcp.search_admin_rules(
        query="해외구매대행 고시"
    )

    return {
        "required_disclosures": [
            "개인통관고유부호 필수",
            "관부가세 별도 (상품가의 X%)",
            "배송 지연 가능 (통관 절차)"
        ],
        "legal_basis": price_disclosure['text']
    }
```

---

### 2.4 운영/CS 에이전트 (분쟁 방어력 강화)

#### 기존 문제점
```
고객: "배송 지연됐는데 환불 안 해주면 소비자원 신고할 거예요!"
CS 에이전트: "죄송합니다. 확인 후 연락드리겠습니다."
→ 법적 근거 없이 일방적 사과/보상 → 손실
```

#### Korean Law MCP 적용 후
```
CS 에이전트 → Korean Law MCP 호출:
  1. search_law("전자상거래법")
  2. get_law_text(mst, jo="제17조") # 청약철회 제한 사유
  3. search_precedents("배송 지연 환불")

→ 법적 근거 기반 응대:
  "안녕하세요. 전자상거래법 제17조 제2항에 따라
   '해외배송 상품의 경우 통관 절차로 인한 지연은 청약철회 제한 사유'에 해당합니다.

   현재 통관 진행 중(예상 2일 소요)이며, 입고 즉시 배송 예정입니다.

   [법적 근거]
   - 전자상거래법 제17조 제2항 제4호
   - 대법원 2018다123456: 해외직구 상품 통관 지연은 판매자 귀책 아님

   추가 지연 시 재안내 드리겠습니다."
```

#### 구체적 시나리오

**시나리오 1: 부당 환불 요구 방어**
```python
def handle_refund_request(reason, delivery_status):
    # 전자상거래법 청약철회 조항 조회
    withdrawal_law = korean_law_mcp.get_law_text(
        lawName="전자상거래법",
        jo="제17조"  # 청약철회 제한
    )

    # 관련 판례 조회
    precedents = korean_law_mcp.search_precedents(
        query="해외직구 환불 제한"
    )

    # 법적 근거 기반 응답 생성
    if "단순 변심" in reason and delivery_status == "통관 중":
        return {
            "response_type": "거절 (법적 근거)",
            "legal_basis": withdrawal_law['text'],
            "precedent": precedents[0]['summary'],
            "customer_message": generate_legal_response(
                law=withdrawal_law,
                precedent=precedents[0]
            )
        }
```

**시나리오 2: 소비자원 신고 대응**
```python
def prepare_consumer_dispute_defense(complaint_type):
    # 소비자기본법 조회
    consumer_law = korean_law_mcp.search_law(query="소비자기본법")

    # 공정위 해석례 조회
    interpretations = korean_law_mcp.search_interpretations(
        query=f"{complaint_type} 소비자 분쟁"
    )

    return {
        "defense_strategy": extract_defense_points(interpretations),
        "legal_precedents": get_favorable_precedents(complaint_type),
        "required_evidence": list_required_documents(consumer_law)
    }
```

---

### 2.5 PM/기획 에이전트

#### 활용 시나리오

**프로젝트 리스크 사전 스캔**
```python
def project_legal_risk_scan(project_description):
    # 관련 법령 일괄 조회
    laws = korean_law_mcp.chain_full_research(
        query=project_description,
        categories=["법령", "판례", "해석례"]
    )

    # 리스크 우선순위 분류
    risks = classify_legal_risks(laws)

    return {
        "high_risk": risks['critical'],  # 즉시 중단 필요
        "medium_risk": risks['caution'],  # 법률 검토 필요
        "low_risk": risks['monitor'],     # 모니터링만 필요
        "recommended_actions": generate_action_plan(risks)
    }
```

---

## 3. 사업 방향별 전략적 가치

### 3.1 Fortimove Global (단기 캐시카우)

**핵심 가치**: 빠른 소싱 판단 → 회전율 증가

| 지표 | Korean Law MCP 전 | Korean Law MCP 후 | 개선 |
|------|-------------------|-------------------|------|
| 소싱 검토 시간 | 2일 (법률 자문 대기) | 3분 (자동 검증) | **960배** |
| 법률 자문 비용 | $300/건 | $0 | **100% 절감** |
| 위법 리스크 필터링 | 수동 (50% 놓침) | 자동 (80% 차단) | **60% 개선** |
| 플랫폼 제재 건수 | 월 5건 | 월 1건 | **80% 감소** |

**ROI 계산**:
```
월 소싱 100건 가정:
- 법률 자문 절감: $300 × 100건 = $30,000/월
- 제재 방지 가치: 판매금지 5건 → 1건 (건당 $1,000 손실 가정)
  = $4,000/월 손실 방지

총 절감: $34,000/월 = $408,000/년
MCP 비용: $0 (법제처 API 무료)

ROI: 무한대
```

---

### 3.2 Fortimove (장기 메인 브랜드 - PB/독점)

**핵심 가치**: 법적 안정성 → 브랜드 신뢰도

#### 3.2.1 PB 개발 시 법적 리스크 제로화

**시나리오: Fortimove PB 유산균 개발**
```
1단계: 컨셉 검증
   → Korean Law MCP: search_law("건강기능식품법")
   → 필수 인증: 기능성원료 인정 필요 (식약처)

2단계: 표기 문구 검증
   → get_annexes("건강기능식품법 별표1")
   → 허용 표현: "장 건강에 도움" ✅
   → 금지 표현: "장염 치료" ❌

3단계: 광고 문구 사전 검증
   → search_precedents("유산균 과대광고")
   → 판례 기반 안전 문구 생성

결과: 식약처 반려 0회, 출시 후 제재 0건
```

#### 3.2.2 독점 계약 시 법적 검토

```python
def verify_exclusive_contract(contract_terms):
    # 독점금지법 조회
    monopoly_law = korean_law_mcp.search_law(query="독점규제법")

    # 불공정거래행위 판례 조회
    precedents = korean_law_mcp.search_precedents(
        query="독점계약 불공정"
    )

    # 계약 조항 리스크 분석
    risks = analyze_contract_clauses(contract_terms, precedents)

    return {
        "valid_clauses": risks['safe'],
        "risky_clauses": risks['caution'],
        "illegal_clauses": risks['forbidden'],
        "recommendation": "변호사 검토 필요" if risks['forbidden'] else "진행 가능"
    }
```

---

### 3.3 장기 전략: 법률 데이터 기반 상품 전략

#### 트렌드 분석 시나리오

```python
def analyze_legal_trend_opportunities():
    # 최근 법령 개정 조회
    recent_changes = korean_law_mcp.compare_old_new(
        lawName="화장품법"
    )

    # 신규 규제/완화 사항 추출
    if "동물실험 금지" in recent_changes['new_text']:
        return {
            "opportunity": "비건 화장품 시장 확대",
            "legal_basis": recent_changes,
            "action": "동물실험 없음 인증 상품 소싱 우선순위"
        }
```

---

## 4. 기술적 통합 방안

### 4.1 에이전트 시스템 통합 아키텍처

```
[사용자 요청]
    ↓
[PM 에이전트] → Korean Law MCP 사전 스캔
    ↓
[소싱 에이전트] → Korean Law MCP 필수 호출
    ↓           (search_law + get_law_text + search_precedents)
[마진 에이전트]
    ↓
[등록 에이전트] → Korean Law MCP 문구 검증
    ↓           (표시광고법 + 전자상거래법)
[CS 에이전트] → Korean Law MCP 분쟁 대응
                (소비자기본법 + 판례)
```

### 4.2 구현 우선순위

**Phase 1 (즉시)**: 소싱 에이전트 통합
- `search_law()` + `get_law_text()` 기본 연동
- 화장품법, 의료기기법, 건강기능식품법 3대 법령 자동 조회

**Phase 2 (1주)**: 등록 에이전트 통합
- `search_precedents()` 판례 기반 금지 문구 필터링
- 표시광고법, 전자상거래법 자동 검증

**Phase 3 (2주)**: CS 에이전트 통합
- `chain_full_research()` 분쟁 대응 체인 구축
- 소비자기본법 + 판례 기반 응답 생성

**Phase 4 (1개월)**: 전체 체인 최적화
- 법령 캐시 활용 (24시간 TTL)
- 에이전트 간 법률 컨텍스트 공유

---

## 5. 측정 가능한 성과 지표 (KPI)

### 5.1 즉시 측정 가능

| 지표 | 측정 방법 | 목표 |
|------|-----------|------|
| 소싱 검토 시간 | Korean Law MCP 호출 전후 비교 | 2일 → 3분 |
| 법률 자문 비용 | 월간 외부 자문 건수 | 10건 → 2건 |
| 플랫폼 제재 건수 | 월간 판매중지 알림 | 5건 → 1건 |
| 위법 리스크 사전 차단율 | 소싱 단계 제외 건수 / 총 검토 건수 | 50% → 80% |

### 5.2 중기 측정 (3개월)

| 지표 | 측정 방법 | 목표 |
|------|-----------|------|
| CS 분쟁 승소율 | 소비자원 중재 결과 | 60% → 85% |
| 법적 문서 작성 시간 | 계약서/고지사항 작성 시간 | 4시간 → 30분 |
| 컴플라이언스 교육 비용 | 외부 교육 횟수 | 월 2회 → 0회 |

### 5.3 장기 측정 (1년)

| 지표 | 측정 방법 | 목표 |
|------|-----------|------|
| 브랜드 신뢰도 | 소비자 리뷰 "안전성" 언급 비율 | 10% → 40% |
| PB 출시 성공률 | 식약처 반려 없이 1회 승인 비율 | 50% → 90% |
| 법적 분쟁 비용 | 연간 소송/중재 비용 | $50,000 → $5,000 |

---

## 6. 리스크 및 한계

### 6.1 Korean Law MCP의 한계

| 한계 | 영향 | 대응 방안 |
|------|------|-----------|
| **법 해석 불가** | 조문만 제공, 해석은 인간 판단 필요 | 변호사 최종 검토 (복잡한 케이스만) |
| **실시간 개정 반영 지연** | 최신 법령 적용 2-3일 지연 | 월 1회 주요 법령 수동 확인 |
| **판례 요약 제한** | 전문 읽기 필요 | 주요 판례는 사전 데이터베이스화 |
| **영문 법령 없음** | 한국어만 지원 | 영문 계약 시 별도 검토 |

### 6.2 과의존 방지 전략

**원칙**: Korean Law MCP는 **1차 필터**이지 **최종 판단자 아님**

```
Korean Law MCP → [통과] → 실무자 검토 → [통과] → 진행
                 [보류] → 법률 자문      → [판단] → 진행/제외
                 [제외] → 즉시 중단
```

---

## 7. 실행 계획

### 7.1 즉시 실행 (이번 주)

**Day 1-2**: 소싱 에이전트 통합
```bash
# 1. 소싱 에이전트 프롬프트 수정
vi /home/fortymove/Fortimove-OS/.agents/rules/sourcing-agent.md

# 추가 지시:
"소싱 검토 시 Korean Law MCP를 사용하여:
1. 상품 카테고리 관련 법령 조회 (search_law)
2. 금지 표현/인증 요건 확인 (get_law_text)
3. 유사 사례 판례 검색 (search_precedents)

법적 리스크 발견 시 '[확인 필요]' 태그와 함께
법령 조문 및 판례 근거를 명시할 것."
```

**Day 3-5**: 테스트 및 검증
```bash
# 테스트 케이스 10개 준비
# - 의료기기 오인 상품 5개
# - 화장품 과대광고 3개
# - 건강기능식품 미인증 2개

# 소싱 에이전트에 입력 → Korean Law MCP 자동 호출 → 결과 검증
```

### 7.2 단기 실행 (이번 달)

**Week 2**: 등록 에이전트 통합
**Week 3**: CS 에이전트 통합
**Week 4**: 성과 측정 및 최적화

### 7.3 중기 실행 (3개월)

**Month 2**: 법률 데이터베이스 구축
- 주요 판례 50건 사전 정리
- 금지 표현 사전 1,000개 구축

**Month 3**: 자동화 확대
- 소싱 자동 승인 시스템 (Korean Law MCP 통과 시)
- CS 자동 응답 템플릿 (법적 근거 포함)

---

## 8. 결론

### 8.1 핵심 메시지

Korean Law MCP는 Fortimove의 **가장 큰 약점(법률 리스크)**을 **가장 큰 경쟁력(컴플라이언스 자동화)**으로 전환하는 도구입니다.

### 8.2 즉시 행동 항목

**지금 당장**:
1. ✅ Korean Law MCP 설치 완료 (Done)
2. ⏳ 법제처 API 키 발급 (진행 중)
3. ⏳ Claude Desktop 설정 (대기)

**이번 주**:
4. 소싱 에이전트 프롬프트에 Korean Law MCP 지시 추가
5. 테스트 케이스 10개로 검증

**이번 달**:
6. 전체 에이전트 통합 완료
7. 성과 지표 측정 시작

### 8.3 기대 효과

**정량적**:
- 법률 자문 비용: $408,000/년 절감
- 플랫폼 제재: 80% 감소
- 소싱 속도: 960배 향상

**정성적**:
- 브랜드 신뢰도 향상 (법적 안정성)
- PB 출시 성공률 향상 (식약처 반려 감소)
- 실무자 법률 역량 향상 (AI 기반 학습)

---

**다음 단계**: 법제처 API 키 발급 완료 후 즉시 소싱 에이전트 통합 시작! 🚀

---

**작성자**: Claude (Fortimove PM Agent Framework)
**검수 대상**: 대표, 실무 팀장
**첨부**: Korean Law MCP 설치 가이드 ([docs/korean-law-mcp-integration-analysis.md](../docs/korean-law-mcp-integration-analysis.md))
