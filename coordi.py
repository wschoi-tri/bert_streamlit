import streamlit as st
import requests
import random
import os
import streamlit.components.v1 as components

# API URL 설정 (브라우저에서 호출됨)
COORDI_API_URL = "https://dev-api.halfclub.com/recommend/coordiitem"
SIMILAR_API_URL = "https://dev-api.halfclub.com/recommend/similaritem"
BEST_URL = "https://hapix.halfclub.com/searches/prdList/?selAcntCd=A6082&limit=0,40&sortSeq=12&siteCd=1&device=pc&icnSet="

# 1. 페이지 설정
st.set_page_config(
    page_title="하프 코디 추천 대시보드 (클라이언트 호출)",
    layout="wide"
)

# 2. 브라우저용 API Fetcher 컴포넌트 선언
parent_dir = os.path.dirname(os.path.abspath(__file__))
build_dir = os.path.join(parent_dir, "components/api_fetcher")
api_fetcher = components.declare_component("api_fetcher", path=build_dir)

# 3. 프리미엄 컴팩트 스타일 CSS 적용 (오밀조밀한 레이아웃 구성)
st.markdown("""
    <style>
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 0.2rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }
    div[data-testid="element-container"] {
        margin-top: 0px !important;
        margin-bottom: 2px !important;
        padding-top: 0px !important;
        padding-bottom: 0px !important;
    }
    .product-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
        gap: 8px;
        width: 100%;
    }
    .product-card {
        background-color: white;
        padding: 6px !important;
        border-radius: 6px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
        border: 1px solid #f1f5f9;
        text-align: left;
        display: flex;
        flex-direction: column;
        justify-content: flex-start;
        box-sizing: border-box;
        width: 180px;
        height: auto;
        overflow: hidden;
        margin-bottom: 4px;
        transition: transform 0.15s;
    }
    .product-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.04);
    }
    .product-card img {
        width: 168px;
        height: 168px;
        object-fit: cover;
        border-radius: 4px;
        margin-bottom: 2px;
    }
    .brand-text {
        font-size: 12.5px;
        font-weight: 600;
        color: #888888;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        margin-top: 2px;
        line-height: 1.15;
    }
    .title-text {
        font-size: 12.5px;
        color: #333333;
        margin-top: 2px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        line-height: 1.15;
    }
    .price-text {
        font-size: 14px;
        font-weight: 800;
        color: #ff4b4b;
        margin-top: 2px;
        line-height: 1.15;
    }
    .badge-tag {
        background-color: #ff4b4b;
        color: white;
        font-size: 11.5px;
        font-weight: bold;
        text-align: center;
        padding: 2px 0;
        border-radius: 4px 4px 0 0;
        margin-bottom: 2px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .badge-tag-inactive {
        background-color: #f1f5f9;
        color: #475569;
        font-size: 11.5px;
        font-weight: bold;
        text-align: center;
        padding: 2px 0;
        border-radius: 4px 4px 0 0;
        margin-bottom: 2px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .divider {
        margin: 5px 0 !important;
        border-bottom: 1px solid #e2e8f0;
    }
    </style>
""", unsafe_allow_html=True)

st.title("하프 코디 추천 대시보드 (클라이언트 호출)")
st.caption("대상 상품 중 하나를 선택하면 사용자의 브라우저(사내망)에서 직접 API를 호출하여 매칭 코디 추천 결과를 조회합니다.")

def format_price(value):
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return str(value)

from services.coordi_rule import get_coordi_target_categories

def get_expected_targets(ctgr1, ctgr2, ctgr3):
    target_ctgr2_list, target_ctgr3_list, is_sports, is_setup, is_golf, label, desc = get_coordi_target_categories(
        ctgr1, ctgr2, ctgr3
    )
    
    if not target_ctgr2_list and not target_ctgr3_list:
        return '<div style="color:#ef4444; font-weight:bold; font-size:11px;">[비대상] 코디 비대상 카테고리 (추천 제외)</div>'
        
    targets = target_ctgr3_list if target_ctgr3_list else target_ctgr2_list
    
    if targets:
        badges = "".join([f'<span style="display:inline-block; background-color:#eff6ff; color:#1e40af; padding:2.5px 6px; border-radius:4px; margin-right:4px; margin-bottom:4px; font-size:11px; font-weight:600; border:1px solid #bfdbfe;">{t}</span>' for t in targets])
        
        return (
            f'<div style="font-size:11px; line-height:1.45; color:#475569; margin-top:2px;">'
            f'매칭 방식 : <span style="font-weight:bold; color:#0f172a; background-color:#f1f5f9; padding:2px 6px; border-radius:4px;">{label}</span><br/>'
            f'<div style="font-size:10px; color:#64748b; margin-top:4px; margin-bottom:8px;">({desc})</div>'
            f'<div style="font-weight:bold; color:#0f172a; margin-bottom:4px;">추천 대상 상품군 :</div>'
            f'<div style="display:flex; flex-wrap:wrap; gap:4px; max-height:85px; overflow-y:auto; padding-right:2px;">{badges}</div>'
            f'</div>'
        )
    
    return '<div style="color:#94a3b8; font-size:11px;">매핑 정보 없음</div>'

# 4. 베스트 상품 리스트 조회 (서버 측 캐시 가능 공공 API)
@st.cache_data(ttl=600)
def get_best_products():
    try:
        resp = requests.get(BEST_URL, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        hits = data if isinstance(data, list) else data.get("data", {}).get("result", {}).get("hits", {}).get("hits", [])
        if not hits and isinstance(data, dict):
            hits = data.get("result", {}).get("hits", {}).get("hits", [])
        
        products = []
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            src = hit.get("_source", {}) if "_source" in hit else hit
            prd_no = src.get("prdNo") or src.get("prd_no")
            if prd_no:
                products.append({
                    "prd_no": prd_no,
                    "prd_nm": src.get("prdNm") or src.get("prd_nm", ""),
                    "prd_img": src.get("appPrdImgUrl") or src.get("prd_img", ""),
                    "brand_nm": src.get("brandNm") or src.get("brand_nm", ""),
                    "price": src.get("dcPrcMc") or src.get("price", 0),
                    "ctgr1": src.get("dpCtgrNm1") or src.get("ctgr1", ""),
                    "ctgr2": src.get("dpCtgrNm2") or src.get("ctgr2", ""),
                    "ctgr3": src.get("dpCtgrNm3") or src.get("ctgr3", "")
                })
        return products
    except Exception as e:
        st.error(f"상품 목록 조회 에러: {e}")
        return []

# 5. 상단 상품번호 검색 입력 UI 구성
col_title, col_search = st.columns([3, 2])
with col_title:
    st.markdown("<h4 style='margin: 0; padding-top: 10px;'>코디 추천 대상 상품 조회</h4>", unsafe_allow_html=True)
with col_search:
    col_input, col_btn = st.columns([3, 1])
    with col_input:
        custom_prd_input = st.text_input(
            "상품번호 입력", 
            value="", 
            placeholder="상품번호 입력 후 Enter 혹은 조회 클릭", 
            label_visibility="collapsed"
        )
    with col_btn:
        search_clicked = st.button("조회", use_container_width=True)

# 6. 세션 상태 및 쿼리 매개변수를 기반으로 현재 선택 상품 결정
if "selected_prd_no" not in st.session_state:
    st.session_state.selected_prd_no = 0

query_params = st.query_params
if "selectedPrdNo" in query_params:
    try:
        st.session_state.selected_prd_no = int(query_params["selectedPrdNo"])
    except Exception:
        pass

# 검색 입력 시 세션 업데이트 및 쿼리 파라미터 갱신
if custom_prd_input.strip() and (search_clicked or custom_prd_input != st.session_state.get("prev_input", "")):
    if custom_prd_input.strip().isdigit():
        p_no = int(custom_prd_input.strip())
        st.session_state.prev_input = custom_prd_input
        st.session_state.selected_prd_no = p_no
        st.query_params["selectedPrdNo"] = str(p_no)
        st.rerun()

# 7. 베스트 상품 선택 리스트 그리드로 렌더링
best_products = get_best_products()
if best_products:
    st.subheader("대상 상품 리스트 (선택 시 해당 상품 코디 노출)")
    
    grid_items_html = []
    selected_no = st.session_state.selected_prd_no
    
    for prd in best_products:
        btn_label = prd["ctgr2"] if prd["ctgr2"] else "미분류"
        p_no = prd["prd_no"]
        img_url = prd["prd_img"] or ""
        
        badge_class = "badge-tag" if p_no == selected_no else "badge-tag-inactive"
        
        price_val = prd["price"]
        try:
            price_str = f"{int(price_val):,}원"
        except (ValueError, TypeError):
            price_str = f"{price_val}원"
            
        card_html = (
            f'<div class="product-card">'
            f'<a href="?selectedPrdNo={p_no}" target="_self" style="text-decoration: none; color: inherit; display: block;">'
            f'<div class="{badge_class}">{btn_label}</div>'
            f'<img src="{img_url}">'
            f'<div style="font-size:10px; color:#888888; margin-top:2px; line-height:1.1;">{p_no}</div>'
            f'<div class="brand-text" style="font-size:12px; font-weight:600; color:#333333; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin-top:2px; line-height:1.15;">{prd["brand_nm"]}</div>'
            f'<div class="title-text" style="font-size:12px; color:#475569; margin-top:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; line-height:1.15;">{prd["prd_nm"]}</div>'
            f'<div class="price-text" style="font-size:14px; font-weight:800; color:#ff4b4b; margin-top:3px; line-height:1.15;">{price_str}</div>'
            f'</a>'
            f'</div>'
        )
        grid_items_html.append(card_html)
        
    st.markdown(f'<div class="product-grid">{"".join(grid_items_html)}</div>', unsafe_allow_html=True)

st.divider()

# 8. 선택된 대상 상품 정보 및 코디 추천 렌더링
if st.session_state.selected_prd_no > 0:
    active_no = st.session_state.selected_prd_no
    
    # 8-1. 브라우저단 API 호출을 통해 상품 상세 데이터 획득
    details_res = api_fetcher(
        url=SIMILAR_API_URL,
        params={"prdNo": [active_no], "size": 1, "originPrdYn": True, "siteCd": 1},
        requestId=f"details_{active_no}",
        key=f"fetch_details_{active_no}"
    )
    
    if details_res is None:
        st.info("브라우저에서 상품 상세 정보를 조회하는 중입니다. (잠시만 기다려주세요...)")
    elif not details_res.get("success"):
        st.error(f"상품 상세 정보를 가져오는데 실패했습니다: {details_res.get('error')}")
    else:
        # 상품 상세 매핑
        results = details_res.get("data", {}).get("result", [])
        selected_prd = None
        for item in results:
            if item.get("type") == "origin":
                selected_prd = {
                    "prd_no": active_no,
                    "prd_nm": item.get("prdNm") or item.get("prd_nm", ""),
                    "prd_img": item.get("appPrdImgUrl") or item.get("prd_img", ""),
                    "brand_nm": item.get("brandNm", ""),
                    "price": item.get("dcPrcMc") or item.get("price", 0),
                    "ctgr1": item.get("dpCtgrNm1") or item.get("ctgr1", ""),
                    "ctgr2": item.get("dpCtgrNm2") or item.get("ctgr2", ""),
                    "ctgr3": item.get("dpCtgrNm3") or item.get("ctgr3", "")
                }
                break
        
        if not selected_prd:
            selected_prd = {
                "prd_no": active_no,
                "prd_nm": f"조회 상품 ({active_no})",
                "prd_img": "",
                "brand_nm": "기타",
                "price": 0,
                "ctgr1": "미분류", "ctgr2": "미분류", "ctgr3": "미분류"
            }
            
        ctgr_path = f"{selected_prd['ctgr1']} > {selected_prd['ctgr2']}"
        if selected_prd['ctgr3']:
            ctgr_path += f" > {selected_prd['ctgr3']}"
            
        st.markdown(f"### 추천 대상 상품: {selected_prd['ctgr1']}")
        
        expected_target_mapping = get_expected_targets(
            selected_prd.get('ctgr1', ''), 
            selected_prd.get('ctgr2', ''), 
            selected_prd.get('ctgr3', '')
        )
        
        price_val = selected_prd.get("price", 0)
        try:
            price_str = f"{int(price_val):,}원"
        except (ValueError, TypeError):
            price_str = f"{price_val}원"
            
        html_block = (
            '<div style="display: flex; gap: 8px; flex-wrap: wrap; align-items: stretch; width: 100%; margin-top: 5px; margin-bottom: 10px;">'
            '<div class="product-card" style="width: 180px; flex-shrink: 0; margin-bottom: 0;">'
            f'<img src="{selected_prd["prd_img"] or ""}">'
            f'<div style="font-size:10px; color:#888888; margin-top:2px; line-height:1.1;">{selected_prd["prd_no"]}</div>'
            f'<div class="brand-text" style="font-size:12px; font-weight:600; color:#333333; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin-top:2px; line-height:1.15;">{selected_prd["brand_nm"]}</div>'
            f'<div class="title-text" style="font-size:12px; color:#475569; margin-top:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; line-height:1.15;">{selected_prd["prd_nm"]}</div>'
            f'<div class="price-text" style="font-size:14px; font-weight:800; color:#ff4b4b; margin-top:3px; line-height:1.15;">{price_str}</div>'
            '</div>'
            '<div class="product-card" style="width: 260px; padding: 8px !important; margin-bottom: 0; min-height: 198px;">'
            f'<div style="font-size: 12.5px; font-weight: bold; color: #1e293b; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; margin-bottom: 6px;">{selected_prd["brand_nm"]}</div>'
            f'<div style="font-size: 12.5px; font-weight: bold; color: #333333; margin-bottom: 8px; line-height: 1.25; height: 35px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;">{selected_prd["prd_nm"]}</div>'
            '<div style="font-size: 11px; color: #475569; line-height: 1.45;">'
            f'브랜드 : {selected_prd["brand_nm"]}<br/>'
            f'상품 : <a href="https://www.halfclub.com/product/{selected_prd["prd_no"]}" target="_blank">{selected_prd["prd_no"]}</a><br/>'
            f'가격 : {price_str}<br/>'
            f'분류 : {ctgr_path}'
            '</div>'
            '</div>'
            '<div class="product-card" style="width: 630px; padding: 8px !important; margin-bottom: 0; min-height: 198px;">'
            '<div style="font-size: 12.5px; font-weight: bold; color: #1e293b; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; margin-bottom: 6px;">코디 매핑 연산 결과</div>'
            f'{expected_target_mapping}'
            '</div>'
            '</div>'
        )
        st.markdown(html_block, unsafe_allow_html=True)
            
        st.divider()
        
        # 8-2. 브라우저단 API 호출을 통해 코디 추천 목록 획득
        st.subheader("매칭 코디 추천 상품 목록")
        
        coordi_res = api_fetcher(
            url=COORDI_API_URL,
            params={"prdNo": active_no, "size": 100, "siteCd": 1, "randomYn": False, "originPrdYn": True},
            requestId=f"coordi_{active_no}",
            key=f"fetch_coordi_{active_no}"
        )
        
        if coordi_res is None:
            st.info("브라우저에서 매칭 코디 상품 정보를 조회하는 중입니다...")
        elif not coordi_res.get("success"):
            st.error(f"코디 추천 API 호출 실패: {coordi_res.get('error')}")
        else:
            coordi_data = coordi_res.get("data", {})
            st.caption(f"호출 API URL: {COORDI_API_URL} (브라우저에서 직접 요청됨)")
            
            recs = coordi_data.get("result", [])
            count = len(recs)
            st.info(f"추천 건수: {count}개")
            
            if count > 0:
                grid_items_html = []
                for rec in recs:
                    img_url = rec.get("appPrdImgUrl") or rec.get("prd_img") or ""
                    p_no = rec.get("prdNo") or rec.get("prd_no")
                    score = rec.get("score", 0.0)
                    esscore = rec.get("esscore", 0.0)
                    
                    season_map = {"01": "봄", "02": "여름", "03": "가을", "04": "겨울", "05": "사계절"}
                    sgn_list = rec.get("sgnCd", [])
                    seasons = ", ".join([season_map.get(s, s) for s in sgn_list]) if isinstance(sgn_list, list) else ""
                    
                    rec_ctgr_path = f"{rec.get('dpCtgrNm1', '')} > {rec.get('dpCtgrNm2', '')} > {rec.get('dpCtgrNm3', '')}"
                    
                    price_val = rec.get('dcPrcMc') or rec.get('price', 0)
                    try:
                        price_str = f"{int(price_val):,}원"
                    except (ValueError, TypeError):
                        price_str = f"{price_val}원"
                    
                    card_html = (
                        f'<a href="https://www.halfclub.com/product/{p_no}" target="_blank" style="text-decoration: none; color: inherit; display: block;">'
                        f'<div class="product-card">'
                        f'<img src="{img_url}">'
                        f'<div style="font-size:10px; color:#888888; margin-top:2px; line-height:1.1;">{p_no}</div>'
                        f'<div class="brand-text" style="font-size:12px; font-weight:600; color:#333333; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; margin-top:2px; line-height:1.15;">{rec.get("brandNm", "")}</div>'
                        f'<div class="title-text" style="font-size:12px; color:#475569; margin-top:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; line-height:1.15;">{rec.get("prdNm") or rec.get("prd_nm", "")}</div>'
                        f'<div style="font-size:11px; color:#64748b; line-height:1.3; margin-top:3px;">'
                        f'분류: {rec_ctgr_path}<br/>'
                        f'시즌: {seasons}<br/>'
                        f'점수: {score:.4f} / ES: {esscore:.4f}'
                        f'</div>'
                        f'<div class="price-text" style="font-size:14px; font-weight:800; color:#ff4b4b; margin-top:3px; line-height:1.15;">{price_str}</div>'
                        f'</div>'
                        f'</a>'
                    )
                    grid_items_html.append(card_html)
                    
                grid_html = f'<div class="product-grid">{"".join(grid_items_html)}</div>'
                st.markdown(grid_html, unsafe_allow_html=True)
            else:
                st.warning("코디 대상에 적합한 반대 카테고리 매칭 결과가 존재하지 않습니다.")
else:
    st.info("위 상품 목록에서 상품 카드를 클릭하거나 상단에 상품번호를 입력하여 코디 매칭 결과를 확인해 보세요.")

st.divider()

# 9. 최하단 매핑 규칙 가이드 가시화
st.subheader("카테고리 코디 맵핑 설정 가이드")
st.markdown(
    r"""
    현재 설정서([docs/category_mapping.md](file:///Users/wonseok/Library/CloudStorage/OneDrive-트라이씨클/Source/20260526/hf_recomm_api/docs/category_mapping.md))에 기록된 매칭 룰 요약입니다.
    
    ### 1. 중분류(ctgr2) 매핑 룰
    - **상의군 (티셔츠, 셔츠/블라우스, 니트/스웨터, 가디건, 베스트, 셔츠, 가디건/베스트, 맨투맨/후드티 등)** $\leftrightarrow$ **하의군 (팬츠, 스커트, 데님팬츠, 하의 등)**
    - **아우터군 (자켓, 점퍼, 패딩/다운, 코트 등)** $\rightarrow$ **하의군**
    - **원피스군 (원피스)** $\rightarrow$ **아우터군**
    
    ### 2. 소분류(ctgr3) 스타일 매핑 룰 (소분류 매핑 우선 적용)
    - **정장/오피스룩 (FORMAL)**:
      - 상의/아우터 (기본/솔리드, 정장/테일러드, 기본, 셔츠/블라우스, 셔츠, 울/캐시미어, 트렌치) $\leftrightarrow$ 하의 (슬랙스/정장, H라인/정장, 슬랙스)
    - **캐주얼룩 (CASUAL)**:
      - 상의/아우터 (라운드넥, 맨투맨/후드, 반팔, 캐주얼, 후드/집업, 데님, 브이넥, 터틀넥 등) $\leftrightarrow$ 하의 (데님팬츠, 반바지, 레깅스, 밴딩, 와이드, 기모 등)
 
    ### 3. 스포츠/아웃도어 매핑 룰 (동일 브랜드/상품군 내 매칭 유지)
    - 스포츠/아웃도어/골프의류 카테고리(`ctgr2`가 아웃도어, 스포츠의류 등인 경우):
      - **상의/아우터 소분류** (티셔츠, 상의, 맨투맨, 자켓, 바람막이, 조끼 등) $\leftrightarrow$ **하의 소분류** (팬츠, 하의, 레깅스, 바지 등)
      - 스포츠/아웃도어는 전체 룩의 일관성을 위해 **동일 중분류(예: 아웃도어는 아웃도어끼리) 범주 안에서만** 크로스 카테고리 매칭이 진행됩니다.
    """
)
