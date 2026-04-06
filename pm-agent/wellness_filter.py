"""
Wellness Filter — 구매대행 합법 웰니스 상품만 선별

대한민국 법규 준수:
- 건강기능식품법: 식약처 인정 성분 외 효능 광고 금지
- 약사법: 의약품 수입 금지
- 의료기기법: 미허가 의료기기 수입 금지
- 관세법: 2026년 8월 개정 $100 초과 과세 대상
- 표시광고법: 과대/허위 광고 금지
"""

import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
# 합법 웰니스 화이트리스트 (구매대행 가능)
# ══════════════════════════════════════════════════════════

WELLNESS_ALLOWED = {
    "비타민": {
        "keywords": ["비타민", "vitamin", "멀티비타민", "비타민D", "비타민C", "비타민B"],
        "risk_level": "low",
        "margin_potential": "high",
        "notes": "건강기능식품 원료로 등록된 성분",
    },
    "오메가3": {
        "keywords": ["오메가", "omega", "피쉬오일", "fish oil", "EPA", "DHA", "알래스카"],
        "risk_level": "low",
        "margin_potential": "high",
        "notes": "건강기능식품 인정 원료",
    },
    "프로바이오틱스": {
        "keywords": ["프로바이오틱", "probiotic", "유산균", "lactobacillus", "bifido"],
        "risk_level": "low",
        "margin_potential": "very_high",
        "notes": "19가지 균주 식약처 인정",
    },
    "단백질": {
        "keywords": ["프로틴", "protein", "웨이", "whey", "카제인", "casein", "BCAA", "아미노산"],
        "risk_level": "low",
        "margin_potential": "medium",
        "notes": "일반 식품 분류",
    },
    "미네랄": {
        "keywords": ["마그네슘", "magnesium", "아연", "zinc", "칼슘", "calcium", "철분", "iron", "셀레늄"],
        "risk_level": "low",
        "margin_potential": "high",
        "notes": "기초 미네랄, 건강기능식품 인정",
    },
    "콜라겐": {
        "keywords": ["콜라겐", "collagen", "히알루론산", "hyaluronic"],
        "risk_level": "low",
        "margin_potential": "very_high",
        "notes": "건강기능식품 원료",
    },
    "항산화": {
        "keywords": ["코큐텐", "CoQ10", "유비퀴놀", "ubiquinol", "resveratrol", "글루타치온", "glutathione", "아스타잔틴", "아스타잔신", "astaxanthin", "nac", "alpha lipoic"],
        "risk_level": "low",
        "margin_potential": "very_high",
        "notes": "건강기능식품 인정 항산화 성분",
    },
    "안티에이징": {
        "keywords": ["NMN", "NR", "nicotinamide", "resveratrol", "spermidine", "fisetin", "quercetin", "pterostilbene"],
        "risk_level": "medium",
        "margin_potential": "very_high",
        "notes": "항노화 트렌드 고마진 — 효능 광고 주의",
    },
    "관절": {
        "keywords": ["글루코사민", "glucosamine", "콘드로이친", "chondroitin", "MSM", "보스웰리아"],
        "risk_level": "low",
        "margin_potential": "high",
        "notes": "건강기능식품 인정",
    },
    "누트로픽": {
        "keywords": ["L-카르니틴", "L-테아닌", "라이온스메인", "사자갈기버섯", "lion's mane", "Alpha-GPC", "크레아틴", "creatine"],
        "risk_level": "medium",
        "margin_potential": "very_high",
        "notes": "뇌 기능 광고 금지 — 활력/운동 용도로만",
    },
    "어댑토겐": {
        "keywords": ["아쉬와간다", "ashwagandha", "로디올라", "rhodiola", "홍경천", "마카", "maca"],
        "risk_level": "medium",
        "margin_potential": "very_high",
        "notes": "스트레스/수면 효능 광고 금지",
    },
    "식이섬유": {
        "keywords": ["이눌린", "inulin", "차전자피", "psyllium", "섬유소", "fiber"],
        "risk_level": "low",
        "margin_potential": "medium",
        "notes": "일반 식품",
    },
    "슈퍼푸드": {
        "keywords": ["스피룰리나", "spirulina", "클로렐라", "chlorella", "모링가", "비트루트", "beetroot", "강황", "turmeric", "커큐민"],
        "risk_level": "low",
        "margin_potential": "high",
        "notes": "건강기능식품 또는 일반 식품",
    },

    # ══════════════════════════════════════════════════════════
    # 확장 카테고리 — 애견 용품
    # ══════════════════════════════════════════════════════════

    "애견_영양제": {
        "keywords": ["강아지 영양제", "dog vitamin", "pet vitamin", "강아지 관절", "dog joint", "강아지 글루코사민", "반려동물 영양제", "pet supplement", "강아지 오메가", "dog omega", "omega bites", "hip and joint", "multivitamin for dogs", "zesty paws", "pet naturals", "vetriscience", "nutramax"],
        "risk_level": "low",
        "margin_potential": "very_high",
        "notes": "반려동물 영양제 — 동물용의약품 아닌 보조식품만 가능",
    },
    "애견_프로바이오틱스": {
        "keywords": ["강아지 유산균", "dog probiotic", "pet probiotic", "반려동물 장건강", "cat probiotic", "고양이 유산균", "daily probiotic", "digestive for dogs", "pet digestive"],
        "risk_level": "low",
        "margin_potential": "very_high",
        "notes": "반려동물 장 건강 보조식품",
    },
    "애견_덴탈": {
        "keywords": ["강아지 치약", "dog dental", "pet toothbrush", "강아지 구강", "강아지 이빨", "dental chew", "덴탈껌", "플라크 제거", "nylabone", "greenies", "chew toy"],
        "risk_level": "low",
        "margin_potential": "high",
        "notes": "반려동물 구강 관리 — 의약품 성분 제외",
    },
    "애견_피부모질": {
        "keywords": ["강아지 피부", "dog skin", "pet coat", "강아지 샴푸", "dog shampoo", "pet omega oil", "강아지 피모"],
        "risk_level": "low",
        "margin_potential": "high",
        "notes": "반려동물 피부/털 관리 — 일반 미용 용품",
    },
    "애견_간식": {
        "keywords": ["강아지 간식", "dog treat", "pet treat", "덴탈 간식", "훈련 간식", "수제 간식", "freeze dried", "동결건조"],
        "risk_level": "low",
        "margin_potential": "medium",
        "notes": "반려동물 간식 — 일반 사료/간식",
    },
    "애견_용품": {
        "keywords": ["강아지 장난감", "dog toy", "pet toy", "dog collar", "dog leash", "하네스", "harness", "강아지 옷", "dog clothes", "ped bed", "강아지 방석", "pet carrier", "이동가방", "poop bag", "waste bag", "dog bowl", "feeder", "자동급식기", "배변패드", "potty pad", "pet wipe", "강아지 물티슈", "brush", "강아지 빗"],
        "risk_level": "low",
        "margin_potential": "medium",
        "notes": "반려동물 용품 — 일반 잡화",
    },

    # ══════════════════════════════════════════════════════════
    # 확장 카테고리 — 요가/홈트레이닝
    # ══════════════════════════════════════════════════════════

    "요가_매트": {
        "keywords": ["요가매트", "yoga mat", "필라테스 매트", "pilates mat", "운동매트", "exercise mat", "TPE매트", "코르크 매트"],
        "risk_level": "low",
        "margin_potential": "high",
        "notes": "요가/필라테스 매트 — 일반 스포츠 용품",
    },
    "요가_블록": {
        "keywords": ["요가블럭", "yoga block", "요가링", "yoga ring", "요가벨트", "yoga strap", "요가볼", "balance ball", "짐볼", "피트볼"],
        "risk_level": "low",
        "margin_potential": "medium",
        "notes": "요가 보조 도구",
    },
    "홈트_밴드": {
        "keywords": ["저항밴드", "resistance band", "풀업밴드", "pull up band", "루프밴드", "loop band", "미니밴드", "튜빙밴드", "근막이완"],
        "risk_level": "low",
        "margin_potential": "high",
        "notes": "홈 트레이닝 밴드 — 일반 운동용품",
    },
    "홈트_덤벨": {
        "keywords": ["덤벨", "dumbbell", "케틀벨", "kettlebell", "바벨", "barbell", "원판", "plate", "가변덤벨", "adjustable"],
        "risk_level": "low",
        "margin_potential": "medium",
        "notes": "홈 트레이닝 프리웨이트",
    },
    "홈트_장비": {
        "keywords": ["푸시업바", "pushup bar", "푸쉬업", "평행봉", "딥스바", "복근롤러", "ab roller", "스텝박스", "aerobic step", "요가휠", "yoga wheel", "밸런스보드", "bosu ball"],
        "risk_level": "low",
        "margin_potential": "high",
        "notes": "홈 트레이닝 장비 — 일반 스포츠 용품",
    },
    "홈트_마사지": {
        "keywords": ["폼롤러", "foam roller", "마사지볼", "massage ball", "근막이완", "트리거포인트", "점프로프", "줄넘기", "jump rope"],
        "risk_level": "low",
        "margin_potential": "high",
        "notes": "자가 근막 이완/유산소 — 일반 스포츠 용품",
    },

    # ══════════════════════════════════════════════════════════
    # 확장 카테고리 — 보호대 (의료기기 아닌 것만)
    # ══════════════════════════════════════════════════════════

    "스포츠_보호대": {
        "keywords": ["무릎보호대", "knee sleeve", "knee support", "팔꿈치보호대", "elbow sleeve", "손목보호대", "wrist wrap", "wrist band", "발목보호대", "ankle sleeve", "ankle brace", "허리보호대", "back support belt", "lifting belt", "웨이트 벨트", "헤드밴드"],
        "risk_level": "low",
        "margin_potential": "high",
        "notes": "스포츠 보호대 — 일반 스포츠 용품 (의료기기 X)",
    },
    "자세_교정": {
        "keywords": ["자세교정밴드", "posture corrector", "견갑골", "어깨 교정", "척추 지지대", "사이클링 보호대"],
        "risk_level": "medium",
        "margin_potential": "high",
        "notes": "자세교정 일반 용품 — 의료 효능 광고 금지",
    },
    "컴프레션_웨어": {
        "keywords": ["컴프레션 슬리브", "compression sleeve", "compression socks", "종아리 슬리브", "calf sleeve", "arm sleeve", "기능성 양말"],
        "risk_level": "low",
        "margin_potential": "high",
        "notes": "컴프레션 웨어 — 스포츠/운동 용품",
    },

    # ══════════════════════════════════════════════════════════
    # 확장 카테고리 — 일상 웰니스 잡화
    # ══════════════════════════════════════════════════════════

    "텀블러_보틀": {
        "keywords": ["텀블러", "tumbler", "보온병", "thermos", "쉐이커", "shaker bottle", "blender bottle", "물병", "hydro flask", "워터보틀", "water bottle", "nalgene", "스포츠 보틀", "sports bottle"],
        "risk_level": "low",
        "margin_potential": "high",
        "notes": "운동/일상용 텀블러 — 일반 잡화",
    },
    "웰니스_침구": {
        "keywords": ["경추베개", "메모리폼 베개", "memory foam pillow", "자세 베개", "기능성 베개", "사이드슬리퍼", "lumbar pillow"],
        "risk_level": "low",
        "margin_potential": "high",
        "notes": "기능성 베개 — 일반 생활용품",
    },
    "아로마_웰빙": {
        "keywords": ["디퓨저", "diffuser", "essential oil", "에센셜오일", "아로마", "aroma", "humidifier", "가습기"],
        "risk_level": "low",
        "margin_potential": "medium",
        "notes": "아로마/웰빙 용품 — 치료 효능 광고 금지",
    },
}

# ══════════════════════════════════════════════════════════
# 금지 품목 블랙리스트 (구매대행 불가)
# ══════════════════════════════════════════════════════════

WELLNESS_BLOCKED = {
    "의약품": {
        "keywords": ["타이레놀", "tylenol", "아스피린", "aspirin", "ibuprofen", "이부프로펜", "처방", "prescription", "Rx"],
        "law": "약사법",
        "reason": "수입 금지 (식약처 허가 필수)",
    },
    "호르몬제": {
        "keywords": ["DHEA", "프레그네놀론", "pregnenolone", "멜라토닌", "melatonin", "테스토스테론", "testosterone"],
        "law": "약사법",
        "reason": "한국에서 의약품으로 분류됨 (구매대행 불법)",
    },
    "대마관련": {
        "keywords": ["CBD", "hemp oil", "대마", "cannabis", "marijuana", "THC"],
        "law": "마약류관리법",
        "reason": "한국 수입 금지",
    },
    "수면유도제": {
        "keywords": ["ZMA", "GABA 고함량", "수면제", "sleeping pill"],
        "law": "약사법",
        "reason": "의약품 분류 가능성",
    },
    "의료기기": {
        "keywords": ["혈압계", "혈당측정", "콘택트렌즈", "임신테스트", "체온계", "맥박계", "산소포화도", "EMS", "저주파", "TENS", "IR 치료", "적외선 치료기", "초음파 치료"],
        "law": "의료기기법",
        "reason": "의료기기 수입 허가 필요",
    },
    "의료용_보호대": {
        "keywords": ["의료용 보호대", "medical brace", "medical cervical", "orthopedic brace", "경추보조기", "경추보호대", "cervical collar", "neck brace", "재활 보호대", "골절 보호대", "깁스", "cast", "의료용 깁스"],
        "law": "의료기기법",
        "reason": "의료용 보호대는 의료기기 — 일반 스포츠 보호대는 허용",
    },
    "동물_의약품": {
        "keywords": ["강아지 진통제", "dog pain relief", "dog antibiotic", "반려동물 항생제", "pet medicine", "기생충 구충제", "dewormer", "heartgard", "frontline", "flea and tick", "dog insulin"],
        "law": "동물용의약품법",
        "reason": "동물용의약품 수입 금지 (수의사 처방 필요)",
    },
    "화장품_의약외품": {
        "keywords": ["모발이식", "hair regrowth", "미녹시딜", "minoxidil", "프로페시아", "finasteride", "니조랄", "salicylic 고함량"],
        "law": "약사법/화장품법",
        "reason": "의약품/의약외품 수입 허가 필요",
    },
    "화장품_고기능": {
        "keywords": ["화이트닝", "whitening", "주름개선", "anti-wrinkle", "기미제거", "여드름치료"],
        "law": "화장품법",
        "reason": "기능성 화장품 수입 허가 필요",
    },
    "다이어트_의심": {
        "keywords": ["다이어트 약", "체중감량 효과", "garcinia 고함량", "에페드린", "ephedrine", "요힘빈"],
        "law": "약사법",
        "reason": "다이어트 의약품/부작용 위험",
    },
}


class WellnessFilter:
    """웰니스 상품 합법성 필터"""

    def classify(self, product_name: str, description: str = "", category: str = "") -> Dict:
        """상품이 구매대행 가능한 웰니스 상품인지 분류"""
        text = f"{product_name} {description} {category}".lower()

        # 1. 블랙리스트 체크 (우선순위 높음) — 단어 경계 체크
        import re as _re
        for block_type, info in WELLNESS_BLOCKED.items():
            for kw in info["keywords"]:
                kw_lower = kw.lower()
                # 짧은 약어(4자 이하)는 단어 경계 매칭, 긴 키워드는 substring 매칭
                if len(kw_lower) <= 4:
                    pattern = r'\b' + _re.escape(kw_lower) + r'\b'
                    if _re.search(pattern, text):
                        matched = True
                    else:
                        matched = False
                else:
                    matched = kw_lower in text

                if matched:
                    return {
                        "allowed": False,
                        "decision": "BLOCKED",
                        "category": block_type,
                        "matched_keyword": kw,
                        "law": info["law"],
                        "reason": info["reason"],
                        "action": "거부 — 구매대행 불법",
                    }

        # 1.5. 애견 제품 힌트 (dog/pet/강아지/고양이/cat 키워드 + 애견 전용 브랜드)
        pet_hints = ["dog", "pet", "강아지", "고양이", "cat", "반려동물", "반려견", "반려묘", " for dogs", " for cats"]
        pet_brands = ["nylabone", "kong ", "greenies", "zesty paws", "frontline", "pet naturals", "vetriscience", "nutramax", "wellness pet", "blue buffalo", "royal canin"]
        pet_specific = ["dental chew", "chew toy", "poop bag", "litter", "cat tree", "scratch post", "litter box"]
        is_pet_product = (any(h in text for h in pet_hints) or
                          any(b in text for b in pet_brands) or
                          any(s in text for s in pet_specific))

        # 2. 화이트리스트 체크
        matched_categories = []
        for wellness_type, info in WELLNESS_ALLOWED.items():
            # 애견 제품이면 "애견_" 카테고리만 체크
            if is_pet_product and not wellness_type.startswith("애견_"):
                continue
            # 애견 제품이 아니면 애견 카테고리 건너뛰기
            if not is_pet_product and wellness_type.startswith("애견_"):
                continue

            for kw in info["keywords"]:
                if kw.lower() in text:
                    matched_categories.append({
                        "type": wellness_type,
                        "matched": kw,
                        "risk_level": info["risk_level"],
                        "margin_potential": info["margin_potential"],
                        "notes": info["notes"],
                    })
                    break

        if matched_categories:
            # 가장 고마진 카테고리를 우선 선택
            priority_order = {"very_high": 4, "high": 3, "medium": 2, "low": 1}
            matched_categories.sort(
                key=lambda x: priority_order.get(x["margin_potential"], 0),
                reverse=True
            )
            primary = matched_categories[0]
            return {
                "allowed": True,
                "decision": "APPROVED",
                "primary_category": primary["type"],
                "all_matches": matched_categories,
                "risk_level": primary["risk_level"],
                "margin_potential": primary["margin_potential"],
                "notes": primary["notes"],
                "action": f"통과 — {primary['type']} 카테고리 ({primary['margin_potential']} 마진)",
            }

        # 3. 매칭 안 됨 → 수동 검토 필요
        return {
            "allowed": None,
            "decision": "MANUAL_REVIEW",
            "category": "UNCLASSIFIED",
            "action": "수동 검토 필요 — 웰니스 카테고리 키워드 미발견",
        }

    def filter_products(self, products: List[Dict]) -> Dict:
        """상품 목록을 필터링하여 합법/불법/검토필요로 분류"""
        approved = []
        blocked = []
        review = []

        for p in products:
            name = p.get("product_name") or p.get("title") or ""
            desc = p.get("description", "")
            cat = p.get("category", "")
            result = self.classify(name, desc, cat)

            enriched = {**p, "wellness_filter": result}

            if result["decision"] == "APPROVED":
                approved.append(enriched)
            elif result["decision"] == "BLOCKED":
                blocked.append(enriched)
            else:
                review.append(enriched)

        # 마진 잠재력으로 정렬
        priority_order = {"very_high": 4, "high": 3, "medium": 2, "low": 1}
        approved.sort(
            key=lambda x: priority_order.get(x["wellness_filter"].get("margin_potential", "low"), 0),
            reverse=True
        )

        return {
            "total": len(products),
            "approved": approved,
            "blocked": blocked,
            "review_needed": review,
            "stats": {
                "approved_count": len(approved),
                "blocked_count": len(blocked),
                "review_count": len(review),
                "approval_rate": round(len(approved) / len(products) * 100, 1) if products else 0,
            }
        }
