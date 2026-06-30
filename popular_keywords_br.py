import streamlit as st
import requests

# 페이지 설정
st.set_page_config(
    page_title="검색결과확인 Top10",
    page_icon="🔎",
    layout="wide"
)

# 커스텀 CSS 적용으로 프리미엄 스타일 구현
st.markdown("""
    <style>
    /* 여백 최소화 */
    .block-container {
        padding-top: 2.5rem !important;
        padding-bottom: 0.2rem !important;
        padding-left: 1.0rem !important;
        padding-right: 1.0rem !important;
    }
    /* Streamlit 위젯 요소들 자체의 기본 하단 마진 제거 (버튼-리스트 사이의 빈 여백 완화) */
    div[data-testid="element-container"] {
        margin-top: 0px !important;
        margin-bottom: 2px !important;
        padding-top: 0px !important;
        padding-bottom: 0px !important;
    }
    /* stButton(인기 검색어 10개 버튼)이 포함된 stHorizontalBlock 행만 선택하여 하단 마진을 음수로 적용 (타이틀 행 침범 방지) */
    div[data-testid="stHorizontalBlock"]:has(div.stButton) {
        margin-bottom: -15px !important;
    }

    /* 버튼 컴팩트화 */
    div.stButton > button {
        padding: 2px 4px !important;
        font-size: 0.72rem !important;
        height: auto !important;
    }
    .keyword-title {
        font-size: 0.95rem;
        font-weight: 700;
        color: #1e293b;
        margin-top: 2px !important;
        margin-bottom: 2px !important;
    }
    .product-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
        gap: 5px;
    }
    .product-card {
        background-color: white;
        padding: 3px 5px !important;
        border-radius: 6px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02);
        margin-bottom: 2px !important;
        transition: transform 0.15s;
        border: 1px solid #f1f5f9;
        display: flex;
        align-items: center;
        gap: 8px;
        height: 50px;
        box-sizing: border-box;
    }
    .product-card:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.04);
    }
    .divider {
        margin: 1px 0 !important;
        border-bottom: 1px solid #e2e8f0;
    }
    /* 연관 키워드 배지 */
    .rel-keyword-badge {
        display: inline-block;
        background-color: #f1f5f9;
        color: #475569;
        padding: 2px 5px;
        border-radius: 4px;
        margin-right: 4px;
        margin-bottom: 4px;
        font-size: 0.72em;
        text-decoration: none;
        font-weight: 500;
        border: 1px solid #e2e8f0;
    }
    .rel-keyword-badge:hover {
        background-color: #e2e8f0;
        color: #1e293b;
    }
    </style>
""", unsafe_allow_html=True)

API_URL = "https://apix.boribori.co.kr/searches/popularKeyword/?countryCd=001&langCd=001&siteCd=2&deviceCd=002&mandM=b_boribori"

@st.cache_data(ttl=300)
def fetch_popular_keywords():
    try:
        response = requests.get(API_URL, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"인기 검색어 API 호출 중 오류가 발생했습니다: {e}")
        return None

# 단일 키워드의 상품 정보와 연관 키워드를 가져와 캐싱하는 함수 (온디맨드 호출)
@st.cache_data(ttl=300)
def fetch_product_data_for_keyword(kw):
    search_api_url = "https://apix.boribori.co.kr/searches/prdList/"
    params = {
        "keyword": kw,
        "limit": "0,40",
        "sortSeq": "12",
        "siteCd": "2",
        "device": "mc",
    }
    try:
        resp = requests.get(search_api_url, params=params, timeout=10)
        resp.raise_for_status()
        search_data = resp.json()
        hits = search_data.get("data", {}).get("result", {}).get("hits", {}).get("hits", [])
        rel_keywords = search_data.get("data", {}).get("rel_keywords", [])
        return {
            "hits": hits,
            "rel_keywords": rel_keywords,
            "url": resp.url,
            "raw_data": search_data
        }
    except Exception as e:
        return {
            "hits": [],
            "rel_keywords": [],
            "url": "",
            "raw_data": {},
            "error": str(e)
        }

if "popular_keywords_data" not in st.session_state:
    with st.spinner("실시간 인기 검색어를 불러오는 중..."):
        st.session_state.popular_keywords_data = fetch_popular_keywords()

data = st.session_state.popular_keywords_data

if data:
    keywords = []
    
    def extract_keywords_from_list(items):
        return [item.get("keyword") for item in items if isinstance(item, dict) and item.get("keyword")]

    if isinstance(data, list):
        keywords = extract_keywords_from_list(data)
    elif isinstance(data, dict):
        target_data = data.get("data")
        if isinstance(target_data, list):
            keywords = extract_keywords_from_list(target_data)
        elif isinstance(target_data, dict):
            for key in ("result", "list", "items"):
                if isinstance(target_data.get(key), list):
                    keywords = extract_keywords_from_list(target_data[key])
                    break

    if keywords:
        top_keywords = keywords[:10]
        
        # 세션 상태 초기화
        if "selected_keyword" not in st.session_state or st.session_state.selected_keyword not in top_keywords:
            st.session_state.selected_keyword = top_keywords[0]

        selected_kw = st.session_state.selected_keyword

        # 버튼 클릭 시 즉시 탭 상태 업데이트 콜백
        def select_keyword_callback(kw):
            st.session_state.selected_keyword = kw
            st.session_state.cleared_state = True  # 화면 클리어 상태 활성화

        # 상단 타이틀은 좌측 정렬, 키워드 표시 및 검색 이동 버튼은 우측 정렬로 수평 배치
        col_head_left, col_head_right = st.columns([1, 1])
        with col_head_left:
            st.markdown(f'<div class="keyword-title" style="margin-top: 6px; text-align: left; font-size: 1.15rem; font-weight: 800; color: #ff4b4b;">인기키워드 검색 (Top 10)</div>', unsafe_allow_html=True)
        with col_head_right:
            # flex 컨테이너를 사용하여 우측 정렬 및 링크 버튼 수평 배치
            right_html = (
                f'<div style="display: flex; justify-content: flex-end; align-items: center; gap: 15px; margin-top: 6px;">'
                f'<div class="keyword-title" style="margin: 0;">🛍️ "{selected_kw}" 검색 결과</div>'
                f'<a href="https://m.boribori.co.kr/search/{selected_kw}" target="_blank" class="rel-keyword-badge" '
                f'style="margin: 0; padding: 4px 10px; background-color: #ff4b4b; color: white; border: none; font-size: 0.8em; border-radius: 6px;">🔗 보리 검색</a>'
                f'</div>'
            )
            st.markdown(right_html, unsafe_allow_html=True)

        # 10열 그리드로 인기 검색어 버튼을 상단에 1줄로 배치
        cols_btn = st.columns(10)
        for idx, kw in enumerate(top_keywords):
            btn_label = f"{idx+1}. {kw}"
            # 현재 선택된 키워드 강조 표시
            if kw == st.session_state.selected_keyword:
                btn_label = f"✨{idx+1}.{kw}"
                
            cols_btn[idx].button(
                btn_label, 
                key=f"btn_{kw}", 
                use_container_width=True, 
                on_click=select_keyword_callback, 
                args=(kw,)
            )



        # 탭 전환 시 화면 지우기 구현: cleared_state가 True이면 지워진 상태로 즉시 한 번 렌더링하고 다시 Rerun
        if st.session_state.get("cleared_state", False):
            st.session_state.cleared_state = False
            st.info("🔄 새로운 상품 목록을 불러오는 중...")
            st.rerun()
            
        # 온디맨드 방식으로 현재 선택된 키워드의 데이터만 가져옴 (첫 로딩 속도 10배 이상 향상 및 멀티스레드 차단 방지)
        kw_data = fetch_product_data_for_keyword(selected_kw)
        hits = kw_data.get("hits", [])
        rel_kws = kw_data.get("rel_keywords", [])
        
        if "error" in kw_data:
            st.error(f"상품 정보를 불러오는 중 오류가 발생했습니다: {kw_data['error']}")
        else:
            if hits:
                # 40개 상품 카드를 단 하나의 HTML 그리드로 묶어서 렌더링 (Streamlit WebSocket 컴포넌트 렌더링 병목 해결)
                grid_items_html = []
                for hit in hits:
                    source = hit.get("_source", {})
                    prd_nm = source.get("prdNm", "")
                    prd_no = source.get("prdNo", "")
                    price = source.get("dcPrcMc", 0)
                    img_url = source.get("appPrdImgUrl", "")
                    brand_nm = source.get("brandNm", "")
                    
                    try:
                        price_str = f"{int(price):,}원"
                    except (ValueError, TypeError):
                        price_str = f"{price}원"
                        
                    card_html = (
                        f'<a href="https://m.boribori.co.kr/product/{prd_no}" target="_blank" style="text-decoration: none; color: inherit; display: block; width: 100%;">'
                        f'<div class="product-card">'
                        f'<img src="{img_url}" style="width: 44px; height: 44px; border-radius: 4px; object-fit: cover; flex-shrink: 0;">'
                        f'<div style="flex-grow: 1; min-width: 0; display: flex; flex-direction: column; justify-content: space-between; height: 42px; padding: 1px 0; box-sizing: border-box;">'
                        f'<div style="display: flex; justify-content: space-between; align-items: center; line-height: 1; margin-bottom: 2px;">'
                        f'<span style="font-size: 9px; font-weight: 600; color: #888888; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100px;">{brand_nm}</span>'
                        f'<span style="font-size: 10px; font-weight: 800; color: #ff4b4b; white-space: nowrap; flex-shrink: 0;">{price_str}</span>'
                        f'</div>'
                        f'<div style="font-size: 10px; color: #333333; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1;">{prd_nm}</div>'
                        f'</div>'
                        f'</div>'
                        f'</a>'
                    )
                    grid_items_html.append(card_html)
                
                # HTML Grid 구조 생성 및 일괄 렌더링 (구분선과 리스트를 하나의 HTML 블록으로 합쳐 Streamlit 컴포넌트 간 강제 공백 제거)
                grid_html = (
                    f'<div class="divider" style="margin-top: 0px; margin-bottom: 4px;"></div>'
                    f'<div class="product-grid">{"".join(grid_items_html)}</div>'
                )
                st.markdown(grid_html, unsafe_allow_html=True)
                        
            else:
                st.info("검색 결과가 없습니다.")

            # 연관 키워드 영역 (한 줄로 배치하여 공간 절약)
            if rel_kws:
                st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
                badge_htmls = []
                for item in rel_kws:
                    rel_kw = item.get("keyword")
                    if rel_kw:
                        badge_htmls.append(
                            f'<a class="rel-keyword-badge" style="margin: 0 4px 0 0;" href="https://m.boribori.co.kr/search/{rel_kw}" target="_blank">{rel_kw}</a>'
                        )
                
                rel_html = (
                    f'<div style="display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 6px; margin-bottom: 6px;">'
                    f'<span style="font-size: 0.8rem; font-weight: bold; color: #475569; white-space: nowrap;">🔗 연관 검색어:</span>'
                    f'{"".join(badge_htmls)}'
                    f'</div>'
                )
                st.markdown(rel_html, unsafe_allow_html=True)
                
            with st.expander("🛠️ 개발자용 API 정보 확인"):
                st.caption(f"검색 API URL: [이동]({kw_data.get('url')})")
                st.json(kw_data.get("raw_data"))
        
    else:
        st.warning("키워드 목록을 찾을 수 없습니다. 응답 구조를 확인해 주세요.")
        with st.expander("API 응답 원본 확인"):
            st.json(data)
