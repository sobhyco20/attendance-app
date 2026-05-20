import streamlit as st
import pandas as pd
from datetime import date
from io import BytesIO
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    PageBreak,
    Image
)
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    PageBreak,
    Image
)

st.set_page_config(page_title="Monthly Attendance", layout="wide")


st.markdown("""
<style>

.stApp{
    background:#020817;
    color:#f8fafc;
    direction:rtl;
}

/* SIDEBAR */

section[data-testid="stSidebar"]{
    background:#0f172a;
    border-left:1px solid #1e293b;
}

/* CARDS */

.employee-card{
    background:linear-gradient(145deg,#0f172a,#111827);
    border:1px solid #1e293b;
    border-radius:28px;
    padding:30px;
    margin-bottom:30px;
    box-shadow:0 10px 30px rgba(0,0,0,.35);
}

/* KPI */

.kpi-card{
    background:#0f172a;
    border:1px solid #1e293b;
    border-radius:22px;
    padding:18px;
}

/* METRICS */

[data-testid="stMetric"]{
    background:#0f172a;
    border:1px solid #1e293b;
    padding:18px;
    border-radius:22px;
    text-align:center;
    box-shadow:0 4px 18px rgba(0,0,0,.25);
}

[data-testid="stMetricLabel"]{
    justify-content:center;
}

[data-testid="stMetricLabel"] p{
    color:#94a3b8 !important;
    font-size:15px !important;
    font-weight:700 !important;
}

[data-testid="stMetricValue"]{
    color:#ffffff !important;
    font-size:38px !important;
    font-weight:900 !important;
}

/* TABLE */

div[data-testid="stDataFrame"]{
    border:1px solid #1e293b;
    border-radius:20px;
    overflow:hidden;
}

/* BUTTONS */

.stDownloadButton button{
    background:linear-gradient(135deg,#2563eb,#1d4ed8);
    color:white;
    border:none;
    border-radius:16px;
    height:52px;
    font-weight:700;
    font-size:16px;
}

.stDownloadButton button:hover{
    background:linear-gradient(135deg,#1d4ed8,#1e40af);
    color:white;
}

/* UPLOADER */

div[data-testid="stFileUploader"]{
    background:#0f172a;
    border:1px solid #1e293b;
    border-radius:22px;
    padding:20px;
}

/* TEXT */

h1,h2,h3,h4,h5,h6,p,label,span{
    color:#f8fafc;
}

            

.stTitle {
    color:#ffffff !important;
}

[data-testid="stCaptionContainer"] {
    color:#94a3b8 !important;
    font-size:22px !important;
    font-weight:700 !important;
}

            
div[data-testid="stVerticalBlockBorderWrapper"]{
    background:linear-gradient(145deg,#0f172a,#111827);
    border:1px solid #1e293b !important;
    border-radius:30px !important;
    padding:25px !important;
    box-shadow:0 12px 30px rgba(0,0,0,.35);
}

h1{
    color:#ffffff !important;
    font-size:42px !important;
    font-weight:900 !important;
}

[data-testid="stCaptionContainer"]{
    color:#94a3b8 !important;
    font-size:22px !important;
    font-weight:700 !important;
}


</style>
            
""", unsafe_allow_html=True)



def ar_text(text):
    if pd.isna(text):
        return ""
    text = str(text)
    return get_display(arabic_reshaper.reshape(text))


def get_period(year, month):
    if month == 1:
        start_date = date(year - 1, 12, 8)
    else:
        start_date = date(year, month - 1, 8)

    end_date = date(year, month, 7)
    return start_date, end_date


def clean_columns(df):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df

def parse_duration_to_hours(value):

    if pd.isna(value):
        return 0.0

    try:

        # =========================================
        # TIMEDELTA
        # =========================================

        if isinstance(value, pd.Timedelta):

            return value.total_seconds() / 3600

        value = str(value).strip()

        if value.lower() in ["", "nan", "nat", "none"]:
            return 0.0

        # =========================================
        # REMOVE EXTRA TEXT
        # =========================================

        value = value.replace("Õ", "").strip()

        # =========================================
        # HANDLE DAYS FORMAT
        # مثال:
        # 1 days 02:30:15
        # =========================================

        if "day" in value.lower():

            td = pd.to_timedelta(value)

            return td.total_seconds() / 3600

        # =========================================
        # SPLIT HH:MM:SS
        # =========================================

        parts = value.split(":")

        if len(parts) == 1:

            return float(parts[0])

        hours = int(parts[0])

        minutes = int(parts[1])

        seconds = int(parts[2]) if len(parts) > 2 else 0

        total_hours = (
            hours
            + (minutes / 60)
            + (seconds / 3600)
        )

        return total_hours

    except Exception:

        return 0.0

def calc_work_hours(row):
    att_hours = parse_duration_to_hours(row.get("ATT_Time", 0))

    if att_hours > 0:
        return att_hours

    try:
        clock_in = str(row.get("Clock In", "")).strip()
        clock_out = str(row.get("Clock Out", "")).strip()

        if clock_in.lower() in ["", "nan", "nat", "none"]:
            return 0.0

        if clock_out.lower() in ["", "nan", "nat", "none"]:
            return 0.0

        start = pd.to_datetime(clock_in).time()
        end = pd.to_datetime(clock_out).time()

        start_dt = pd.Timestamp.combine(date.today(), start)
        end_dt = pd.Timestamp.combine(date.today(), end)

        if end_dt < start_dt:
            end_dt += pd.Timedelta(days=1)

        return round((end_dt - start_dt).total_seconds() / 3600, 2)

    except Exception:
        return 0.0


def format_num(value):

    try:

        total_seconds = int(float(value) * 3600)

        hours = total_seconds // 3600

        minutes = (total_seconds % 3600) // 60

        seconds = total_seconds % 60

        return f"{hours:02}:{minutes:02}:{seconds:02}"

    except Exception:

        return "00:00:00"


def load_employees():
    try:
        emp_df = pd.read_excel("employees.xlsx")
    except Exception:
        st.error("❌ ملف employees.xlsx غير موجود بجانب app.py")
        st.stop()

    emp_df = clean_columns(emp_df)

    rename_map = {
        "Employee ID": "employee_id",
        "Emp ID": "employee_id",
        "AC-No.": "employee_id",
        "AC-No": "employee_id",
        "Arabic Name": "Arabic name",
        "Employee Name": "Name",
        "Department": "Section | Department",
        "Section": "Section | Department",
    }

    emp_df.rename(columns=rename_map, inplace=True)

    required_cols = [
        "employee_id",
        "Name",
        "Arabic name",
        "Nationality",
        "Section | Department",
        "attendance_calculation",
    ]

    for col in required_cols:
        if col not in emp_df.columns:
            emp_df[col] = ""

    emp_df["employee_id"] = pd.to_numeric(emp_df["employee_id"], errors="coerce")
    emp_df = emp_df.dropna(subset=["employee_id"])
    emp_df["employee_id"] = emp_df["employee_id"].astype(int)
    emp_df = emp_df.drop_duplicates(subset=["employee_id"])

    return emp_df


def create_pdf(summary_df, details_df, start_date, end_date, lang="ar"):

    buffer = BytesIO()

    try:

        pdfmetrics.registerFont(
            TTFont(
                "Arabic",
                "fonts/Amiri-Regular.ttf"
            )
        )

        font_name = "Arabic"

    except Exception:

        font_name = "Helvetica"

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18,
        leftMargin=18,
        topMargin=18,
        bottomMargin=18,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "title_style",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=16,
        alignment=1,
    )

    normal_style = ParagraphStyle(
        "normal_style",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=9,
        alignment=1,
    )

    elements = []

    # =====================================================
    # LOGO
    # =====================================================

    import os

    logo_path = "assets/logo.png"

    if os.path.exists(logo_path):

        try:

            logo = Image(
                logo_path,
                width=120,
                height=30
            )

            elements.append(logo)

            elements.append(
                Spacer(1, 5)
            )

        except Exception:
            pass

    # =====================================================
    # EMPLOYEES LOOP
    # =====================================================

    for emp_index, (_, emp) in enumerate(summary_df.iterrows()):

        emp_id = emp["employee_id"]

        emp_details = details_df[
            details_df["employee_id"] == emp_id
        ]

        if emp_index > 0:

            elements.append(
                PageBreak()
            )

        # =====================================================
        # TITLES
        # =====================================================

        if lang == "ar":

            title = "ملخص الحضور الشهري"

            dept = emp["Section | Department"]

            period = (
                f"الفترة من {start_date} إلى {end_date}"
            )

            header = [
                "كود الموظف",
                "اسم الموظف",
                "الإدارة",
                "الجنسية",
                "أيام الحضور",
                "ساعات العمل",
                "الإضافي",
                "التأخير",
                "خروج مبكر",
            ]

            detail_header = [
                "التاريخ",
                "الدخول",
                "الخروج",
                "ساعات العمل",
                "الإضافي",
                "التأخير",
                "خروج مبكر",
            ]

        else:

            title = "Monthly Attendance Summary"

            dept = emp["Section | Department"]

            period = (
                f"Period from {start_date} to {end_date}"
            )

            header = [
                "Employee ID",
                "Employee",
                "Department",
                "Nationality",
                "Attendance Days",
                "Work Hours",
                "Overtime",
                "Late",
                "Early",
            ]

            detail_header = [
                "Date",
                "Clock In",
                "Clock Out",
                "Work Hours",
                "Overtime",
                "Late",
                "Early",
            ]

        # =====================================================
        # REPORT HEADER
        # =====================================================

        elements.append(
            Paragraph(
                ar_text(title)
                if lang == "ar"
                else title,
                title_style
            )
        )

        elements.append(
            Paragraph(
                ar_text(period)
                if lang == "ar"
                else period,
                normal_style
            )
        )

        elements.append(
            Spacer(1, 15)
        )

        # =====================================================
        # EMPLOYEE NAME STYLE
        # =====================================================

        employee_header_style = ParagraphStyle(
            "employee_header_style",
            parent=styles["Heading1"],
            fontName=font_name,
            fontSize=28,
            leading=40,
            alignment=1,
            textColor=colors.HexColor("#0f172a"),
        )

        employee_sub_style = ParagraphStyle(
            "employee_sub_style",
            parent=styles["Normal"],
            fontName=font_name,
            fontSize=15,
            leading=20,
            alignment=1,
            textColor=colors.HexColor("#334155"),
        )

        english_style = ParagraphStyle(
            "english_style",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=24,
            alignment=1,
            textColor=colors.HexColor("#64748b"),
        )

        arabic_name = ar_text(
            emp["Arabic name"]
        )

        english_name = emp["Name"]

        if lang == "ar":

            employee_sub = ar_text(
                f"الرقم الوظيفي: {emp_id} | الإدارة: {dept}"
            )

        else:

            employee_sub = (
                f"Employee ID: {emp_id} | Department: {dept}"
            )

        elements.append(
            Paragraph(
                arabic_name,
                employee_header_style
            )
        )

        elements.append(
            Paragraph(
                english_name,
                english_style
            )
        )

        elements.append(
            Paragraph(
                employee_sub,
                employee_sub_style
            )
        )

        elements.append(
            Spacer(1, 18)
        )

        # =====================================================
        # SUMMARY TABLE
        # =====================================================

        summary_data = [

            [
                ar_text(h)
                if lang == "ar"
                else h
                for h in header
            ],

            [
                str(emp["employee_id"]),

                ar_text(emp["Arabic name"])
                if lang == "ar"
                else str(emp["Name"]),

                ar_text(emp["Section | Department"])
                if lang == "ar"
                else str(emp["Section | Department"]),

                ar_text(emp["Nationality"])
                if lang == "ar"
                else str(emp["Nationality"]),

                str(emp["attendance_days"]),

                format_num(emp["work_hours"]),

                format_num(emp["overtime_hours"]),

                format_num(emp["late_hours"]),

                format_num(emp["early_hours"]),
            ]
        ]

        summary_table = Table(

            summary_data,

            repeatRows=1,

            colWidths=[
                55,
                95,
                80,
                55,
                55,
                65,
                65,
                65,
                65,
            ]
        )

        summary_table.setStyle(TableStyle([

            ("FONTNAME", (0, 0), (-1, -1), font_name),

            ("BACKGROUND", (0, 0), (-1, 0),
             colors.HexColor("#0f172a")),

            ("TEXTCOLOR", (0, 0), (-1, 0),
             colors.white),

            ("GRID", (0, 0), (-1, -1),
             0.4, colors.grey),

            ("ALIGN", (0, 0), (-1, -1),
             "CENTER"),

            ("VALIGN", (0,0), (-1,-1),
             "MIDDLE"),

            ("FONTSIZE", (0, 0), (-1, -1),
             7),

            ("BOTTOMPADDING", (0,0), (-1,-1),
             6),

            ("TOPPADDING", (0,0), (-1,-1),
             6),

        ]))

        elements.append(summary_table)

        elements.append(
            Spacer(1, 18)
        )

        # =====================================================
        # DETAILS TABLE
        # =====================================================

        details_data = [

            [
                ar_text(h)
                if lang == "ar"
                else h
                for h in detail_header
            ]
        ]

        for _, d in emp_details.iterrows():

            details_data.append([

                str(d["Date"]),

                str(d["Clock In"]),

                str(d["Clock Out"]),

                format_num(d["work_hours"]),

                format_num(d["overtime_hours"]),

                format_num(d["late_hours"]),

                format_num(d["early_hours"]),
            ])

        details_table = Table(

            details_data,

            repeatRows=1,

            colWidths=[
                75,
                75,
                75,
                65,
                65,
                65,
                65,
            ]
        )

        details_table.setStyle(TableStyle([

            ("FONTNAME", (0, 0), (-1, -1), font_name),

            ("BACKGROUND", (0, 0), (-1, 0),
             colors.HexColor("#1e293b")),

            ("TEXTCOLOR", (0, 0), (-1, 0),
             colors.white),

            ("GRID", (0, 0), (-1, -1),
             0.4, colors.grey),

            ("ALIGN", (0, 0), (-1, -1),
             "CENTER"),

            ("VALIGN", (0,0), (-1,-1),
             "MIDDLE"),

            ("FONTSIZE", (0, 0), (-1, -1),
             7),

            ("BOTTOMPADDING", (0,0), (-1,-1),
             6),

            ("TOPPADDING", (0,0), (-1,-1),
             6),

            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                colors.white,
                colors.HexColor("#f8fafc")
            ]),

        ]))

        elements.append(
            details_table
        )

        # =====================================================
        # SIGNATURE
        # =====================================================

        sign_path = "assets/sign.png"

        if os.path.exists(sign_path):

            try:

                elements.append(
                    Spacer(1, 30)
                )

                sign = Image(
                    sign_path,
                    width=140,
                    height=70
                )

                sign_table = Table(
                    [[sign]],
                    colWidths=[500]
                )

                sign_table.setStyle(
                    TableStyle([
                        ("ALIGN", (0,0), (-1,-1), "RIGHT"),
                    ])
                )

                elements.append(
                    sign_table
                )

            except Exception:
                pass

    doc.build(elements)

    buffer.seek(0)

    return buffer.getvalue()


today = date.today()

with st.sidebar:
    st.header("⚙️ إعدادات التقرير")

    year = st.number_input(
        "السنة",
        min_value=2020,
        max_value=2035,
        value=today.year,
    )

    month = st.selectbox(
        "شهر التقرير",
        list(range(1, 13)),
        index=today.month - 1,
    )

    start_date, end_date = get_period(int(year), int(month))

    st.success(f"الفترة: {start_date} → {end_date}")


emp_df = load_employees()

uploaded_file = st.file_uploader(
    "📄 ارفع ملف البصمة",
    type=["xlsx", "xls"]
)

if uploaded_file is None:
    st.info("ارفع ملف البصمة لعرض الملخص الشهري.")
    st.stop()


attendance_df = pd.read_excel(uploaded_file)

summary_df, details_df = build_report(
    attendance_df,
    emp_df,
    start_date,
    end_date
)


with st.sidebar:

    st.header("🔍 اختيار الموظف")

    employee_options = ["كل الموظفين"]

    for _, row in summary_df.iterrows():

        employee_options.append(
            f'{row["employee_id"]} - {row["Arabic name"] or row["Name"]}'
        )

    selected_employee = st.selectbox(
        "الموظف",
        employee_options
    )

    # =========================================
    # SIDEBAR FOOTER LOGO
    # =========================================

    st.markdown("<br><br><br>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1,2,1])

    with c2:

        try:

            st.image(
                "sing.png",
                width=170
            )

        except:
            pass

    st.markdown("<br>", unsafe_allow_html=True)

filtered_summary = summary_df.copy()
filtered_details = details_df.copy()

if selected_employee != "كل الموظفين":
    selected_id = int(selected_employee.split(" - ")[0])

    filtered_summary = summary_df[
        summary_df["employee_id"] == selected_id
    ]

    filtered_details = details_df[
        details_df["employee_id"] == selected_id
    ]
for _, emp in filtered_summary.iterrows():

    emp_id = emp["employee_id"]

    emp_details = filtered_details[
        filtered_details["employee_id"] == emp_id
    ]

    # =====================================================
    # EMPLOYEE HEADER CARD
    # =====================================================

    st.markdown(
        """
        <div style="
            background:linear-gradient(145deg,#0f172a,#111827);
            border:1px solid #1e293b;
            border-radius:30px;
            padding:35px;
            margin-bottom:25px;
            box-shadow:0 12px 30px rgba(0,0,0,.35);
        ">
        """,
        unsafe_allow_html=True
    )

    # =====================================================
    # TOP AREA
    # =====================================================



    with st.container(border=True):

        top1, top2 = st.columns([6,1])

        with top1:

            st.markdown("<br>", unsafe_allow_html=True)

            st.title(
                f'👤 {emp["Arabic name"]}'
            )

            st.caption(
                emp["Name"]
            )

            st.markdown("<br>", unsafe_allow_html=True)

        with top2:

            st.markdown("<br>", unsafe_allow_html=True)

            try:

                st.image(
                    "assets/logo.png",
                    width=120
                )

            except:
                pass

    # =====================================================
    # EMPLOYEE INFO
    # =====================================================

    st.markdown("<br>", unsafe_allow_html=True)

    info1, info2, info3 = st.columns(3)

    with info1:

        st.markdown(
            """
            <div style="
                background:#020817;
                border:1px solid #1e293b;
                border-radius:22px;
                padding:18px;
            ">
            """,
            unsafe_allow_html=True
        )

        st.metric(
            "الرقم الوظيفي",
            emp_id
        )

        st.markdown("</div>", unsafe_allow_html=True)

    with info2:

        st.markdown(
            """
            <div style="
                background:#020817;
                border:1px solid #1e293b;
                border-radius:22px;
                padding:18px;
            ">
            """,
            unsafe_allow_html=True
        )

        st.metric(
            "الإدارة",
            emp["Section | Department"]
        )

        st.markdown("</div>", unsafe_allow_html=True)

    with info3:

        st.markdown(
            """
            <div style="
                background:#020817;
                border:1px solid #1e293b;
                border-radius:22px;
                padding:18px;
            ">
            """,
            unsafe_allow_html=True
        )

        st.metric(
            "الجنسية",
            emp["Nationality"]
        )

        st.markdown("</div>", unsafe_allow_html=True)

    # =====================================================
    # KPIS
    # =====================================================

    st.markdown("<br>", unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)

    with k1:

        st.metric(
            "أيام الحضور",
            int(emp["attendance_days"])
        )

    with k2:

        st.metric(
            "ساعات العمل",
            round(emp["work_hours"], 2)
        )

    with k3:

        st.metric(
            "الإضافي",
            round(emp["overtime_hours"], 2)
        )

    with k4:

        st.metric(
            "التأخير",
            round(emp["late_hours"], 2)
        )

    # =====================================================
    # END CARD
    # =====================================================

    st.markdown(
        "</div>",
        unsafe_allow_html=True
    )





st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown("""
<div style="
    font-size:28px;
    font-weight:900;
    margin-bottom:20px;
">
    ⬇️ تصدير التقارير
</div>
""", unsafe_allow_html=True)
st.subheader("⬇️ التصدير")

pdf_ar = create_pdf(
    filtered_summary,
    filtered_details,
    start_date,
    end_date,
    lang="ar"
)

pdf_en = create_pdf(
    filtered_summary,
    filtered_details,
    start_date,
    end_date,
    lang="en"
)

excel_buffer = BytesIO()

with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
    filtered_summary.to_excel(writer, sheet_name="Summary", index=False)
    filtered_details.to_excel(writer, sheet_name="Details", index=False)

excel_buffer.seek(0)

col1, col2, col3 = st.columns(3)

with col1:
    st.download_button(
        label="📄 تحميل PDF عربي",
        data=pdf_ar,
        file_name="monthly_attendance_ar.pdf",
        mime="application/pdf",
        width="stretch",
    )

with col2:
    st.download_button(
        label="📄 Download English PDF",
        data=pdf_en,
        file_name="monthly_attendance_en.pdf",
        mime="application/pdf",
        width="stretch",
    )

with col3:
    st.download_button(
        label="📊 تحميل Excel",
        data=excel_buffer,
        file_name="monthly_attendance_summary.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )

st.markdown("</div>", unsafe_allow_html=True)
