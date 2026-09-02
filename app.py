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
        st.stop()
    else:
        if st.sidebar.button("Lock Admin Session"):
            st.session_state.authenticated = False
            st.rerun()

# -------------------------------------------------------------
# DEPARTMENT & COURSE DICTIONARY
# -------------------------------------------------------------
default_geography_courses = {
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

department_courses = {
    "Geography & Environment": default_geography_courses,
    "Geography&Environment": default_geography_courses,
    "Math": {
        "1st Year": ["ME 101: Basic Mechanical Engineering", "ME 102: Engineering Drawing"],
        "2nd Year": ["ME 201: Thermodynamics", "ME 202: Mechanics of Solids", "ME 203: Fluid Mechanics"],
        "3rd Year": ["ME 301: Heat Transfer", "ME 302: Machine Design"],
        "4th Year": ["ME 401: Power Plant Engineering", "ME 402: Automobile Engineering"]
    },
    "Physics": {
        "1st Year": ["CSE 101: Structured Programming Language", "CSE 102: Discrete Mathematics"],
        "2nd Year": ["CSE 201: Data Structures", "CSE 202: Object Oriented Programming"],
        "3rd Year": ["CSE 301: Database Management Systems", "CSE 302: Software Engineering"],
        "4th Year": ["CSE 401: Artificial Intelligence", "CSE 402: Computer Networks"]
    },
    "Chemistry": {
        "1st Year": ["CSE 101: Structured Programming Language", "CSE 102: Discrete Mathematics"],
        "2nd Year": ["CSE 201: Data Structures", "CSE 202: Object Oriented Programming"],
        "3rd Year": ["CSE 301: Database Management Systems", "CSE 302: Software Engineering"],
        "4th Year": ["CSE 401: Artificial Intelligence", "CSE 402: Computer Networks"]
    }
}


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
        departments = (
            df_students["Department"].dropna().unique().tolist()
            if "Department" in df_students.columns
            else ["Geography & Environment"]
        )
        selected_department = st.selectbox(
            "Select Department", departments, key="attendance_dept"
        )

        if "Department" in df_students.columns:
            dept_filtered_students = df_students[
                df_students["Department"] == selected_department
            ]
        else:
            dept_filtered_students = df_students.copy()

        available_years = (
            dept_filtered_students["Academic Year"].dropna().unique().tolist()
            if "Academic Year" in dept_filtered_students.columns and not dept_filtered_students.empty
            else ["1st Year", "2nd Year", "3rd Year", "4th Year"]
        )
        selected_year = st.selectbox(
            "Select Academic Year", available_years, key="attendance_year"
        )

        clean_selected_dept = str(selected_department).strip()
        dept_courses = department_courses.get(clean_selected_dept, default_geography_courses)

        clean_selected_year = str(selected_year).strip()
        available_courses = dept_courses.get(clean_selected_year, ["General Course"])

        selected_course = st.selectbox("Select Course Code & Title", available_courses)

        filtered_students = dept_filtered_students.copy()
        if "Academic Year" in filtered_students.columns:
            filtered_students = filtered_students[
                filtered_students["Academic Year"] == selected_year
            ]

        att_date = st.date_input("Select Date", value=date.today())

        st.markdown(f"### Student List for: **{selected_department}** | **{selected_year}** | **{selected_course}**")
        st.info("Check the box next to the student if they are **Present**. (Unchecked means Absent)")

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
                st.warning("এই ডিপার্টমেন্ট এবং ইয়ারে কোনো স্টুডেন্ট পাওয়া যায়নি।")
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


# -------------------------------------------------------------
# 2. REGISTER STUDENT
# -------------------------------------------------------------
elif menu == "Register Student":
    st.header("Register New Student")

    with st.form("register_form"):
        student_id = st.text_input("Student ID")
        name = st.text_input("Full Name")
        session = st.text_input("Session (e.g., 2020-2021)")
        academic_year = st.selectbox("Academic Year", ["1st Year", "2nd Year", "3rd Year", "4th Year"])
        department = st.selectbox("Department", ["Geography & Environment", "Math", "Physics", "Chemistry"])

        reg_submitted = st.form_submit_button("Register Student")

        if reg_submitted:
            if not student_id or not name:
                st.error("Student ID and Name are required fields!")
            else:
                df_students = load_students()
                headers = ["Student ID", "Name", "Session", "Academic Year", "Department"]

                # চেক করা ID অলরেডি আছে কিনা
                if not df_students.empty and "Student ID" in df_students.columns:
                    existing_ids = df_students["Student ID"].astype(str).str.strip().tolist()
                    if str(student_id).strip() in existing_ids:
                        st.error(f"Student ID '{student_id}' is already registered!")
                        st.stop()
                    rows_to_save = [df_students.columns.tolist()] + df_students.values.tolist()
                else:
                    rows_to_save = [headers]

                rows_to_save.append([str(student_id).strip(), name, session, academic_year, department])

                students_worksheet.clear()
                students_worksheet.update(rows_to_save)
                st.success(f"Student **{name}** (ID: {student_id}) successfully registered!")


# -------------------------------------------------------------
# 3. VIEW RECORDS
# -------------------------------------------------------------
elif menu == "View Records":
    st.header("View Attendance Records")

    df_attendance = load_attendance()

    if df_attendance.empty:
        st.info("No attendance records found.")
    else:
        # ফিল্টার অপশনসমূহ
        col1, col2, col3 = st.columns(3)

        with col1:
            dept_list = ["All"] + (df_attendance["Department"].dropna().unique().tolist() if "Department" in df_attendance.columns else [])
            v_dept = st.selectbox("Filter by Department", dept_list, key="v_dept")

        with col2:
            course_list = ["All"] + (df_attendance["Course"].dropna().unique().tolist() if "Course" in df_attendance.columns else [])
            v_course = st.selectbox("Filter by Course", course_list, key="v_course")

        with col3:
            date_list = ["All"] + (df_attendance["Date"].dropna().unique().tolist() if "Date" in df_attendance.columns else [])
            v_date = st.selectbox("Filter by Date", date_list, key="v_date")

        filtered_view = df_attendance.copy()

        if v_dept != "All" and "Department" in filtered_view.columns:
            filtered_view = filtered_view[filtered_view["Department"] == v_dept]

        if v_course != "All" and "Course" in filtered_view.columns:
            filtered_view = filtered_view[filtered_view["Course"] == v_course]

        if v_date != "All" and "Date" in filtered_view.columns:
            filtered_view = filtered_view[filtered_view["Date"] == v_date]

        # ID অনুযায়ী সর্টিং
        if not filtered_view.empty and "Student ID" in filtered_view.columns:
            try:
                filtered_view["_sort_id"] = pd.to_numeric(filtered_view["Student ID"])
                filtered_view = filtered_view.sort_values(by="_sort_id", ascending=True).drop(columns=["_sort_id"])
            except Exception:
                pass

        st.dataframe(filtered_view, use_container_width=True)


# -------------------------------------------------------------
# 4. MANAGE STUDENTS
# -------------------------------------------------------------
elif menu == "Manage Students":
    st.header("Manage Registered Students")

    df_students = load_students()

    if df_students.empty:
        st.warning("No students registered yet.")
    else:
        # ফিল্টার
        col1, col2 = st.columns(2)
        with col1:
            m_dept_list = ["All"] + (df_students["Department"].dropna().unique().tolist() if "Department" in df_students.columns else [])
            m_dept = st.selectbox("Filter Department", m_dept_list, key="m_dept")
        with col2:
            m_year_list = ["All"] + (df_students["Academic Year"].dropna().unique().tolist() if "Academic Year" in df_students.columns else [])
            m_year = st.selectbox("Filter Academic Year", m_year_list, key="m_year")

        m_filtered = df_students.copy()
        if m_dept != "All" and "Department" in m_filtered.columns:
            m_filtered = m_filtered[m_filtered["Department"] == m_dept]
        if m_year != "All" and "Academic Year" in m_filtered.columns:
            m_filtered = m_filtered[m_filtered["Academic Year"] == m_year]

        # ID সর্টিং
        if not m_filtered.empty and "Student ID" in m_filtered.columns:
            try:
                m_filtered["_sort_id"] = pd.to_numeric(m_filtered["Student ID"])
                m_filtered = m_filtered.sort_values(by="_sort_id", ascending=True).drop(columns=["_sort_id"])
            except Exception:
                pass

        st.dataframe(m_filtered, use_container_width=True)

        st.markdown("---")
        st.subheader("Delete Student Record")

        student_to_delete = st.selectbox(
            "Select Student ID to Delete",
            ["None"] + df_students["Student ID"].astype(str).tolist(),
            key="del_student"
        )

        if student_to_delete != "None":
            if st.button(f"Delete Student ID: {student_to_delete}", type="primary"):
                df_updated = df_students[df_students["Student ID"].astype(str) != str(student_to_delete)]
                
                rows_to_save = [df_updated.columns.tolist()] + df_updated.values.tolist()
                students_worksheet.clear()
                students_worksheet.update(rows_to_save)
                
                st.success(f"Student ID '{student_to_delete}' removed successfully!")
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
        # Select Department and Year filters
        col1, col2 = st.columns(2)
        with col1:
            dept_list = (
                df_students["Department"].dropna().unique().tolist()
                if "Department" in df_students.columns
                else ["Geography & Environment"]
            )
            selected_dept = st.selectbox("Select Department", dept_list, key="pct_dept")

        with col2:
            filtered_students = (
                df_students[df_students["Department"] == selected_dept]
                if "Department" in df_students.columns
                else df_students.copy()
            )
            year_list = ["All Years"]
            if "Academic Year" in filtered_students.columns:
                year_list += filtered_students["Academic Year"].dropna().unique().tolist()
            selected_year = st.selectbox("Select Academic Year", year_list, key="pct_year")

        if selected_year != "All Years" and "Academic Year" in filtered_students.columns:
            filtered_students = filtered_students[filtered_students["Academic Year"] == selected_year]

        st.markdown("---")
        
        # Blank ID input box by default
        input_student_id = st.text_input(
            "Enter Your Student ID",
            value="",
            placeholder="e.g., 32006",
            key="pct_input_id"
        ).strip()

        if not input_student_id:
            st.info("Please enter your Student ID above to view your attendance progress.")
        else:
            # Check if student exists in the filtered department/year list
            matched_student = filtered_students[
                filtered_students["Student ID"].astype(str).str.strip() == input_student_id
            ]

            if matched_student.empty:
                st.error(f"No registered student found with ID '{input_student_id}' under {selected_dept} ({selected_year}).")
            else:
                student_name = matched_student.iloc[0]["Name"]

                # Fetch attendance logs
                filtered_att = df_attendance.copy()
                if not filtered_att.empty and "Department" in filtered_att.columns:
                    filtered_att = filtered_att[filtered_att["Department"] == selected_dept]

                if not filtered_att.empty and "Student ID" in filtered_att.columns:
                    st_att = filtered_att[filtered_att["Student ID"].astype(str).str.strip() == input_student_id]
                    total_recorded = len(st_att)
                    p_count = int((st_att["Status"] == "Present").sum())
                    a_count = int((st_att["Status"] == "Absent").sum())
                else:
                    total_recorded = 0
                    p_count = 0
                    a_count = 0

                percentage = round((p_count / total_recorded) * 100, 2) if total_recorded > 0 else 0.0

                # Display Individual Student Summary Card & Metrics
                st.markdown(f"### Progress Summary for: **{student_name}** (ID: {input_student_id})")
                
                summary_df = pd.DataFrame([{
                    "Student ID": input_student_id,
                    "Name": student_name,
                    "Total Classes Recorded": total_recorded,
                    "Present": p_count,
                    "Absent": a_count,
                    "Attendance Percentage (%)": percentage
                }])
                
                st.dataframe(summary_df, use_container_width=True)

                st.markdown("---")
                st.metric(label="Attendance Percentage", value=f"{percentage}%")
                st.progress(float(percentage) / 100)
                st.write(f"**Total Classes:** {total_recorded} | **Present:** {p_count} | **Absent:** {a_count}")
