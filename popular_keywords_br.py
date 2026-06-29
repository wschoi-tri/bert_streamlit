import streamlit as st
import requests

# 페이지 설정
st.set_page_config(
    page_title="보리 인기 키워드",
    layout="wide"
)

# 커스텀 CSS 적용으로 프리미엄 스타일 구현
st.markdown("""
    <style>
    /* 여백 최소화 */
    .block-container {
        padding-top: 3.5rem !important;
        padding-bottom: 1rem !important;
    }
    /* 버튼 컴팩트화 */
    div.stButton > button {
        padding: 4px 6px !important;
        font-size: 0.75rem !important;
        height: auto !important;
    }
    .keyword-title {
        font-size: 1.0rem;
        font-weight: 700;
        color: #1e293b;
    }
    .product-card {
        background-color: white;
        padding: 5px;
        border-radius: 6px;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.02);
        margin-bottom: 5px;
        transition: transform 0.2s;
        border: 1px solid #f1f5f9;
        text-align: left;
    }
    .product-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.05);
    }
    .brand-text {
        font-size: 0.6em;
        font-weight: 600;
        color: #888888;
        margin-bottom: 1px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .price-text {
        font-size: 0.8em;
        font-weight: 800;
        color: #ff4b4b;
        margin: 1px 0;
    }
    .title-text {
        font-size: 0.65em;
        color: #333333;
        font-weight: 500;
        overflow: hidden;
        text-overflow: ellipsis;
        display: -webkit-box;
        -webkit-line-clamp: 1;
        -webkit-box-orient: vertical;
        height: 1.3em;
        line-height: 1.3;
    }
    .divider {
        margin: 8px 0;
        border-bottom: 1px solid #e2e8f0;
    }
    /* 연관 키워드 배지 */
    .rel-keyword-badge {
        display: inline-block;
        background-color: #f1f5f9;
        color: #475569;
        padding: 2px 6px;
        border-radius: 4px;
        margin-right: 5px;
        margin-bottom: 5px;
        font-size: 0.75em;
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

@st.cache_data(ttl=300)
def fetch_all_products_data(keywords_list):
    all_data = {}
    search_api_url = "https://apix.boribori.co.kr/searches/prdList/"
    for kw in keywords_list:
        params = {
            "keyword": kw,
            "limit": "0,40",
            "sortSeq": "12",
            "siteCd": "2",
            "device": "mc",
        }
        try:
            resp = requests.get(search_api_url, params=params, timeout=15)
            resp.raise_for_status()
            search_data = resp.json()
            hits = search_data.get("data", {}).get("result", {}).get("hits", {}).get("hits", [])
            rel_keywords = search_data.get("data", {}).get("rel_keywords", [])
            all_data[kw] = {
                "hits": hits,
                "rel_keywords": rel_keywords,
                "url": resp.url,
                "raw_data": search_data
            }
        except Exception as e:
            all_data[kw] = {
                "hits": [],
                "rel_keywords": [],
                "url": "",
                "raw_data": {},
                "error": str(e)
            }
    return all_data

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
        
        # 구버전 캐시 데이터 자동 갱신 (마이그레이션 방지)
        if "products_cache" in st.session_state and st.session_state.products_cache:
            first_val = list(st.session_state.products_cache.values())[0]
            if "rel_keywords" not in first_val:
                del st.session_state.products_cache

        if "products_cache" not in st.session_state:
            with st.spinner("전체 인기 키워드의 상품 정보를 일괄 사전 로드 중입니다..."):
                st.session_state.products_cache = fetch_all_products_data(top_keywords)
        
        products_cache = st.session_state.products_cache
        
        # 세션 상태 초기화
        if "selected_keyword" not in st.session_state or st.session_state.selected_keyword not in top_keywords:
            st.session_state.selected_keyword = top_keywords[0]

        selected_kw = st.session_state.selected_keyword

        # 버튼 클릭 시 즉시 탭 상태 업데이트 콜백
        def select_keyword_callback(kw):
            st.session_state.selected_keyword = kw

        # 상단 타이틀 및 현황을 한 줄로 모아 공간 절약
        col_head1, col_head2, col_head3 = st.columns([4, 4, 2])
        with col_head1:
            st.markdown(f'<div class="keyword-title" style="margin-top: 6px;">📊 인기 검색어 결과 (Top 10)</div>', unsafe_allow_html=True)
        with col_head2:
            st.markdown(f'<div class="keyword-title" style="margin-top: 6px; text-align: center;">🛍️ "{selected_kw}" 검색 결과</div>', unsafe_allow_html=True)
        with col_head3:
            st.link_button(f"🔗 보리 검색 이동", f"https://m.boribori.co.kr/search/{selected_kw}", use_container_width=True)

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

        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
            
        # 사전 로드된 상품 정보 가져오기 (딜레이 없음)
        kw_data = products_cache.get(selected_kw, {"hits": [], "rel_keywords": [], "url": "", "raw_data": {}})
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
                        f'<a href="https://m.boribori.co.kr/product/{prd_no}" target="_blank" style="text-decoration: none; color: inherit;">'
                        f'<div class="product-card">'
                        f'<img src="{img_url}" style="width:100%; height:95px; border-radius:6px; margin-bottom:4px; object-fit: cover;">'
                        f'<div class="brand-text">{brand_nm}</div>'
                        f'<div class="title-text">{prd_nm}</div>'
                        f'<div class="price-text">{price_str}</div>'
                        f'</div>'
                        f'</a>'
                    )
                    grid_items_html.append(card_html)
                
                # HTML Grid 구조 생성 및 일괄 렌더링 (들여쓰기가 없는 단일 텍스트 구조로 생성하여 마크다운 코드블록 처리 회피)
                grid_html = f'<div style="display: grid; grid-template-columns: repeat(10, 1fr); gap: 8px;">{"".join(grid_items_html)}</div>'
                st.markdown(grid_html, unsafe_allow_html=True)
                        
            else:
                st.info("검색 결과가 없습니다.")

            # 연관 키워드 영역
            if rel_kws:
                st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
                st.markdown("<span style='font-size:0.85rem; font-weight:bold; color:#475569;'>🔗 연관 검색어:</span>", unsafe_allow_html=True)
                badge_htmls = []
                for item in rel_kws:
                    rel_kw = item.get("keyword")
                    if rel_kw:
                        badge_htmls.append(
                            f'<a class="rel-keyword-badge" href="https://m.boribori.co.kr/search/{rel_kw}" target="_blank">{rel_kw}</a>'
                        )
                st.markdown("".join(badge_htmls), unsafe_allow_html=True)
                
            with st.expander("🛠️ 개발자용 API 정보 확인"):
                st.caption(f"검색 API URL: [이동]({kw_data.get('url')})")
                st.json(kw_data.get("raw_data"))
        
    else:
        st.warning("키워드 목록을 찾을 수 없습니다. 응답 구조를 확인해 주세요.")
        with st.expander("API 응답 원본 확인"):
            st.json(data)
