import streamlit as st
# ⭐ 반드시 코드의 가장 최상단(첫 번째 스트림릿 명령행)에 위치해야 합니다!
st.set_page_config(
    page_title="가평군 사회복지시설 검색",  # 카톡 제목에 뜰 글자
    page_icon="📍",                           # 브라우저 탭에 뜰 아이콘
    layout="wide"                            # 화면을 넓게 쓰는 옵션 (기존에 있었다면 유지)
)
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import difflib
import urllib.parse

# --- 페이지 설정 ---
st.set_page_config(page_title="가평군 사회복지시설 검색", layout="centered")

# 🌟 메인 화면 맨 위 로고 이미지 삽입 (정중앙 배치)
col1, col2, col3 = st.columns([1, 2, 1]) # 가운데 열을 넓게, 양옆을 여백으로 사용하여 중앙 정렬 효과
with col2:
    try:
        # 이미지 파일명은 실제 저장된 이름과 확장자가 동일해야 합니다.
        st.image("gpssn 로고.png", use_container_width=True)
    except Exception:
        # 이미지가 같은 폴더에 없어도 프로그램이 에러를 뿜지 않도록 패스
        pass

st.title("가평군 사회복지 생활시설 검색")

# --- 데이터 로드 및 결측치 완벽 제거 ---
@st.cache_data
def load_data():
    filename = '2026 가평군 사회복지자원 목록_20260610기준.xlsx - 가평군 사회복지 생활시설 현황.csv'
    try:
        df = pd.read_csv(filename, encoding='cp949')
    except UnicodeDecodeError:
        df = pd.read_csv(filename, encoding='utf-8-sig')
    except Exception as e:
        st.error(f"📁 엑셀 CSV 파일을 읽는 중 오류가 발생했습니다.\n에러 내용: {e}")
        return None
        
    df.columns = df.columns.str.replace(r'\n', '', regex=True).str.strip()
    
    # 결측치(NaN)를 빈칸으로 처리
    df = df.fillna('')
    df = df.astype(str).replace('nan', '')
    
    return df

df = load_data()

if df is None:
    st.stop()

# 지오코더 설정
geolocator = Nominatim(user_agent="gapyeong_welfare_stable_app")

@st.cache_data
def get_lat_lon(address):
    if not address or address.strip() in ['', 'nan', 'None']:
        return 37.8315, 127.5095, False

    clean_address = str(address).split('(')[0].split(',')[0].strip()
    
    try:
        location = geolocator.geocode(clean_address)
        if location:
            return location.latitude, location.longitude, True
            
        parts = clean_address.split()
        if len(parts) >= 3:
            short_addr = " ".join(parts[:3])
            location = geolocator.geocode(short_addr)
            if location:
                return location.latitude, location.longitude, False 
    except:
        pass
        
    return 37.8315, 127.5095, False 

# --- 세션 상태 초기화 ---
if 'step' not in st.session_state:
    st.session_state.step = 1  
if 'previous_step' not in st.session_state:
    st.session_state.previous_step = 4 # 뒤로가기 라우팅용
if 'main_cat' not in st.session_state:
    st.session_state.main_cat = None
if 'sub_cat' not in st.session_state:
    st.session_state.sub_cat = None
if 'search_mode' not in st.session_state:
    st.session_state.search_mode = None
if 'selected_facility' not in st.session_state:
    st.session_state.selected_facility = None

def go_step(step_num):
    st.session_state.step = step_num
    if step_num == 1:
        st.session_state.main_cat = None
        st.session_state.sub_cat = None
        st.session_state.search_mode = None
        st.session_state.selected_facility = None
    elif step_num == 2:
        st.session_state.sub_cat = None
        st.session_state.search_mode = None
        st.session_state.selected_facility = None
    elif step_num == 3:
        st.session_state.search_mode = None
        st.session_state.selected_facility = None
    elif step_num == 4:
        st.session_state.selected_facility = None

# 시설 선택 시 어느 단계에서 넘어왔는지 기록 (1단계 통합검색 or 4단계 세부검색)
def select_facility(facility, from_step):
    st.session_state.selected_facility = facility
    st.session_state.previous_step = from_step
    st.session_state.step = 5

# --- UI 함수: 시설 상세 정보 및 레이아웃 ---
def display_facility_details(facility):
    st.markdown("---")
    st.subheader(f"🏢 {facility['시설기관명']}")
    
    address = facility.get('주소', '')
    duties = facility.get('비고', '')
    phone = facility.get('대표전화', '')
    fax = facility.get('팩스', '')
    homepage = facility.get('홈페이지', '')
    
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**📍 주소:** {address}")
        st.write(f"**📋 주요 업무:** {duties}")
        
    with col2:
        st.write(f"**📞 전화번호:** {phone}")
        st.write(f"**📠 팩스번호:** {fax}")
        
        # 전화걸기 버튼
        clean_phone = ''.join(filter(str.isdigit, str(phone))) if phone else ""
        if clean_phone:
            st.markdown(f"""
            <a href="tel:{clean_phone}" style="text-decoration:none;">
                <div style="width:100%; text-align:center; padding:10px; margin-top:10px; background-color:#4CAF50; color:white; border-radius:8px; font-weight:bold; font-size:14px; cursor:pointer; box-shadow: 0px 2px 5px rgba(0,0,0,0.1);">
                    📞 전화걸기
                </div>
            </a>
            """, unsafe_allow_html=True)
    
    # 지도 앱 연동
    encoded_name = urllib.parse.quote(facility['시설기관명'])
    st.markdown(f"""
    <div style="display:flex; gap:10px; margin:25px 0 10px 0;">
        <a href="https://map.kakao.com/link/search/{encoded_name}" target="_blank" style="flex:1; text-decoration:none;">
            <div style="width:100%; text-align:center; padding:12px; background-color:#FEE500; color:#000000; border-radius:8px; font-weight:bold; font-size:14px; cursor:pointer; box-shadow: 0px 2px 5px rgba(0,0,0,0.1);">
                🟡 카카오맵
            </div>
        </a>
        <a href="https://map.naver.com/v5/search/{encoded_name}" target="_blank" style="flex:1; text-decoration:none;">
            <div style="width:100%; text-align:center; padding:12px; background-color:#03C75A; color:#FFFFFF; border-radius:8px; font-weight:bold; font-size:14px; cursor:pointer; box-shadow: 0px 2px 5px rgba(0,0,0,0.1);">
                🟢 네이버맵
            </div>
        </a>
        <a href="tmap://search?name={encoded_name}" style="flex:1; text-decoration:none;">
            <div style="width:100%; text-align:center; padding:12px; background-color:#000000; color:#FFFFFF; border-radius:8px; font-weight:bold; font-size:14px; cursor:pointer; box-shadow: 0px 2px 5px rgba(0,0,0,0.1);">
                🔴 T맵
            </div>
        </a>
    </div>
    """, unsafe_allow_html=True)

    # 홈페이지 바로가기 버튼
    homepage_str = str(homepage).strip()
    if homepage_str and homepage_str.lower() not in ['nan', 'none', 'null', '']:
        url = homepage_str if homepage_str.startswith('http') else f"http://{homepage_str}"
        st.markdown(f"""
        <div style="margin-bottom:25px;">
            <a href="{url}" target="_blank" style="text-decoration:none;">
                <div style="width:100%; text-align:center; padding:12px; background-color:#2196F3; color:white; border-radius:8px; font-weight:bold; font-size:14px; cursor:pointer; box-shadow: 0px 2px 5px rgba(0,0,0,0.1);">
                    🌐 홈페이지 바로가기
                </div>
            </a>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("<div style='margin-bottom:25px;'></div>", unsafe_allow_html=True)

    # 위치 지도 생성
    st.write("#### 🗺️ 위치 지도")
    lat, lon, is_exact = get_lat_lon(address)
    
    if not is_exact:
        st.info("💡 무료 지도 API(오픈스트리트맵) 특성상 상세 주소를 찾지 못해 대략적인 위치(또는 가평군청)로 표시되었습니다. 정확한 위치는 위의 카카오/네이버맵 버튼을 이용해 주세요.")
        
    try:
        m = folium.Map(location=[lat, lon], zoom_start=16)
        popup_html = f"<div style='white-space: nowrap; font-size: 14px;'><b>{facility['시설기관명']}</b><br>{address}</div>"
        
        folium.Marker(
            [lat, lon], 
            popup=folium.Popup(popup_html, max_width=300), 
            tooltip=facility['시설기관명'],
            icon=folium.Icon(color="blue", icon="info-sign")
        ).add_to(m)
        
        st_folium(m, height=400, use_container_width=True, key=f"map_{facility['시설기관명']}")
        
    except Exception as e:
        st.warning("지도를 화면에 표시하는 중 문제가 발생했습니다.")

# ==========================================
# 화면 렌더링 로직
# ==========================================

# --- 1단계: 메인 첫 화면 (통합 이름 검색 + 대분류 선택) ---
if st.session_state.step == 1:
    # 🌟 수정된 부분: "통합 이름으로 검색하기" -> "시설 이름으로 검색하기"
    st.write("### 🔍 시설 이름으로 검색하기")
    global_search_query = st.text_input("검색할 시설 기관명을 입력해 주세요 (전체 시설 대상):", key="global_search")
    
    if global_search_query:
        facility_names = [name for name in df['시설기관명'].tolist() if name != '']
        matches = difflib.get_close_matches(global_search_query, facility_names, n=5, cutoff=0.1)
        
        if matches:
            st.write("✨ 가장 일치하는 시설 목록 (클릭 시 상세정보 확인):")
            for match_name in matches:
                matched_rows = df[df['시설기관명'] == match_name]
                if not matched_rows.empty:
                    matched_facility = matched_rows.iloc[0]
                    st.button(match_name, key=f"g_name_{matched_facility.name}", 
                              on_click=select_facility, args=(matched_facility, 1), use_container_width=True)
        else:
            st.warning("유사한 이름의 기관을 찾지 못했습니다.")
            
    st.markdown("---")
    
    # 🌟 1. 시설기관 대분류 선택
    st.write("### 📂 1. 시설기관 대분류 선택")
    if '시설기관 대분류' in df.columns:
        main_categories = [cat for cat in df['시설기관 대분류'].unique() if cat != '']
        cols = st.columns(2)
        for i, cat in enumerate(main_categories):
            if cols[i % 2].button(cat, use_container_width=True, key=f"main_{i}"):
                st.session_state.main_cat = cat
                st.session_state.step = 2
                st.rerun()

elif st.session_state.step == 2:
    st.button("⬅️ 이전으로 가기 (대분류 선택)", on_click=go_step, args=(1,), type="secondary", use_container_width=True)
    st.write(f"### 2. [{st.session_state.main_cat}] 세분류 선택")
    
    sub_df = df[df['시설기관 대분류'] == st.session_state.main_cat]
    sub_categories = [cat for cat in sub_df['시설기관 세분류'].unique() if cat != '']
    
    cols = st.columns(2)
    for i, sub_cat in enumerate(sub_categories):
        if cols[i % 2].button(sub_cat, key=f"sub_{i}", use_container_width=True):
            st.session_state.sub_cat = sub_cat
            st.session_state.step = 3
            st.rerun()

elif st.session_state.step == 3:
    col_back, col_home = st.columns(2)
    col_back.button("⬅️ 이전으로 (세분류 선택)", on_click=go_step, args=(2,), use_container_width=True)
    col_home.button("🏠 처음으로 (대분류)", on_click=go_step, args=(1,), use_container_width=True)
    
    st.write(f"### 3. [{st.session_state.sub_cat}] 검색 방식 선택")
    mode_cols = st.columns(3)
    if mode_cols[0].button("🧭 내 주변 검색", use_container_width=True, key="mode_1"):
        st.session_state.search_mode = "주변"
        st.session_state.step = 4
        st.rerun()
    if mode_cols[1].button("🔍 이름 검색", use_container_width=True, key="mode_2"):
        st.session_state.search_mode = "이름"
        st.session_state.step = 4
        st.rerun()
    if mode_cols[2].button("🗺️ 지역 검색", use_container_width=True, key="mode_3"):
        st.session_state.search_mode = "지역"
        st.session_state.step = 4
        st.rerun()

elif st.session_state.step == 4:
    col_back, col_home = st.columns(2)
    col_back.button("⬅️ 이전으로 (검색방식 변경)", on_click=go_step, args=(3,), use_container_width=True)
    col_home.button("🏠 처음으로 (대분류)", on_click=go_step, args=(1,), use_container_width=True)
    
    target_df = df[(df['시설기관 대분류'] == st.session_state.main_cat) & 
                   (df['시설기관 세분류'] == st.session_state.sub_cat)]
    
    if st.session_state.search_mode == "주변":
        st.subheader("🧭 내 주변 검색")
        my_address = st.text_input("현재 계신 위치나 기준 주소를 입력하세요 (예: 가평군청, 청평면):", "가평군청")
        if my_address:
            with st.spinner('좌표 및 거리를 계산 중입니다...'):
                user_lat, user_lon, _ = get_lat_lon(my_address)
                user_coords = (user_lat, user_lon)
                
                facilities_with_dist = []
                for idx, row in target_df.iterrows():
                    f_lat, f_lon, _ = get_lat_lon(row['주소']) 
                    dist = geodesic(user_coords, (f_lat, f_lon)).km
                    facilities_with_dist.append((dist, row))
                
                facilities_with_dist.sort(key=lambda x: x[0])
                st.write(f"📍 **'{my_address}' 기준 가까운 시설 목록** (클릭 시 상세정보 확인)")
                
                for dist, facility in facilities_with_dist[:10]:
                    st.button(f"{facility['시설기관명']} (약 {dist:.1f}km)", key=f"near_{facility.name}", 
                              on_click=select_facility, args=(facility, 4), use_container_width=True)
                        
    elif st.session_state.search_mode == "이름":
        st.subheader("🔍 이름으로 검색")
        search_query = st.text_input("해당 분류 내에서 찾을 기관명을 입력하세요:")
        if search_query:
            facility_names = [name for name in target_df['시설기관명'].tolist() if name != '']
            matches = difflib.get_close_matches(search_query, facility_names, n=5, cutoff=0.1)
            
            if matches:
                st.write("✨ 가장 일치하는 시설 목록 (클릭 시 상세정보 확인):")
                for match_name in matches:
                    matched_rows = target_df[target_df['시설기관명'] == match_name]
                    if not matched_rows.empty:
                        matched_facility = matched_rows.iloc[0]
                        st.button(match_name, key=f"name_{matched_facility.name}", 
                                  on_click=select_facility, args=(matched_facility, 4), use_container_width=True)
            else:
                st.warning("유사한 이름의 기관을 찾지 못했습니다.")
                
    elif st.session_state.search_mode == "지역":
        st.subheader("🗺️ 지역으로 검색")
        def extract_region(address):
            words = str(address).split()
            for word in words:
                if word.endswith('읍') or word.endswith('면'):
                    return word
            return "기타 지역"
            
        target_df = target_df.copy()
        target_df['지역'] = target_df['주소'].apply(extract_region)
        regions = [r for r in target_df['지역'].unique() if r != "기타 지역" and r != ''] + ["기타 지역"]
        
        selected_region = st.selectbox("가평군 내 세부 행정구역을 선택하세요:", regions)
        filtered_by_region = target_df[target_df['지역'] == selected_region]
        
        if not filtered_by_region.empty:
            st.write(f"🏢 **{selected_region} 시설 목록** (클릭 시 상세정보 확인)")
            for idx, facility in filtered_by_region.iterrows():
                st.button(facility['시설기관명'], key=f"reg_{facility.name}", 
                          on_click=select_facility, args=(facility, 4), use_container_width=True)
        else:
            st.warning("해당 지역에 일치하는 시설이 없습니다.")

# --- 5단계: 선택한 시설 단독 상세보기 화면 ---
elif st.session_state.step == 5 and st.session_state.selected_facility is not None:
    col_back, col_home = st.columns(2)
    col_back.button("⬅️ 이전 화면으로 돌아가기", on_click=go_step, args=(st.session_state.previous_step,), use_container_width=True)
    col_home.button("🏠 처음으로 (대분류)", on_click=go_step, args=(1,), use_container_width=True)
    
    display_facility_details(st.session_state.selected_facility)