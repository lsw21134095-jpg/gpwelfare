import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import difflib
import urllib.parse
import os

# --- 페이지 설정 ---
st.set_page_config(page_title="가평군 사회복지자원 검색", layout="centered")

# --- 파일 경로 설정 ---
DATA_FILE = '2026 가평군 사회복지자원 목록_20260610기준.xlsx - 가평군 사회복지 생활시설 현황.csv'
PW_FILE = 'admin_pw.xlsx'

# --- 🌟 관리자 비밀번호 관리 함수 ---
def get_admin_pw():
    if os.path.exists(PW_FILE):
        try:
            df_pw = pd.read_excel(PW_FILE)
            current_pw = str(df_pw['password'].iloc[0])
            if current_pw == 'admin1234':
                set_admin_pw('1234')
                return '1234'
            return current_pw
        except:
            return '1234'
    else:
        pd.DataFrame({'password': ['1234']}).to_excel(PW_FILE, index=False)
        return '1234'

def set_admin_pw(new_pw):
    pd.DataFrame({'password': [new_pw]}).to_excel(PW_FILE, index=False)

# --- 검색 알고리즘 (오타 보정 + 10개 출력) ---
def get_search_results(query, names_list, top_n=10):
    query_clean = query.replace(" ", "")
    contains_matches = [name for name in names_list if query_clean in name.replace(" ", "")]
    fuzzy_matches = difflib.get_close_matches(query, names_list, n=top_n, cutoff=0.1)
    
    results = contains_matches.copy()
    for f in fuzzy_matches:
        if f not in results:
            results.append(f)
    return results[:top_n]

# --- 키워드 기반 세분류 추천 알고리즘 ---
def get_matching_sub_categories(query, df):
    query_clean = query.replace(" ", "")
    if len(query_clean) < 2: 
        return []
        
    if query_clean == "요양원":
        query_clean = "요양"
        
    sub_categories = [s for s in df['시설기관 세분류'].unique() if s]
    matched_subs = [sub for sub in sub_categories if query_clean in sub.replace(" ", "")]
    return matched_subs

# --- 데이터 로드 및 저장 ---
@st.cache_data
def load_data():
    try:
        df = pd.read_csv(DATA_FILE, encoding='cp949')
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(DATA_FILE, encoding='utf-8-sig')
        except:
            st.error("데이터 파일을 찾을 수 없거나 읽을 수 없습니다.")
            return pd.DataFrame() 
    except Exception as e:
        return pd.DataFrame()
        
    df.columns = df.columns.str.replace(r'\n', '', regex=True).str.strip()
    df = df.fillna('')
    df = df.astype(str).replace('nan', '')
    return df

def save_data(df):
    try:
        df.to_csv(DATA_FILE, index=False, encoding='cp949')
    except:
        df.to_csv(DATA_FILE, index=False, encoding='utf-8-sig')
    load_data.clear() 

df = load_data()

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
    st.session_state.previous_step = 4
if 'main_cat' not in st.session_state:
    st.session_state.main_cat = None
if 'sub_cat' not in st.session_state:
    st.session_state.sub_cat = None
if 'search_mode' not in st.session_state:
    st.session_state.search_mode = None
if 'selected_facility' not in st.session_state:
    st.session_state.selected_facility = None
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False
if 'show_admin_panel' not in st.session_state:
    st.session_state.show_admin_panel = False

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

def select_facility(facility, from_step):
    st.session_state.selected_facility = facility
    st.session_state.previous_step = from_step
    st.session_state.step = 5

def route_to_subcat(sub_cat):
    main_cat = df[df['시설기관 세분류'] == sub_cat]['시설기관 대분류'].iloc[0]
    st.session_state.main_cat = main_cat
    st.session_state.sub_cat = sub_cat
    st.session_state.step = 3
    st.session_state.search_mode = None
    st.session_state.selected_facility = None

# --- 🌟 사이드바: 관리자 메뉴 ---
with st.sidebar:
    st.markdown("### ⚙️ 시스템 관리자 메뉴")
    if not st.session_state.is_admin:
        admin_pw_input = st.text_input("관리자 비밀번호", type="password")
        if st.button("로그인", width='stretch'):
            if admin_pw_input == get_admin_pw():
                st.session_state.is_admin = True
                st.success("로그인 성공!")
                st.rerun()
            else:
                st.error("비밀번호가 일치하지 않습니다.")
    else:
        st.success("✅ 관리자 권한 활성화됨")
        if st.button("관리자 대시보드 열기/닫기", width='stretch'):
            st.session_state.show_admin_panel = not st.session_state.show_admin_panel
            st.rerun()
        if st.button("로그아웃", width='stretch'):
            st.session_state.is_admin = False
            st.session_state.show_admin_panel = False
            st.rerun()

# ==========================================
# 🌟 관리자 대시보드 화면
# ==========================================
if st.session_state.show_admin_panel:
    st.markdown("<h3 style='text-align: center; font-size: 20px; color: #E91E63;'>🛠️ 관리자 설정 대시보드</h3>", unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["📝 시설 추가/수정", "📁 데이터 일괄 업로드", "🔒 비밀번호 변경"])
    
    with tab1:
        st.write("개별 시설의 정보를 수정하거나 새로운 시설을 추가합니다.")
        edit_mode = st.radio("작업 선택:", ["기존 시설 수정", "새 시설 추가"], horizontal=True)
        
        if edit_mode == "기존 시설 수정":
            st.markdown("---")
            search_edit = st.text_input("🔍 수정할 시설 이름 검색 (일부 입력 가능)")
            
            if search_edit:
                edit_candidates = df[df['시설기관명'].str.contains(search_edit, case=False, na=False)]['시설기관명'].tolist()
            else:
                edit_candidates = df['시설기관명'].unique().tolist()
                
            if len(edit_candidates) == 0:
                st.warning("검색된 시설이 없습니다.")
            else:
                target_name = st.selectbox("수정할 시설 선택", edit_candidates)
                if target_name:
                    row_data = df[df['시설기관명'] == target_name].iloc[0]
                    
                    with st.form("edit_form"):
                        e_main = st.text_input("대분류", row_data.get('시설기관 대분류', ''))
                        e_sub = st.text_input("세분류", row_data.get('시설기관 세분류', ''))
                        e_name = st.text_input("시설기관명", row_data.get('시설기관명', ''))
                        e_addr = st.text_input("주소", row_data.get('주소', ''))
                        e_phone = st.text_input("대표전화", row_data.get('대표전화', ''))
                        e_fax = st.text_input("팩스", row_data.get('팩스', ''))
                        e_home = st.text_input("홈페이지", row_data.get('홈페이지', ''))
                        e_note = st.text_area("주요 업무(비고)", row_data.get('비고', ''))
                        
                        if st.form_submit_button("수정 내용 저장"):
                            idx = df[df['시설기관명'] == target_name].index[0]
                            df.at[idx, '시설기관 대분류'] = e_main
                            df.at[idx, '시설기관 세분류'] = e_sub
                            df.at[idx, '시설기관명'] = e_name
                            df.at[idx, '주소'] = e_addr
                            df.at[idx, '대표전화'] = e_phone
                            df.at[idx, '팩스'] = e_fax
                            df.at[idx, '홈페이지'] = e_home
                            df.at[idx, '비고'] = e_note
                            save_data(df)
                            st.success("시설 정보가 성공적으로 수정되었습니다!")
                        
        else:
            st.markdown("---")
            main_options = sorted([c for c in df['시설기관 대분류'].unique() if c]) + ["(직접 입력)"]
            selected_main = st.selectbox("대분류 선택", main_options)
            
            final_main = selected_main
            if selected_main == "(직접 입력)":
                final_main = st.text_input("새 대분류 직접 입력")
            
            sub_options = ["(직접 입력)"]
            if selected_main != "(직접 입력)" and final_main:
                subs = sorted([c for c in df[df['시설기관 대분류'] == final_main]['시설기관 세분류'].unique() if c])
                sub_options = subs + sub_options
                
            selected_sub = st.selectbox("세분류 선택", sub_options)
            
            final_sub = selected_sub
            if selected_sub == "(직접 입력)":
                final_sub = st.text_input("새 세분류 직접 입력")

            with st.form("add_form"):
                a_name = st.text_input("시설기관명 (필수)")
                a_addr = st.text_input("주소")
                a_phone = st.text_input("대표전화")
                a_fax = st.text_input("팩스")
                a_home = st.text_input("홈페이지")
                a_note = st.text_area("주요 업무(비고)")
                
                if st.form_submit_button("새 시설 추가"):
                    if a_name and final_main and final_sub:
                        new_row = pd.DataFrame([{
                            '시설기관 대분류': final_main, '시설기관 세분류': final_sub, '시설기관명': a_name,
                            '주소': a_addr, '대표전화': a_phone, '팩스': a_fax, 
                            '홈페이지': a_home, '비고': a_note
                        }])
                        df = pd.concat([df, new_row], ignore_index=True)
                        save_data(df)
                        st.success(f"'{a_name}' 시설이 추가되었습니다!")
                    else:
                        st.error("대분류, 세분류, 시설기관명은 필수 항목입니다.")
                        
    with tab2:
        st.write("대량의 데이터가 변경된 엑셀/CSV 파일을 업로드하여 기존 데이터를 완전히 교체합니다.")
        uploaded_file = st.file_uploader("새 데이터 파일 업로드", type=['csv', 'xlsx'])
        if uploaded_file is not None:
            if st.button("데이터 교체 실행", type="primary"):
                try:
                    if uploaded_file.name.endswith('.csv'):
                        new_df = pd.read_csv(uploaded_file, encoding='cp949')
                    else:
                        new_df = pd.read_excel(uploaded_file)
                    save_data(new_df)
                    st.success("데이터가 성공적으로 일괄 업데이트 되었습니다!")
                except Exception as e:
                    st.error(f"업로드 실패: {e}")
                    
    with tab3:
        st.write("관리자 로그인 비밀번호를 변경합니다. (별도 엑셀 파일에 저장됨)")
        new_pw1 = st.text_input("새 비밀번호 입력", type="password")
        new_pw2 = st.text_input("새 비밀번호 확인", type="password")
        if st.button("비밀번호 변경 완료"):
            if new_pw1 == new_pw2 and new_pw1 != "":
                set_admin_pw(new_pw1)
                st.success("비밀번호가 성공적으로 변경되었습니다!")
            else:
                st.error("비밀번호가 일치하지 않거나 비어있습니다.")

# ==========================================
# 일반 사용자 메인 앱 화면
# ==========================================
else:
    col_l1, col_l2, col_l3 = st.columns([1, 2, 1])
    with col_l2:
        try:
            st.image("gpssn 로고.png", width='stretch')
        except:
            pass

    st.markdown("<h3 style='text-align: center; font-size: 20px; font-weight: 800; margin-bottom: 20px; letter-spacing: -1px;'>가평군 사회복지(시설)자원 검색</h3>", unsafe_allow_html=True)

    def display_facility_details(facility):
        st.markdown("---")
        st.markdown(f"<div style='font-size: 18px; font-weight: bold; margin-bottom: 10px;'>🏢 {facility['시설기관명']}</div>", unsafe_allow_html=True)
        
        address = facility.get('주소', '')
        duties = facility.get('비고', '')
        phone = facility.get('대표전화', '')
        fax = facility.get('팩스', '')
        homepage = facility.get('홈페이지', '')
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"<div style='font-size:14px;'><b>📍 주소:</b> {address}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:14px; margin-top:5px;'><b>📋 주요 업무:</b> {duties}</div>", unsafe_allow_html=True)
            
        with col2:
            st.markdown(f"<div style='font-size:14px;'><b>📞 전화번호:</b> {phone}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='font-size:14px; margin-top:5px;'><b>📠 팩스번호:</b> {fax}</div>", unsafe_allow_html=True)
            
            clean_phone = ''.join(filter(str.isdigit, str(phone))) if phone else ""
            if clean_phone:
                st.markdown(f"""
                <a href="tel:{clean_phone}" style="text-decoration:none;">
                    <div style="width:100%; text-align:center; padding:8px; margin-top:10px; background-color:#4CAF50; color:white; border-radius:6px; font-weight:bold; font-size:13px; cursor:pointer; box-shadow: 0px 2px 5px rgba(0,0,0,0.1);">
                        📞 전화걸기
                    </div>
                </a>
                """, unsafe_allow_html=True)
        
        addr_for_map = address.split('(')[0].split(',')[0].strip()
        if addr_for_map and "가평" not in addr_for_map and "경기" not in addr_for_map:
            addr_for_map = "경기도 가평군 " + addr_for_map
            
        map_search_query = addr_for_map if addr_for_map else facility['시설기관명']
        encoded_query = urllib.parse.quote(map_search_query.encode('utf-8'))
        
        # 🌟 핵심 수정: T맵에 target="_blank" 추가하여 기존 화면이 에러 페이지로 날아가는 브라우저 버그 방지
        st.markdown(f"""
        <div style="display:flex; gap:6px; margin:20px 0 10px 0; width:100%;">
            <a href="https://map.kakao.com/link/search/{encoded_query}" target="_blank" style="flex:1; text-decoration:none; min-width:0;">
                <div style="width:100%; text-align:center; padding:10px 0px; background-color:#FEE500; color:#000000; border-radius:6px; font-weight:bold; font-size:12px; cursor:pointer; box-shadow: 0px 1px 4px rgba(0,0,0,0.15); white-space:nowrap; overflow:hidden;">
                    🟡 카카오맵
                </div>
            </a>
            <a href="https://map.naver.com/v5/search/{encoded_query}" target="_blank" style="flex:1; text-decoration:none; min-width:0;">
                <div style="width:100%; text-align:center; padding:10px 0px; background-color:#03C75A; color:#FFFFFF; border-radius:6px; font-weight:bold; font-size:12px; cursor:pointer; box-shadow: 0px 1px 4px rgba(0,0,0,0.15); white-space:nowrap; overflow:hidden;">
                    🟢 네이버맵
                </div>
            </a>
            <a href="tmap://search?name={encoded_query}" target="_blank" style="flex:1; text-decoration:none; min-width:0;">
                <div style="width:100%; text-align:center; padding:10px 0px; background-color:#000000; color:#FFFFFF; border-radius:6px; font-weight:bold; font-size:12px; cursor:pointer; box-shadow: 0px 1px 4px rgba(0,0,0,0.15); white-space:nowrap; overflow:hidden;">
                    🔴 T맵
                </div>
            </a>
        </div>
        """, unsafe_allow_html=True)

        homepage_str = str(homepage).strip()
        if homepage_str and homepage_str.lower() not in ['nan', 'none', 'null', '']:
            url = homepage_str if homepage_str.startswith('http') else f"http://{homepage_str}"
            st.markdown(f"""
            <div style="margin-bottom:20px;">
                <a href="{url}" target="_blank" style="text-decoration:none;">
                    <div style="width:100%; text-align:center; padding:10px; background-color:#2196F3; color:white; border-radius:6px; font-weight:bold; font-size:13px; cursor:pointer; box-shadow: 0px 2px 5px rgba(0,0,0,0.1);">
                        🌐 홈페이지 바로가기
                    </div>
                </a>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)

        st.markdown("<div style='font-size: 15px; font-weight: bold;'>🗺️ 위치 지도</div>", unsafe_allow_html=True)
        lat, lon, is_exact = get_lat_lon(address)
        
        if not is_exact:
            st.info("💡 무료 지도 특성상 상세 주소를 찾지 못해 대략적인 위치로 표시되었습니다. 위 지도 버튼을 이용해 주세요.", icon="ℹ️")
            
        try:
            m = folium.Map(location=[lat, lon], zoom_start=16)
            popup_html = f"<div style='white-space: nowrap; font-size: 13px;'><b>{facility['시설기관명']}</b><br>{address}</div>"
            
            folium.Marker(
                [lat, lon], 
                popup=folium.Popup(popup_html, max_width=300), 
                tooltip=facility['시설기관명'],
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(m)
            
            st_folium(m, height=400, width='stretch', key=f"map_{facility['시설기관명']}")
        except Exception as e:
            st.warning("지도를 화면에 표시하는 중 문제가 발생했습니다.")


    # --- 메인 화면 렌더링 (1단계) ---
    if st.session_state.step == 1:
        st.markdown("<div style='font-size: 16px; font-weight: bold; margin-bottom: 8px;'>🔍 시설 이름으로 검색하기</div>", unsafe_allow_html=True)
        global_search_query = st.text_input("검색할 시설 기관명을 입력해 주세요 (전체 시설 대상):", key="global_search", label_visibility="collapsed", placeholder="시설 이름 입력 (예: 센터, 요양원)")
        
        if global_search_query:
            matched_subs = get_matching_sub_categories(global_search_query, df)
            
            if matched_subs:
                st.write(f"💡 '{global_search_query}'(이)가 포함된 시설 분류입니다. (선택 시 이동)")
                cols_sub = st.columns(2)
                for i, sub in enumerate(matched_subs):
                    cols_sub[i % 2].button(f"📂 {sub}", key=f"rec_sub_{i}", on_click=route_to_subcat, args=(sub,), width='stretch')
                st.markdown("<br>", unsafe_allow_html=True)
            else:
                facility_names = [name for name in df['시설기관명'].tolist() if name != '']
                matches = get_search_results(global_search_query, facility_names, top_n=10)
                
                if matches:
                    st.write("✨ 개별 시설 검색 결과:")
                    for match_name in matches:
                        matched_rows = df[df['시설기관명'] == match_name]
                        if not matched_rows.empty:
                            matched_facility = matched_rows.iloc[0]
                            st.button(match_name, key=f"g_name_{matched_facility.name}", 
                                      on_click=select_facility, args=(matched_facility, 1), width='stretch')
                else:
                    st.warning("유사한 이름의 기관이나 분류를 찾지 못했습니다.")
                
        st.markdown("---")
        
        st.markdown("<div style='font-size: 16px; font-weight: bold; margin-bottom: 8px;'>📂 1. 시설기관 대분류 선택</div>", unsafe_allow_html=True)
        if '시설기관 대분류' in df.columns:
            main_categories = sorted([cat for cat in df['시설기관 대분류'].unique() if cat != ''])
            cols = st.columns(2)
            for i, cat in enumerate(main_categories):
                if cols[i % 2].button(cat, width='stretch', key=f"main_{i}"):
                    st.session_state.main_cat = cat
                    st.session_state.step = 2
                    st.rerun()

    elif st.session_state.step == 2:
        st.button("⬅️ 이전으로 가기 (대분류 선택)", on_click=go_step, args=(1,), type="secondary", width='stretch')
        st.markdown(f"<div style='font-size: 16px; font-weight: bold; margin: 15px 0 8px 0;'>📂 2. [{st.session_state.main_cat}] 세분류 선택</div>", unsafe_allow_html=True)
        
        sub_df = df[df['시설기관 대분류'] == st.session_state.main_cat]
        sub_categories = sorted([cat for cat in sub_df['시설기관 세분류'].unique() if cat != ''])
        
        cols = st.columns(2)
        for i, sub_cat in enumerate(sub_categories):
            if cols[i % 2].button(sub_cat, key=f"sub_{i}", width='stretch'):
                st.session_state.sub_cat = sub_cat
                st.session_state.step = 3
                st.rerun()

    elif st.session_state.step == 3:
        col_back, col_home = st.columns(2)
        col_back.button("⬅️ 이전으로", on_click=go_step, args=(2,), width='stretch')
        col_home.button("🏠 처음으로", on_click=go_step, args=(1,), width='stretch')
        
        st.markdown(f"<div style='font-size: 16px; font-weight: bold; margin: 15px 0 8px 0;'>📂 3. [{st.session_state.sub_cat}] 검색 방식 선택</div>", unsafe_allow_html=True)
        mode_cols = st.columns(3)
        if mode_cols[0].button("🧭 내주변검색", width='stretch', key="mode_1"):
            st.session_state.search_mode = "주변"
            st.session_state.step = 4
            st.rerun()
        if mode_cols[1].button("🔍 이름검색", width='stretch', key="mode_2"):
            st.session_state.search_mode = "이름"
            st.session_state.step = 4
            st.rerun()
        if mode_cols[2].button("🗺️ 지역검색", width='stretch', key="mode_3"):
            st.session_state.search_mode = "지역"
            st.session_state.step = 4
            st.rerun()

    elif st.session_state.step == 4:
        col_back, col_home = st.columns(2)
        col_back.button("⬅️ 이전으로", on_click=go_step, args=(3,), width='stretch')
        col_home.button("🏠 처음으로", on_click=go_step, args=(1,), width='stretch')
        
        target_df = df[(df['시설기관 대분류'] == st.session_state.main_cat) & 
                       (df['시설기관 세분류'] == st.session_state.sub_cat)]
        
        if st.session_state.search_mode == "주변":
            st.markdown("<div style='font-size: 16px; font-weight: bold; margin: 15px 0 8px 0;'>🧭 내 주변 검색</div>", unsafe_allow_html=True)
            my_address = st.text_input("기준 주소를 입력하세요 (예: 가평군청):", "가평군청")
            if my_address:
                with st.spinner('계산 중...'):
                    user_lat, user_lon, _ = get_lat_lon(my_address)
                    user_coords = (user_lat, user_lon)
                    
                    facilities_with_dist = []
                    for idx, row in target_df.iterrows():
                        f_lat, f_lon, _ = get_lat_lon(row['주소']) 
                        dist = geodesic(user_coords, (f_lat, f_lon)).km
                        facilities_with_dist.append((dist, row))
                    
                    facilities_with_dist.sort(key=lambda x: x[0])
                    st.write(f"📍 **'{my_address}' 기준 가까운 시설 목록**")
                    
                    for dist, facility in facilities_with_dist[:10]:
                        st.button(f"{facility['시설기관명']} (약 {dist:.1f}km)", key=f"near_{facility.name}", 
                                  on_click=select_facility, args=(facility, 4), width='stretch')
                            
        elif st.session_state.search_mode == "이름":
            st.markdown("<div style='font-size: 16px; font-weight: bold; margin: 15px 0 8px 0;'>🔍 이름으로 검색</div>", unsafe_allow_html=True)
            search_query = st.text_input("찾을 기관명을 입력하세요:", label_visibility="collapsed")
            if search_query:
                facility_names = [name for name in target_df['시설기관명'].tolist() if name != '']
                matches = get_search_results(search_query, facility_names, top_n=10)
                
                if matches:
                    st.write("✨ 일치하는 시설 목록:")
                    for match_name in matches:
                        matched_rows = target_df[target_df['시설기관명'] == match_name]
                        if not matched_rows.empty:
                            matched_facility = matched_rows.iloc[0]
                            st.button(match_name, key=f"name_{matched_facility.name}", 
                                      on_click=select_facility, args=(matched_facility, 4), width='stretch')
                else:
                    st.warning("유사한 기관을 찾지 못했습니다.")
                    
        elif st.session_state.search_mode == "지역":
            st.markdown("<div style='font-size: 16px; font-weight: bold; margin: 15px 0 8px 0;'>🗺️ 지역으로 검색</div>", unsafe_allow_html=True)
            def extract_region(address):
                words = str(address).split()
                for word in words:
                    if word.endswith('읍') or word.endswith('면'):
                        return word
                return "기타 지역"
                
            target_df = target_df.copy()
            target_df['지역'] = target_df['주소'].apply(extract_region)
            regions = [r for r in target_df['지역'].unique() if r != "기타 지역" and r != ''] + ["기타 지역"]
            
            selected_region = st.selectbox("가평군 내 세부 행정구역 선택:", regions)
            filtered_by_region = target_df[target_df['지역'] == selected_region]
            
            if not filtered_by_region.empty:
                st.write(f"🏢 **{selected_region} 시설 목록**")
                for idx, facility in filtered_by_region.iterrows():
                    st.button(facility['시설기관명'], key=f"reg_{facility.name}", 
                              on_click=select_facility, args=(facility, 4), width='stretch')
            else:
                st.warning("해당 지역에 일치하는 시설이 없습니다.")

    elif st.session_state.step == 5 and st.session_state.selected_facility is not None:
        col_back, col_home = st.columns(2)
        col_back.button("⬅️ 이전 화면으로", on_click=go_step, args=(st.session_state.previous_step,), width='stretch')
        col_home.button("🏠 처음으로", on_click=go_step, args=(1,), width='stretch')
        
        display_facility_details(st.session_state.selected_facility)