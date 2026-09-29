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


# --- CACHED DATA LOADING FUNCTIONS (Rate Limit / API Quota Error 429 রোধ করার জন্য) ---

@st.cache_data(ttl=60)
def load_students():
    data = students_worksheet.get_all_records()
    df = pd.DataFrame(data)
    if not df.empty:
        df.columns = df.columns.str.strip()
    return df


@st.cache_data(ttl=60)
def load_attendance():
    data = attendance_worksheet.get_all_records()
    df = pd.DataFrame(data)
    if not df.empty:
        df.columns = df.columns.str.strip()
    return df


@st.cache_data(ttl=60)
def load_courses():
    try:
        courses_worksheet = sheet.worksheet("Courses")
        data = courses_worksheet.get_all_records()
        df = pd.DataFrame(data)
        if not df.empty:
            df.columns = df.columns.str.strip()
        return df
    except Exception:
        return pd.DataFrame()


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
# 1. MARK ATTENDANCE
# -------------------------------------------------------------
if menu == "Mark Attendance":
    st.header("Mark Daily Attendance")

    df_students = load_students()
    df_courses = load_courses()

    if df_students.empty or "Student ID" not in df_students.columns:
        st.warning(
            "No students found or missing 'Student ID' column in the 'Students' sheet! Please check your Google Sheet headers: [Student ID, Name, Session, Academic Year]."
        )
    else:
        raw_years = (
            df_students["Academic Year"].unique().tolist()
            if "Academic Year" in df_students.columns
            else ["1st Year", "2nd Year", "3rd Year", "4th Year"]
        )
        academic_years = ["-- Select Academic Year --"] + raw_years

        selected_year = st.selectbox(
            "Select Academic Year to Mark", academic_years, index=0
        )

        if selected_year == "-- Select Academic Year --":
            st.info("👆 Please select an Academic Year above to display courses and student list.")
        else:
            available_courses = []
            if not df_courses.empty and "Academic Year" in df_courses.columns and "Course Title" in df_courses.columns:
                filtered_courses = df_courses[
                    df_courses["Academic Year"].astype(str).str.strip() == str(selected_year).strip()
                ]
                available_courses = filtered_courses["Course Title"].dropna().tolist()

            if not available_courses:
                available_courses = ["General Course"]

            selected_course = st.selectbox("Select Course Code & Title", available_courses)

            filtered_students = df_students.copy()
            if "Academic Year" in df_students.columns:
                filtered_students = df_students[
                    df_students["Academic Year"] == selected_year
                ]

            att_date = st.date_input("Select Date", value=date.today())

            st.markdown(f"### Student List for {selected_year} - {selected_course}")
            st.info("Check the box next to the student if they are **Present**. (Unchecked means **Absent**)")

            sort_order = st.selectbox(
                "Sort Student ID by:",
                ["Ascending (Low to High)", "Descending (High to Low)"],
                key="attendance_id_sort",
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

            if filtered_students.empty:
                st.warning(f"No students registered under {selected_year}.")
            else:
                with st.form("attendance_form"):
                    attendance_status = {}

                    h_col1, h_col2, h_col3, h_col4 = st.columns([1, 2, 3, 2])
                    with h_col1:
                        st.markdown("**Status**")
                    with h_col2:
                        st.markdown("**Student ID**")
                    with h_col3:
                        st.markdown("**Name**")
                    with h_col4:
                        st.markdown("**Session**")

                    st.markdown("---")

                    for index, row in filtered_students.iterrows():
                        s_id = str(row["Student ID"]).strip()
                        s_name = str(row["Name"]).strip()
                        s_session = (
                            str(row["Session"]).strip()
                            if "Session" in df_students.columns
                            else ""
                        )

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

                    st.markdown("---")
                    submitted = st.form_submit_button("Save Attendance", use_container_width=True)

                    if submitted:
                        df_attendance = load_attendance()

                        if not df_attendance.empty and "Date" in df_attendance.columns:
                            rows_to_save = [
                                df_attendance.columns.tolist()
                            ] + df_attendance.values.tolist()
                        else:
                            rows_to_save = [["Date", "Course", "Student ID", "Name", "Status"]]

                        for s_id, data in attendance_status.items():
                            rows_to_save.append(
                                [
                                    str(att_date),
                                    str(selected_course),
                                    str(s_id),
                                    str(data["Name"]),
                                    str(data["Status"]),
                                ]
                            )

                        attendance_worksheet.clear()
                        attendance_worksheet.update(rows_to_save)
                        
                        # ক্যাশ ক্লিয়ার করা
                        st.cache_data.clear()
                        
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
                "2021-22", "2022-23", "2023-24", "2024-25", "2025-26",
                "2026-27", "2027-28", "2028-29", "2029-30", "2030-31"
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
                    
                    # ক্যাশ ক্লিয়ার করা
                    st.cache_data.clear()
                    
                    st.success(
                        f"Student {name} (ID: {student_id}, {academic_year}) successfully added!"
                    )

# -------------------------------------------------------------
# 3. VIEW RECORDS & ANALYTICS
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

            selected_year = st.selectbox(
                "Filter by Academic Year", academic_years, key="view_year"
            )

        with filter_col2:
            unique_dates = df_attendance["Date"].unique().tolist()
            selected_date = st.selectbox(
                "Filter by Date", ["All Dates"] + unique_dates, key="view_date"
            )

        with filter_col3:
            sort_by = st.selectbox(
                "Sort Records by:",
                ["Date (Newest First)", "Date (Oldest First)", "Student ID"],
                key="view_sort"
            )

        filtered_df = df_attendance.copy()
        if not df_students.empty and "Academic Year" in df_students.columns:
            if "Academic Year" not in filtered_df.columns:
                filtered_df = filtered_df.merge(
                    df_students[["Student ID", "Academic Year"]],
                    on="Student ID",
                    how="left"
                )

        if selected_year != "All Years" and "Academic Year" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Academic Year"] == selected_year]

        if selected_date != "All Dates":
            filtered_df = filtered_df[filtered_df["Date"] == selected_date]

        if "Date" in filtered_df.columns:
            try:
                filtered_df["_temp_date"] = pd.to_datetime(filtered_df["Date"])
                if sort_by == "Date (Newest First)":
                    filtered_df = filtered_df.sort_values(by="_temp_date", ascending=False)
                elif sort_by == "Date (Oldest First)":
                    filtered_df = filtered_df.sort_values(by="_temp_date", ascending=True)
                filtered_df = filtered_df.drop(columns=["_temp_date"])
            except Exception:
                pass

        if sort_by == "Student ID" and "Student ID" in filtered_df.columns:
            try:
                filtered_df["_temp_id"] = pd.to_numeric(filtered_df["Student ID"])
                filtered_df = filtered_df.sort_values(by="_temp_id", ascending=True).drop(columns=["_temp_id"])
            except Exception:
                filtered_df = filtered_df.sort_values(by="Student ID", ascending=True)

        total_records = len(filtered_df)
        present_count = len(
            filtered_df[filtered_df["Status"].astype(str).str.lower() == "present"]
        )
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
# 4. MANAGE STUDENTS (WITH INDIVIDUAL PROMOTION)
# -------------------------------------------------------------
elif menu == "Manage Students":
    st.header("Student Directory & Promotion")

    df_students = load_students()

    if df_students.empty or "Student ID" not in df_students.columns:
        st.info(
            "No students registered yet or missing 'Student ID' column header in Google Sheets."
        )
    else:
        st.subheader("🔍 Filter & Individual Student Promotion")
        
        # ১. ইয়ার ওয়াইজ ফিল্টার
        raw_years = (
            df_students["Academic Year"].unique().tolist()
            if "Academic Year" in df_students.columns
            else ["1st Year", "2nd Year", "3rd Year", "4th Year"]
        )
        filter_year = st.selectbox(
            "Filter Students by Academic Year", 
            ["All Years"] + raw_years
        )

        if filter_year != "All Years" and "Academic Year" in df_students.columns:
            filtered_df = df_students[df_students["Academic Year"] == filter_year].copy()
        else:
            filtered_df = df_students.copy()

        st.write(f"Showing **{len(filtered_df)}** student(s)")

        # ২. ইন্ডিভিজুয়াল প্রমোট বাটন সহ টেবিল
        if filtered_df.empty:
            st.warning("No students found for the selected Academic Year.")
        else:
            h_col1, h_col2, h_col3, h_col4, h_col5, h_col6 = st.columns([2, 3, 2, 2, 2, 2])
            with h_col1:
                st.markdown("**Student ID**")
            with h_col2:
                st.markdown("**Name**")
            with h_col3:
                st.markdown("**Session**")
            with h_col4:
                st.markdown("**Current Year**")
            with h_col5:
                st.markdown("**Promote To**")
            with h_col6:
                st.markdown("**Action**")

            st.markdown("---")

            year_map = {
                "1st Year": "2nd Year",
                "2nd Year": "3rd Year",
                "3rd Year": "4th Year",
                "4th Year": "Graduated"
            }

            for index, row in filtered_df.iterrows():
                s_id = str(row["Student ID"]).strip()
                s_name = str(row["Name"]).strip()
                s_session = str(row.get("Session", "")).strip()
                curr_year = str(row.get("Academic Year", "1st Year")).strip()

                col1, col2, col3, col4, col5, col6 = st.columns([2, 3, 2, 2, 2, 2])
                
                with col1:
                    st.write(s_id)
                with col2:
                    st.write(f"**{s_name}**")
                with col3:
                    st.write(s_session)
                with col4:
                    st.write(curr_year)
                with col5:
                    default_next = year_map.get(curr_year, "Graduated")
                    target_year = st.selectbox(
                        "Target Year",
                        ["1st Year", "2nd Year", "3rd Year", "4th Year", "Graduated"],
                        index=["1st Year", "2nd Year", "3rd Year", "4th Year", "Graduated"].index(default_next),
                        key=f"target_{s_id}",
                        label_visibility="collapsed"
                    )
                with col6:
                    if st.button("Promote 🎓", key=f"btn_promote_{s_id}"):
                        df_students.loc[
                            df_students["Student ID"].astype(str).str.strip() == s_id, 
                            "Academic Year"
                        ] = target_year

                        rows_to_save = [df_students.columns.tolist()] + df_students.values.tolist()

                        try:
                            students_worksheet.clear()
                            students_worksheet.update(rows_to_save)
                            
                            # ক্যাশ ক্লিয়ার করা যাতে নতুন আপডেট প্রতিফলিত হয়
                            st.cache_data.clear()
                            
                            st.success(f"Updated {s_name} (ID: {s_id}) to {target_year}!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error updating Google Sheets: {e}")

        st.markdown("---")

        # ৩. Delete Student Section
        st.subheader("🗑️ Delete a Student")
        del_id = st.selectbox(
            "Select Student ID to remove",
            df_students["Student ID"].astype(str).values,
        )

        if st.button("Delete Student"):
            cell = students_worksheet.find(str(del_id))
            if cell:
                students_worksheet.delete_rows(cell.row)
                st.cache_data.clear()
                st.success(f"Student ID {del_id} removed from Google Sheets!")
                st.rerun()
            else:
                st.error("Student ID not found in sheet.")

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
        input_student_id = st.text_input(
            "Enter Your Student ID",
            value="",
            placeholder="Roll",
            key="pct_input_id"
        ).strip()

        if not input_student_id:
            st.info("Please enter your Student ID above to view your attendance progress.")
        else:
            matched_student = df_students[
                df_students["Student ID"].astype(str).str.strip() == input_student_id
            ]

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

                st.markdown("---")
                st.subheader(" Detailed Date-wise Attendance Logs")

                if st_att.empty:
                    st.info("No detailed class records found for this student.")
                else:
                    display_cols = [col for col in ["Date", "Course", "Status"] if col in st_att.columns]

                    if display_cols:
                        detailed_df = st_att[display_cols].copy()

                        if "Date" in detailed_df.columns:
                            try:
                                detailed_df["Date"] = pd.to_datetime(detailed_df["Date"])
                                detailed_df = detailed_df.sort_values(by="Date", ascending=False)
                                detailed_df["Date"] = detailed_df["Date"].dt.strftime('%Y-%m-%d')
                            except Exception:
                                pass

                        st.dataframe(detailed_df, use_container_width=True)
                    else:
                        st.dataframe(st_att, use_container_width=True)
