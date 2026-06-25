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
    /* 여백 조정 (상단 헤더 고려) */
    .block-container {
        padding-top: 4.5rem !important;
        padding-bottom: 1rem !important;
    }
    .keyword-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #1e293b;
    }
    .product-card {
        background-color: white;
        padding: 6px;
        border-radius: 6px;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.03);
        margin-bottom: 8px;
        transition: transform 0.2s, box-shadow 0.2s;
        border: 1px solid #f1f5f9;
        text-align: left;
    }
    .product-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.06);
    }
    .brand-text {
        font-size: 0.65em;
        font-weight: 600;
        color: #888888;
        margin-bottom: 1px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .price-text {
        font-size: 0.85em;
        font-weight: 800;
        color: #ff4b4b;
        margin: 2px 0;
    }
    .title-text {
        font-size: 0.7em;
        color: #333333;
        font-weight: 500;
        overflow: hidden;
        text-overflow: ellipsis;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        height: 2.6em;
        line-height: 1.3;
    }
    .divider {
        margin: 10px 0;
        border-bottom: 1px solid #e2e8f0;
    }
    </style>
""", unsafe_allow_html=True)

API_URL = "https://apix.boribori.co.kr/searches/popularKeyword/?countryCd=001&langCd=001&siteCd=2&deviceCd=002&mandM=b_boribori"

@st.cache_data(ttl=300)  # 인기 검색어 API 캐싱 (5분)
def fetch_popular_keywords():
    try:
        response = requests.get(API_URL, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"인기 검색어 API 호출 중 오류가 발생했습니다: {e}")
        return None

# 모든 키워드의 상품 정보를 한 번에 불러와 캐싱하는 함수
@st.cache_data(ttl=300)  # 상품 정보 일괄 캐싱 (5분)
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
            all_data[kw] = {
                "hits": hits,
                "url": resp.url,
                "raw_data": search_data
            }
        except Exception as e:
            all_data[kw] = {
                "hits": [],
                "url": "",
                "raw_data": {},
                "error": str(e)
            }
    return all_data

# 세션 상태를 활용한 캐싱 (Rerun 시 스피너 번쩍임 방지)
if "popular_keywords_data" not in st.session_state:
    with st.spinner("실시간 인기 검색어를 불러오는 중..."):
        st.session_state.popular_keywords_data = fetch_popular_keywords()

data = st.session_state.popular_keywords_data

if data:
    keywords = []
    
    # 키워드 추출 헬퍼 함수
    def extract_keywords_from_list(items):
        return [item.get("keyword") for item in items if isinstance(item, dict) and item.get("keyword")]

    # 응답 JSON 구조 파싱
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
        top_keywords = keywords[:10]  # 상위 10개 키워드 타겟팅
        
        # 첫 진입 또는 캐시 만료 시에만 상품 정보를 가져오고 세션에 보관 (이후 탭 전환 시 스피너 완전 패스)
        if "products_cache" not in st.session_state:
            with st.spinner("전체 인기 키워드의 상품 정보를 일괄 사전 로드 중입니다. 잠시만 기다려주세요..."):
                st.session_state.products_cache = fetch_all_products_data(top_keywords)
        
        products_cache = st.session_state.products_cache
        
        # 세션 상태 초기화
        if "selected_keyword" not in st.session_state or st.session_state.selected_keyword not in top_keywords:
            st.session_state.selected_keyword = top_keywords[0]

        # 버튼 클릭 시 즉시 이전 리스트를 비우기 위한 콜백 함수
        def select_keyword_callback(kw):
            st.session_state.selected_keyword = kw
            st.session_state.cleared_state = True

        # st.subheader("📊 실시간 인기 검색어 순위 (Top 10)")
        
        # 10열 그리드로 인기 검색어 버튼을 최상단에 1줄로 배치
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
        
        # 탭 전환 시 화면 지우기 구현: cleared_state가 True이면 지워진 상태로 즉시 한 번 렌더링하고 다시 Rerun
        if st.session_state.get("cleared_state", False):
            st.session_state.cleared_state = False
            st.info("새로운 상품 목록을 불러오는 중...")
            st.rerun()

        # 선택된 키워드 및 해당 상품 영역
        selected_kw = st.session_state.selected_keyword
        
        col_title, col_link = st.columns([5, 1])
        with col_title:
            st.markdown(f'<div class="keyword-title">"{selected_kw}" 키워드 검색</div>', unsafe_allow_html=True)
        with col_link:
            st.link_button(f"🔗 보리 검색", f"https://m.boribori.co.kr/search/{selected_kw}", use_container_width=True)
            
        # 사전 로드된 상품 정보 가져오기 (딜레이 없음)
        kw_data = products_cache.get(selected_kw, {"hits": [], "url": "", "raw_data": {}})
        hits = kw_data.get("hits", [])
        
        if "error" in kw_data:
            st.error(f"상품 정보를 불러오는 중 오류가 발생했습니다: {kw_data['error']}")
        else:
            if hits:
                # 10열 그리드로 변경하여 초고밀도 화면 구성
                cols = st.columns(10)
                for idx, hit in enumerate(hits):
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
                        
                    with cols[idx % 10]:
                        # 전체 카드를 클릭 가능하게 <a> 태그로 감싸고, 불필요한 상품 보기 텍스트 링크 제거
                        st.markdown(f"""
                            <a href="https://m.boribori.co.kr/product/{prd_no}" target="_blank" style="text-decoration: none; color: inherit;">
                                <div class="product-card">
                                    <img src="{img_url}" style="width:100%; border-radius:6px; margin-bottom:6px; aspect-ratio: 1/1; object-fit: cover;">
                                    <div class="brand-text">{brand_nm}</div>
                                    <div class="title-text">{prd_nm}</div>
                                    <div class="price-text">{price_str}</div>
                                </div>
                            </a>
                        """, unsafe_allow_html=True)
                        
            else:
                st.info("검색 결과가 없습니다.")
                
            with st.expander("🛠️ 개발자용 API 정보 확인"):
                st.caption(f"검색 API URL: [이동]({kw_data.get('url')})")
                st.json(kw_data.get("raw_data"))
        
    else:
        st.warning("키워드 목록을 찾을 수 없습니다. 응답 구조를 확인해 주세요.")
        with st.expander("API 응답 원본 확인"):
            st.json(data)
