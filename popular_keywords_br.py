import streamlit as st
import requests

# 페이지 설정
st.set_page_config(
    page_title="인기키워드",
    page_icon="🔥",
    layout="centered"
)

st.title("보리 인기 키워드 확인")

API_URL = "https://apix.boribori.co.kr/searches/popularKeyword/?countryCd=001&langCd=001&siteCd=2&deviceCd=002&mandM=b_boribori"

@st.cache_data(ttl=3)  # API 호출 결과를 5분(300초) 동안 캐싱
def fetch_popular_keywords():
    try:
        response = requests.get(API_URL, timeout=15)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"API 호출 중 오류가 발생했습니다: {e}")
        return None

with st.spinner("인기 검색어를 불러오는 중..."):
    data = fetch_popular_keywords()

if data:
    keywords = []
    
    # 키워드 추출 헬퍼 함수
    def extract_keywords_from_list(items):
        return [item.get("keyword") for item in items if isinstance(item, dict) and item.get("keyword")]

    # 응답 JSON 구조 파싱
    if isinstance(data, list):
        keywords = extract_keywords_from_list(data)
    elif isinstance(data, dict):
        # 하프/보리 API의 일반적인 응답 구조 (data -> result 등) 대응
        target_data = data.get("data")
        if isinstance(target_data, list):
            keywords = extract_keywords_from_list(target_data)
        elif isinstance(target_data, dict):
            for key in ("result", "list", "items"):
                if isinstance(target_data.get(key), list):
                    keywords = extract_keywords_from_list(target_data[key])
                    break

    if keywords:
        table_data = [{"키워드": kw} for kw in keywords]
        st.dataframe(table_data, use_container_width=True, hide_index=True)
        
        with st.spinner("각 키워드별 상품 정보를 모두 불러오는 중입니다..."):
            for i, kw in enumerate(keywords, 1):
                st.markdown(f"### **{i}.** {kw}")
                st.caption(f"🔗 [https://m.boribori.co.kr/search/{kw}](https://m.boribori.co.kr/search/{kw})")
                
                search_api_url = "https://apix.boribori.co.kr/searches/prdList/"
                params = {
                    "keyword": kw,
                    "limit": "0,40",
                    "sortSeq": "12",
                    "siteCd": "2",
                    "device": "mc",
                }
                try:
                    search_resp = requests.get(search_api_url, params=params, timeout=15)
                    search_resp.raise_for_status()
                    
                    st.caption(f"🔗 API URL: [{search_resp.url}]({search_resp.url})")
                    search_data = search_resp.json()
                    
                    hits = search_data.get("data", {}).get("result", {}).get("hits", {}).get("hits", [])
                    
                    if hits:
                        # 화면이 너무 길어지지 않도록 상위 4개 상품만 1줄로 표시
                        display_hits = hits[:20]
                        cols = st.columns(4)
                        for idx, hit in enumerate(display_hits):
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
                                
                            with cols[idx % 4]:
                                if img_url:
                                    st.image(img_url, use_container_width=True)
                                st.markdown(f"<div style='font-size:0.8em; color:gray;'>{brand_nm}</div>", unsafe_allow_html=True)
                                if prd_no:
                                    st.markdown(f"<div style='font-size:0.8em;'><a href='https://m.boribori.co.kr/product/{prd_no}' target='_blank'>{prd_no}</a></div>", unsafe_allow_html=True)
                                st.markdown(f"<div style='font-size:0.9em; font-weight:bold;'>{price_str}</div>", unsafe_allow_html=True)
                                st.markdown(f"<div style='font-size:0.8em; overflow:hidden; text-overflow:ellipsis; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; height:3.8em;'>{prd_nm}</div><br/>", unsafe_allow_html=True)
                    else:
                        st.info("검색 결과가 없습니다.")
                except Exception as e:
                    st.error(f"검색 API 호출 중 오류가 발생했습니다: {e}")
                
                # st.markdown("---")
        
    else:
        st.warning("키워드 목록을 찾을 수 없습니다. 응답 구조를 확인해 주세요.")
        with st.expander("API 응답 원본 확인"):
            st.json(data)
