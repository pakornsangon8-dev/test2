import os
import plotly.express as px
import pandas as pd
import streamlit as st

# Page Configuration
st.set_page_config(
    page_title="Dashboard พนักงานเจ้าหน้าที่",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Title & Subtitle
st.title("Dashboard พนักงานเจ้าหน้าที่ตาม พ.ร.บ. ไซเบอร์ฯ / คอมพิวเตอร์ฯ")
st.caption(
    "ระบบวิเคราะห์สถานะการหมดอายุ (Expired Timestamps), การเสนอชื่อซ้ำ/ตั้งซ้ำ/ต่ออายุ"
    " และสรุปข้อมูลภาพรวมเชิงสถิติ"
)

# ==========================================
# 1. จัดการโหลดไฟล์/ฐานข้อมูล (รองรับการเริ่มใหม่ที่เครื่องใหม่แบบคลีน)
# ==========================================
DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "officers_database.db"
)
DATA_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "SUM_พนักงานเจ้าหน้าที่แยกตามระดับ_Cleaned.csv",
)


@st.cache_data
def load_data():
  # พยายามโหลดจาก SQLite Database ก่อน
  if os.path.exists(DB_PATH):
    try:
      import sqlite3

      with sqlite3.connect(DB_PATH) as conn:
        df_sql = pd.read_sql("SELECT * FROM officers_history", conn)
        if not df_sql.empty:
          return df_sql
    except Exception:
      pass

  # ถ้าไม่มีใน DB ให้ลองมองหาไฟล์ CSV
  if os.path.exists(DATA_PATH):
    return pd.read_csv(DATA_PATH)

  # ถ้าไม่มีทั้งสองอย่าง ให้สร้างตารางเปล่าโครงสร้างครบถ้วนเพื่อไม่ให้แอปพัง
  return pd.DataFrame(columns=[
      "ชื่อ",
      "นามสกุล",
      "ชื่อ-นามสกุล",
      "ประกาศฉบับที่",
      "หน่วยงาน",
      "จังหวัด",
      "ภาค",
      "ระยะวันที่หมดอายุไปแล้วหรือเหลืออีกกี่วันจะหมดอายุ",
      "รัฐมนตรี (minister)",
      "วันที่เริ่ม (announcement_date)",
      "วันหมดอายุบัตร (ค.ศ.)",
      "ลำดับรวม",
      "ลำดับตามประกาศ",
      "อีเมล",
  ])


df_raw = load_data()

if df_raw.empty:
  st.warning(
      "⚠️ ไม่พบข้อมูลในระบบ (เครื่องใหม่ยังไม่มีฐานข้อมูลหรือไฟล์ CSV)"
      " กรุณาไปที่หน้าจัดการระบบเพื่ออัปโหลดข้อมูล"
  )

# Data Preprocessing
df = df_raw.copy()
df["clean_full_name"] = (
    df.get("ชื่อ", pd.Series([""] * len(df)))
    .fillna("")
    .astype(str)
    .str.strip()
    + " "
    + df.get("นามสกุล", pd.Series([""] * len(df)))
    .fillna("")
    .astype(str)
    .str.strip()
)


def get_status_type(days):
  if pd.isna(days):
    return "UNKNOWN"
  try:
    d = int(days)
  except:
    return "UNKNOWN"

  if d < 0:
    return "EXPIRED"
  elif d <= 90:
    return "WARNING"
  else:
    return "ACTIVE"


if "ระยะวันที่หมดอายุไปแล้วหรือเหลืออีกกี่วันจะหมดอายุ" in df.columns:
  df["status_type"] = (
      df["ระยะวันที่หมดอายุไปแล้วหรือเหลืออีกกี่วันจะหมดอายุ"].apply(
          get_status_type
      )
  )
else:
  df["status_type"] = "UNKNOWN"

# Count Duplicates (Renewals / Multiple Appointments)
if not df.empty and "clean_full_name" in df.columns:
  name_counts = df["clean_full_name"].value_counts()
  df["is_duplicate"] = df["clean_full_name"].map(
      lambda x: name_counts.get(x, 0) > 1
  )
else:
  df["is_duplicate"] = False

# Sidebar Filters
st.sidebar.header("🔍 ตัวกรองข้อมูล (Filters)")
search_term = st.sidebar.text_input("ค้นหา (ชื่อ / ตำแหน่ง / หน่วยงาน):", "")

status_options = {
    "ทั้งหมด": "ALL",
    "🔴 หมดอายุแล้ว (Expired)": "EXPIRED",
    "🟡 ใกล้หมดอายุ (ภายใน 90 วัน)": "WARNING",
    "🟢 ปกติ (ยังไม่หมดอายุ)": "ACTIVE",
    "🔄 เฉพาะผู้ได้รับการแต่งตั้งซ้ำ/ต่ออายุ": "DUPLICATE",
}
selected_status_label = st.sidebar.selectbox(
    "สถานะการหมดอายุ:", list(status_options.keys())
)
selected_status = status_options[selected_status_label]

announcement_list = ["ทุกฉบับประกาศ"] + sorted([
    str(x)
    for x in df.get("ประกาศฉบับที่", pd.Series()).dropna().unique()
    if str(x) != "nan"
])
selected_ann = st.sidebar.selectbox("ประกาศฉบับที่:", announcement_list)

region_list = ["ทุกภาค"] + sorted(
    [str(x) for x in df.get("ภาค", pd.Series()).dropna().unique()]
)
selected_region = st.sidebar.selectbox("ภาค / พื้นที่:", region_list)

province_list = ["ทุกจังหวัด"] + sorted(
    [str(x) for x in df.get("จังหวัด", pd.Series()).dropna().unique()]
)
selected_province = st.sidebar.selectbox("จังหวัด:", province_list)

agency_list = ["ทุกหน่วยงาน"] + sorted(
    [str(x) for x in df.get("หน่วยงาน", pd.Series()).dropna().unique()]
)
selected_agency = st.sidebar.selectbox("หน่วยงาน:", agency_list)

# Apply Filtering
filtered_df = df.copy()

if search_term and not filtered_df.empty:
  term = search_term.lower()
  name_col = (
      "ชื่อ-นามสกุล"
      if "ชื่อ-นามสกุล" in filtered_df.columns
      else "clean_full_name"
  )
  filtered_df = filtered_df[
      filtered_df[name_col].fillna("").str.lower().str.contains(term)
      | filtered_df.get("หน่วยงาน", pd.Series([""] * len(filtered_df)))
      .fillna("")
      .str.lower()
      .str.contains(term)
  ]

if not filtered_df.empty:
  if selected_status == "EXPIRED":
    filtered_df = filtered_df[filtered_df["status_type"] == "EXPIRED"]
  elif selected_status == "WARNING":
    filtered_df = filtered_df[filtered_df["status_type"] == "WARNING"]
  elif selected_status == "ACTIVE":
    filtered_df = filtered_df[filtered_df["status_type"] == "ACTIVE"]
  elif selected_status == "DUPLICATE":
    filtered_df = filtered_df[filtered_df["is_duplicate"] == True]

  if selected_ann != "ทุกฉบับประกาศ" and "ประกาศฉบับที่" in filtered_df.columns:
    filtered_df = (
        filtered_df[filtered_df["ประกาศฉบับที่"].astype(str) == selected_ann]
    )

  if selected_region != "ทุกภาค" and "ภาค" in filtered_df.columns:
    filtered_df = filtered_df[filtered_df["ภาค"] == selected_region]

  if selected_province != "ทุกจังหวัด" and "จังหวัด" in filtered_df.columns:
    filtered_df = filtered_df[filtered_df["จังหวัด"] == selected_province]

  if selected_agency != "ทุกหน่วยงาน" and "หน่วยงาน" in filtered_df.columns:
    filtered_df = filtered_df[filtered_df["หน่วยงาน"] == selected_agency]

# Top KPI Metric Cards
total_count = int(len(filtered_df))
unique_count = (
    int(filtered_df["clean_full_name"].nunique())
    if not filtered_df.empty and "clean_full_name" in filtered_df.columns
    else 0
)
expired_count = (
    int((filtered_df["status_type"] == "EXPIRED").sum())
    if not filtered_df.empty
    else 0
)
warning_count = (
    int((filtered_df["status_type"] == "WARNING").sum())
    if not filtered_df.empty
    else 0
)
active_count = (
    int((filtered_df["status_type"] == "ACTIVE").sum())
    if not filtered_df.empty
    else 0
)
duplicate_count = (
    int(filtered_df["is_duplicate"].sum()) if not filtered_df.empty else 0
)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("👥 เจ้าหน้าที่ทั้งหมด", f"{total_count:,} รายการ", f"{unique_count:,} บุคคล")
col2.metric(
    "🔴 หมดอายุแล้ว",
    f"{expired_count:,}",
    (
        f"{(expired_count/total_count*100 if total_count > 0 else 0):.1f}%"
    ),
)
col3.metric("🟡 ใกล้หมดอายุ (90 วัน)", f"{warning_count:,}")
col4.metric("🟢 ยังไม่หมดอายุ (Active)", f"{active_count:,}")
col5.metric("🔄 แต่งตั้งซ้ำ / ต่ออายุ", f"{duplicate_count:,} รายการ")

st.markdown("---")

# Navigation Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 สรุปภาพรวม & กราฟสถิติ",
    "⏳ วิเคราะห์สถานะหมดอายุ & Timestamp",
    "🔄 รายชื่อเสนอชื่อซ้ำ / ต่ออายุ (Duplicate & Renewal)",
    "📋 ตารางค้นหาข้อมูลทั้งหมด (Full Directory)",
])

# Horizontal Bar Charts
with tab1:
  col_chart1, col_chart2 = st.columns(2)

  with col_chart1:
    st.subheader("🎯 สัดส่วนสถานะบัตรพนักงานเจ้าหน้าที่")
    status_df = pd.DataFrame({
        "สถานะ": ["ยังไม่หมดอายุ", "ใกล้หมดอายุ", "หมดอายุแล้ว"],
        "จำนวน": [active_count, warning_count, expired_count],
    })
    fig_status = px.bar(
        status_df,
        x="จำนวน",
        y="สถานะ",
        orientation="h",
        color="สถานะ",
        color_discrete_map={
            "ยังไม่หมดอายุ": "#10b981",
            "ใกล้หมดอายุ": "#f59e0b",
            "หมดอายุแล้ว": "#ef4444",
        },
        text="จำนวน",
    )
    fig_status.update_layout(
        showlegend=False, height=320, margin=dict(l=10, r=10, t=10, b=10)
    )
    st.plotly_chart(fig_status, use_container_width=True)

  with col_chart2:
    st.subheader("🗺️ จำนวนพนักงานเจ้าหน้าที่แยกตามภาค")
    if not filtered_df.empty and "ภาค" in filtered_df.columns:
      region_counts = filtered_df["ภาค"].value_counts().reset_index()
      region_counts.columns = ["ภาค", "จำนวน"]
      fig_region = px.bar(
          region_counts,
          x="จำนวน",
          y="ภาค",
          orientation="h",
          color_discrete_sequence=["#3b82f6"],
          text="จำนวน",
      )
      fig_region.update_layout(
          yaxis={"categoryorder": "total ascending"},
          height=320,
          margin=dict(l=10, r=10, t=10, b=10),
      )
      st.plotly_chart(fig_region, use_container_width=True)
    else:
      st.info("ไม่มีข้อมูลภาคสำหรับแสดงกราฟ")

  col_chart3, col_chart4 = st.columns(2)

  with col_chart3:
    st.subheader("✍️ แต่งตั้งแยกตามรัฐมนตรีผู้ลงนาม")
    min_col = (
        "รัฐมนตรี (minister)"
        if "รัฐมนตรี (minister)" in filtered_df.columns
        else None
    )
    if not filtered_df.empty and min_col:
      minister_counts = filtered_df[min_col].value_counts().reset_index()
      minister_counts.columns = ["รัฐมนตรี", "จำนวน"]
      fig_min = px.bar(
          minister_counts,
          x="จำนวน",
          y="รัฐมนตรี",
          orientation="h",
          color_discrete_sequence=["#8b5cf6"],
          text="จำนวน",
      )
      fig_min.update_layout(
          yaxis={"categoryorder": "total ascending"},
          height=320,
          margin=dict(l=10, r=10, t=10, b=10),
      )
      st.plotly_chart(fig_min, use_container_width=True)
    else:
      st.info("ไม่มีข้อมูลรัฐมนตรีสำหรับแสดงกราฟ")

  with col_chart4:
    st.subheader("🏢 Top 10 หน่วยงานที่มีพนักงานเจ้าหน้าที่มากที่สุด")
    if not filtered_df.empty and "หน่วยงาน" in filtered_df.columns:
      agency_counts = (
          filtered_df["หน่วยงาน"].value_counts().head(10).reset_index()
      )
      agency_counts.columns = ["หน่วยงาน", "จำนวน"]
      fig_agency = px.bar(
          agency_counts,
          x="จำนวน",
          y="หน่วยงาน",
          orientation="h",
          color_discrete_sequence=["#06b6d4"],
          text="จำนวน",
      )
      fig_agency.update_layout(
          yaxis={"categoryorder": "total ascending"},
          height=320,
          margin=dict(l=10, r=10, t=10, b=10),
      )
      st.plotly_chart(fig_agency, use_container_width=True)
    else:
      st.info("ไม่มีข้อมูลหน่วยงานสำหรับแสดงกราฟ")


def style_days(val):
  if pd.isna(val):
    return ""
  try:
    v = int(val)
  except:
    return ""
  if v < 0:
    return (
        "color: #ef4444; font-weight: bold; background-color: rgba(239, 68, 68,"
        " 0.1);"
    )
  elif v <= 90:
    return (
        "color: #d97706; font-weight: bold; background-color: rgba(245, 158,"
        " 11, 0.1);"
    )
  else:
    return (
        "color: #10b981; font-weight: bold; background-color: rgba(16, 185,"
        " 129, 0.1);"
    )


# TAB 2: EXPIRATION & TIMESTAMP ANALYSIS
with tab2:
  st.subheader(
      "⏳ ตารางวิเคราะห์ Timestamp และระยะเวลาหมดอายุ (Days Expired /"
      " Remaining)"
  )
  st.info(
      "💡 สัญลักษณ์สีตัวเลขระยะเวลา: 🔴 สีแดง = หมดอายุแล้ว | 🟡 สีเหลือง ="
      " ใกล้หมดอายุ (<= 90 วัน) | 🟢 สีเขียว = ยังไม่หมดอายุ"
  )

  if (
      not filtered_df.empty
      and "ระยะวันที่หมดอายุไปแล้วหรือเหลืออีกกี่วันจะหมดอายุ"
      in filtered_df.columns
  ):
    exp_df = filtered_df.sort_values(
        by="ระยะวันที่หมดอายุไปแล้วหรือเหลืออีกกี่วันจะหมดอายุ", ascending=True
    )
    cols_check = [
        "ลำดับรวม",
        "ชื่อ-นามสกุล",
        "หน่วยงาน",
        "จังหวัด",
        "ประกาศฉบับที่",
        "วันที่เริ่ม (announcement_date)",
        "วันหมดอายุบัตร (ค.ศ.)",
        "ระยะวันที่หมดอายุไปแล้วหรือเหลืออีกกี่วันจะหมดอายุ",
        "รัฐมนตรี (minister)",
    ]
    actual_cols = [c for c in cols_check if c in exp_df.columns]
    exp_display = exp_df[actual_cols].copy()

    exp_styled = exp_display.style.map(
        style_days,
        subset=["ระยะวันที่หมดอายุไปแล้วหรือเหลืออีกกี่วันจะหมดอายุ"],
    )
    st.dataframe(exp_styled, use_container_width=True, height=500)
  else:
    st.info("ไม่มีข้อมูลระยะเวลาหมดอายุสำหรับแสดงตาราง")

# TAB 3: DUPLICATE & RENEWAL TRACKER
with tab3:
  st.subheader(
      "🔄 รายชื่อพนักงานเจ้าหน้าที่ที่ได้รับการเสนอชื่อซ้ำ / แต่งตั้งซ้ำ / ต่ออายุ"
  )
  if not df.empty and "is_duplicate" in df.columns:
    dup_names = df[df["is_duplicate"]]["clean_full_name"].unique()
  else:
    dup_names = []

  if len(dup_names) == 0:
    st.success("ไม่พบข้อมูลผู้ได้รับการแต่งตั้งซ้ำหรือต่ออายุ")
  else:
    for name in dup_names:
      person_records = df[df["clean_full_name"] == name].sort_values(
          by="ประกาศฉบับที่"
      )
      with st.expander(
          f"👤 {name} มีประวัติการแต่งตั้ง {len(person_records)} ฉบับประกาศ",
          expanded=False,
      ):
        cols = st.columns(len(person_records) if len(person_records) > 0 else 1)
        for idx, (_, rec) in enumerate(person_records.iterrows()):
          with cols[idx]:
            days = rec.get(
                "ระยะวันที่หมดอายุไปแล้วหรือเหลืออีกกี่วันจะหมดอายุ", 0
            )
            try:
              d_val = int(days)
            except:
              d_val = 0

            if d_val < 0:
              status_str = f"<span style='color:#ef4444; font-weight:bold;'>🔴 หมดอายุแล้ว ({d_val} วัน)</span>"
            elif d_val <= 90:
              status_str = f"<span style='color:#d97706; font-weight:bold;'>🟡 ใกล้หมดอายุ (เหลือ {d_val} วัน)</span>"
            else:
              status_str = f"<span style='color:#10b981; font-weight:bold;'>🟢 ปกติ (เหลือ {d_val} วัน)</span>"

            st.markdown(
                f"""
                        **ฉบับที่ {rec.get('ประกาศฉบับที่', '-')}** (ลำดับที่ {rec.get('ลำดับตามประกาศ', '-')})
                        - 🏢 **สังกัด:** {rec.get('หน่วยงาน', '-')}
                        - 📍 **จังหวัด:** {rec.get('จังหวัด', '-')}
                        - 📅 **เริ่ม:** {rec.get('วันที่เริ่ม (announcement_date)', '-')}
                        - 📅 **หมดอายุ:** {rec.get('วันหมดอายุบัตร (ค.ศ.)', '-')}
                        - ✍️ **รัฐมนตรี:** {rec.get('รัฐมนตรี (minister)', '-')}
                        - 📌 **สถานะ:** {status_str}
                        """,
                unsafe_allow_html=True,
            )

# TAB 4: FULL DIRECTORY & CSV DOWNLOAD
with tab4:
  st.subheader("📋 ตารางพนักงานเจ้าหน้าที่ทั้งหมด (Full Officer Directory)")

  if (
      not filtered_df.empty
      and "ระยะวันที่หมดอายุไปแล้วหรือเหลืออีกกี่วันจะหมดอายุ"
      in filtered_df.columns
  ):
    main_styled = filtered_df.style.map(
        style_days,
        subset=["ระยะวันที่หมดอายุไปแล้วหรือเหลืออีกกี่วันจะหมดอายุ"],
    )
    st.dataframe(main_styled, use_container_width=True, height=500)
  else:
    st.dataframe(filtered_df, use_container_width=True, height=500)

  csv_data = filtered_df.to_csv(index=False, encoding="utf-8-sig")
  st.download_button(
      label="📥 ดาวน์โหลดข้อมูลเป็น CSV (ภาษาไทย)",
      data=csv_data,
      file_name="officers_export.csv",
      mime="text/csv",
  )