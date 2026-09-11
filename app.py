from datetime import date
import os
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st
import cv2
import numpy as np
from PIL import Image

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


# -------------------------------------------------------------
# FAST FACE DETECTION FUNCTION (OpenCV)
# -------------------------------------------------------------
def detect_faces(image):
    # Convert PIL Image to OpenCV format
    img_array = np.array(image.convert('RGB'))
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    
    # Load Haar Cascade Classifier
    cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    face_cascade = cv2.CascadeClassifier(cascade_path)
    
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    return len(faces) > 0, img_array


st.title("OASIS")
st.markdown("---")

# Sidebar Navigation
menu = st.sidebar.selectbox(
    "Navigation",
    [
        "Mark Attendance",
        "Register Student",
        "Manage Students",
        "View Records",
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
        st.stop()
    else:
        if st.sidebar.button("Lock Admin Session"):
            st.session_state.authenticated = False
            st.rerun()

# -------------------------------------------------------------
# 1. MARK ATTENDANCE (FAST & LIGHTWEIGHT)
# -------------------------------------------------------------
if menu == "Mark Attendance":
    st.header("Mark Daily Attendance via Smart Camera Scan")

    df_students = load_students()

    if df_students.empty or "Student ID" not in df_students.columns:
        st.warning(
            "No students found or missing 'Student ID' column in the 'Students' sheet!"
        )
    else:
        academic_years = (
            df_students["Academic Year"].unique().tolist()
            if "Academic Year" in df_students.columns
            else ["1st Year", "2nd Year", "3rd Year", "4th Year"]
        )
        selected_year = st.selectbox(
            "Select Academic Year to Mark", academic_years
        )

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

        available_courses = year_courses.get(selected_year, ["General Course"])
        selected_course = st.selectbox("Select Course Code & Title", available_courses)

        filtered_students = df_students[df_students["Academic Year"] == selected_year] if "Academic Year" in df_students.columns else df_students
        att_date = st.date_input("Select Date", value=date.today())

        st.markdown(f"### Student Selection & Verification")
        
        # স্টুডেন্ট সিলেক্ট করার বক্স
        student_list = filtered_students["Student ID"].astype(str).tolist() if not filtered_students.empty else []
        selected_student_id = st.selectbox("Select Student ID for Verification:", student_list)

        if selected_student_id:
            student_info = filtered_students[filtered_students["Student ID"].astype(str) == selected_student_id]
            student_name = student_info.iloc[0]["Name"] if not student_info.empty else "N/A"
            st.info(f"👤 Selected Student: **{student_name}** (ID: {selected_student_id})")

            # ক্যামেরা ইনপুট
            img_buffer = st.camera_input("Take photo for Face Detection Attendance")

            if img_buffer is not None:
                image = Image.open(img_buffer)
                face_found, _ = detect_faces(image)

                if face_found:
                    st.success(f"✅ Live Face Detected for Student: {student_name}!")
                    
                    if st.button("Confirm & Save Attendance"):
                        df_attendance = load_attendance()

                        if not df_attendance.empty and "Date" in df_attendance.columns:
                            rows_to_save = [df_attendance.columns.tolist()] + df_attendance.values.tolist()
                        else:
                            rows_to_save = [["Date", "Course", "Student ID", "Name", "Status"]]

                        for index, row in filtered_students.iterrows():
                            s_id = str(row["Student ID"]).strip()
                            s_name = str(row["Name"]).strip()
                            status = "Present" if s_id == selected_student_id else "Absent"

                            rows_to_save.append(
                                [
                                    str(att_date),
                                    str(selected_course),
                                    str(s_id),
                                    str(s_name),
                                    str(status),
                                ]
                            )

                        attendance_worksheet.clear()
                        attendance_worksheet.update(rows_to_save)
                        st.balloons()
                        st.success(f"Attendance recorded! Student ID {selected_student_id} marked as Present.")
                else:
                    st.error("❌ No face detected in the photo. Please look at the camera properly.")

# -------------------------------------------------------------
# 2. REGISTER STUDENT
# -------------------------------------------------------------
elif menu == "Register Student":
    st.header("Register a New Student")

    with st.form("student_form"):
        student_id = st.text_input("Student ID")
        name = st.text_input("Full Name")
        department = st.selectbox(
            "Session",
            [f"20{i:02d}-{i+1:02d}" for i in range(21, 40)]
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
                    and "Student ID" in df_students.columns
                    and str(student_id) in df_students["Student ID"].astype(str).values
                ):
                    st.error(f"Student ID '{student_id}' already exists!")
                else:
                    students_worksheet.append_row(
                        [str(student_id), name, department, academic_year]
                    )
                    st.success(
                        f"Student {name} (ID: {student_id}, {academic_year}) successfully added!"
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
        filter_col1, filter_col2, filter_col3 = st.columns(3)

        with filter_col1:
            academic_years = ["All Years"]
            if not df_students.empty and "Academic Year" in df_students.columns:
                academic_years += df_students["Academic Year"].dropna().unique().tolist()
            selected_year = st.selectbox("Filter by Academic Year", academic_years, key="view_year")

        with filter_col2:
            unique_dates = df_attendance["Date"].unique().tolist()
            selected_date = st.selectbox("Filter by Date", ["All Dates"] + unique_dates, key="view_date")

        with filter_col3:
            sort_by = st.selectbox("Sort Records by:", ["Date (Newest First)", "Date (Oldest First)", "Student ID"], key="view_sort")

        filtered_df = df_attendance.copy()
        if not df_students.empty and "Academic Year" in df_students.columns:
            if "Academic Year" not in filtered_df.columns:
                filtered_df = filtered_df.merge(df_students[["Student ID", "Academic Year"]], on="Student ID", how="left")

        if selected_year != "All Years" and "Academic Year" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Academic Year"] == selected_year]

        if selected_date != "All Dates":
            filtered_df = filtered_df[filtered_df["Date"] == selected_date]

        total_records = len(filtered_df)
        present_count = len(filtered_df[filtered_df["Status"].astype(str).str.lower() == "present"])
        absent_count = total_records - present_count

        st.markdown("---")
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric("Total Records", total_records)
        m_col2.metric("Present", present_count)
        m_col3.metric("Absent", absent_count)

        st.dataframe(filtered_df, use_container_width=True)

        csv = filtered_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download Attendance as CSV",
            data=csv,
            file_name=f"attendance_report_{selected_year}_{selected_date}.csv",
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
        del_id = st.selectbox("Select Student ID to remove", df_students["Student ID"].astype(str).values)

        if st.button("Delete Student"):
            cell = students_worksheet.find(str(del_id))
            if cell:
                students_worksheet.delete_rows(cell.row)
                st.success(f"Student ID {del_id} removed from Google Sheets!")
                st.rerun()

# -------------------------------------------------------------
# 5. STUDENT PERCENTAGE CHECKER
# -------------------------------------------------------------
elif menu == "Student Percentage Checker":
    st.header("Student Attendance Percentage Checker")

    df_attendance = load_attendance()
    df_students = load_students()

    if df_students.empty:
        st.warning("No student records found in 'Students' sheet!")
    else:
        input_student_id = st.text_input("Enter Your Student ID", value="", placeholder="Roll", key="pct_input_id").strip()

        if not input_student_id:
            st.info("Please enter your Student ID above to view your attendance progress.")
        else:
            matched_student = df_students[df_students["Student ID"].astype(str).str.strip() == input_student_id]

            if matched_student.empty:
                st.error(f"No registered student found with ID '{input_student_id}'.")
            else:
                student_name = matched_student.iloc[0]["Name"]
                filtered_att = df_attendance.copy()

                if not filtered_att.empty and "Student ID" in filtered_att.columns:
                    st_att = filtered_att[filtered_att["Student ID"].astype(str).str.strip() == input_student_id]
                    total_recorded = len(st_att)
                    p_count = int((st_att["Status"] == "Present").sum())
                    a_count = int((st_att["Status"] == "Absent").sum())
                else:
                    st_att = pd.DataFrame()
                    total_recorded = 0
                    p_count = 0
                    a_count = 0

                percentage = round((p_count / total_recorded) * 100, 2) if total_recorded > 0 else 0.0

                st.markdown(f"### Progress Summary for: **{student_name}** (ID: {input_student_id})")
                st.metric(label="Attendance Percentage", value=f"{percentage}%")
                st.progress(float(percentage) / 100)
                st.write(f"**Total Classes:** {total_recorded} | **Present:** {p_count} | **Absent:** {a_count}")

                st.markdown("---")
                st.subheader("Detailed Date-wise Attendance Logs")
                if not st_att.empty:
                    st.dataframe(st_att, use_container_width=True)
                else:
                    st.info("No records found.")
