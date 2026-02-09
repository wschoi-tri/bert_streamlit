import streamlit as st
import os
from dotenv import load_dotenv
import requests
import pandas as pd
import numpy as np
import altair as alt
from sklearn.decomposition import PCA
from sklearn.preprocessing import normalize
import torch
from transformers import AutoTokenizer, AutoModel
from pymilvus import connections, Collection

load_dotenv()

# --- 설정 (api_milvus_br.py 참고) ---
# MILVUS_URI = os.getenv("ZILLIZ_URI")
# MILVUS_TOKEN = os.getenv("ZILLIZ_TOKEN")
MILVUS_URI = st.secrets["MILVUS"]["MILVUS_URI"]
MILVUS_TOKEN = st.secrets["MILVUS"]["MILVUS_TOKEN"]
os.environ["HF_TOKEN"] = st.secrets["MILVUS"]["HF_TOKEN"]
os.environ["HUGGINGFACEHUB_API_TOKEN"] = st.secrets["MILVUS"]["HF_TOKEN"]


# 상품 상세 정보 조회용 외부 API (하프클럽)
PRD_INFO_API_URL = "http://hapix.halfclub.com/searches/prdList/"
PRD_DETAIL_URL = "https://www.halfclub.com/product/"

def format_price(value):
    try:
        return f"{int(float(value)):,}"
    except (TypeError, ValueError):
        return str(value)

@st.cache_resource
def load_resources(model_name, collection_name):
    """모델 로드 및 Milvus 연결 (캐싱)"""
    # 1. Device 설정
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # 2. BERT 모델 로드
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    model.to(device)
    model.eval()

    # 3. Milvus 연결
    connections.connect(uri=MILVUS_URI, token=MILVUS_TOKEN)
    
    # 컬렉션 로드
    collection = Collection(collection_name)
    collection.load()
    
    return tokenizer, model, collection, device

def get_product_detail(prd_no):
    """외부 API에서 상품 이미지 및 상세 정보를 가져옵니다."""
    try:
        params = {
            "keyword": prd_no,
            "siteCd": 2,
            "device": "mc"
        }
        response = requests.get(PRD_INFO_API_URL, params=params, timeout=0.5)
        if response.status_code == 200:
            data = response.json()
            hits = data.get("data", {}).get("result", {}).get("hits", {}).get("hits", [])
            if hits:
                return hits[0].get("_source", {})
    except Exception:
        pass
    return {}

def show_grid(items, columns_per_row=4):
    """아이템을 그리드 형태로 표시합니다."""
    rows = [items[i: i + columns_per_row] for i in range(0, len(items), columns_per_row)]
    for row in rows:
        cols = st.columns(len(row), gap="small")
        for col, item in zip(cols, row):
            with col:
                if item.get("html_text"):
                    st.markdown(item["html_text"], unsafe_allow_html=True)

def generate_sparkline(vector):
    """벡터 데이터를 SVG 스파크라인으로 시각화합니다."""
    if not vector or len(vector) < 2:
        return ""
    
    # SVG 설정
    width = 200
    height = 30
    
    try:
        min_val = min(vector)
        max_val = max(vector)
        val_range = max_val - min_val if max_val > min_val else 1
        
        points = [f"{(i / (len(vector) - 1) * width):.1f},{height - ((val - min_val) / val_range * height):.1f}" for i, val in enumerate(vector)]
        points_str = " ".join(points)
        
        return f"""
        <div style="margin: 5px 0;" title="Vector Visualization (Min: {min_val:.2f}, Max: {max_val:.2f})">
            <svg width="100%" height="{height}" viewBox="0 0 {width} {height}" preserveAspectRatio="none" style="background-color:#f1f3f5; border-radius:2px;">
                <polyline points="{points_str}" fill="none" stroke="#3498db" stroke-width="1" />
            </svg>
        </div>
        """
    except Exception:
        return ""

def visualize_embeddings(results):
    """검색 결과의 벡터 분포를 PCA로 차원 축소하여 시각화합니다."""
    # 벡터 데이터가 있는 항목만 추출
    vectors = [item.get('vector') for item in results if item.get('vector')]
    
    # 데이터가 너무 적으면 시각화 생략 (PCA 최소 2개 필요)
    if len(vectors) < 2:
        return

    try:
        # Cosine Similarity 시각화를 위한 전처리: L2 정규화
        # 벡터의 크기를 1로 통일하여 방향(각도) 차이가 거리에 반영되도록 함
        vectors_norm = normalize(np.array(vectors), norm='l2')
        
        # PCA 차원 축소 (2차원)
        pca = PCA(n_components=2)
        components = pca.fit_transform(vectors_norm)
        
        # 데이터프레임 생성
        df = pd.DataFrame(components, columns=['x', 'y'])
        df['Rank'] = range(len(vectors))
        # 첫 번째 결과(Top 1)와 나머지 구분
        df['Type'] = ['Top 1' if i == 0 else 'Others' for i in range(len(vectors))]
        df['Label'] = [f"Rank {i+1} (ID: {results[i].get('prd_no')})" for i in range(len(vectors))]
        
        st.markdown("---")
        st.markdown("### 📊 검색 결과 벡터 분포 (Cosine Space - Normalized PCA)")
        
        # Altair 차트 생성
        base = alt.Chart(df).encode(
            x=alt.X('x', axis=None),
            y=alt.Y('y', axis=None),
            tooltip=['Label', 'Type', 'Rank']
        )
        
        line = base.mark_line(color='#bdc3c7', strokeWidth=1).encode(order='Rank')
        
        points = base.mark_circle().encode(
            color=alt.Color('Type', scale=alt.Scale(domain=['Top 1', 'Others'], range=['#e74c3c', '#3498db']), legend=alt.Legend(title="구분")),
            size=alt.condition(alt.datum.Type == 'Top 1', alt.value(300), alt.value(100))
        )
        
        chart = (line + points).properties(
            height=500,
            title="Normalized Vector Distribution (Cosine Similarity)"
        ).interactive()
        
        st.altair_chart(chart, use_container_width=True)
    except Exception as e:
        st.warning(f"분포도 시각화 중 오류가 발생했습니다: {e}")

def visualize_similarity_scores(results):
    """검색 결과의 코사인 유사도 점수를 라인 차트로 시각화합니다."""
    if not results:
        return

    df = pd.DataFrame({
        'Rank': range(1, len(results) + 1),
        'Score': [item.get('score', 0) for item in results],
        'PrdNo': [item.get('prd_no', '') for item in results]
    })

    st.markdown("### 📈 코사인 유사도 점수 추이")
    
    chart = alt.Chart(df).mark_line(point=True, color='#3498db').encode(
        x=alt.X('Rank:Q', title='순위 (Rank)'),
        y=alt.Y('Score:Q', title='코사인 유사도 (Cosine Similarity)', scale=alt.Scale(zero=False)),
        tooltip=['Rank', 'Score', 'PrdNo']
    ).properties(
        height=300
    ).interactive()
    
    st.altair_chart(chart, use_container_width=True)

def visualize_vector_patterns(results, top_n=100):
    """상위 검색 결과의 벡터 값 패턴을 겹쳐서 시각화합니다."""
    if not results:
        return
        
    # 데이터 양 조절을 위해 상위 N개만 시각화
    display_results = results[:top_n]
    
    data_list = []
    for idx, item in enumerate(display_results):
        vector = item.get('vector', [])
        if not vector:
            continue
        
        # 벡터 차원별 값 추출
        for dim_idx, val in enumerate(vector):
            data_list.append({
                "Rank": f"{idx+1}위",
                "Product": str(item.get('prd_no', '')),
                "Dimension": dim_idx,
                "Value": val
            })
            
    if not data_list:
        return
        
    df = pd.DataFrame(data_list)
    
    st.markdown(f"### 🧬 벡터 패턴 상세 분석 (Top {top_n})")
    st.caption("아래 미니맵(Overview) 차트에서 구간을 드래그하여 선택하면, 위쪽 상세 차트에서 해당 구간이 확대되어 표시됩니다.")

    # 브러시 (구간 선택 도구)
    brush = alt.selection_interval(encodings=['x'])

    # 기본 차트 설정
    base = alt.Chart(df).mark_line(opacity=0.8, strokeWidth=1.5).encode(
        color=alt.Color('Rank:N', sort=[f"{i+1}위" for i in range(top_n)]),
        tooltip=['Rank', 'Product', 'Dimension', 'Value']
    )

    # 상세 차트 (Detail)
    detail = base.encode(
        x=alt.X('Dimension:Q', title='차원 (Dimension)', scale=alt.Scale(domain=brush)),
        y=alt.Y('Value:Q', title='값 (Value)'),
    ).properties(
        height=400
    )

    # 미니맵 차트 (Overview)
    overview = base.encode(
        x=alt.X('Dimension:Q', title='전체 구간 (드래그하여 선택)'),
        y=alt.Y('Value:Q', axis=None, title=None)
    ).properties(
        height=60
    ).add_params(brush)
    
    st.altair_chart(detail & overview, use_container_width=True)

def main():
    st.set_page_config(page_title="BERT 조회", layout="centered")
    st.title("BERT 조회")

    # 모델 선택
    model_options = {
        "intfloat/multilingual-e5-large": "hf_llm_1024", # 1024차원
        # "BAAI/bge-m3": "hf_llm_1024_baai", # 1024차원
        # "jhgan/ko-sroberta-multitask": "hf_llm", # 768차원
        # "klue/bert-base": "hf_llm_768", # 768차원
    }
    
    selected_model = st.selectbox("모델 선택", list(model_options.keys()))
    selected_collection = model_options[selected_model]

    # 리소스 로드
    with st.spinner("모델 및 데이터베이스 연결 중..."):
        try:
            tokenizer, model, collection, device = load_resources(selected_model, selected_collection)
        except Exception as e:
            st.error(f"리소스 로드 실패: {e}")
            return

    top_k = 100

    # 검색 UI (탭으로 분리)
    tab1, tab2 = st.tabs([" 키워드 검색", " 상품 번호 검색"])

    with tab1:
        with st.form(key='search_form'):
            col1, col2 = st.columns([4, 1], vertical_alignment="bottom")
            with col1:
                query = st.text_input("검색어를 입력하세요", placeholder="")
            with col2:
                submit_button = st.form_submit_button(label='검색')

    with tab2:
        with st.form(key='prd_search_form'):
            p_col1, p_col2 = st.columns([4, 1], vertical_alignment="bottom")
            with p_col1:
                prd_no_input = st.text_input("상품 번호를 입력하세요", placeholder="")
            with p_col2:
                prd_submit_button = st.form_submit_button(label='검색')

    if submit_button:
        if not query.strip():
            st.warning("검색어를 입력해주세요.")
            return

        with st.spinner("AI가 상품을 검색하고 상세 정보를 조회 중입니다..."):
            try:
                # 1. BERT 임베딩 생성
                if selected_model in ["intfloat/multilingual-e5-large"]:
                    inputs = tokenizer(f"query: {query}", return_tensors="pt", padding=True, truncation=True, max_length=512).to(device)
                else:
                    inputs = tokenizer(f"{query}", return_tensors="pt", padding=True, truncation=True, max_length=512).to(device)
                with torch.no_grad():
                    outputs = model(**inputs)
                    cls_embedding = outputs.last_hidden_state[:, 0, :].cpu().numpy()
                
                query_vector = cls_embedding[0].tolist()

                # 2. Milvus 검색
                search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
                results = collection.search(
                    data=[query_vector], 
                    anns_field="vector", 
                    param=search_params, 
                    limit=top_k,
                    output_fields=["vector"]
                )

                # 3. 결과 매핑
                search_result = []
                for hits in results:
                    for hit in hits:
                        search_result.append({
                            "prd_no": hit.id,
                            "score": hit.distance,
                            "vector": hit.entity.get("vector")
                        })
                
                if not search_result:
                    st.info("검색 결과가 없습니다.")
                else:
                    st.success(f"'{query}'에 대한 검색 결과 {len(search_result)}건")
                    display_results(search_result)

            except Exception as e:
                st.error(f"알 수 없는 오류가 발생했습니다: {e}")

    elif prd_submit_button:
        if not prd_no_input.strip():
            st.warning("상품 번호를 입력해주세요.")
            return
        
        try:
            target_prd_no = int(prd_no_input.strip())
        except ValueError:
            st.warning("유효한 상품 번호(숫자)를 입력해주세요.")
            return

        with st.spinner(f"상품 번호 {target_prd_no}로 유사 상품을 검색 중입니다..."):
            try:
                # 1. 상품 번호로 벡터 조회
                res = collection.query(
                    expr=f"prd_no == {target_prd_no}",
                    output_fields=["vector"],
                    limit=1
                )
                
                if not res:
                    st.error(f"상품 번호 {target_prd_no}에 대한 데이터를 찾을 수 없습니다.")
                    return
                
                query_vector = res[0]["vector"]

                # 2. Milvus 검색
                search_params = {"metric_type": "COSINE", "params": {"nprobe": 10}}
                results = collection.search(
                    data=[query_vector], 
                    anns_field="vector", 
                    param=search_params, 
                    limit=top_k,
                    output_fields=["vector"]
                )

                # 3. 결과 매핑
                search_result = []
                for hits in results:
                    for hit in hits:
                        search_result.append({
                            "prd_no": hit.id,
                            "score": hit.distance,
                            "vector": hit.entity.get("vector")
                        })
                
                if not search_result:
                    st.info("검색 결과가 없습니다.")
                else:
                    st.success(f"상품 번호 '{target_prd_no}'와 유사한 상품 {len(search_result)}건")
                    display_results(search_result)

            except Exception as e:
                st.error(f"알 수 없는 오류가 발생했습니다: {e}")

def display_results(results):
    """검색 결과를 Grid 형태로 표시합니다."""
    formatted_items = []
    
    # 진행률 표시줄
    progress_bar = st.progress(0)
    total_items = len(results)

    for idx, item in enumerate(results):
        prd_no = str(item.get('prd_no', ''))
        score = item.get('score', 0)
        vector = item.get('vector', [])
        
        # 외부 API에서 상세 정보 조회
        detail = get_product_detail(prd_no)
        srh_url = f"{PRD_INFO_API_URL}?keyword={prd_no}&siteCd=2&device=mc"
        
        # 상세 정보 매핑 (API 응답 필드 추정: prdNm, brandNm, selPrc 등)
        if not detail:
            meta_nm = "상품 정보 없음"
            meta_brand = "-"
            meta_prc = 0
            img_url = ""
            category_path = "-"
        else:
            meta_nm = detail.get("prdNm") or detail.get("prd_nm") or "상품명 없음"
            meta_brand = detail.get("brandNm") or detail.get("brand") or "-"
            meta_brand_url = detail.get("appBrandUrl") or detail.get("brand") or "-"
            meta_prc = detail.get("dcPrcMc") or detail.get("selPrc") or 0
            img_url = detail.get("appPrdImgUrl") or detail.get("imageUrl") or ""
            
            # 카테고리
            cat1 = detail.get("dpCtgrNm1") or detail.get("dpCtgrNo") or ""
            cat2 = detail.get("dpCtgrNm2") or detail.get("dpCtgrNo") or ""
            cat3 = detail.get("dpCtgrNm3") or detail.get("dpCtgrNo") or ""
            cats = [c for c in [cat1, cat2, cat3] if c]
            category_path = " &gt; ".join(cats) if cats else "-"
        
        # 벡터 시각화 생성
        # vector_chart = generate_sparkline(vector)
        vector_chart = ""

        # HTML 컨텐츠 구성
        text = f"""
        <div style="border-radius:8px; padding:10px; margin-bottom:10px; height:100%;">
            <div style="text-align:center; margin-bottom:8px;">
                <img src="{img_url if img_url else 'https://via.placeholder.com/150x200?text=No+Image'}" style="max-width:100%; height:200px; object-fit:cover; border-radius:4px;">
            </div>
            <div style="font-size:0.9em;">
                <div style="display:flex; justify-content:space-between; color:#666; font-size:0.8em; margin-bottom:4px;">{prd_no}</div>
                <div style="display:flex; justify-content:space-between; color:#666; font-size:0.8em; margin-bottom:4px;">Score: {score:.4f}</div>
                <div style="display:flex; justify-content:space-between; color:#666; font-size:0.8em; margin-bottom:4px;"><a href="{meta_brand_url}" target="_blank" style="text-decoration:none; color:#3498db; font-weight:bold; font-size:0.9em;">{meta_brand}</a></div>
                <div style="display:flex; justify-content:space-between; color:#666; font-size:0.8em; margin-bottom:4px;">{meta_nm}</div>
                <div style="display:flex; justify-content:space-between; color:#666; font-size:0.8em; margin-bottom:4px;">{format_price(meta_prc)}원</div>
                <div style="display:flex; justify-content:space-between; color:#666; font-size:0.8em; margin-bottom:4px;">{category_path}</div>
                <div style="display:flex; justify-content:space-between; color:#666; font-size:0.8em; margin-bottom:4px;"><a href="{PRD_DETAIL_URL}{prd_no}" target="_blank" style="text-decoration:none; color:#3498db; font-weight:bold; font-size:0.9em;">상품 상세 보기</a></div>
                <div style="display:flex; justify-content:space-between; color:#666; font-size:0.8em; margin-bottom:4px;"><a href="{srh_url}" target="_blank" style="text-decoration:none; color:#3498db; font-weight:bold; font-size:0.9em;">검색 데이터</a></div>
            </div>
            {vector_chart}
        </div>
        """
        
        formatted_items.append({"html_text": text})
        progress_bar.progress((idx + 1) / total_items)

    progress_bar.empty()
    show_grid(formatted_items, columns_per_row=5)

if __name__ == "__main__":
    main()
    
