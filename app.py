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
# 5. STUDENT PERCENTAGE CHECKER
# -------------------------------------------------------------
elif menu == "Student Percentage Checker":
    st.header("Student Attendance Percentage Checker")

    df_attendance = load_attendance()
    df_students = load_students()

    if df_students.empty and df_attendance.empty:
        st.info("No records found in Students or Attendance sheets.")
    else:
        # ১. Select Department
        dept_list = (
            df_students["Department"].dropna().unique().tolist()
            if "Department" in df_students.columns and not df_students.empty
            else df_attendance["Department"].dropna().unique().tolist() if "Department" in df_attendance.columns else ["Geography & Environment"]
        )
        selected_dept = st.selectbox("Select Department", dept_list, key="pct_dept")

        # ডিপার্টমেন্ট অনুযায়ী স্টুডেন্ট ফিল্টার
        filtered_students = df_students[df_students["Department"] == selected_dept] if "Department" in df_students.columns else df_students.copy()

        # ২. Select Academic Year
        year_list = ["All Years"]
        if "Academic Year" in filtered_students.columns:
            year_list += filtered_students["Academic Year"].dropna().unique().tolist()
        selected_year = st.selectbox("Select Academic Year", year_list, key="pct_year")

        if selected_year != "All Years" and "Academic Year" in filtered_students.columns:
            filtered_students = filtered_students[filtered_students["Academic Year"] == selected_year]

        # ৩. Select Student (ID - Name)
        student_options = ["All Students"]
        if not filtered_students.empty and "Student ID" in filtered_students.columns and "Name" in filtered_students.columns:
            for _, row in filtered_students.iterrows():
                student_options.append(f"{row['Student ID']} - {row['Name']}")
        
        selected_student = st.selectbox("Select Student", student_options, key="pct_student")

        # অ্যাটেন্ডেন্স ফিল্টারিং
        filtered_att = df_attendance.copy()
        if "Department" in filtered_att.columns:
            filtered_att = filtered_att[filtered_att["Department"] == selected_dept]

        # যদি ড্রপডাউন থেকে নির্দিষ্ট স্টুডেন্ট নির্বাচন করা হয়
        if selected_student != "All Students":
            student_id = selected_student.split(" - ")[0].strip()
            filtered_att = filtered_att[filtered_att["Student ID"].astype(str) == student_id]
        elif not filtered_students.empty and "Student ID" in filtered_students.columns:
            valid_ids = filtered_students["Student ID"].astype(str).tolist()
            filtered_att = filtered_att[filtered_att["Student ID"].astype(str).isin(valid_ids)]

        st.markdown(f"### Summary for Department: **{selected_dept}** | Year: **{selected_year}**")

        if filtered_att.empty:
            st.warning("No attendance records found for the selected options.")
        else:
            filtered_att["Student ID"] = filtered_att["Student ID"].astype(str)

            # পার্সেন্টেজ হিসাব
            summary_list = []
            grouped = filtered_att.groupby(["Student ID", "Name"])

            for (s_id, name), group in grouped:
                total_recorded = len(group)
                p_count = (group["Status"] == "Present").sum()
                a_count = (group["Status"] == "Absent").sum()
                percentage = round((p_count / total_recorded) * 100, 2) if total_recorded > 0 else 0.0

                summary_list.append({
                    "Student ID": s_id,
                    "Name": name,
                    "Total Classes Recorded": total_recorded,
                    "Present": p_count,
                    "Absent": a_count,
                    "Attendance Percentage (%)": percentage
                })

            summary_df = pd.DataFrame(summary_list)

            # আইডি নিউমেরিক সর্টিং
            try:
                summary_df["_sort_id"] = pd.to_numeric(summary_df["Student ID"])
                summary_df = summary_df.sort_values(by="_sort_id", ascending=True).drop(columns=["_sort_id"])
            except Exception:
                pass

            st.dataframe(summary_df, use_container_width=True)

            # নির্দিষ্ট একজন স্টুডেন্ট নির্বাচন করলে তার ভিজ্যুয়াল মেট্রিক
            if selected_student != "All Students" and not summary_df.empty:
                row = summary_df.iloc[0]
                st.markdown("---")
                st.success(f"**Student Name:** {row['Name']}")
                st.metric(label="Attendance Percentage", value=f"{row['Attendance Percentage (%)']}%")
                st.progress(float(row['Attendance Percentage (%)']) / 100)
                st.write(f"**Total Classes:** {row['Total Classes Recorded']} | **Present:** {row['Present']} | **Absent:** {row['Absent']}")
