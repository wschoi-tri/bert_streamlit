import streamlit as st
import os
from pymilvus import connections, Collection, utility
import requests

# 1. Streamlit Secrets 로드 (.streamlit/secrets.toml 참조)
ZILLIZ_URI = st.secrets["MILVUS"]["MILVUS_URI"]
ZILLIZ_TOKEN = st.secrets["MILVUS"]["MILVUS_TOKEN"]

# 컬렉션 이름 정의 (lf_prd_meta만 사용)
lf_prd_meta_collection_name = st.secrets["MILVUS"]["COLLECTION_PRD_META"]

# 2. Zilliz(Milvus) 직접 연결 및 로드 (싱글톤 패턴 유사하게 캐싱)
@st.cache_resource
def get_zilliz_collection():
    try:
        connections.connect(alias="default", uri=ZILLIZ_URI, token=ZILLIZ_TOKEN)
        
        lf_meta_col = None
        if utility.has_collection(lf_prd_meta_collection_name):
            lf_meta_col = Collection(lf_prd_meta_collection_name)
            lf_meta_col.load()
            
        return lf_meta_col
    except Exception as e:
        st.error(f"❌ Zilliz 연결 에러: {e}")
        return None

# 3. 직접 검색 함수 정의
def search_direct(collection, prd_no, limit, output_fields, base_expr=None):
    """
    collection: 유사 상품을 검색할 컬렉션
    prd_no: 검색 기준 상품 번호
    base_expr: 기본 필터링 표현식 (예: 'sel_acnt_cd == "A6082"')
    """
    if not collection:
        return []
    
    try:
        # Milvus 필드 타입(Int64)에 맞추기 위해 정수형 변환
        try:
            int_prd_no = int(str(prd_no).strip())
        except ValueError:
            st.error("❌ 상품 번호는 숫자 형식이어야 합니다.")
            return []

        # 1. 요청된 상품(prd_no)의 벡터(vector) 및 ctgr1 조회
        res = collection.query(
            expr=f'prd_no == {int_prd_no}', 
            output_fields=["vector", "ctgr1"],
            limit=1
        )
        
        if not res:
            st.warning(f"⚠️ 컬렉션 내에서 입력하신 상품 번호({int_prd_no})를 찾을 수 없습니다.")
            return []
            
        query_vector = res[0]["vector"]
        target_ctgr1 = res[0].get("ctgr1")
        
        # 2. 기존 필터 조건에 ctgr1 일치 조건 추가 동적 결합
        final_expr = base_expr
        if target_ctgr1:
            # 문자열 내 따옴표 이스케이프 처리
            safe_ctgr1 = target_ctgr1.replace('"', '\\"')
            ctgr_filter = f'ctgr1 == "{safe_ctgr1}"'
            if final_expr:
                final_expr = f'({final_expr}) and {ctgr_filter}'
            else:
                final_expr = ctgr_filter

        # 3. 조회된 벡터를 기반으로 유사한 상품 검색
        search_params = {
            "metric_type": "COSINE", 
            "params": {}
        }
        
        search_res = collection.search(
            data=[query_vector],
            anns_field="vector",
            param=search_params,
            limit=limit,
            output_fields=output_fields,
            expr=final_expr # 조립된 최종 필터 조건 적용
        )
        
        results = []
        if search_res and len(search_res) > 0:
            hits = search_res[0]
            for hit in hits:
                item = hit.entity.to_dict()
                item["similarity_score"] = hit.distance
                results.append(item)
        return results
    except Exception as e:
        st.error(f"검색 오류: {e}")
        return []

# --- Streamlit UI 시작 ---

st.set_page_config(page_title="유사상품 추천", page_icon="🛍️", layout="wide")

st.title("🛍️ 상품 정보 기반 유사 상품 추천 (전체상품)")

# Zilliz 컬렉션 초기화
lf_meta_collection = get_zilliz_collection()

# 고정 설정
DEFAULT_LIMIT = 80

@st.cache_data(show_spinner=False, ttl=3600)
def get_product_detail(prd_no):
    """외부 API에서 상품 이미지 및 상세 정보를 가져옵니다."""
    try:
        params = {"keyword": prd_no, "siteCd": 1, "device": "pc"}
        response = requests.get("http://hapix.halfclub.com/searches/prdList/", params=params, timeout=3.0)
        if response.status_code == 200:
            data = response.json()
            hits = data.get("data", {}).get("result", {}).get("hits", {}).get("hits", [])
            if hits: return hits[0].get("_source", {})
    except Exception: pass
    return {}

def display_product_grid(data, prd_no_input, score_label="유사도"):
    if not data:
        st.info("조건에 일치하는 유사 상품을 찾을 수 없습니다.")
        return

    COLS_PER_ROW = 8
    for row_start in range(0, len(data), COLS_PER_ROW):
        cols = st.columns(COLS_PER_ROW)
        row_items = data[row_start:row_start + COLS_PER_ROW]
        
        for idx, item in enumerate(row_items):
            zilliz_prd_no = item.get("prd_no", "")
            detail = get_product_detail(zilliz_prd_no)
            
            img_url = detail.get("appPrdImgUrl") or detail.get("prdImgUrl")
            if img_url and img_url.startswith("//"): img_url = "https:" + img_url
            
            score = item.get("similarity_score", 0)
            
            api_prd_no = detail.get("prdNo", zilliz_prd_no)
            api_prd_nm = detail.get("prdNm", "(상품명 없음)")
            api_brand = detail.get("brandNm", "")
            api_sel_prc = detail.get("selPrc", 0)
            api_ctgr = f"{detail.get('dpCtgrNm1','')} > {detail.get('dpCtgrNm2','')} > {detail.get('dpCtgrNm3','')}".strip(" >")
            
            # Zilliz 카테고리와 차이 확인
            zilliz_ctgr = f"{item.get('ctgr1','')} > {item.get('ctgr2','')} > {item.get('ctgr3','')}".strip(" >")
            zilliz_diff_html = ""
            if zilliz_ctgr and api_ctgr != zilliz_ctgr:
                zilliz_diff_html = f"<div style='color:#f57c00; margin-top:2px; font-weight:bold;'>  {zilliz_ctgr}</div>"

            score_html = f"{score:.4f}"
            if score >= 0.999 or str(zilliz_prd_no).strip() == str(prd_no_input).strip():
                score_html += " <span style='color:#d32f2f; font-weight:bold;'>(검색)</span>"

            with cols[idx]:
                with st.container(border=True):
                    if img_url: st.image(img_url, width="stretch")
                    else: st.write("이미지 없음")
                        
                    html_content = (
                        f"<div style='margin-bottom: 4px;'>"
                        f"<div style='font-size:0.9em; font-weight:bold; height:2.4em; overflow:hidden; text-overflow:ellipsis; margin-bottom: 4px; line-height: 1.2;'>"
                        f"<a href='http://www.halfclub.com/product/{api_prd_no}' target='_blank' style='text-decoration:none;'>{api_prd_nm} 🔗</a>"
                        f"</div>"
                        f"<div style='font-size:0.75em; color:#555; line-height: 1.25;'>"
                        f"• 상품번호: {api_prd_no}<br>"
                        f"• 브랜드: {api_brand}<br>"
                        f"• 카테고리:<br>"
                        f"  {api_ctgr}<br>"
                        f"{zilliz_diff_html}"
                        f"<div style='color:#d32f2f; font-weight:bold; font-size:1.1em;'>• 가격: {api_sel_prc:,}원</div>"
                        f"</div>"
                        f"</div>"
                        f"<div style='border-top: 1px dashed #ccc; margin: 6px 0;'></div>"
                        f"<div style='margin-bottom: 5px;'>"
                        f"<div style='font-size:0.75em; color:#555; line-height: 1.25;'>"
                        f"• {score_label}: {score_html}<br>"
                        f"</div>"
                        f"</div>"
                    )
                    st.markdown(html_content, unsafe_allow_html=True)

# URL 파라미터에서 prd_no 가져오기
query_params = st.query_params
url_prd_no = query_params.get("prd_no", "")

# URL 파라미터가 있을 경우 초기 검색 자동 실행 설정
if url_prd_no and "url_processed" not in st.session_state:
    st.session_state['searched'] = True
    st.session_state['url_processed'] = True

# 상단 레이아웃
main_top_col1, main_top_col2 = st.columns([1, 5])

with main_top_col1:
    prd_no_input = st.text_input("상품 번호(prd_no)를 입력하세요, (사입 or 업배) (413157091)", value=url_prd_no, placeholder="예: 413157091")
    search_button = st.button("유사 상품 찾기", type="primary", use_container_width=True)

if prd_no_input.strip() and (search_button or st.session_state.get('searched')):
    st.session_state['searched'] = True
    
    target_info = get_product_detail(prd_no_input.strip())
    
    with main_top_col2:
        if target_info:
            t_col1, t_col2 = st.columns([1, 6])
            with t_col1:
                img_url = target_info.get("appPrdImgUrl") or target_info.get("prdImgUrl")
                if img_url:
                    if img_url.startswith("//"): img_url = "https:" + img_url
                    st.image(img_url, width="stretch")
                else: st.markdown("**(이미지 없음)**")
            with t_col2:
                st.markdown("### 🎯 기준 상품")
                api_ctgr = f"{target_info.get('dpCtgrNm1','')} > {target_info.get('dpCtgrNm2','')} > {target_info.get('dpCtgrNm3','')}".strip(" >")
                st.markdown(f"""
                <h3 style='margin-bottom: 10px; margin-top: 0;'>{target_info.get("prdNm", "이름 없음")}</h3>
                <div style='line-height: 1.8; font-size: 1.0em; margin-bottom: 10px;'>
                <b>상품 번호:</b> {target_info.get('prdNo', prd_no_input.strip())}<br>
                <b>카테고리:</b> {api_ctgr}<br>
                <b>브랜드:</b> {target_info.get('brandNm', '알 수 없음')}<br>
                <b>판매가:</b> <span style='font-size:1.1em; color:#d32f2f; font-weight:bold;'>{target_info.get('selPrc', 0):,}원</span>
                </div>
                """, unsafe_allow_html=True)

    st.markdown("---")

    st.subheader("📊 상품 정보 기반 유사 상품 추천 (전체 상품)")
    
    # 기본 sel_acnt_cd 필터 전달 -> search_direct 함수 내부에서 ctgr1 조건과 AND 결합 처리됨
    meta_h = search_direct(
        lf_meta_collection, 
        prd_no_input.strip(), 
        DEFAULT_LIMIT, 
        ["prd_no", "brand", "sel_prc", "ctgr1", "ctgr2", "ctgr3"],
        # base_expr='sel_acnt_cd == "A6082"'
    )
    
    display_product_grid(meta_h, prd_no_input.strip())

elif not prd_no_input.strip() and search_button:
    st.warning("⚠️ 상품 번호를 입력해 주세요.")
