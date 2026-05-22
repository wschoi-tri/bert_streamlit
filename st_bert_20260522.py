import streamlit as st
import os
import requests
from elasticsearch import Elasticsearch
from dotenv import load_dotenv

# 1. 환경 변수 로드 (.env 및 Streamlit Secrets 호환 지원)
base_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(base_dir, "..", ".."))
env_path = os.path.join(project_root, ".env")
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)

# ES URL 및 API Key 로드
ES_URL = os.getenv("ES_URL")
ES_KEY = os.getenv("ES_KEY")

if not ES_URL and "ELASTICSEARCH" in st.secrets:
    ES_URL = st.secrets["ELASTICSEARCH"].get("ES_URL")
    ES_KEY = st.secrets["ELASTICSEARCH"].get("ES_KEY")

# 인덱스 물리 별칭(Alias) 정의
ES_INDEX_NAME = "rcm_hf_prd_meta_vec"


# 2. Elasticsearch 연결 싱글톤 캐시 구현
@st.cache_resource
def get_es_client():
    try:
        if not ES_URL:
            st.error("❌ ES_URL 환경 변수가 누락되었습니다. .env 파일이나 Streamlit Secrets를 확인해 주세요.")
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


# --- Streamlit UI 셋업 및 고급 디자인 스타일링 ---

st.set_page_config(page_title="유사상품 추천 (ES 하이브리드)", page_icon="🛍️", layout="wide")

# 프리미엄 HSL 색감 및 Glassmorphism 디자인 주입
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=Noto+Sans+KR:wght@300;400;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Outfit', 'Noto Sans KR', sans-serif;
        background-color: #0b0f17;
        color: #e2e8f0;
    }
    
    /* 로고 및 메인 타이틀 장식 */
    .main-title {
        background: linear-gradient(135deg, #74b9ff, #0984e3);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 2.2em;
        margin-bottom: 20px;
    }
    
    /* Glassmorphism 메인 프레임 카드 */
    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        background: rgba(17, 24, 39, 0.7) !important;
        border-radius: 18px !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        padding: 18px !important;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5) !important;
        backdrop-filter: blur(8px) !important;
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
    }
    
    div[data-testid="stVerticalBlock"] > div[style*="border"]:hover {
        transform: translateY(-4px) !important;
        border-color: rgba(9, 132, 227, 0.5) !important;
        box-shadow: 0 15px 35px rgba(9, 132, 227, 0.2) !important;
    }
    
    /* 썸네일 둥글기 처리 및 줌 효과 */
    img {
        border-radius: 12px !important;
        transition: transform 0.4s ease !important;
    }
    
    img:hover {
        transform: scale(1.04) !important;
    }
    
    /* 프리미엄 텍스트 및 태그 스타일 */
    .prd-name {
        font-size: 13px;
        font-weight: 600;
        color: #f1f2f6;
        height: 2.4em;
        overflow: hidden;
        text-overflow: ellipsis;
        margin-bottom: 8px;
        line-height: 1.3;
    }
    
    .prd-link {
        text-decoration: none;
        color: #74b9ff;
        transition: color 0.2s;
    }
    
    .prd-link:hover {
        color: #0984e3;
        text-decoration: underline;
    }
    
    /* 배지 데코레이터 */
    .tag-badge {
        display: inline-block;
        padding: 2px 7px;
        font-size: 10.5px;
        border-radius: 5px;
        margin-right: 4px;
        margin-bottom: 5px;
        font-weight: bold;
    }
    .badge-es {
        background-color: rgba(9, 132, 227, 0.15);
        color: #74b9ff;
        border: 1px solid rgba(9, 132, 227, 0.3);
    }
    .badge-sim {
        background-color: rgba(0, 184, 148, 0.15);
        color: #55efc4;
        border: 1px solid rgba(0, 184, 148, 0.3);
    }
</style>
""", unsafe_allow_html=True)

st.markdown("<div class='main-title'>🛍️ 하이브리드 KNN 유사 상품 추천 (Elasticsearch)</div>", unsafe_allow_html=True)

# ES 클라이언트 초기 로드
es_client = get_es_client()

# 추천 표출 개수 상한 설정
DEFAULT_LIMIT = 80


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


def display_product_grid(data, prd_no_input, score_label="유사도"):
    """결과 데이터를 8열의 품격 있는 미디어 카스케이드 형태로 그리드 렌더링"""
    if not data:
        st.info("조건에 매칭되는 유사 추천 상품 정보가 존재하지 않습니다.")
        return

    COLS_PER_ROW = 8
    for row_start in range(0, len(data), COLS_PER_ROW):
        cols = st.columns(COLS_PER_ROW)
        row_items = data[row_start:row_start + COLS_PER_ROW]
        
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
            api_ctgr = f"{detail.get('dpCtgrNm1','')}>{detail.get('dpCtgrNm2','')}>{detail.get('dpCtgrNm3','')}".strip(">")
            
            # ES 인덱스 정보와 API 간 카테고리 디싱크 발생 시 디버깅 태그 표출
            es_ctgr = f"{item.get('ctgr1','')}>{item.get('ctgr2','')}>{item.get('ctgr3','')}".strip(">")
            diff_ctgr_html = ""
            if es_ctgr and api_ctgr != es_ctgr:
                diff_ctgr_html = f"<div style='color:#e67e22; font-size:10px; font-weight:bold; margin-top:2px;'>📊 {es_ctgr}</div>"

            score_html = f"{score:.4f}"
            if str(es_prd_no).strip() == str(prd_no_input).strip():
                score_html += " <span style='color:#e74c3c; font-weight:bold;'>(검색 기준)</span>"

            with cols[idx]:
                with st.container(border=True):
                    if img_url:
                        st.image(img_url, use_column_width=True)
                    else:
                        st.write("이미지 없음")
                        
                    html_content = (
                        f"<div class='prd-name'>"
                        f"<a href='http://www.halfclub.com/product/{api_prd_no}' class='prd-link' target='_blank'>{api_prd_nm} 🔗</a>"
                        f"</div>"
                        f"<div style='font-size:11px; color:#a4b0be; line-height:1.4;'>"
                        f"• 번호: {api_prd_no}<br>"
                        f"• 브랜드: {api_brand}<br>"
                        f"• API 카테고리:<br>"
                        f"  <span style='color:#74b9ff;'>{api_ctgr}</span>"
                        f"{diff_ctgr_html}"
                        f"<div style='color:#ff7675; font-weight:bold; font-size:12px; margin-top:4px;'>• 가격: {api_sel_prc:,}원</div>"
                        f"</div>"
                        f"<div style='border-top:1px dashed rgba(255,255,255,0.1); margin:7px 0;'></div>"
                        f"<div style='font-size:11px; color:#55efc4; font-weight:600;'>"
                        f"• {score_label}: {score_html}"
                        f"</div>"
                    )
                    st.markdown(html_content, unsafe_allow_html=True)


# URL 쿼리 파라미터에서 prd_no 추출
query_params = st.query_params
url_prd_no = query_params.get("prd_no", "")

# 쿼리 파라미터가 유효할 경우, session_state 검색 트리거 자동 주입
if url_prd_no and "url_processed" not in st.session_state:
    st.session_state['searched'] = True
    st.session_state['url_processed'] = True

# 상단 입력 폼 레이아웃
form_col1, form_col2 = st.columns([1.5, 4.5])

with form_col1:
    prd_no_input = st.text_input(
        "🎯 상품 번호 (prd_no) 입력",
        value=url_prd_no or "413157091",
        placeholder="예: 413157091"
    )
    search_button = st.button("유사 상품 찾기 🚀", type="primary", use_container_width=True)

if prd_no_input.strip() and (search_button or st.session_state.get('searched')):
    st.session_state['searched'] = True
    
    target_info = get_product_detail(prd_no_input.strip())
    
    with form_col2:
        if target_info:
            target_cols = st.columns([1, 5])
            with target_cols[0]:
                img_url = target_info.get("appPrdImgUrl") or target_info.get("prdImgUrl")
                if img_url:
                    if img_url.startswith("//"):
                        img_url = "https:" + img_url
                    st.image(img_url, use_column_width=True)
                else:
                    st.markdown("*(이미지 없음)*")
            with target_cols[1]:
                api_ctgr = f"{target_info.get('dpCtgrNm1','')} > {target_info.get('dpCtgrNm2','')} > {target_info.get('dpCtgrNm3','')}".strip(" >")
                st.markdown(f"""
                <h3 style='margin: 0 0 8px 0; color: #ffffff;'>{target_info.get("prdNm", "상품명 없음")}</h3>
                <div style='line-height: 1.7; font-size: 13.5px; color:#cbd5e1;'>
                <b>기준 상품 번호:</b> {target_info.get('prdNo', prd_no_input.strip())}<br>
                <b>카테고리 경로:</b> {api_ctgr}<br>
                <b>소속 브랜드:</b> {target_info.get('brandNm', '알 수 없음')}<br>
                <b>실시간 판매가:</b> <span style='font-size:15px; color:#ff7675; font-weight:bold;'>{target_info.get('selPrc', 0):,}원</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("💡 실시간 상세 API 서버로부터 기준 상품 메타 데이터를 로드하지 못했으나, 인덱스 내 검색을 강행합니다.")

    st.markdown("<hr style='border-color: rgba(255,255,255,0.08); margin: 20px 0;'>", unsafe_allow_html=True)

    # 4. Elasticsearch 기반 하이브리드 KNN 추천 서칭 작동
    with st.spinner("⚡ Elasticsearch 하이브리드 KNN 클러스터 쿼리 실행 중..."):
        meta_h = search_direct_es(
            es_client, 
            prd_no_input.strip(), 
            DEFAULT_LIMIT,
            base_expr_cd="A6082"
        )
    
    st.subheader(f"📊 유사 추천 결과 ({len(meta_h)}개)")
    display_product_grid(meta_h, prd_no_input.strip())

elif not prd_no_input.strip() and search_button:
    st.warning("⚠️ 추천의 기준이 될 상품 번호를 올바르게 입력해 주세요.")
