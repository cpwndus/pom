import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
import sys
sys.path.append('.')
from utils import compute_allocation, CENTER_SUPPLY

def show_hospital(df):
    hospital = st.session_state.selected_institution
    hosp_info = df[df['hospital_name'] == hospital].iloc[0]

    # ── 사이드바 ──────────────────────────────────────
    with st.sidebar:
        st.markdown(f"### 🏥 {hospital}")
        st.markdown(f"**혈액원:** {hosp_info['blood_center']}")
        st.markdown(f"**유형:** {hosp_info['hospital_type']}")
        st.markdown(f"**응급등급:** {hosp_info['er_level']}응급의료센터")
        st.markdown(f"**병상수:** {int(hosp_info['beds']):,}개")
        st.markdown("---")
        selected_date = st.date_input(
            "조회 날짜",
            value=datetime(2024, 10, 14),
            min_value=datetime(2024, 1, 1),
            max_value=datetime(2024, 12, 31)
        )
        st.markdown("---")
        if st.button("🚪 로그아웃", use_container_width=True):
            for k in ['logged_in','role','selected_institution','login_step']:
                st.session_state[k] = False if k == 'logged_in' else (1 if k == 'login_step' else None)
            st.rerun()

    target_date = pd.Timestamp(selected_date)

    # ── 헤더 ──────────────────────────────────────────
    st.markdown(f"""
    <div style='display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem;'>
        <span style='font-size:2.2rem;'>🏥</span>
        <div>
            <h2 style='margin:0;color:#1565c0;'>{hospital}</h2>
            <p style='margin:0;color:#888;font-size:0.9rem;'>
            혈소판 배정 현황 — {target_date.strftime('%Y년 %m월 %d일')}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── AI 배정 계산 ──────────────────────────────────
    alloc_df = compute_allocation(df, target_date)
    if alloc_df.empty:
        st.warning("선택한 날짜의 데이터가 없습니다.")
        return

    my_row = alloc_df[alloc_df['hospital_name'] == hospital]
    if my_row.empty:
        st.warning("해당 병원 데이터가 없습니다.")
        return
    my_row = my_row.iloc[0]

    alloc_key = f"{hospital}_{target_date.date()}"
    allocated = st.session_state.approved_allocations.get(alloc_key, my_row['allocated'])
    status    = "✅ 승인됨" if alloc_key in st.session_state.approved_allocations else "⏳ 검토 중"
    s_color   = "#4caf50" if "승인" in status else "#ff9800"

    # ── 지표 카드 ─────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    surplus_pct = (allocated - my_row['predicted']) / my_row['predicted'] * 100 if my_row['predicted'] > 0 else 0

    for col, title, val, unit, color in [
        (c1, "AI 권장 배정량",  f"{allocated:.0f}",         "Units",    "#1565c0"),
        (c2, "예측 수요량",     f"{my_row['predicted']:.0f}", "Units",   "#333"),
        (c3, "안전재고 여유",   f"+{surplus_pct:.1f}%",      "예측 대비","#2e7d32"),
        (c4, "배정 상태",       status,                       "HITL",     s_color),
    ]:
        with col:
            st.markdown(f"""
            <div class='metric-card'>
                <p style='color:#888;margin:0;font-size:0.82rem;'>{title}</p>
                <h2 style='color:{color};margin:0.3rem 0;font-size:1.6rem;'>{val}</h2>
                <p style='color:#aaa;margin:0;font-size:0.78rem;'>{unit}</p>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 탭 ────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs(["📊 배정 추이", "🚨 긴급 요청", "📋 권역 현황"])

    # 탭1: 배정 추이
    with tab1:
        st.markdown("#### 최근 30일 배정량 vs 실사용량")
        hosp_df = df[df['hospital_name'] == hospital].sort_values('date')
        recent  = hosp_df[hosp_df['date'] <= target_date].tail(30)

        fig, axes = plt.subplots(2, 1, figsize=(12, 6),
                                  gridspec_kw={'height_ratios': [3, 1]})
        ax1, ax2 = axes

        ax1.fill_between(recent['date'], recent['actual_use'], alpha=0.1, color='#2196F3')
        ax1.plot(recent['date'], recent['actual_use'], color='#2196F3', lw=2,
                 label='Actual Use')
        ax1.plot(recent['date'], recent['order_qty'],  color='#f44336', lw=1.5,
                 linestyle='--', label='Hospital Order (Before)')
        if 'ma7_pred' in recent.columns:
            ax1.plot(recent['date'], recent['ma7_pred'], color='#ff9800', lw=1.5,
                     linestyle=':', label='AI Prediction (MA-7)')
        ax1.axhline(allocated, color='#4caf50', lw=2, linestyle='-.',
                    label=f"Today's Allocation ({allocated:.0f})")
        ax1.set_ylabel('Units')
        ax1.legend(fontsize=8)
        ax1.spines['top'].set_visible(False)
        ax1.spines['right'].set_visible(False)
        ax1.grid(axis='y', color='#eeeeee')
        ax1.set_title(f'{hospital} — Platelet Demand & Allocation (Last 30 Days)',
                      fontsize=11, fontweight='bold')

        bw_colors = ['#f44336' if r >= 1.3 else '#90CAF9' for r in recent['bullwhip_ratio']]
        ax2.bar(recent['date'], recent['bullwhip_ratio'], color=bw_colors, width=1.0, alpha=0.8)
        ax2.axhline(1.3, color='orange', lw=1.2, linestyle='--', label='Threshold 1.3')
        ax2.axhline(1.0, color='gray',   lw=0.8)
        ax2.set_ylabel('Bullwhip\nRatio', fontsize=8)
        ax2.set_ylim(0.8, 2.0)
        ax2.legend(fontsize=8)
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)

        fig.tight_layout()
        st.pyplot(fig)
        plt.close()

        avg_bw = recent['bullwhip_ratio'].mean()
        if avg_bw >= 1.3:
            st.markdown(f"""<div class='alert-box'>
            ⚠️ <b>Bullwhip 경보</b> — 최근 30일 평균 Bullwhip Ratio: {avg_bw:.2f}
            (임계값 1.3 초과)</div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""<div class='success-box'>
            ✅ <b>정상 범위</b> — 최근 30일 평균 Bullwhip Ratio: {avg_bw:.2f}</div>""",
            unsafe_allow_html=True)

    # 탭2: 긴급 요청
    with tab2:
        st.markdown("#### 🚨 긴급 혈소판 추가 요청")
        st.markdown(f"""<div class='info-box'>
        ℹ️ 배정량({allocated:.0f} Units)이 부족할 경우 긴급 요청을 제출하세요.
        혈액원 담당자가 검토 후 승인합니다. (Human-in-the-Loop)</div>""",
        unsafe_allow_html=True)

        with st.form("emergency_form"):
            c1, c2 = st.columns(2)
            with c1:
                req_qty = st.number_input("추가 요청량 (Units)", min_value=1, max_value=500, value=50)
            with c2:
                urgency = st.selectbox("긴급도", [
                    "🔴 즉시 (4시간 이내)",
                    "🟡 당일 (24시간 이내)",
                    "🟢 일반 (48시간 이내)"
                ])
            reason = st.selectbox("요청 사유", [
                "예정 외 긴급 수술",
                "응급실 환자 급증",
                "재고 임계치 도달",
                "예측 대비 실사용 초과",
                "기타"
            ])
            detail = st.text_area("상세 내용 (선택)")
            if st.form_submit_button("🚨 긴급 요청 제출", type="primary"):
                st.session_state.emergency_requests.append({
                    'id':       len(st.session_state.emergency_requests) + 1,
                    'hospital': hospital,
                    'date':     target_date.strftime('%Y-%m-%d'),
                    'time':     datetime.now().strftime('%H:%M:%S'),
                    'qty':      req_qty,
                    'urgency':  urgency,
                    'reason':   reason,
                    'detail':   detail,
                    'status':   '대기 중'
                })
                st.success(f"✅ 긴급 요청 제출 완료 (+{req_qty} Units)")

        my_reqs = [r for r in st.session_state.emergency_requests if r['hospital'] == hospital]
        if my_reqs:
            st.markdown("#### 📋 요청 이력")
            for r in reversed(my_reqs):
                bg  = '#fff3f3' if r['status'] == '대기 중' else '#f0faf0'
                bd  = '#f44336' if r['status'] == '대기 중' else '#4caf50'
                st.markdown(f"""
                <div style='background:{bg};border-left:4px solid {bd};
                border-radius:8px;padding:0.7rem;margin:0.3rem 0;font-size:0.88rem;'>
                <b>#{r['id']} {r['reason']}</b> — +{r['qty']} Units ({r['urgency']})
                <span style='float:right;color:#888;'>{r['date']} {r['time']} | {r['status']}</span>
                </div>""", unsafe_allow_html=True)

    # 탭3: 권역 현황
    with tab3:
        st.markdown("#### 같은 혈액원 권역 배정 현황")
        my_center    = hosp_info['blood_center']
        center_alloc = alloc_df[alloc_df['blood_center'] == my_center][[
            'hospital_name','er_level','predicted','allocated','shortage','surplus'
        ]].copy()
        center_alloc.columns = ['병원명','응급등급','예측수요','배정량','부족','잉여']

        def highlight(row):
            if row['병원명'] == hospital:
                return ['background-color:#e3f2fd'] * len(row)
            if row['부족'] > 0:
                return ['background-color:#fff3f3'] * len(row)
            return [''] * len(row)

        st.dataframe(
            center_alloc.sort_values('배정량', ascending=False)
                        .style.apply(highlight, axis=1)
                        .format({'예측수요':'{:.1f}','배정량':'{:.1f}','부족':'{:.1f}','잉여':'{:.1f}'}),
            use_container_width=True, hide_index=True
        )
        supply = CENTER_SUPPLY.get(my_center, 0)
        used   = center_alloc['배정량'].sum()
        st.markdown(f"""<div class='info-box'>
        🏦 {my_center} 오늘 공급량: <b>{supply:,} Units</b>
        | 배정: <b>{used:.0f} Units</b>
        | 잔량: <b>{supply - used:.0f} Units</b> (버퍼)</div>""",
        unsafe_allow_html=True)
