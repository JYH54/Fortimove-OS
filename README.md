# Fortimove 운영 시스템 (Fortimove-OS)

Fortimove의 **비즈니스 운영 문서 + AI 에이전트 자동화 시스템**을 통합 관리하는 저장소입니다.
소싱→법률검증→상품등록→CS까지 전 파이프라인을 7개 AI 에이전트가 처리합니다.

## 1. 폴더 구조 및 역할

### 비즈니스 문서
*   `docs/`: 실무 기준서, 가이드라인(SOP), 마케팅/기획 등 비즈니스 운영 문서.
*   `prompts/`: 반복 업무 및 콘텐츠 생성에 활용할 AI 프롬프트 템플릿.
*   `templates/`: 고객 응대, 발주서 등 반복 실무용 서식 및 양식.

### 자동화 시스템
*   `pm-agent/`: PM 에이전트 — 7개 에이전트 오케스트레이션, 리뷰 콘솔, 승인 큐, API.
*   `daily-scout/`: Daily Wellness Scout — 4개 지역 웰니스 트렌드 자동 모니터링.
*   `image-localization-system/`: 이미지 현지화 — OCR→번역→리스크감지→무드톤 적용.
*   `korean-law-mcp/`: 한국 법령 MCP — 40개+ 법령 검색 도구 (법제처 API 연동).

### 설정
*   `.claude/`: Claude AI 프로젝트 특화 지침서 (`CLAUDE.md`).
*   `.agents/rules/`: AI 에이전트 범용 규칙.

## 2. 문서 권장 읽기 순서

저장소를 파악하기 위해 아래 순서대로 문서를 읽는 것을 권장합니다.

1.  `README.md` (본 문서: 전체 구조 및 금지사항 파악)
2.  `docs/business-goals.md` (단기/중기/장기 비즈니스 목표)
3.  `docs/brand-context.md` (브랜드 분리 및 사업 전략 원칙)
4.  `docs/sourcing-sop.md`, `docs/product-registration-sop.md`, `docs/cs-sop.md` (실무 파이프라인)

## 3. 저장소 제출 금지 항목 (Not Allowed)

아래 항목은 절대 이곳에 넣지 마십시오.

*   운영 시스템과 무관한 외부 웹 개발 코드 (별도 저장소 생성 원칙)
*   개인정보가 포함된 실제 고객의 주문 내역 DB 파일이나 정산 엑셀 원본 파일
*   `.env` 파일 및 API 키, 비밀번호 등 시크릿 (`.gitignore`로 차단됨)
*   임시 테스트 파일 및 쓰레기 값 문서 (`test.md`, `dummy.txt` 등)

## 4. 브랜드 구조 (Brand Context) 요약

*   **Fortimove Global (현재 실행 브랜드)**: 단순 구매대행, 신규 아이템 소싱 테스트. 매출 및 시장 데이터 확보(단기적 캐시카우).
*   **Fortimove (장기 메인 브랜드)**: 웰니스·헬스케어 플랫폼. 데이터가 검증된 핵심 상품의 권리(PB/독점)를 확보하여 쌓아가는 브랜드(장기적 자산).

## 5. 자동화 시스템 (Automation Systems)

본 저장소는 비즈니스 문서 중심이지만, 운영 효율화를 위한 **자동화 도구**가 일부 포함되어 있습니다.

### 현재 구축된 시스템

#### A. Image Localization System (이미지 현지화)
- **위치**: `image-localization-system/`
- **기능**: 중국 상품 이미지의 텍스트를 OCR로 추출하고 한국어로 번역, 리스크 이미지 감지
- **접속**: http://localhost:3000 (프론트엔드), http://localhost:8000 (API)
- **실행**: `cd image-localization-system && docker-compose up -d`

#### B. Daily Wellness Scout (자동 트렌드 모니터링)
- **위치**: `daily-scout/`
- **기능**: 매일 자동으로 4개 지역(일본, 중국, 미국, 영국)의 웰니스 트렌드를 스캔하고 AI 리스크 필터링
- **실행**: Docker 백그라운드 자동 실행 (매일 오전 9시)
- **출력**: 이메일 리포트, Slack 알림, SQLite 데이터베이스

### 시작 가이드

**빠른 시작**:
```bash
cd /home/fortymove/Fortimove-OS/image-localization-system
docker-compose up -d
```

**상세 가이드**: [docs/setup-guide.md](docs/setup-guide.md)

**알림 설정**: [docs/notification-setup.md](docs/notification-setup.md)

### 주의사항

- 이 시스템들은 **실무 자동화 도구**로서 예외적으로 포함됩니다.
- 새로운 개발 프로젝트는 별도 저장소 생성을 원칙으로 합니다.
- 시스템 문의: 개발팀 또는 [docs/setup-guide.md](docs/setup-guide.md) 참고

## 6. 문서 작성 및 버전 관리 원칙

*   **한국어로 작성할 것.**
*   **실무형으로 작성할 것.**
*   **추상적 표현은 배제할 것.**
*   **복붙 가능한 완성형**: 대표 및 실무자가 바로 [복사/붙여넣기] 해서 사용할 수 있는 완성형을 지향할 것.
*   **문서 버전 관리**: 주요 정책(SOP 등) 변경 시 사유와 함께 버전을 업데이트하여 기록할 것.
