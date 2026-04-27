import streamlit as st
import os
from pymilvus import connections, Collection, utility
import requests

# 1. Streamlit Secrets 로드 (.streamlit/secrets.toml 참조)
ZILLIZ_URI = st.secrets["MILVUS"]["MILVUS_URI"]
ZILLIZ_TOKEN = st.secrets["MILVUS"]["MILVUS_TOKEN"]

# 컬렉션 이름 정의
prd_meta_collection_name = "Product_Embeddings"
prd_desc_collection_name = "prd_llm_desc_vec"

# 2. Zilliz(Milvus) 직접 연결 및 로드 (싱글톤 패턴 유사하게 캐싱)
@st.cache_resource
def get_zilliz_collections():
    try:
        connections.connect(alias="default", uri=ZILLIZ_URI, token=ZILLIZ_TOKEN)
        
        meta_col = None
        if utility.has_collection(prd_meta_collection_name):
            meta_col = Collection(prd_meta_collection_name)
            meta_col.load()
            
        desc_col = None
        if utility.has_collection(prd_desc_collection_name):
            desc_col = Collection(prd_desc_collection_name)
            desc_col.load()
            
        return meta_col, desc_col
    except Exception as e:
        st.error(f"❌ Zilliz 연결 에러: {e}")
        return None, None

# 3. 직접 검색 함수 정의
def search_direct(collection, prd_no, limit, output_fields):
    if not collection:
        return []
    
    try:
        # 1. 요청된 상품(prd_no)의 벡터(vector) 조회
        res = collection.query(
            expr=f'prd_no == "{prd_no}"', 
            output_fields=["vector"],
            limit=1
        )
        
        if not res:
            return []
            
        query_vector = res[0]["vector"]
        
        # 2. 조회된 벡터를 기반으로 유사한 상품 검색
        search_params = {
            "metric_type": "COSINE", 
            "params": {}
        }
        
        search_res = collection.search(
            data=[query_vector],
            anns_field="vector",
            param=search_params,
            limit=limit,
            output_fields=output_fields
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

st.set_page_config(page_title="BERT 유사 상품", page_icon="🛍️", layout="wide")

st.title("🛍️ BERT 유사 상품 추천 확인")

# Zilliz 컬렉션 초기화
meta_collection, desc_collection = get_zilliz_collections()

# 고정 설정
DEFAULT_LIMIT = 80
HYBRID_INTERNAL_LIMIT = 1000

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

def display_product_grid(data, prd_no_input, is_hybrid=False, score_label="유사도"):
    if not data:
        st.info("유사 상품을 찾을 수 없습니다.")
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
            
            if is_hybrid:
                h_meta = item.get("h_meta_score", 0)
                h_desc = item.get("h_desc_score", 0)
                is_both = item.get("is_both", False)
                both_tag = " <span style='color:#ffffff; font-size:0.7em; background:#2e7d32; padding:2px 5px; border-radius:4px; font-weight:bold; margin-left:5px;'>BOTH</span>" if is_both else ""
                score_html = f"<b style='font-size:1.1em; color:#d32f2f;'>{score:.4f}</b>{both_tag}<br><span style='font-size:0.8em; color:#666;'>(M:{h_meta:.2f} + D:{h_desc:.2f})</span>"
            else:
                score_html = f"{score:.4f}"
                if score >= 0.999 or str(zilliz_prd_no).strip() == str(prd_no_input).strip():
                    score_html += " <span style='color:#d32f2f; font-weight:bold;'>(검색)</span>"

            if is_hybrid:
                h_meta_txt = item.get("h_meta_txt", "")
                h_desc_txt = item.get("h_desc_txt", "")
                zilliz_txt_html = ""
                if h_meta_txt: zilliz_txt_html += f"<div style='font-size:0.75em; color:#1976d2; margin-top:2px; font-weight:bold;'>[Meta]</div><div title='{h_meta_txt}' style='font-size:0.8em; background-color:#eef5ff; padding:4px; border-radius:4px; line-height:1.2; height:50px; overflow-y:auto; border:1px solid #cce0ff;'>{h_meta_txt}</div>"
                if h_desc_txt: zilliz_txt_html += f"<div style='font-size:0.75em; color:#388e3c; margin-top:2px; font-weight:bold;'>[Desc]</div><div title='{h_desc_txt}' style='font-size:0.8em; background-color:#f1f8e9; padding:4px; border-radius:4px; line-height:1.2; height:50px; overflow-y:auto; border:1px solid #dcedc8;'>{h_desc_txt}</div>"
            else:
                zilliz_txt = item.get("txt") or item.get("desc") or "정보 없음"
                zilliz_txt_html = f"<div title='{zilliz_txt}' style='font-size:0.85em; background-color:#eef5ff; padding:5px; border-radius:4px; margin-top:4px; line-height:1.4; height:100px; overflow-y:auto; border:1px solid #cce0ff; word-break:keep-all;'>{zilliz_txt}</div>"

            with cols[idx]:
                with st.container(border=True):
                    if img_url: st.image(img_url, use_container_width=True)
                    else: st.write("이미지 없음")
                        
                    html_content = f"""
                    <div style="margin-bottom: 4px;">
                        <div style='font-size:0.9em; font-weight:bold; height:2.4em; overflow:hidden; text-overflow:ellipsis; margin-bottom: 4px; line-height: 1.2;'>
                            <a href='http://www.halfclub.com/product/{api_prd_no}' target='_blank' style='text-decoration:none;'>{api_prd_nm} 🔗</a>
                        </div>
                        <div style='font-size:0.75em; color:#555; line-height: 1.25;'>
                            • 번호: {api_prd_no}<br>
                            • 분류: {api_ctgr}<br>
                            • 브랜드: {api_brand}<br>
                            <span style='color:#d32f2f; font-weight:bold; font-size:1.1em;'>• 가격: {api_sel_prc:,}원</span>
                        </div>
                    </div>
                    <div style="border-top: 1px dashed #ccc; margin: 6px 0;"></div>
                    <div style="margin-bottom: 5px;">
                        <div style='font-size:0.75em; color:#555; line-height: 1.25;'>
                            • {score_label}: {score_html}<br>
                            {zilliz_txt_html}
                        </div>
                    </div>
                    """
                    st.markdown(html_content, unsafe_allow_html=True)

# URL 파라미터에서 prd_no 가져오기
query_params = st.query_params
url_prd_no = query_params.get("prd_no", "")

# URL 파라미터가 있을 경우 초기 검색 자동 실행 설정
if url_prd_no and "url_processed" not in st.session_state:
    st.session_state['searched'] = True
    st.session_state['url_processed'] = True

# 상단 레이아웃
main_top_col1, main_top_col2 = st.columns([1, 4])

with main_top_col1:
    # URL 파라미터가 있으면 기본값으로 설정
    prd_no_input = st.text_input("상품 번호(prd_no)를 입력하세요", value=url_prd_no, placeholder="예: 111464580")
    st.write("")
    search_button = st.button("유사 상품 찾기", type="primary", use_container_width=True)

if prd_no_input.strip() and (search_button or st.session_state.get('searched')):
    st.session_state['searched'] = True
    
    target_info = get_product_detail(prd_no_input.strip())
    
    with main_top_col2:
        if target_info:
            st.markdown("### 🎯 기준 상품")
            t_col1, t_col2 = st.columns([1, 3])
            with t_col1:
                img_url = target_info.get("appPrdImgUrl") or target_info.get("prdImgUrl")
                if img_url:
                    if img_url.startswith("//"): img_url = "https:" + img_url
                    st.image(img_url, use_container_width=True)
                else: st.markdown("**(이미지 없음)**")
            with t_col2:
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

    tab1, tab2, tab3, tab4 = st.tabs(["📊 상품 정보 (메타)", "📝 상품 설명", "🧬 평균 합산", "🔥 가중치 합산"])

    # 공통 대량 검색 (하이브리드 및 메타 우선용)
    meta_h = search_direct(meta_collection, prd_no_input.strip(), HYBRID_INTERNAL_LIMIT, ["prd_no", "brand", "sel_prc", "ctgr1", "ctgr2", "ctgr3", "txt"])
    desc_h = search_direct(desc_collection, prd_no_input.strip(), HYBRID_INTERNAL_LIMIT, ["prd_no", "desc"])
    
    # 하이브리드 맵 생성
    hybrid_map = {}
    for item in meta_h:
        p_no = str(item["prd_no"]).strip()
        hybrid_map[p_no] = {"data": item, "meta_score": item["similarity_score"], "desc_score": 0.0, "meta_txt": item.get("txt", ""), "desc_txt": ""}
    
    for item in desc_h:
        p_no = str(item["prd_no"]).strip()
        if p_no in hybrid_map:
            hybrid_map[p_no]["desc_score"] = item["similarity_score"]
            hybrid_map[p_no]["desc_txt"] = item.get("desc") or item.get("txt", "")
        else:
            hybrid_map[p_no] = {"data": item, "meta_score": 0.0, "desc_score": item["similarity_score"], "meta_txt": "", "desc_txt": item.get("desc") or item.get("txt", "")}

    with tab1:
        st.subheader("상품 정보 (메타) 기반 유사 상품")
        display_product_grid(meta_h[:DEFAULT_LIMIT], prd_no_input.strip())

    with tab2:
        st.subheader("상품 설명 기반 유사 상품")
        display_product_grid(desc_h[:DEFAULT_LIMIT], prd_no_input.strip())

    with tab3:
        st.subheader("평균 합산 추천 결과 (Meta + Desc)")
        
        h_col1, h_col2 = st.columns(2)
        with h_col1: w_meta = st.slider("메타 데이터 가중치", 0.0, 1.0, 0.5, 0.1, key="w_meta_tab3")
        with h_col2:
            w_desc = 1.0 - w_meta
            st.write(f"설명 데이터 가중치: **{w_desc:.1f}**")
        
        hybrid_results = []
        for p_no, val in hybrid_map.items():
            is_both = val["meta_score"] > 0 and val["desc_score"] > 0
            total_score = (val["meta_score"] * w_meta) + (val["desc_score"] * w_desc)
            item_data = val["data"].copy()
            item_data.update({"similarity_score": total_score, "h_meta_score": val["meta_score"], "h_desc_score": val["desc_score"], "h_meta_txt": val["meta_txt"], "h_desc_txt": val["desc_txt"], "is_both": is_both})
            hybrid_results.append(item_data)
        
        hybrid_results = sorted(hybrid_results, key=lambda x: (x["is_both"], x["similarity_score"]), reverse=True)[:DEFAULT_LIMIT]
        display_product_grid(hybrid_results, prd_no_input.strip(), is_hybrid=True)

    with tab4:
        st.subheader("가중치 합산 추천 결과")
        
        w_extra = st.slider("설명 데이터 추가 점수 가중치", 0.0, 1.0, 0.3, 0.05, key="w_extra_tab4")
        
        meta_first_results = []
        for p_no, val in hybrid_map.items():
            # 메타 데이터 결과에 존재하는 상품만 대상으로 함
            if val["meta_score"] <= 0:
                continue
            
            # 최종 점수 = Meta Score + (Desc Score * Weight)
            # 메타가 기본이므로 메타 점수가 1.0에 가까운 것들이 상단에 유지되면서 설명이 비슷하면 더 올라감
            combined_score = val["meta_score"] + (val["desc_score"] * w_extra)
            
            item_data = val["data"].copy()
            item_data.update({
                "similarity_score": combined_score, 
                "h_meta_score": val["meta_score"], 
                "h_desc_score": val["desc_score"], 
                "h_meta_txt": val["meta_txt"], 
                "h_desc_txt": val["desc_txt"], 
                "is_both": val["meta_score"] > 0 and val["desc_score"] > 0
            })
            meta_first_results.append(item_data)
        
        # 합산 점수 기준으로 정렬
        meta_first_results = sorted(meta_first_results, key=lambda x: x["similarity_score"], reverse=True)[:DEFAULT_LIMIT]
        display_product_grid(meta_first_results, prd_no_input.strip(), is_hybrid=True, score_label="보정 점수")

elif not prd_no_input.strip() and search_button:
    st.warning("⚠️ 상품 번호를 입력해 주세요.")
