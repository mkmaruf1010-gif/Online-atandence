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
            st.info(" Please select an Academic Year above to display courses and student list.")
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
# 2. REGISTER STUDENT (WITH BULK EXCEL / CSV UPLOAD)
# -------------------------------------------------------------
elif menu == "Register Student":
    st.header("Register Students")

    # দুই ধরণের অপশন দেওয়া হচ্ছে: ১. ম্যানুয়াল সিঙ্গেল রেজিস্ট্রেশন, ২. বাল্ক এক্সেল আপলোড
    reg_option = st.radio(
        "Choose Registration Method",
        ["Single Student Registration", "Bulk Upload via Excel / CSV"],
        horizontal=True
    )

    df_students = load_students()

    # --- অপশন ১: ম্যানুয়ালি একজন একজন করে অ্যাড করা ---
    if reg_option == "Single Student Registration":
        st.subheader("Add Single Student")
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
                        st.cache_data.clear()
                        st.success(
                            f"Student {name} (ID: {student_id}, {academic_year}) successfully added!"
                        )

    # --- অপশন ২: এক্সেল বা CSV ফাইল আপলোড করে এক ক্লিকে রেজিস্ট্রেশন ---
    elif reg_option == "Bulk Upload via Excel / CSV":
        st.subheader(" Bulk Upload Students via Excel / CSV")
        st.info(
            "আপনার এক্সেল/সিএসভি ফাইলে অবশ্যই এই ৪টি কলাম থাকতে হবে: **Student ID**, **Name**, **Session**, **Academic Year**"
        )

        uploaded_file = st.file_uploader(
            "Upload Excel or CSV File", type=["xlsx", "xls", "csv"]
        )

        if uploaded_file is not None:
            try:
                # ফাইল টাইপ অনুযায়ী রিড করা
                if uploaded_file.name.endswith(".csv"):
                    new_df = pd.read_csv(uploaded_file)
                else:
                    new_df = pd.read_excel(uploaded_file)

                # কলাম হেডার ক্লিন করা
                new_df.columns = new_df.columns.str.strip()

                required_cols = ["Student ID", "Name", "Session", "Academic Year"]
                missing_cols = [col for col in required_cols if col not in new_df.columns]

                if missing_cols:
                    st.error(f" আপনার এক্সেল ফাইলে নিচের কলামগুলো অনুপস্থিত: {', '.join(missing_cols)}")
                else:
                    # ফাইল থেকে প্রয়োজনীয় কলাম ফিল্টার করা ও স্ট্রিং-এ কনভার্ট করা
                    new_df = new_df[required_cols].dropna(subset=["Student ID", "Name"])
                    new_df["Student ID"] = new_df["Student ID"].astype(str).str.strip()
                    new_df["Name"] = new_df["Name"].astype(str).str.strip()
                    new_df["Session"] = new_df["Session"].astype(str).str.strip()
                    new_df["Academic Year"] = new_df["Academic Year"].astype(str).str.strip()

                    # আপলোড করা ডেটা প্রিভিউ দেখানো
                    st.write("###  Uploaded Data Preview:")
                    st.dataframe(new_df, use_container_width=True)

                    if st.button(" Import All Students to Google Sheets", type="primary"):
                        existing_ids = []
                        if not df_students.empty and "Student ID" in df_students.columns:
                            existing_ids = df_students["Student ID"].astype(str).str.strip().tolist()

                        # ডুপ্লিকেট বাদ দিয়ে নতুন স্টুডেন্ট ফিল্টার করা
                        filtered_new_df = new_df[~new_df["Student ID"].isin(existing_ids)]
                        duplicate_count = len(new_df) - len(filtered_new_df)

                        if filtered_new_df.empty:
                            st.warning(" আপলোড করা এক্সেল ফাইলের সকল স্টুডেন্ট আইডি আগেই গুগল শিটে বিদ্যমান আছে!")
                        else:
                            # গুগল শিটে অ্যাপেন্ড করার জন্য লিস্ট তৈরি
                            rows_to_append = filtered_new_df.values.tolist()
                            students_worksheet.append_rows(rows_to_append)

                            st.cache_data.clear()

                            st.success(f"  সফলভাবে **{len(filtered_new_df)}** জন নতুন শিক্ষার্থী যুক্ত করা হয়েছে!")
                            if duplicate_count > 0:
                                st.info(f"  {duplicate_count} জন স্টুডেন্ট আইডি আগের ডাটাবেজে ছিল বলে বাদ দেওয়া হয়েছে (Duplicate avoidance)।")
                            st.rerun()

            except Exception as e:
                st.error(f"Error processing file: {e}")
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
# 4. MANAGE STUDENTS (WITH MANDATORY YEAR SELECTION & MULTI-SELECT PROMOTION)
# -------------------------------------------------------------
elif menu == "Manage Students":
    st.header("Student Directory & Promotion")

    df_students = load_students()

    if df_students.empty or "Student ID" not in df_students.columns:
        st.info(
            "No students registered yet or missing 'Student ID' column header in Google Sheets."
        )
    else:
        st.subheader(" Bulk Promote Selected Students")

        # ১. বাধ্যতামূলক ইয়ার ফিল্টার (ডিফল্টভাবে ফাঁকা থাকবে)
        raw_years = (
            df_students["Academic Year"].dropna().unique().tolist()
            if "Academic Year" in df_students.columns
            else ["1st Year", "2nd Year", "3rd Year", "4th Year"]
        )
        
        # ড্রপডাউনের প্রথম অপশন "-- Select Academic Year --"
        filter_options = ["-- Select Academic Year --"] + raw_years
        selected_filter_year = st.selectbox(
            "Filter Students by Academic Year", 
            filter_options,
            index=0
        )

        # যতক্ষণ পর্যন্ত ইয়ার সিলেক্ট না করা হবে
        if selected_filter_year == "-- Select Academic Year --":
            st.info(" অনুগ্রহ করে স্টুডেন্ট লিস্ট দেখতে এবং প্রমোট করতে উপরে একটি **Academic Year** সিলেক্ট করুন।")
        else:
            filtered_df = df_students[df_students["Academic Year"] == selected_filter_year].copy()

            st.write(f"Showing **{len(filtered_df)}** student(s) for **{selected_filter_year}**")

            # ২. স্টুডেন্ট লিস্ট এবং প্রমোশন ফর্ম
            if filtered_df.empty:
                st.warning(f"No students found for {selected_filter_year}.")
            else:
                year_map = {
                    "1st Year": "2nd Year",
                    "2nd Year": "3rd Year",
                    "3rd Year": "4th Year",
                    "4th Year": "Graduated"
                }

                with st.form("bulk_promotion_form"):
                    # হেডার কলাম
                    h_col1, h_col2, h_col3, h_col4, h_col5 = st.columns([1, 2, 3, 2, 2])
                    with h_col1:
                        st.markdown("**Select**")
                    with h_col2:
                        st.markdown("**Student ID**")
                    with h_col3:
                        st.markdown("**Name**")
                    with h_col4:
                        st.markdown("**Session**")
                    with h_col5:
                        st.markdown("**Current Year**")

                    st.markdown("---")

                    selected_student_ids = []

                    # নির্দিষ্ট ইয়ারের স্টুডেন্টদের লিস্ট দেখানো
                    for index, row in filtered_df.iterrows():
                        s_id = str(row["Student ID"]).strip()
                        s_name = str(row["Name"]).strip()
                        s_session = str(row.get("Session", "")).strip()
                        curr_year = str(row.get("Academic Year", "")).strip()

                        col1, col2, col3, col4, col5 = st.columns([1, 2, 3, 2, 2])
                        
                        with col1:
                            is_selected = st.checkbox(
                                "Select", 
                                value=False, 
                                key=f"promote_chk_{s_id}", 
                                label_visibility="collapsed"
                            )
                        with col2:
                            st.write(s_id)
                        with col3:
                            st.write(f"**{s_name}**")
                        with col4:
                            st.write(s_session)
                        with col5:
                            st.write(curr_year)

                        if is_selected:
                            selected_student_ids.append(s_id)

                    st.markdown("---")

                    # প্রমোশনের টার্গেট ইয়ার সিলেক্ট করা (অটোমেটিক পরবর্তী ইয়ার ক্যাচ করবে)
                    col_target, col_btn = st.columns([2, 2])
                    with col_target:
                        default_target = year_map.get(selected_filter_year, "2nd Year")
                        target_options = ["1st Year", "2nd Year", "3rd Year", "4th Year", "Graduated"]
                        default_index = target_options.index(default_target) if default_target in target_options else 1

                        promote_to_year = st.selectbox(
                            "Promote Selected To:",
                            target_options,
                            index=default_index
                        )

                    with col_btn:
                        st.write("")
                        st.write("")
                        submit_promote = st.form_submit_button("🎓 Promote Selected Students", type="primary", use_container_width=True)

                    if submit_promote:
                        if not selected_student_ids:
                            st.warning("  অনুগ্রহ করে অন্তত একজন স্টুডেন্ট সিলেক্ট করুন যাকে প্রমোট করতে চান।")
                        else:
                            df_students.loc[
                                df_students["Student ID"].astype(str).str.strip().isin(selected_student_ids),
                                "Academic Year"
                            ] = promote_to_year

                            rows_to_save = [df_students.columns.tolist()] + df_students.values.tolist()

                            try:
                                students_worksheet.clear()
                                students_worksheet.update(rows_to_save)
                                st.cache_data.clear()
                                st.success(f" Successfully promoted {len(selected_student_ids)} student(s) to **{promote_to_year}**!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error updating Google Sheets: {e}")

        st.markdown("---")

        # ৩. Delete Student Section
        st.subheader(" Delete a Student")
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
