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
        if isinstance(value, pd.Timedelta):
            return round(value.total_seconds() / 3600, 2)

        value = str(value).strip().replace("Õ", "").strip()

        if value.lower() in ["", "nan", "nat", "none"]:
            return 0.0

        value = value.split()[0]
        parts = value.split(":")

        if len(parts) == 1:
            return float(parts[0])

        h = int(parts[0])
        m = int(parts[1])
        s = int(parts[2]) if len(parts) > 2 else 0

        return round(h + (m / 60) + (s / 3600), 2)

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
        return f"{float(value):,.2f}"
    except Exception:
        return "0.00"


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


def build_report(att_df, emp_df, start_date, end_date):
    att_df = clean_columns(att_df)

    if "AC-No." not in att_df.columns:
        st.error("❌ ملف البصمة لا يحتوي على عمود AC-No.")
        st.stop()

    if "Date" not in att_df.columns:
        st.error("❌ ملف البصمة لا يحتوي على عمود Date")
        st.stop()

    for col in ["Clock In", "Clock Out", "ATT_Time", "OT Time", "Late", "Early"]:
        if col not in att_df.columns:
            att_df[col] = 0

    att_df["employee_id"] = pd.to_numeric(att_df["AC-No."], errors="coerce")
    att_df = att_df.dropna(subset=["employee_id"])
    att_df["employee_id"] = att_df["employee_id"].astype(int)

    att_df["Date"] = pd.to_datetime(att_df["Date"], errors="coerce").dt.date
    att_df = att_df.dropna(subset=["Date"])

    att_df = att_df[
        (att_df["Date"] >= start_date)
        &
        (att_df["Date"] <= end_date)
    ].copy()

    if att_df.empty:
        st.warning("⚠️ لا توجد بيانات داخل الفترة المحددة.")
        st.stop()

    att_df["work_hours"] = att_df.apply(calc_work_hours, axis=1)
    att_df["overtime_hours"] = att_df["OT Time"].apply(parse_duration_to_hours)
    att_df["late_hours"] = att_df["Late"].apply(parse_duration_to_hours)
    att_df["early_hours"] = att_df["Early"].apply(parse_duration_to_hours)

    summary = att_df.groupby("employee_id", as_index=False).agg(
        attendance_days=("Date", "nunique"),
        first_date=("Date", "min"),
        last_date=("Date", "max"),
        work_hours=("work_hours", "sum"),
        overtime_hours=("overtime_hours", "sum"),
        late_hours=("late_hours", "sum"),
        early_hours=("early_hours", "sum"),
    )

    emp_cols = [
        "employee_id",
        "Name",
        "Arabic name",
        "Nationality",
        "Section | Department",
        "attendance_calculation",
    ]

    summary = summary.merge(
        emp_df[emp_cols],
        on="employee_id",
        how="left"
    )

    for col in ["Name", "Arabic name", "Nationality", "Section | Department", "attendance_calculation"]:
        summary[col] = summary[col].fillna("")

    for col in ["work_hours", "overtime_hours", "late_hours", "early_hours"]:
        summary[col] = summary[col].round(2)

    details = att_df.drop(columns=["Name"], errors="ignore")

    details = details.merge(
        emp_df[
            [
                "employee_id",
                "Name",
                "Arabic name",
                "Nationality",
                "Section | Department",
            ]
        ],
        on="employee_id",
        how="left",
        suffixes=("", "_emp")
    )


    # =====================================================
    # FIX COLUMN NAMES
    # =====================================================

    if "Name" not in details.columns:

        if "Name_emp" in details.columns:
            details["Name"] = details["Name_emp"]

        elif "Name_x" in details.columns:
            details["Name"] = details["Name_x"]

        elif "Name_y" in details.columns:
            details["Name"] = details["Name_y"]

        else:
            details["Name"] = ""

    if "Arabic name" not in details.columns:

        if "Arabic name_emp" in details.columns:
            details["Arabic name"] = details["Arabic name_emp"]

        elif "Arabic name_x" in details.columns:
            details["Arabic name"] = details["Arabic name_x"]

        elif "Arabic name_y" in details.columns:
            details["Arabic name"] = details["Arabic name_y"]

        else:
            details["Arabic name"] = ""
            

    for col in ["Name", "Arabic name", "Nationality", "Section | Department"]:
        details[col] = details[col].fillna("")

    details = details[
        [
            "employee_id",
            "Arabic name",
            "Name",
            "Nationality",
            "Section | Department",
            "Date",
            "Clock In",
            "Clock Out",
            "ATT_Time",
            "OT Time",
            "work_hours",
            "overtime_hours",
            "late_hours",
            "early_hours",
        ]
    ]

    summary = summary.sort_values(["Section | Department", "employee_id"])
    details = details.sort_values(["employee_id", "Date"])

    return summary, details


def create_pdf(summary_df, details_df, start_date, end_date, lang="ar"):
    buffer = BytesIO()

    try:
        pdfmetrics.registerFont(TTFont("Arabic", "fonts/Amiri-Regular.ttf"))
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

    try:

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

            except:
                pass

        elements.append(logo)

        elements.append(
            Spacer(1, 5)
        )

    except:
        pass

    for emp_index, (_, emp) in enumerate(summary_df.iterrows()):

        emp_id = emp["employee_id"]
        emp_details = details_df[details_df["employee_id"] == emp_id]

        if emp_index > 0:
            elements.append(PageBreak())

        if lang == "ar":
            title = "ملخص الحضور الشهري"
            emp_name = (
                        f'{emp["Arabic name"]}<br/><font size="14">'
                        f'{emp["Name"]}</font>'
                    )
            dept = emp["Section | Department"]
            period = f"الفترة من {start_date} إلى {end_date}"

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

            emp_name = (
                f'{emp["Arabic name"]}<br/>'
                f'<font size="14">{emp["Name"]}</font>'
            )
            dept = emp["Section | Department"]
            period = f"Period from {start_date} to {end_date}"

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

        elements.append(
            Paragraph(
                ar_text(title) if lang == "ar" else title,
                title_style
            )
        )

        elements.append(
            Paragraph(
                ar_text(period) if lang == "ar" else period,
                normal_style
            )
        )

        # =====================================================
        # EMPLOYEE HEADER
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

        if lang == "ar":

            employee_header = ar_text(emp_name)

            employee_sub = ar_text(
                f"الرقم الوظيفي: {emp_id} | الإدارة: {dept}"
            )

            arabic_name = ar_text(emp["Arabic name"])
            english_name = emp["Name"]
        else:

            employee_header = emp_name

            employee_sub = (
                f"Employee ID: {emp_id} | Department: {dept}"
            )

            arabic_name = ar_text(emp["Arabic name"])
            english_name = emp["Name"]

        # =====================================================
        # ARABIC NAME
        # =====================================================

        elements.append(
            Paragraph(
                arabic_name,
                employee_header_style
            )
        )

        # =====================================================
        # ENGLISH NAME
        # =====================================================

        english_style = ParagraphStyle(
            "english_style",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=24,
            alignment=1,
            textColor=colors.HexColor("#64748b"),
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
            Spacer(1, 16)
        )

        elements.append(Spacer(1, 12))

        summary_data = [
            [
                ar_text(h) if lang == "ar" else h
                for h in header
            ],
            [
                str(emp["employee_id"]),
                ar_text(emp["Arabic name"]) if lang == "ar" else str(emp["Name"]),
                ar_text(emp["Section | Department"]) if lang == "ar" else str(emp["Section | Department"]),
                ar_text(emp["Nationality"]) if lang == "ar" else str(emp["Nationality"]),
                str(emp["attendance_days"]),
                format_num(emp["work_hours"]),
                format_num(emp["overtime_hours"]),
                format_num(emp["late_hours"]),
                format_num(emp["early_hours"]),
            ]
        ]

        summary_table = Table(summary_data, repeatRows=1)

        summary_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))

        elements.append(summary_table)
        elements.append(Spacer(1, 16))

        details_data = [
            [
                ar_text(h) if lang == "ar" else h
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

        details_table = Table(details_data, repeatRows=1)

        details_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                colors.white,
                colors.HexColor("#f8fafc")
            ]),
        ]))

        elements.append(details_table)

        # =====================================================
        # SIGNATURE
        # =====================================================

        elements.append(
            Spacer(1, 30)
        )

        try:

            sign = Image(
                "sign.png",
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

            elements.append(sign_table)

        except:
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
                    "logo.png",
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