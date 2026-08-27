from datetime import date
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st

# Page Configuration
st.set_page_config(
    page_title="Online Attendance System (Google Sheets)",
    page_icon="📋",
    layout="wide",
)

# -------------------------------------------------------------
# GOOGLE SHEETS CONNECTION SETUP
# -------------------------------------------------------------
# Define scopes required for Google Sheets API
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


@st.cache_resource
def init_connection():
    """Connects to Google Sheets using credentials stored in Streamlit secrets"""
    credentials_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(
        credentials_dict, scopes=SCOPES
    )
    client = gspread.authorize(creds)
    return client


# Connect and open the Google Sheet (Make sure to share your sheet with the service account email!)
try:
    client = init_connection()
    # Replace "AttendanceDB" with the exact name of your Google Sheet
    sheet = client.open("OASIS")
    students_worksheet = sheet.worksheet("Students")
    attendance_worksheet = sheet.worksheet("Attendance")
except Exception as e:
    st.error(
        f"Failed to connect to Google Sheets. Check your secrets configuration and permissions. Error: {e}"
    )
    st.stop()


# Helper Functions to Load Data from Sheets
def load_students():
    data = students_worksheet.get_all_records()
    return pd.DataFrame(data)


def load_attendance():
    data = attendance_worksheet.get_all_records()
    return pd.DataFrame(data)


st.title("📋 Online Attendance Management System (Google Sheets Connected)")
st.markdown("---")

# Sidebar Navigation
menu = st.sidebar.selectbox(
    "Navigation",
    ["Mark Attendance", "Register Student", "View Records", "Manage Students"],
)

# -------------------------------------------------------------
# 1. MARK ATTENDANCE
# -------------------------------------------------------------
if menu == "Mark Attendance":
    st.header("📌 Mark Daily Attendance")

    df_students = load_students()

    if df_students.empty:
        st.warning(
            "No students found! Please register students first in the 'Register Student' section."
        )
    else:
        att_date = st.date_input("Select Date", value=date.today())

        st.markdown("### Student List")
        st.info("Check the box next to the student if they are **Present**.")

        with st.form("attendance_form"):
            attendance_status = {}

            for index, row in df_students.iterrows():
                col1, col2, col3 = st.columns([1, 3, 2])
                with col1:
                    is_present = st.checkbox(
                        "Present",
                        value=True,
                        key=f"att_{row['Student ID']}",
                        label_visibility="collapsed",
                    )
                with col2:
                    st.write(
                        f"**{row['Name']}** *(ID: {row['Student ID']})*"
                    )
                with col3:
                    st.write(f"Dept: {row['Department']}")

                attendance_status[row["Student ID"]] = {
                    "Name": row["Name"],
                    "Status": "Present" if is_present else "Absent",
                }

            submitted = st.form_submit_button("Save Attendance")

            if submitted:
                # Load current attendance to remove duplicates for this specific date if overwriting
                df_attendance = load_attendance()
                if not df_attendance.empty:
                    # Filter out records for the selected date
                    df_attendance = df_attendance[
                        df_attendance["Date"] != str(att_date)
                    ]
                    rows_to_save = [df_attendance.columns.tolist()] + df_attendance.values.tolist()
                else:
                    rows_to_save = [["Date", "Student ID", "Name", "Status"]]

                # Append new records
                for s_id, data in attendance_status.items():
                    rows_to_save.append(
                        [str(att_date), str(s_id), data["Name"], data["Status"]]
                    )

                # Update Google Sheet
                attendance_worksheet.clear()
                attendance_worksheet.update(rows_to_save)
                st.success(
                    f"Attendance successfully saved to Google Sheets for {att_date}!"
                )

# -------------------------------------------------------------
# 2. REGISTER STUDENT
# -------------------------------------------------------------
elif menu == "Register Student":
    st.header("➕ Register a New Student")

    with st.form("student_form"):
        student_id = st.text_input("Student ID")
        name = st.text_input("Full Name")
        department = st.selectbox(
            "Department",
            [
                "Geography and Environment",
                "Computer Science",
                "Environmental Science",
                "Data Science",
                "Other",
            ],
        )

        submit_student = st.form_submit_button("Add Student")

        if submit_student:
            if not student_id or not name:
                st.error("Please fill in both Student ID and Name.")
            else:
                df_students = load_students()
                if not df_students.empty and str(student_id) in df_students["Student ID"].astype(str).values:
                    st.error(f"Student ID '{student_id}' already exists!")
                else:
                    # Append row to Google Sheet
                    students_worksheet.append_row([str(student_id), name, department])
                    st.success(
                        f"Student {name} (ID: {student_id}) successfully added to Google Sheets!"
                    )

# -------------------------------------------------------------
# 3. VIEW RECORDS & ANALYTICS
# -------------------------------------------------------------
elif menu == "View Records":
    st.header("📊 Attendance Records & Reports")

    df_attendance = load_attendance()

    if df_attendance.empty:
        st.info("No attendance records found yet.")
    else:
        unique_dates = df_attendance["Date"].unique()
        selected_date = st.selectbox(
            "Filter by Date", ["All Dates"] + list(unique_dates)
        )

        filtered_df = df_attendance.copy()
        if selected_date != "All Dates":
            filtered_df = filtered_df[filtered_df["Date"] == selected_date]

        total_records = len(filtered_df)
        present_count = len(filtered_df[filtered_df["Status"] == "Present"])
        absent_count = total_records - present_count

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Records", total_records)
        col2.metric("Present", present_count)
        col3.metric("Absent", absent_count)

        st.dataframe(filtered_df, use_container_width=True)

        csv = filtered_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Attendance as CSV",
            data=csv,
            file_name="attendance_report.csv",
            mime="text/csv",
        )

# -------------------------------------------------------------
# 4. MANAGE STUDENTS
# -------------------------------------------------------------
elif menu == "Manage Students":
    st.header("⚙️ Student Directory")

    df_students = load_students()

    if df_students.empty:
        st.info("No students registered yet.")
    else:
        st.dataframe(df_students, use_container_width=True)

        st.subheader("Delete a Student")
        del_id = st.selectbox(
            "Select Student ID to remove",
            df_students["Student ID"].astype(str).values,
        )

        if st.button("Delete Student"):
            # Find row index in Google Sheets to delete
            cell = students_worksheet.find(str(del_id))
            if cell:
                students_worksheet.delete_rows(cell.row)
                st.success(f"Student ID {del_id} removed from Google Sheets!")
                st.rerun()
            else:
                st.error("Student ID not found in sheet.")
