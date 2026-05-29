import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(
    page_title="BloodAI — 혈소판 공급망 AI",
    page_icon="🩸",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #f8f9fa; }
.metric-card {
    background: white; border-radius: 12px; padding: 1.2rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.07); text-align: center;
    margin-bottom: 0.5rem;
}
.alert-box {
    background: #fff3f3; border-left: 4px solid #f44336;
    border-radius: 8px; padding: 0.8rem; margin: 0.4rem 0;
}
.success-box {
    background: #f0faf0; border-left: 4px solid #4caf50;
    border-radius: 8px; padding: 0.8rem; margin: 0.4rem 0;
}
.info-box {
    background: #f0f7ff; border-left: 4px solid #2196F3;
    border-radius: 8px; padding: 0.8rem; margin: 0.4rem 0;
}
.stButton > button { border-radius: 8px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    df = pd.read_csv('data/synthetic_blood_data_v2.csv')
    df['date'] = pd.to_datetime(df['date'])
    df['ma7_pred'] = df.groupby('hospital_id')['actual_use'].transform(
        lambda x: x.shift(1).rolling(7, min_periods=1).mean()
    )
    return df

# 세션 초기화
for key, val in {
    'logged_in': False, 'role': None,
    'selected_institution': None,
    'emergency_requests': [],
    'approved_allocations': {},
    'login_step': 1,
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ── 로그인 화면 ───────────────────────────────────────
if not st.session_state.logged_in:
    st.markdown("<br>", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("""
        <div style='text-align:center; margin-bottom:2rem;'>
            <h1 style='color:#c62828; font-size:2.8rem; margin:0;'>🩸 BloodAI</h1>
            <p style='color:#666; font-size:1.05rem; margin:0.3rem 0;'>
            Korea Blood Supply Chain — AI 자동 배정 시스템</p>
            <p style='color:#aaa; font-size:0.85rem;'>Powered by Bullwhip Effect Analysis</p>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.login_step == 1:
            st.markdown("#### 역할을 선택하세요")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("""
                <div style='background:white;border-radius:12px;padding:1.5rem;
                border:2px solid #e3f2fd;text-align:center;margin-bottom:0.5rem;'>
                <div style='font-size:2.5rem;'>🏥</div>
                <h3 style='color:#1565c0;margin:0.3rem 0;'>병원</h3>
                <p style='color:#888;font-size:0.85rem;margin:0;'>배정량 확인 및 긴급 요청</p>
                </div>""", unsafe_allow_html=True)
                if st.button("병원으로 로그인", use_container_width=True, type="primary"):
                    st.session_state.role = 'hospital'
                    st.session_state.login_step = 2
                    st.rerun()
            with c2:
                st.markdown("""
                <div style='background:white;border-radius:12px;padding:1.5rem;
                border:2px solid #ffebee;text-align:center;margin-bottom:0.5rem;'>
                <div style='font-size:2.5rem;'>🏦</div>
                <h3 style='color:#c62828;margin:0.3rem 0;'>혈액원</h3>
                <p style='color:#888;font-size:0.85rem;margin:0;'>AI 배정안 승인 및 관리</p>
                </div>""", unsafe_allow_html=True)
                if st.button("혈액원으로 로그인", use_container_width=True, type="primary"):
                    st.session_state.role = 'blood_center'
                    st.session_state.login_step = 2
                    st.rerun()

        elif st.session_state.login_step == 2:
            df = load_data()
            st.markdown("---")
            if st.session_state.role == 'hospital':
                st.markdown("#### 🏥 병원을 선택하세요")
                hospitals = sorted(df['hospital_name'].unique())
                selected  = st.selectbox("병원명", hospitals)
            else:
                st.markdown("#### 🏦 혈액원을 선택하세요")
                centers  = sorted(df['blood_center'].unique())
                selected = st.selectbox("혈액원명", centers)

            c1, c2 = st.columns([3, 1])
            with c1:
                if st.button("입장하기 →", use_container_width=True, type="primary"):
                    st.session_state.logged_in = True
                    st.session_state.selected_institution = selected
                    st.rerun()
            with c2:
                if st.button("← 뒤로", use_container_width=True):
                    st.session_state.login_step = 1
                    st.session_state.role = None
                    st.rerun()

# ── 로그인 후 라우팅 ──────────────────────────────────
else:
    df = load_data()
    if st.session_state.role == 'hospital':
        from pages.hospital import show_hospital
        show_hospital(df)
    else:
        from pages.blood_center import show_blood_center
        show_blood_center(df)
