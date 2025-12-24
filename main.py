import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import unicodedata
import io

# -------------------------
# 기본 설정
# -------------------------
st.set_page_config(
    page_title="극지식물 최적 EC 농도 연구",
    layout="wide"
)

# 한글 폰트 (Streamlit + Plotly)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap');
html, body, [class*="css"] {
    font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}
</style>
""", unsafe_allow_html=True)

PLOTLY_FONT = dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif")

# -------------------------
# 상수 정의
# -------------------------
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

EC_INFO = {
    "송도고": 1.0,
    "하늘고": 2.0,
    "아라고": 4.0,
    "동산고": 8.0
}

# -------------------------
# 유틸: NFC/NFD 안전 파일 찾기
# -------------------------
def normalize(text):
    return unicodedata.normalize("NFC", text)

def find_file_by_name(directory: Path, target_name: str):
    target_norm = normalize(target_name)
    for file in directory.iterdir():
        if normalize(file.name) == target_norm:
            return file
    return None

# -------------------------
# 데이터 로딩
# -------------------------
@st.cache_data
def load_environment_data():
    data = {}
    with st.spinner("환경 데이터 로딩 중..."):
        for school in EC_INFO.keys():
            filename = f"{school}_환경데이터.csv"
            file_path = find_file_by_name(DATA_DIR, filename)
            if file_path is None:
                st.error(f"환경 데이터 파일을 찾을 수 없습니다: {filename}")
                return None
            df = pd.read_csv(file_path)
            df["학교"] = school
            data[school] = df
    return data

@st.cache_data
def load_growth_data():
    with st.spinner("생육 결과 데이터 로딩 중..."):
        xlsx_name = "4개교_생육결과데이터.xlsx"
        file_path = find_file_by_name(DATA_DIR, xlsx_name)
        if file_path is None:
            st.error("생육 결과 엑셀 파일을 찾을 수 없습니다.")
            return None

        xls = pd.ExcelFile(file_path, engine="openpyxl")
        data = {}
        for sheet in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet)
            df["학교"] = sheet
            df["EC"] = EC_INFO.get(sheet, None)
            data[sheet] = df
        return data

env_data = load_environment_data()
growth_data = load_growth_data()

if env_data is None or growth_data is None:
    st.stop()

# -------------------------
# 사이드바
# -------------------------
st.sidebar.title("🏫 학교 선택")
selected_school = st.sidebar.selectbox(
    "학교",
    ["전체"] + list(EC_INFO.keys())
)

# -------------------------
# 제목
# -------------------------
st.title("🌱 극지식물 최적 EC 농도 연구")

tab1, tab2, tab3 = st.tabs(["📖 실험 개요", "🌡️ 환경 데이터", "📊 생육 결과"])

# =========================================================
# Tab 1: 실험 개요
# =========================================================
with tab1:
    st.subheader("연구 배경 및 목적")
    st.markdown(
        """
        본 연구는 **극지 환경에서 생육 가능한 식물의 최적 EC 농도**를 도출하기 위해  
        서로 다른 EC 조건에서 재배된 극지식물의 **환경 데이터와 생육 결과**를 비교·분석하였다.
        """
    )

    info_df = pd.DataFrame({
        "학교": EC_INFO.keys(),
        "EC 목표": EC_INFO.values(),
        "개체수": [len(growth_data[s]) for s in EC_INFO.keys()]
    })
    st.subheader("학교별 EC 조건")
    st.dataframe(info_df, use_container_width=True)

    total_plants = info_df["개체수"].sum()
    avg_temp = pd.concat(env_data.values())["temperature"].mean()
    avg_hum = pd.concat(env_data.values())["humidity"].mean()

    growth_all = pd.concat(growth_data.values())
    best_ec = (
        growth_all.groupby("EC")["생중량(g)"]
        .mean()
        .idxmax()
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 개체수", f"{total_plants} 개")
    c2.metric("평균 온도", f"{avg_temp:.1f} ℃")
    c3.metric("평균 습도", f"{avg_hum:.1f} %")
    c4.metric("최적 EC", f"{best_ec}")

# =========================================================
# Tab 2: 환경 데이터
# =========================================================
with tab2:
    st.subheader("학교별 환경 평균 비교")

    env_all = pd.concat(env_data.values())
    env_mean = env_all.groupby("학교").mean(numeric_only=True).reset_index()

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=("평균 온도", "평균 습도", "평균 pH", "목표 EC vs 실측 EC")
    )

    fig.add_bar(x=env_mean["학교"], y=env_mean["temperature"], row=1, col=1)
    fig.add_bar(x=env_mean["학교"], y=env_mean["humidity"], row=1, col=2)
    fig.add_bar(x=env_mean["학교"], y=env_mean["ph"], row=2, col=1)

    fig.add_bar(
        x=list(EC_INFO.keys()),
        y=list(EC_INFO.values()),
        name="목표 EC",
        row=2, col=2
    )
    fig.add_bar(
        x=env_mean["학교"],
        y=env_mean["ec"],
        name="실측 EC",
        row=2, col=2
    )

    fig.update_layout(height=700, font=PLOTLY_FONT)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("환경 데이터 시계열")

    if selected_school != "전체":
        df = env_data[selected_school]

        fig_ts = make_subplots(rows=3, cols=1, shared_xaxes=True,
                               subplot_titles=("온도 변화", "습도 변화", "EC 변화"))

        fig_ts.add_scatter(x=df["time"], y=df["temperature"], row=1, col=1)
        fig_ts.add_scatter(x=df["time"], y=df["humidity"], row=2, col=1)
        fig_ts.add_scatter(x=df["time"], y=df["ec"], row=3, col=1)

        fig_ts.add_hline(y=EC_INFO[selected_school], row=3, col=1)

        fig_ts.update_layout(height=700, font=PLOTLY_FONT)
        st.plotly_chart(fig_ts, use_container_width=True)

    with st.expander("📥 환경 데이터 원본"):
        st.dataframe(env_all, use_container_width=True)
        buffer = io.BytesIO()
        env_all.to_csv(buffer, index=False)
        buffer.seek(0)
        st.download_button(
            "CSV 다운로드",
            data=buffer,
            file_name="환경데이터_전체.csv",
            mime="text/csv"
        )

# =========================================================
# Tab 3: 생육 결과
# =========================================================
with tab3:
    growth_all = pd.concat(growth_data.values())

    st.subheader("🥇 EC별 평균 생중량")
    mean_weight = growth_all.groupby("EC")["생중량(g)"].mean().reset_index()
    best_ec = mean_weight.loc[mean_weight["생중량(g)"].idxmax(), "EC"]

    c1, c2, c3, c4 = st.columns(4)
    for col, (_, row) in zip([c1, c2, c3, c4], mean_weight.iterrows()):
        label = f"EC {row['EC']}"
        if row["EC"] == best_ec:
            label += " ⭐"
        col.metric(label, f"{row['생중량(g)']:.2f} g")

    st.subheader("EC별 생육 비교")

    metrics = {
        "평균 생중량": "생중량(g)",
        "평균 잎 수": "잎 수(장)",
        "평균 지상부 길이": "지상부 길이(mm)",
        "개체수": None
    }

    fig2 = make_subplots(rows=2, cols=2, subplot_titles=list(metrics.keys()))

    i = 0
    for title, col_name in metrics.items():
        r, c = divmod(i, 2)
        if col_name:
            y = growth_all.groupby("EC")[col_name].mean()
        else:
            y = growth_all.groupby("EC").size()
        fig2.add_bar(x=y.index, y=y.values, row=r+1, col=c+1)
        i += 1

    fig2.update_layout(height=700, font=PLOTLY_FONT)
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader("학교별 생중량 분포")
    fig_box = px.box(
        growth_all,
        x="학교",
        y="생중량(g)",
        color="학교"
    )
    fig_box.update_layout(font=PLOTLY_FONT)
    st.plotly_chart(fig_box, use_container_width=True)

    st.subheader("상관관계 분석")
    c1, c2 = st.columns(2)

    fig_sc1 = px.scatter(
        growth_all,
        x="잎 수(장)",
        y="생중량(g)",
        color="학교"
    )
    fig_sc1.update_layout(font=PLOTLY_FONT)
    c1.plotly_chart(fig_sc1, use_container_width=True)

    fig_sc2 = px.scatter(
        growth_all,
        x="지상부 길이(mm)",
        y="생중량(g)",
        color="학교"
    )
    fig_sc2.update_layout(font=PLOTLY_FONT)
    c2.plotly_chart(fig_sc2, use_container_width=True)

    with st.expander("📥 생육 데이터 원본"):
        st.dataframe(growth_all, use_container_width=True)
        buffer = io.BytesIO()
        growth_all.to_excel(buffer, index=False, engine="openpyxl")
        buffer.seek(0)
        st.download_button(
            "XLSX 다운로드",
            data=buffer,
            file_name="생육결과_전체.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
