import streamlit as st
import requests
from elasticsearch import Elasticsearch

# 1. Streamlit Secrets 로드 (.streamlit/secrets.toml 참조)
ES_URL = st.secrets["ELASTICSEARCH"]["ES_URL"]
ES_KEY = st.secrets["ELASTICSEARCH"]["ES_KEY"]

# 인덱스 물리 별칭(Alias) 정의
ES_INDEX_NAME = st.secrets["ELASTICSEARCH"]["ES_IDX"]


# 2. Elasticsearch 연결 싱글톤 캐시 구현
@st.cache_resource
def get_es_client():
    try:
        if not ES_URL:
            st.error("❌ secrets.toml 내에 ELASTICSEARCH.ES_URL 설정이 누락되었습니다.")
            return None
        
        # 최신 elasticsearch SDK 규격에 맞는 연결 인스턴스 반환
        if ES_KEY:
            es = Elasticsearch(hosts=[ES_URL], api_key=ES_KEY)
        else:
            es = Elasticsearch(hosts=[ES_URL])
            
        # 가벼운 ping 체크로 가용성 즉각 판단
        es.info()
        return es
    except Exception as e:
        st.error(f"❌ Elasticsearch 서버 연결에 실패했습니다: {e}\n(ES 인스턴스가 켜져 있는지 확인하십시오)")
        return None


# 3. ES KNN 하이브리드 추천 쿼리 프로세서
def search_direct_es(es, prd_no, limit, base_expr_cd="A6082"):
    """
    es: Elasticsearch 연결 클라이언트
    prd_no: 타겟 기준 상품 번호 (Long/String 대응)
    limit: 추천 개수
    base_expr_cd: 필터링할 기본 판매자 계정 코드 (기본값: "A6082")
    """
    if not es:
        return []
    
    try:
        # 1. 기준 상품의 임베딩 및 ctgr1 추출
        str_prd_no = str(prd_no).strip()
        
        res = es.search(
            index=ES_INDEX_NAME,
            query={"term": {"prd_no": str_prd_no}},
            source=["embedding", "ctgr1"],
            size=1
        )
        
        hits = res.get("hits", {}).get("hits", [])
        if not hits:
            st.warning(f"⚠️ Elasticsearch 인덱스 내에서 해당 상품 번호({str_prd_no})를 찾을 수 없습니다.")
            return []
            
        source_doc = hits[0]["_source"]
        query_vector = source_doc.get("embedding")
        target_ctgr1 = source_doc.get("ctgr1")
        
        if not query_vector:
            st.error("❌ 선택하신 상품에 임베딩 벡터 데이터가 인덱싱되어 있지 않습니다.")
            return []
            
        # 2. KNN 프리필터 하이브리드 조건 구성 (ES 8.x/9.x Spec)
        # sel_acnt_cd 필터와 대카테고리(ctgr1) 매칭 조건을 filter 컨텍스트에 묶음
        filter_conditions = [
            {"term": {"sel_acnt_cd": base_expr_cd}}
        ]
        
        if target_ctgr1:
            filter_conditions.append({"term": {"ctgr1": target_ctgr1}})
            
        knn_query = {
            "field": "embedding",
            "query_vector": query_vector,
            "k": limit,
            "num_candidates": max(limit * 2, 100),
            "filter": filter_conditions
        }
        
        # 3. 하이브리드 벡터 유사 검색 질의 실행
        # Deprecated body 형태를 배제하고 최신 파라미터 규격을 다이렉트로 바인딩
        search_res = es.search(
            index=ES_INDEX_NAME,
            knn=knn_query,
            source=["prd_no", "brand", "sel_prc", "ctgr1", "ctgr2", "ctgr3"],
            size=limit
        )
        
        search_hits = search_res.get("hits", {}).get("hits", [])
        results = []
        for hit in search_hits:
            item = hit["_source"]
            # ES Cosine 유사도 점수 (_score) 맵핑
            item["similarity_score"] = hit.get("_score", 0.0)
            results.append(item)
            
        return results
    except Exception as e:
        st.error(f"ES KNN 하이브리드 검색 처리 중 에러 발생: {e}")
        return []


# --- Streamlit UI 셋업 및 오리지널 스크린샷 완벽 싱크 테마 CSS 주입 ---

st.set_page_config(page_title="유사상품 추천 (ES 하이브리드)", page_icon="🛍️", layout="wide")

# CSS 주입으로 오리지널 스크린샷 룩앤필 재현
# f-string 내 들여쓰기가 Streamlit Markdown 파서에 의해 코드로 인식되어 <pre><code> 블록이 노출되는 것을 막기 위해,
# CSS 문자열에서 공백과 탭 들여쓰기를 원천 제거한 단일 문자열 결합 구조를 준수합니다.
css_style = (
"<style>"
"@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');"
"html, body, [data-testid='stAppViewContainer'], [data-testid='stApp'] {"
"font-family: 'Noto Sans KR', sans-serif !important;"
"background-color: #ffffff !important;"
"color: #1e293b !important;"
"}"
"[data-testid='stHeader'] {"
"background-color: rgba(255, 255, 255, 0.8) !important;"
"backdrop-filter: blur(8px) !important;"
"}"
"div[data-testid='stVerticalBlockBorderWrapper']:has(.is-search-card) {"
"background-color: transparent !important;"
"border: none !important;"
"border-radius: 0 !important;"
"padding: 0 !important;"
"color: #1e293b !important;"
"box-shadow: none !important;"
"}"
".search-card-title {"
"font-size: 14.5px !important;"
"font-weight: 500 !important;"
"color: #1e293b !important;"
"margin-bottom: 12px !important;"
"line-height: 1.5 !important;"
"}"
"div[data-testid='stVerticalBlockBorderWrapper']:has(.is-search-card) div[data-testid='stTextInput'] input {"
"background-color: #f1f5f9 !important;"
"color: #1e293b !important;"
"border: 1px solid #e2e8f0 !important;"
"border-radius: 8px !important;"
"padding: 12px 16px !important;"
"font-size: 15px !important;"
"font-weight: 500 !important;"
"width: 100% !important;"
"}"
"div[data-testid='stVerticalBlockBorderWrapper']:has(.is-search-card) div[data-testid='stTextInput'] input:focus {"
"border-color: #ff4b4b !important;"
"box-shadow: 0 0 0 1px #ff4b4b !important;"
"}"
"div[data-testid='stVerticalBlockBorderWrapper']:has(.is-search-card) button[data-testid='stBaseButton-primary'] {"
"background-color: #ff4b4b !important;"
"color: #ffffff !important;"
"border: none !important;"
"border-radius: 8px !important;"
"padding: 12px 20px !important;"
"font-weight: bold !important;"
"font-size: 15px !important;"
"transition: all 0.2s ease !important;"
"width: 100% !important;"
"box-shadow: 0 4px 10px rgba(255, 75, 75, 0.15) !important;"
"}"
"div[data-testid='stVerticalBlockBorderWrapper']:has(.is-search-card) button[data-testid='stBaseButton-primary']:hover {"
"background-color: #ff3333 !important;"
"transform: translateY(-1px) !important;"
"}"
"div[data-testid='stVerticalBlockBorderWrapper']:has(.is-target-card) {"
"background-color: transparent !important;"
"border: none !important;"
"border-radius: 0 !important;"
"padding: 0 !important;"
"box-shadow: none !important;"
"}"
".target-product-card h2 {"
"font-size: 22px !important;"
"font-weight: 700 !important;"
"color: #1e293b !important;"
"margin: 0 0 16px 0 !important;"
"display: flex !important;"
"align-items: center !important;"
"gap: 8px !important;"
"}"
".target-product-title-text {"
"font-size: 24px !important;"
"font-weight: 700 !important;"
"color: #1e293b !important;"
"line-height: 1.35 !important;"
"margin-bottom: 20px !important;"
"}"
".target-product-bullets {"
"font-size: 14.5px !important;"
"color: #334155 !important;"
"line-height: 2.0 !important;"
"font-weight: 500 !important;"
"}"
".recommended-grid-card {"
"background-color: #ffffff !important;"
"border: 1px solid #e2e8f0 !important;"
"border-radius: 12px !important;"
"padding: 12px !important;"
"box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02) !important;"
"height: 385px !important;"
"display: flex !important;"
"flex-direction: column !important;"
"transition: transform 0.2s ease, box-shadow 0.2s ease !important;"
"box-sizing: border-box !important;"
"overflow: hidden !important;"
"}"
".recommended-grid-card:hover {"
"transform: translateY(-4px) !important;"
"box-shadow: 0 8px 18px rgba(0, 0, 0, 0.06) !important;"
"}"
".recommended-image-container {"
"position: relative !important;"
"width: 100% !important;"
"padding-top: 110% !important;"
"border-radius: 8px !important;"
"overflow: hidden !important;"
"background-color: #f8fafc !important;"
"margin-bottom: 8px !important;"
"box-sizing: border-box !important;"
"}"
".recommended-image-container img {"
"position: absolute !important;"
"top: 0 !important;"
"left: 0 !important;"
"width: 100% !important;"
"height: 100% !important;"
"object-fit: cover !important;"
"}"
".recommended-title-link {"
"font-size: 11.5px !important;"
"font-weight: 700 !important;"
"color: #0066cc !important;"
"text-decoration: none !important;"
"margin-bottom: 6px !important;"
"line-height: 1.4 !important;"
"overflow: hidden !important;"
"text-overflow: ellipsis !important;"
"display: -webkit-box !important;"
"-webkit-line-clamp: 2 !important;"
"-webkit-box-orient: vertical !important;"
"height: 32px !important;"
"box-sizing: border-box !important;"
"}"
".recommended-title-link:hover {"
"text-decoration: underline !important;"
"}"
".recommended-bullets {"
"font-size: 10.5px !important;"
"color: #555555 !important;"
"line-height: 1.5 !important;"
"margin-bottom: 6px !important;"
"height: 70px !important;"
"overflow: hidden !important;"
"display: flex !important;"
"flex-direction: column !important;"
"justify-content: flex-start !important;"
"box-sizing: border-box !important;"
"}"
".bullet-item {"
"white-space: nowrap !important;"
"overflow: hidden !important;"
"text-overflow: ellipsis !important;"
"width: 100% !important;"
"}"
".recommended-price {"
"font-size: 13px !important;"
"font-weight: 800 !important;"
"color: #ff4b4b !important;"
"margin-top: auto !important;"
"padding-top: 2px !important;"
"box-sizing: border-box !important;"
"}"
".recommended-pill-badge {"
"background-color: #ebf5ff !important;"
"color: #0066cc !important;"
"border-radius: 20px !important;"
"padding: 2px 8px !important;"
"font-size: 10px !important;"
"font-weight: bold !important;"
"display: inline-block !important;"
"margin-top: 6px !important;"
"width: fit-content !important;"
"box-sizing: border-box !important;"
"}"
"div[data-testid='stVerticalBlock'] > div[style*='border'] {"
"border: none !important;"
"box-shadow: none !important;"
"padding: 0 !important;"
"background-color: transparent !important;"
"}"
"div[data-testid='stTextInput'] label {"
"display: none !important;"
"}"
"</style>"
)
st.markdown(css_style, unsafe_allow_html=True)
 

# --- 2. 메인 화면 헤더 및 타이틀 ---
st.markdown("<h2 style='color: #2c3e50; font-weight: 700; margin-top: 5px; margin-bottom: 25px;'>유사상품 추천 ES (LF사입상품)</h2>", unsafe_allow_html=True)

# ES 클라이언트 싱글톤 객체 획득
es_client = get_es_client()

# 추천 표출 개수 상한 (고정 80개)
DEFAULT_LIMIT = 120


@st.cache_data(show_spinner=False, ttl=3600)
def get_product_detail(prd_no):
    """외부 하프클럽 실시간 상품 메타 정보 조회 API 연동"""
    try:
        params = {"keyword": prd_no, "siteCd": 1, "device": "pc"}
        response = requests.get("http://hapix.halfclub.com/searches/prdList/", params=params, timeout=3.0)
        if response.status_code == 200:
            data = response.json()
            hits = data.get("data", {}).get("result", {}).get("hits", {}).get("hits", [])
            if hits:
                return hits[0].get("_source", {})
    except Exception:
        pass
    return {}


# URL 쿼리 파라미터에서 prd_no 추출
query_params = st.query_params
url_prd_no = query_params.get("prd_no", "")

# 쿼리 파라미터가 유효할 경우, session_state 검색 트리거 자동 주입
if url_prd_no and "url_processed" not in st.session_state:
    st.session_state['searched'] = True
    st.session_state['url_processed'] = True

prd_no_input_val = url_prd_no or "413157091"

# --- 3. 🎯 상단 레이아웃 (3열 배치: 다크 검색카드, 이미지, 기준 상품 상세) ---
top_cols = st.columns([3.2, 1.8, 5.0])

with top_cols[0]:
    with st.container(border=True):
        st.markdown("<div class='is-search-card'></div>", unsafe_allow_html=True)
        st.markdown("<div class='search-card-title'>🎯 상품 번호 (prd_no) 입력</div>", unsafe_allow_html=True)
        
        # st.text_input 렌더링
        prd_no_input = st.text_input(
            "상품 번호",
            value=prd_no_input_val,
            placeholder="예: 413157091"
        )
        
        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
        
        # st.button 렌더링
        search_button = st.button("유사 상품 찾기 🚀", type="primary", use_container_width=True)

# 검색 실행 플래그
searched = False
if prd_no_input.strip() and (search_button or st.session_state.get('searched')):
    st.session_state['searched'] = True
    searched = True

with top_cols[1]:
    if searched:
        target_info = get_product_detail(prd_no_input.strip())
        if target_info:
            img_url = target_info.get("appPrdImgUrl") or target_info.get("prdImgUrl")
            if img_url and img_url.startswith("//"):
                img_url = "https:" + img_url
            
            if img_url:
                st.markdown(
                    f"<div style='border-radius: 12px; overflow: hidden; background-color: #ffffff; border: 1px solid #e2e8f0; height: 295px; width: 100%; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 12px rgba(0,0,0,0.02);'>"
                    f"<img src='{img_url}' style='width: 100%; height: 100%; object-fit: cover;' />"
                    f"</div>",
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    "<div style='border-radius: 12px; height: 295px; width: 100%; background: #ffffff; border: 1px solid #e2e8f0; display: flex; align-items: center; justify-content: center; color: #94a3b8; font-size: 13px;'>이미지 없음</div>",
                    unsafe_allow_html=True
                )

with top_cols[2]:
    if searched:
        if target_info:
            api_prd_nm = target_info.get("prdNm", "상품명 없음")
            api_brand = target_info.get("brandNm", "알 수 없음")
            api_sel_prc = target_info.get("selPrc", 0)
            api_ctgr = f"{target_info.get('dpCtgrNm1','') or ''} > {target_info.get('dpCtgrNm2','') or ''} > {target_info.get('dpCtgrNm3','') or ''}".strip(" >")
            
            with st.container(border=True):
                st.markdown("<div class='is-target-card'></div>", unsafe_allow_html=True)
                st.markdown(
                    f"<div class='target-product-card'>"
                    f"<h3>🎯 기준 상품 상세</h3>"
                    f"<a href='http://www.halfclub.com/product/{target_info.get('prdNo', prd_no_input.strip())}' target='_blank' class='target-product-title-link'>{api_prd_nm}</a>"
                    f"<div class='target-product-bullets'>"
                    f"• 상품 번호 : {target_info.get('prdNo', prd_no_input.strip())}<br>"
                    f"• 카테고리 : {api_ctgr}<br>"
                    f"• 소속 브랜드 : {api_brand}<br>"
                    f"• 실시간 판매가 : <span style='font-weight: bold; color: #ff4b4b;'>{api_sel_prc:,}원</span>"
                    f"</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
        else:
            with st.container(border=True):
                st.markdown("<div class='is-target-card'></div>", unsafe_allow_html=True)
                st.markdown(
                    f"<div class='target-product-card' style='display: flex; align-items: center; justify-content: center; height: 247px;'>"
                    f"<div style='text-align: center; color: #7f8c8d;'>"
                    f"<span style='font-size: 24px;'>⚠️</span><br>"
                    f"<span style='font-size: 13px; font-weight: bold; margin-top: 8px; display: inline-block;'>API 서버로부터 기준 상품 정보를 가져오지 못했습니다.</span>"
                    f"</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
    else:
        with st.container(border=True):
            st.markdown("<div class='is-target-card'></div>", unsafe_allow_html=True)
            st.markdown(
                f"<div class='target-product-card' style='display: flex; align-items: center; justify-content: center; height: 247px;'>"
                f"<div style='text-align: center; color: #95a5a6;'>"
                f"<span style='font-size: 28px;'>🔍</span><br>"
                f"<span style='font-size: 13px; font-weight: bold; margin-top: 8px; display: inline-block;'>조회할 상품 번호를 입력한 뒤 유사 상품 찾기를 실행하십시오.</span>"
                f"</div>"
                f"</div>",
                unsafe_allow_html=True
            )


# --- 4. 📊 유사 추천 결과 표출 ---
if searched:
    st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
    
    # Elasticsearch 하이브리드 KNN 추천 서칭 작동
    with st.spinner("⚡ Elasticsearch 하이브리드 KNN 클러스터 쿼리 실행 중..."):
        meta_h = search_direct_es(
            es_client, 
            prd_no_input.strip(), 
            DEFAULT_LIMIT,
            base_expr_cd="A6082"
        )
        
    st.markdown(f"<h3 style='color: #2c3e50; font-weight: 700; margin-bottom: 20px;'>📚 유사 추천 결과 ({len(meta_h)}개)</h3>", unsafe_allow_html=True)
    
    if meta_h:
        COLS_PER_ROW = 8
        for row_start in range(0, len(meta_h), COLS_PER_ROW):
            cols = st.columns(COLS_PER_ROW)
            row_items = meta_h[row_start:row_start + COLS_PER_ROW]
            
            for idx, item in enumerate(row_items):
                es_prd_no = item.get("prd_no", "")
                detail = get_product_detail(es_prd_no)
                
                img_url = detail.get("appPrdImgUrl") or detail.get("prdImgUrl")
                if img_url and img_url.startswith("//"):
                    img_url = "https:" + img_url
                
                score = item.get("similarity_score", 0.0)
                
                api_prd_no = detail.get("prdNo", es_prd_no)
                api_prd_nm = detail.get("prdNm", "(상품명 미확인)")
                api_brand = detail.get("brandNm", "(브랜드 없음)")
                api_sel_prc = detail.get("selPrc", 0)
                api_ctgr = f"{detail.get('dpCtgrNm1','') or ''}>{detail.get('dpCtgrNm2','') or ''}>{detail.get('dpCtgrNm3','') or ''}".strip(">")
                
                es_ctgr = f"{item.get('ctgr1','') or ''}>{item.get('ctgr2','') or ''}>{item.get('ctgr3','') or ''}".strip(">")
                diff_ctgr_html = ""
                if es_ctgr and api_ctgr != es_ctgr:
                    diff_ctgr_html = f"<div class='bullet-item' style='color:#ea580c; font-weight:bold;'>📊 {es_ctgr}</div>"
                
                is_target = str(es_prd_no).strip() == str(prd_no_input).strip()
                if is_target:
                    score_html = f"• 유사도: {score:.4f} <span style='color:#ff4b4b; font-weight:bold;'>(기준)</span>"
                else:
                    score_html = f"• 유사도: {score:.4f}"
                
                with cols[idx]:
                    img_tag = f"<div class='recommended-image-container'><img src='{img_url}'/></div>" if img_url else "<div class='recommended-image-container'><div style='position:absolute;top:0;left:0;width:100%;height:100%;display:flex;align-items:center;justify-content:center;background:#f8fafc;color:#94a3b8;font-size:11px;'>이미지 없음</div></div>"
                    
                    html_content = (
                        f"<div class='recommended-grid-card'>"
                        f"{img_tag}"
                        f"<a href='http://www.halfclub.com/product/{api_prd_no}' target='_blank' class='recommended-title-link'>{api_prd_nm} 🔗</a>"
                        f"<div class='recommended-bullets'>"
                        f"<div class='bullet-item'>• 번호: {api_prd_no}</div>"
                        f"<div class='bullet-item'>• 브랜드: {api_brand}</div>"
                        f"<div class='bullet-item'>• 카테고리: {api_ctgr}</div>"
                        f"{diff_ctgr_html}"
                        f"</div>"
                        f"<div class='recommended-price'>{api_sel_prc:,}원</div>"
                        f"<div class='recommended-pill-badge'>{score_html}</div>"
                        f"</div>"
                    )
                    st.markdown(html_content, unsafe_allow_html=True)
    else:
        st.info("조건에 매칭되는 유사 추천 상품 정보가 존재하지 않습니다.")

elif not prd_no_input.strip() and search_button:
    st.warning("⚠️ 상품 번호를 입력해 주세요.")
