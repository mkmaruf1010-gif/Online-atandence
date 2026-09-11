from datetime import date
import io
import urllib.parse
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from PIL import Image
import qrcode
import requests
import streamlit as st

# Page Configuration
st.set_page_config(
    page_title="OASIS - Attendance System",
    layout="wide",
)

# -------------------------------------------------------------
# GOOGLE SHEETS CONNECTION SETUP
# -------------------------------------------------------------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


@st.cache_resource
def init_connection():
    credentials_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(
        credentials_dict, scopes=SCOPES
    )
    client = gspread.authorize(creds)
    return client


try:
    client = init_connection()
    sheet = client.open("OASIS")
    students_worksheet = sheet.worksheet("Students")
    attendance_worksheet = sheet.worksheet("Attendance")
except Exception as e:
    st.error(
        f"Failed to connect to Google Sheets. Check your secrets configuration and permissions. Error: {e}"
    )
    st.stop()


def load_students():
    data = students_worksheet.get_all_records()
    df = pd.DataFrame(data)
    if not df.empty:
        df.columns = df.columns.str.strip()
    return df


def load_attendance():
    data = attendance_worksheet.get_all_records()
    df = pd.DataFrame(data)
    if not df.empty:
        df.columns = df.columns.str.strip()
    return df


# -------------------------------------------------------------
# CLIENT IP DETECTION UTILITY (Subnet Check)
# -------------------------------------------------------------
def get_real_client_ip():
    """ক্লায়েন্ট বা প্রক্সি হেডার থেকে অরিজিনাল IP পাওয়ার নির্ভরযোগ্য ফাংশন"""
    try:
        headers = st.context.headers
        if headers:
            if "X-Forwarded-For" in headers:
                return headers["X-Forwarded-For"].split(",")[0].strip()
            elif "X-Real-Ip" in headers:
                return headers["X-Real-Ip"].strip()
    except Exception:
        pass

    try:
        res = requests.get("https://api.ipify.org?format=json", timeout=3)
        return res.json().get("ip")
    except Exception:
        return None


# -------------------------------------------------------------
# CHECK URL PARAMETERS (FOR STUDENT LINK ACCESS)
# -------------------------------------------------------------
query_params = st.query_params
url_course = query_params.get("course", None)
url_date = query_params.get("date", None)
url_passcode = query_params.get("pass", None)

# -------------------------------------------------------------
# 1. STUDENT PORTAL (When opened via Generated Link)
# -------------------------------------------------------------
if url_course and url_date and url_passcode:
    st.title("🎓 OASIS - Online Student Attendance Portal")
    st.markdown("---")

    # 🔴 ডিপার্টমেন্টের ওয়াইফাই Subnet Prefix List (Tuple)
    ALLOWED_SUBNET_PREFIX = "103.126.60."

    client_ip = get_real_client_ip()

    # IP Subnet Validation
    if not client_ip or not client_ip.startswith(ALLOWED_SUBNET_PREFIX):
        st.error("🚫 Access Denied!")
        st.warning(
            f"আপনি ডিপার্টমেন্টের ওয়াইফাই নেটওয়ার্কে কানেক্টেড নন। আপনার বর্তমান IP: {client_ip if client_ip else 'Unknown'}"
        )
        st.info(
            "💡 অনুগ্রহ করে Geography & Environment ডিপার্টমেন্টের ওয়াইফাই কানেক্ট করুন এবং পেজটি রিফ্রেশ করুন।"
        )
        st.stop()

    st.subheader("📌 Class Details")
    st.info(f"**Course:** {url_course}\n\n**Date:** {url_date}")

    df_students = load_students()

    with st.form("student_attendance_form"):
        student_id_input = st.text_input(
            "Enter Your Student ID / Roll", placeholder="e.g. 101"
        ).strip()
        entered_passcode = st.text_input(
            "Enter Classroom Passcode",
            type="password",
            placeholder="Ask your teacher for passcode",
        ).strip()

        submit_btn = st.form_submit_button(
            "Submit Attendance", use_container_width=True
        )

        if submit_btn:
            if not student_id_input or not entered_passcode:
                st.error("Please fill in both Student ID and Classroom Passcode.")
            elif entered_passcode != url_passcode:
                st.error(
                    "❌ Invalid Classroom Passcode! Please ask your course teacher."
                )
            else:
                matched_student = df_students[
                    df_students["Student ID"].astype(str).str.strip()
                    == student_id_input
                ]

                if matched_student.empty:
                    st.error(
                        f"❌ Student ID '{student_id_input}' is not registered in the system."
                    )
                else:
                    student_name = matched_student.iloc[0]["Name"]
                    df_attendance = load_attendance()

                    if (
                        not df_attendance.empty
                        and "Student ID" in df_attendance.columns
                    ):
                        already_submitted = df_attendance[
                            (
                                df_attendance["Student ID"]
                                .astype(str)
                                .str.strip()
                                == student_id_input
                            )
                            & (
                                df_attendance["Course"].astype(str).str.strip()
                                == url_course
                            )
                            & (
                                df_attendance["Date"].astype(str).str.strip()
                                == url_date
                            )
                        ]
                        if not already_submitted.empty:
                            st.warning(
                                f"⚠️ {student_name} (ID: {student_id_input}), your attendance for today is already recorded!"
                            )
                            st.stop()

                    attendance_worksheet.append_row([
                        str(url_date),
                        str(url_course),
                        str(student_id_input),
                        str(student_name),
                        "Present",
                    ])
                    st.balloons()
                    st.success(
                        f"✅ Attendance Successfully Marked for **{student_name}** ({student_id_input})!"
                    )

# -------------------------------------------------------------
# MAIN APP NAVIGATION (For Admin / Teachers / General View)
# -------------------------------------------------------------
else:
    st.title("OASIS")
    st.markdown("---")

    menu = st.sidebar.selectbox(
        "Navigation",
        [
            "Generate Session Link",
            "Register Student",
            "Manage Students",
            "View Records",
            "Student Percentage Checker",
        ],
    )

    protected_pages = [
        "Generate Session Link",
        "Register Student",
        "View Records",
        "Manage Students",
    ]

    if menu in protected_pages:
        if "authenticated" not in st.session_state:
            st.session_state.authenticated = False

        if not st.session_state.authenticated:
            st.header("Admin Access Required")
            st.warning("Please enter the password to access this section.")

            entered_password = st.text_input(
                "Enter Admin Password", type="password"
            )

            if st.button("Login"):
                if entered_password == st.secrets.get(
                    "admin_password", "default_password"
                ):
                    st.session_state.authenticated = True
                    st.success("Access granted!")
                    st.rerun()
                else:
                    st.error("Incorrect password. Access denied.")
            st.stop()
        else:
            if st.sidebar.button("Lock Admin Session"):
                st.session_state.authenticated = False
                st.rerun()

    # -------------------------------------------------------------
    # 1. GENERATE SESSION LINK & QR CODE (TEACHER PANEL)
    # -------------------------------------------------------------
    if menu == "Generate Session Link":
        st.header("🔗 Generate Class Attendance Link & QR Code")

        df_students = load_students()

        if df_students.empty or "Academic Year" not in df_students.columns:
            st.warning("No students found in Google Sheets.")
        else:
            academic_years = df_students["Academic Year"].unique().tolist()
            selected_year = st.selectbox("Select Academic Year", academic_years)

            year_courses = {
                "1st Year": [
                    "GETh: 1001: Geographical Thoughts and Concepts",
                    "GETh: 1002: Introduction to Physical Geography",
                    "GETh: 1003: Introduction to Human Geography",
                    "GETh: 1004: Concept of Region and World Regional Pattern",
                ],
                "2nd Year": [
                    "GETh: 2001: Environmental Chemistry",
                    "GETh: 2002: Geomorphology",
                    "GETh: 2003: Climatology",
                    "GETh: 2004: Economic Geography",
                    "GETh: 2005: Cultural Geography",
                    "GETh: 2006: Quantitative Techniques in Geography - I",
                ],
                "3rd Year": [
                    "GETh: 3001: Oceanography",
                    "GETh: 3002: Geography of Soil",
                    "GETh: 3003: Biogeography",
                    "GETh: 3004: Population Geography",
                    "GETh: 3005: Geography of Settlement",
                    "GETh: 3006: Geography of Bangladesh",
                ],
                "4th Year": [
                    "GETh: 4001: Hydrology and Fluvial Morphology",
                    "GETh: 4002: Disaster Management",
                    "GETh: 4003: Regional Geography and Environment of South Asia",
                    "GETh: 4004: Transport Geography",
                    "GETh: 4005: Urban Geography",
                    "GETh: 4006: Political Geography",
                    "GELb: 4007: Quantitative Techniques in Geography - II",
                ],
            }

            available_courses = year_courses.get(
                selected_year, ["General Course"]
            )
            selected_course = st.selectbox("Select Course", available_courses)
            att_date = st.date_input("Select Session Date", value=date.today())

            class_passcode = st.text_input(
                "Set Temporary Class Passcode for Students", value="1234"
            )

            if st.button("Generate Session Link & QR"):
                base_url = "https://geoenvgbcattendence.streamlit.app/"
                encoded_course = urllib.parse.quote(selected_course)
                encoded_pass = urllib.parse.quote(class_passcode)

                generated_url = f"{base_url}?course={encoded_course}&date={att_date}&pass={encoded_pass}"

                st.success("✅ Class Session Link & QR Code Generated!")

                # --- GENERATE QR CODE ---
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(generated_url)
                qr.make(fit=True)

                img = qr.make_image(fill_color="black", back_color="white")

                buf = io.BytesIO()
                img.save(buf, format="PNG")
                byte_im = buf.getvalue()

                col1, col2 = st.columns([2, 1])

                with col1:
                    st.markdown("### 🔗 Shareable Link")
                    st.code(generated_url, language="markdown")
                    st.info(
                        "💡 **How it works:** Share this link or project the QR code. Students scanning this while on the Department WiFi will be taken to the submission page."
                    )

                with col2:
                    st.markdown("### 📱 Scan QR Code")
                    st.image(
                        byte_im,
                        caption="Scan to Mark Attendance",
                        width=250,
                    )

    # -------------------------------------------------------------
    # 2. REGISTER STUDENT
    # -------------------------------------------------------------
    elif menu == "Register Student":
        st.header("Register a New Student")

        with st.form("student_form"):
            student_id = st.text_input("Student ID")
            name = st.text_input("Full Name")
            department = st.selectbox(
                "Session", [f"20{i:02d}-{i+1:02d}" for i in range(21, 40)]
            )
            academic_year = st.selectbox(
                "Academic Year",
                ["1st Year", "2nd Year", "3rd Year", "4th Year"],
            )

            submit_student = st.form_submit_button("Add Student")

            if submit_student:
                if not student_id or not name:
                    st.error("Please fill in both Student ID and Name.")
                else:
                    df_students = load_students()
                    if (
                        not df_students.empty
                        and str(student_id)
                        in df_students["Student ID"].astype(str).values
                    ):
                        st.error(f"Student ID '{student_id}' already exists!")
                    else:
                        students_worksheet.append_row([
                            str(student_id),
                            name,
                            department,
                            academic_year,
                        ])
                        st.success(
                            f"Student {name} (ID: {student_id}) added!"
                        )

    # -------------------------------------------------------------
    # 3. VIEW RECORDS
    # -------------------------------------------------------------
    elif menu == "View Records":
        st.header("Attendance Records & Reports")

        df_attendance = load_attendance()
        df_students = load_students()

        if df_attendance.empty or "Date" not in df_attendance.columns:
            st.info("No attendance records found yet.")
        else:
            filter_col1, filter_col2 = st.columns(2)

            with filter_col1:
                unique_dates = df_attendance["Date"].unique().tolist()
                selected_date = st.selectbox(
                    "Filter by Date", ["All Dates"] + unique_dates
                )

            with filter_col2:
                courses = (
                    df_attendance["Course"].unique().tolist()
                    if "Course" in df_attendance.columns
                    else []
                )
                selected_course_filter = st.selectbox(
                    "Filter by Course", ["All Courses"] + courses
                )

            filtered_df = df_attendance.copy()

            if selected_date != "All Dates":
                filtered_df = filtered_df[
                    filtered_df["Date"] == selected_date
                ]

            if selected_course_filter != "All Courses":
                filtered_df = filtered_df[
                    filtered_df["Course"] == selected_course_filter
                ]

            st.dataframe(filtered_df, use_container_width=True)

            csv = filtered_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download Attendance CSV",
                data=csv,
                file_name="attendance_report.csv",
                mime="text/csv",
            )

    # -------------------------------------------------------------
    # 4. MANAGE STUDENTS
    # -------------------------------------------------------------
    elif menu == "Manage Students":
        st.header("Student Directory")

        df_students = load_students()

        if df_students.empty or "Student ID" not in df_students.columns:
            st.info("No students registered yet.")
        else:
            st.dataframe(df_students, use_container_width=True)

            st.subheader("Delete a Student")
            del_id = st.selectbox(
                "Select Student ID to remove",
                df_students["Student ID"].astype(str).values,
            )

            if st.button("Delete Student"):
                cell = students_worksheet.find(str(del_id))
                if cell:
                    students_worksheet.delete_rows(cell.row)
                    st.success(f"Student ID {del_id} removed!")
                    st.rerun()

    # -------------------------------------------------------------
    # 5. STUDENT PERCENTAGE CHECKER
    # -------------------------------------------------------------
    elif menu == "Student Percentage Checker":
        st.header("Student Attendance Percentage Checker")

        df_attendance = load_attendance()
        df_students = load_students()

        if df_students.empty:
            st.warning("No student records found!")
        else:
            input_student_id = st.text_input(
                "Enter Your Student ID", value="", placeholder="Roll"
            ).strip()

            if not input_student_id:
                st.info("Please enter your Student ID above to view progress.")
            else:
                matched_student = df_students[
                    df_students["Student ID"].astype(str).str.strip()
                    == input_student_id
                ]

                if matched_student.empty:
                    st.error(f"No student found with ID '{input_student_id}'.")
                else:
                    student_name = matched_student.iloc[0]["Name"]
                    filtered_att = df_attendance.copy()

                    if (
                        not filtered_att.empty
                        and "Student ID" in filtered_att.columns
                    ):
                        st_att = filtered_att[
                            filtered_att["Student ID"].astype(str).str.strip()
                            == input_student_id
                        ]
                        total_recorded = len(st_att)
                        p_count = int((st_att["Status"] == "Present").sum())
                    else:
                        st_att = pd.DataFrame()
                        total_recorded = 0
                        p_count = 0

                    percentage = (
                        round((p_count / total_recorded) * 100, 2)
                        if total_recorded > 0
                        else 0.0
                    )

                    st.markdown(
                        f"### Progress Summary for: **{student_name}** (ID: {input_student_id})"
                    )
                    st.metric(label="Attendance Percentage", value=f"{percentage}%")
                    st.progress(float(percentage) / 100)

                    st.markdown("---")
                    st.subheader("Detailed Logs")
                    if not st_att.empty:
                        st.dataframe(st_att, use_container_width=True)
                    else:
                        st.info("No records found.")
