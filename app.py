from datetime import date
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st

# Page Configuration
st.set_page_config(
    page_title="OASIS",
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


st.title("OASIS")
st.markdown("Online Attendance System")

# Sidebar Navigation
menu = st.sidebar.selectbox(
    "Navigation",
    [
        "Mark Attendance",
        "Register Student",
        "View Records",
        "Manage Students",
        "Student Percentage Checker",
    ],
)

# -------------------------------------------------------------
# PASSWORD PROTECTION CHECK FOR ADMIN PAGES
# -------------------------------------------------------------
protected_pages = ["Mark Attendance", "Register Student", "View Records", "Manage Students"]

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
        st.stop()  # Stop execution here until authenticated
    else:
        if st.sidebar.button("Lock Admin Session"):
            st.session_state.authenticated = False
            st.rerun()


# -------------------------------------------------------------
# 1. MARK ATTENDANCE
# -------------------------------------------------------------
if menu == "Mark Attendance":
    st.header("Mark Daily Attendance")

    df_students = load_students()

    if df_students.empty or "Student ID" not in df_students.columns:
        st.warning(
            "No students found or missing 'Student ID' column in the 'Students' sheet! Please check your Google Sheet headers: [Student ID, Name, Session, Academic Year, Department]."
        )
    else:
        # ১. প্রথমে ডিপার্টমেন্ট সিলেক্ট করুন (Google Sheet-এ থাকা Department অনুযায়ী dynamically আসবে)
        departments = (
            df_students["Department"].unique().tolist()
            if "Department" in df_students.columns
            else ["Geography&Environment"]
        )
        selected_department = st.selectbox(
            "১. Select Department", departments, key="attendance_dept"
        )

        # সিলেক্টেড ডিপার্টমেন্ট অনুযায়ী ফিল্টার করা
        if "Department" in df_students.columns:
            dept_filtered_students = df_students[
                df_students["Department"] == selected_department
            ]
        else:
            dept_filtered_students = df_students.copy()

        # ২. ডিপার্টমেন্ট অনুযায়ী এভেলেবল ইয়ার সিলেক্ট করুন
        available_years = (
            dept_filtered_students["Academic Year"].unique().tolist()
            if "Academic Year" in dept_filtered_students.columns and not dept_filtered_students.empty
            else ["1st Year", "2nd Year", "3rd Year", "4th Year"]
        )
        selected_year = st.selectbox(
            "২. Select Academic Year", available_years, key="attendance_year"
        )

        # ৩. ইয়ার অনুযায়ী কোর্সের তালিকা (Subject Selection)
        year_courses = {
            "1st Year": [
                "GETh: 1001: Geographical Thoughts and Concepts",
                "GETh: 1002: Introduction to Physical Geography",
                "GETh: 1003: Introduction to Human Geography",
                "GETh: 1004: Concept of Region and World Regional Pattern",
                "Special Attendance: Occasional"
            ],
            "2nd Year": [
                "GETh: 2001: Environmental Chemistry",
                "GETh: 2002: Geomorphology",
                "GETh: 2003: Climatology",
                "GETh: 2004: Economic Geography",
                "GETh: 2005: Cultural Geography",
                "GETh: 2006: Quantitative Techniques in Geography - I",
                "Special Attendance: Occasional"
            ],
            "3rd Year": [
                "GETh: 3001: Oceanography",
                "GETh: 3002: Geography of Soil",
                "GETh: 3003: Biogeography",
                "GETh: 3004: Population Geography",
                "GETh: 3005: Geography of Settlement",
                "GETh: 3006: Geography of Bangladesh",
                "Special Attendance: Occasional"
            ],
            "4th Year": [
                "GETh: 4001: Hydrology and Fluvial Morphology",
                "GETh: 4002: Disaster Management",
                "GETh: 4003: Regional Geography and Environment of South Asia",
                "GETh: 4004: Transport Geography",
                "GETh: 4005: Urban Geography",
                "GETh: 4006: Political Geography",
                "GELb: 4007: Quantitative Techniques in Geography - II",
                "Special Attendance: Occasional"
            ]
        }

        available_courses = year_courses.get(selected_year, ["General Course"])
        selected_course = st.selectbox("৩. Select Course Code & Title", available_courses)

        # ডিপার্টমেন্ট এবং ইয়ার—উভয়টি অনুযায়ী স্টুডেন্টদের ফিল্টার করা
        filtered_students = dept_filtered_students.copy()
        if "Academic Year" in filtered_students.columns:
            filtered_students = filtered_students[
                filtered_students["Academic Year"] == selected_year
            ]

        att_date = st.date_input("Select Date", value=date.today())

        st.markdown(f"### Student List for: **{selected_department}** | **{selected_year}** | **{selected_course}**")
        st.info("Check the box next to the student if they are **Present**. (Unchecked means Absent)")

        # আইডি অনুযায়ী সর্টিং
        sort_order = st.selectbox(
            "Sort Student ID by:",
            ["Ascending (Low to High)", "Descending (High to Low)"],
            key="attendance_id_sort"
        )

        if not filtered_students.empty and "Student ID" in filtered_students.columns:
            try:
                filtered_students["_sort_id"] = pd.to_numeric(filtered_students["Student ID"])
            except Exception:
                filtered_students["_sort_id"] = filtered_students["Student ID"]

            if sort_order == "Ascending (Low to High)":
                filtered_students = filtered_students.sort_values(by="_sort_id", ascending=True)
            elif sort_order == "Descending (High to Low)":
                filtered_students = filtered_students.sort_values(by="_sort_id", ascending=False)
            
            if "_sort_id" in filtered_students.columns:
                filtered_students = filtered_students.drop(columns=["_sort_id"])

        with st.form("attendance_form"):
            attendance_status = {}

            # টেবিল হেডার
            h_col1, h_col2, h_col3, h_col4 = st.columns([1, 2, 3, 2])
            with h_col1:
                st.markdown("**Present**")
            with h_col2:
                st.markdown("**Student ID**")
            with h_col3:
                st.markdown("**Name**")
            with h_col4:
                st.markdown("**Session**")
            
            st.markdown("---")

            if filtered_students.empty:
                st.warning("এই ডিপার্টমেন্ট এবং ইয়ারে কোনো স্টুডেন্ট পাওয়া যায়নি।")
            else:
                for index, row in filtered_students.iterrows():
                    s_id = str(row["Student ID"])
                    s_name = row["Name"]
                    s_session = row["Session"] if "Session" in df_students.columns else ""

                    col1, col2, col3, col4 = st.columns([1, 2, 3, 2])
                    with col1:
                        is_present = st.checkbox(
                            "Present",
                            value=False,
                            key=f"att_{s_id}",
                            label_visibility="collapsed",
                        )
                    with col2:
                        st.write(f"{s_id}")
                    with col3:
                        st.write(f"**{s_name}**")
                    with col4:
                        st.write(f"{s_session}")

                    attendance_status[s_id] = {
                        "Name": s_name,
                        "Status": "Present" if is_present else "Absent",
                    }

            submitted = st.form_submit_button("Save Attendance")

            if submitted and not filtered_students.empty:
                df_attendance = load_attendance()
                
                headers = ["Date", "Department", "Course", "Student ID", "Name", "Status"]
                
                if not df_attendance.empty and "Date" in df_attendance.columns:
                    rows_to_save = [df_attendance.columns.tolist()] + df_attendance.values.tolist()
                else:
                    rows_to_save = [headers]

                for s_id, data in attendance_status.items():
                    rows_to_save.append(
                        [
                            str(att_date),
                            str(selected_department),
                            str(selected_course),
                            str(s_id),
                            data["Name"],
                            data["Status"],
                        ]
                    )

                attendance_worksheet.clear()
                attendance_worksheet.update(rows_to_save)
                st.success(
                    f"Attendance successfully saved to Google Sheets for **{selected_department}** ({selected_course}) on {att_date}!"
                )
