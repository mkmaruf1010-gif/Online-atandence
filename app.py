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
st.markdown("---")

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
protected_pages = ["Mark Attendance", "Register Student", "Manage Students"]

if menu in protected_pages:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.header(f" Admin Access Required")
        st.warning("Please enter the password to access this section.")

       entered_password = st.text_input("Enter Admin Password", type="password")

if st.button("Login"):
    # সিক্রেটস থেকে পাসওয়ার্ডগুলো লোড করা (স্ট্রিং বা লিস্ট হতে পারে)
    saved_passwords = st.secrets.get("admin_password", ["default_password"])
    
    # যদি একটিমাত্র পাসওয়ার্ড স্ট্রিং আকারে থাকে, সেটাকে লিস্টে কনভার্ট করে নেওয়া
    if isinstance(saved_passwords, str):
        valid_passwords = [saved_passwords]
    else:
        valid_passwords = list(saved_passwords)

    # ইউজার যেই পাসওয়ার্ড দিয়েছে তা লিস্টের কোনোটার সাথে মিলছে কি না চেক করা
    if entered_password in valid_passwords:
        st.session_state.authenticated = True
        st.success("Access granted!")
        st.rerun()
    else:
        st.error("Incorrect password. Access denied.")
        st.stop()  # Stop execution here until authenticated
    else:
        # Option to log out / lock again from sidebar or page
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
            "No students found or missing 'Student ID' column in the 'Students' sheet! Please check your Google Sheet headers: [Student ID, Name, Session, Academic Year]."
        )
    else:
        academic_years = (
            df_students["Academic Year"].unique()
            if "Academic Year" in df_students.columns
            else ["1st Year", "2nd Year", "3rd Year", "4th Year"]
        )
        selected_year = st.selectbox(
            "Select Academic Year to Mark", academic_years
        )

        # ইয়ার অনুযায়ী কোর্সসমূহের তালিকা
        year_courses = {
            "1st Year": [
                "GETh-1001: Geographical Thoughts and Concepts",
               "GETh-1002: Introduction to Physical Geography",
              "GETh-1003: Introduction to Human Geography",
                "GETh-1004:Concept of Region and World Regional Pattern",
            ],
            "2nd Year": [
                "GETh:2001:Environmental Chemistry",
                "GETh:2002:Geomorphology",
                 "GETh:2003:Climatology ",
                 "GETh:2004:Economic Geography",
                 "GETh:2005:Quantitative Techniques in Geography - I",
                 "GETh:2006:Environmental Chemistry",
            ],
            "3rd Year": [
                "GETh: 3001 :Oceanography",
                "GETh: 3002 :Geography of Soil ",
                "GETh: 3003 :Biogeography ",
                "GETh: 3004 :Population Geography ",
                "GETh: 3005 :Geography of Settlement ",
                "GETh: 3006 :Geography of Bangladesh ",
            ],
            "4th Year": [
                "GETh-4001: Hydrology and Fluvial Morphology",
                "GETh-4002: Disaster Management",
                "GETh-4003: Regional Geography and Environment of South Asia ",
                "GETh-4004: Transport Geography",
                "GETh-4005: Urban Geography ",
                "GETh-4006: Political Geography ",
                 "GETh-4007: Quantitative Techniques in Geography - II ",
                
            ]
        }

        # সিলেক্টেড ইয়ারের আন্ডারে কোর্স ফিল্টার করা
        available_courses = year_courses.get(selected_year, ["General Course"])
        selected_course = st.selectbox("Select Course Code & Title", available_courses)

        filtered_students = df_students
        if (
            selected_year != "All"
            and "Academic Year" in df_students.columns
        ):
            filtered_students = df_students[
                df_students["Academic Year"] == selected_year
            ]

        att_date = st.date_input("Select Date", value=date.today())

        st.markdown(f"### Student List for {selected_year} - {selected_course}")
        st.info("Check the box next to the student if they are **Present**. (Unchecked means Absent)")

        with st.form("attendance_form"):
            attendance_status = {}

            for index, row in filtered_students.iterrows():
                s_id = str(row["Student ID"])
                s_name = row["Name"]
                s_session = (
                    row["Session"]
                    if "Session" in df_students.columns
                    else ""
                )

                col1, col2, col3 = st.columns([1, 3, 2])
                with col1:
                    # ডিফল্টভাবে ব্ল্যাঙ্ক বা আনচেকড রাখার জন্য value=False দেওয়া হয়েছে
                    is_present = st.checkbox(
                        "Present",
                        value=False,
                        key=f"att_{s_id}",
                        label_visibility="collapsed",
                    )
                with col2:
                    st.write(f"**{s_name}** *(ID: {s_id})*")
                with col3:
                    st.write(f"Session: {s_session}")

                attendance_status[s_id] = {
                    "Name": s_name,
                    "Status": "Present" if is_present else "Absent",
                }

            submitted = st.form_submit_button("Save Attendance")

            if submitted:
                df_attendance = load_attendance()
                if not df_attendance.empty and "Date" in df_attendance.columns:
                    # একই তারিখ এবং নির্দিষ্ট কোর্সের আগের এন্ট্রি হ্যান্ডেল করার লজিক চাইলে রাখতে পারো
                    rows_to_save = [
                        df_attendance.columns.tolist()
                    ] + df_attendance.values.tolist()
                else:
                    rows_to_save = [["Date", "Course", "Student ID", "Name", "Status"]]

                for s_id, data in attendance_status.items():
                    rows_to_save.append(
                        [str(att_date), str(selected_course), str(s_id), data["Name"], data["Status"]]
                    )

                attendance_worksheet.clear()
                attendance_worksheet.update(rows_to_save)
                st.success(
                    f"Attendance successfully saved to Google Sheets for {selected_course} on {att_date}!"
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
            "Session",
            [
                "2021-22",
                "2022-23",
                "2023-24",
                "2024-25",
                "2025-26",
                "2026-27",
                "2027-28",
                "2028-29",
                "2029-30",
                "2030-31",
                "2031-32",
                "2032-33",
                "2033-34",
                "2034-35",
                "2035-36",
                "2036-37",
                "2037-38",
                "2038-39",
                "2039-40",
            ],
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
                    and str(student_id)
                    in df_students["Student ID"].astype(str).values
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
# 3. VIEW RECORDS & ANALYTICS
# -------------------------------------------------------------
elif menu == "View Records":
    st.header("Attendance Records & Reports")

    df_attendance = load_attendance()

    if df_attendance.empty or "Date" not in df_attendance.columns:
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
        present_count = len(
            filtered_df[filtered_df["Status"].str.lower() == "present"]
        )
        absent_count = total_records - present_count

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Records", total_records)
        col2.metric("Present", present_count)
        col3.metric("Absent", absent_count)

        st.dataframe(filtered_df, use_container_width=True)

        csv = filtered_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download Attendance as CSV",
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
        st.info(
            "No students registered yet or missing 'Student ID' column header in Google Sheets."
        )
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
                st.success(f"Student ID {del_id} removed from Google Sheets!")
                st.rerun()
            else:
                st.error("Student ID not found in sheet.")

# -------------------------------------------------------------
# 5. STUDENT PERCENTAGE CHECKER
# -------------------------------------------------------------
elif menu == "Student Percentage Checker":
    st.header("Individual Attendance Percentage Checker")

    df_students = load_students()
    df_attendance = load_attendance()

    if df_students.empty or "Academic Year" not in df_students.columns:
        st.warning("No student data or academic year records found.")
    else:
        selected_year_filter = st.selectbox(
            "Select Academic Year",
            ["1st Year", "2nd Year", "3rd Year", "4th Year"],
        )

        year_students = df_students[
            df_students["Academic Year"] == selected_year_filter
        ]

        if year_students.empty:
            st.info(f"No students found in {selected_year_filter}.")
        else:
            selected_student_id = st.selectbox(
                "Select Student",
                year_students["Student ID"].astype(str).values,
                format_func=lambda x: f"{x} - {year_students[year_students['Student ID'].astype(str) == x]['Name'].values[0]}",
            )

            if selected_student_id:
                student_row = year_students[
                    year_students["Student ID"].astype(str)
                    == str(selected_student_id)
                ].iloc[0]
                st.subheader(
                    f"Report for: {student_row['Name']} (ID: {selected_student_id})"
                )
                st.write(
                    f"**Department:** {student_row.get('Department', 'N/A')} | **Year:** {student_row['Academic Year']}"
                )

                if df_attendance.empty or "Student ID" not in df_attendance.columns:
                    st.info("No attendance tracking entries recorded yet.")
                else:
                    student_records = df_attendance[
                        df_attendance["Student ID"].astype(str)
                        == str(selected_student_id)
                    ]
                    total_classes = len(student_records)

                    if total_classes == 0:
                        st.info(
                            "No attendance records found for this student."
                        )
                    else:
                        present_classes = len(
                            student_records[
                                student_records["Status"].str.lower()
                                == "present"
                            ]
                        )
                        percentage = (
                            (present_classes / total_classes) * 100
                            if total_classes > 0
                            else 0
                        )

                        col1, col2, col3 = st.columns(3)
                        col1.metric("Total Classes Held", total_classes)
                        col2.metric("Classes Attended", present_classes)
                        col3.metric(
                            "Attendance Percentage", f"{percentage:.2f}%"
                        )

                        st.markdown("### Detailed Logs")
                        st.dataframe(student_records, use_container_width=True)
