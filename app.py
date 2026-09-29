import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# -------------------------------------------------------------
# 1. PAGE CONFIGURATION & STYLING
# -------------------------------------------------------------
st.set_page_config(
    page_title="OASIS - Attendance & Student Management System",
    layout="wide"
)

st.title("OASIS - Attendance & Student Management System")

# -------------------------------------------------------------
# 2. GOOGLE SHEETS CONNECTION SETUP
# -------------------------------------------------------------
@st.cache_resource
def init_connection():
    # Streamlit Secrets থেকে ক্রেডেনশিয়ালস লোড
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scope
    )
    client = gspread.authorize(credentials)
    return client

try:
    client = init_connection()
    # আপনার গুগল শিটের নাম
    spreadsheet = client.open("OASIS_Attendance_DB")
    students_worksheet = spreadsheet.worksheet("Students")
    attendance_worksheet = spreadsheet.worksheet("Attendance")
except Exception as e:
    st.error(f"Google Sheets Connection Error: {e}")
    st.stop()

# -------------------------------------------------------------
# DATA LOADING FUNCTIONS (WITH CACHING)
# -------------------------------------------------------------
@st.cache_data(ttl=60)
def load_students():
    try:
        data = students_worksheet.get_all_records()
        df = pd.DataFrame(data)
        if not df.empty and "Student ID" in df.columns:
            df["Student ID"] = df["Student ID"].astype(str).str.strip()
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=60)
def load_attendance():
    try:
        data = attendance_worksheet.get_all_records()
        df = pd.DataFrame(data)
        if not df.empty and "Student ID" in df.columns:
            df["Student ID"] = df["Student ID"].astype(str).str.strip()
        return df
    except Exception:
        return pd.DataFrame()

# -------------------------------------------------------------
# SIDEBAR NAVIGATION
# -------------------------------------------------------------
st.sidebar.title("Navigation")
menu = st.sidebar.radio(
    "Select Menu Option",
    [
        "Take Attendance",
        "Attendance Records",
        "Register Student",
        "Manage Students"
    ]
)

# -------------------------------------------------------------
# MENU 1: TAKE ATTENDANCE
# -------------------------------------------------------------
if menu == "Take Attendance":
    st.header("Take Attendance")

    df_students = load_students()

    if df_students.empty or "Student ID" not in df_students.columns:
        st.warning("No registered students found! Please register students first.")
    else:
        # ১. ফিল্টারসমূহ
        col1, col2, col3 = st.columns(3)
        with col1:
            raw_years = df_students["Academic Year"].dropna().unique().tolist() if "Academic Year" in df_students.columns else []
            selected_year = st.selectbox("Select Academic Year", raw_years if raw_years else ["1st Year", "2nd Year", "3rd Year", "4th Year"])
        with col2:
            course_name = st.text_input("Course Code / Name", placeholder="e.g., GETH: 4003")
        with col3:
            att_date = st.date_input("Date")

        filtered_students = df_students[df_students["Academic Year"] == selected_year] if "Academic Year" in df_students.columns else df_students

        st.write(f"Showing **{len(filtered_students)}** student(s) for **{selected_year}**")

        if filtered_students.empty:
            st.info("No students registered under this Academic Year.")
        else:
            with st.form("attendance_form"):
                st.subheader("Mark Present / Absent")
                
                # টেবিল হেডার
                h_c1, h_c2, h_c3, h_c4 = st.columns([1, 2, 3, 2])
                with h_c1: st.markdown("**Present?**")
                with h_c2: st.markdown("**Student ID**")
                with h_c3: st.markdown("**Name**")
                with h_c4: st.markdown("**Session**")
                st.markdown("---")

                attendance_data = {}

                for _, row in filtered_students.iterrows():
                    s_id = str(row["Student ID"]).strip()
                    s_name = str(row["Name"]).strip()
                    s_session = str(row.get("Session", "")).strip()

                    c1, c2, c3, c4 = st.columns([1, 2, 3, 2])
                    with c1:
                        is_present = st.checkbox("", value=True, key=f"att_chk_{s_id}")
                    with c2:
                        st.write(s_id)
                    with c3:
                        st.write(f"**{s_name}**")
                    with c4:
                        st.write(s_session)

                    attendance_data[s_id] = {
                        "Name": s_name,
                        "Status": "Present" if is_present else "Absent",
                        "Session": s_session,
                        "Academic Year": selected_year
                    }

                submit_att = st.form_submit_button("Save Attendance", type="primary", use_container_width=True)

                if submit_att:
                    if not course_name.strip():
                        st.error("Please enter a Course Code / Name before saving.")
                    else:
                        rows_to_append = []
                        str_date = str(att_date)

                        for s_id, info in attendance_data.items():
                            rows_to_append.append([
                                str_date,
                                course_name.strip(),
                                s_id,
                                info["Name"],
                                info["Status"],
                                info["Academic Year"]
                            ])

                        try:
                            attendance_worksheet.append_rows(rows_to_append)
                            st.cache_data.clear()
                            st.success(f"Attendance saved successfully for {len(rows_to_append)} students!")
                        except Exception as e:
                            st.error(f"Error saving attendance: {e}")

# -------------------------------------------------------------
# MENU 2: ATTENDANCE RECORDS & REPORTS (DAILY SUMMARY)
# -------------------------------------------------------------
elif menu == "Attendance Records":
    st.header("Attendance Records & Reports")

    df_attendance = load_attendance()
    df_students = load_students()

    if df_attendance.empty or "Student ID" not in df_attendance.columns:
        st.info("No attendance records found.")
    else:
        df_attendance["Student ID"] = df_attendance["Student ID"].astype(str).str.strip()
        
        # ফিল্টার ফিল্ডস
        col_yr, col_date, col_sort = st.columns(3)

        with col_yr:
            raw_years = (
                df_attendance["Academic Year"].dropna().unique().tolist()
                if "Academic Year" in df_attendance.columns
                else ["1st Year", "2nd Year", "3rd Year", "4th Year"]
            )
            filter_year = st.selectbox("Filter by Academic Year", ["All Years"] + raw_years)

        with col_date:
            dates = df_attendance["Date"].dropna().unique().tolist()
            filter_date = st.selectbox("Filter by Date", dates, index=0 if dates else None)

        with col_sort:
            filter_status = st.selectbox(
                "Sort Records by:",
                ["All Students", "Present Only", "Absent Only"]
            )

        # ডাটা ফিল্টারিং
        filtered_df = df_attendance.copy()
        if filter_year != "All Years" and "Academic Year" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["Academic Year"] == filter_year]

        if filter_date:
            filtered_df = filtered_df[filtered_df["Date"] == filter_date]

        if filtered_df.empty:
            st.warning("No records found for the selected criteria.")
        else:
            total_classes_conducted = filtered_df["Course"].nunique() if "Course" in filtered_df.columns else 1

            summary_list = []
            valid_students = df_students.copy()
            if filter_year != "All Years" and "Academic Year" in valid_students.columns:
                valid_students = valid_students[valid_students["Academic Year"] == filter_year]

            if not valid_students.empty and "Student ID" in valid_students.columns:
                valid_students["Student ID"] = valid_students["Student ID"].astype(str).str.strip()

                for _, s_row in valid_students.iterrows():
                    s_id = s_row["Student ID"]
                    s_name = s_row["Name"]
                    s_year = s_row.get("Academic Year", filter_year)

                    st_records = filtered_df[filtered_df["Student ID"] == s_id]

                    if not st_records.empty:
                        p_count = len(st_records[st_records["Status"].str.lower() == "present"])
                        status_label = "Present" if p_count > 0 else "Absent"
                        
                        summary_list.append({
                            "Date": filter_date if filter_date else "N/A",
                            "Student ID": s_id,
                            "Name": s_name,
                            "Academic Year": s_year,
                            "Classes Attended": f"{p_count} / {total_classes_conducted}",
                            "Attended Count": p_count,
                            "Status": status_label
                        })

            summary_df = pd.DataFrame(summary_list)

            if not summary_df.empty:
                if filter_status == "Present Only":
                    summary_df = summary_df[summary_df["Status"] == "Present"]
                    summary_df = summary_df.sort_values(by="Attended Count", ascending=False)
                elif filter_status == "Absent Only":
                    summary_df = summary_df[summary_df["Status"] == "Absent"]
                else:
                    summary_df = summary_df.sort_values(by=["Attended Count", "Student ID"], ascending=[False, True])

                total_st = len(summary_list)
                present_st = len([x for x in summary_list if x["Status"] == "Present"])
                absent_st = total_st - present_st

                col_m1, col_m2, col_m3 = st.columns(3)
                col_m1.metric("Total Students", total_st)
                col_m2.metric("Present Students", present_st)
                col_m3.metric("Absent Students", absent_st)

                st.markdown("---")

                display_df = summary_df[["Date", "Student ID", "Name", "Academic Year", "Classes Attended", "Status"]]
                st.dataframe(display_df, use_container_width=True)

                csv = display_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Attendance Summary as CSV",
                    data=csv,
                    file_name=f"Attendance_Summary_{filter_date}.csv",
                    mime="text/csv"
                )

# -------------------------------------------------------------
# MENU 3: REGISTER STUDENT (SINGLE & EXCEL/CSV BULK UPLOAD)
# -------------------------------------------------------------
elif menu == "Register Student":
    st.header("Register Students")

    reg_option = st.radio(
        "Choose Registration Method",
        ["Single Student Registration", "Bulk Upload via Excel / CSV"],
        horizontal=True
    )

    df_students = load_students()

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

            submit_student = st.form_submit_button("Add Student", type="primary")

            if submit_student:
                if not student_id or not name:
                    st.error("Please fill in both Student ID and Name.")
                else:
                    if (
                        not df_students.empty
                        and "Student ID" in df_students.columns
                        and str(student_id).strip() in df_students["Student ID"].astype(str).str.strip().values
                    ):
                        st.error(f"Student ID '{student_id}' already exists!")
                    else:
                        students_worksheet.append_row(
                            [str(student_id).strip(), name.strip(), department, academic_year]
                        )
                        st.cache_data.clear()
                        st.success(f"Student {name} (ID: {student_id}, {academic_year}) successfully added!")

    elif reg_option == "Bulk Upload via Excel / CSV":
        st.subheader("Bulk Upload Students via Excel / CSV")
        st.info("আপনার এক্সেল/সিএসভি ফাইলে অবশ্যই এই ৪টি কলাম থাকতে হবে: **Student ID**, **Name**, **Session**, **Academic Year**")

        uploaded_file = st.file_uploader("Upload Excel or CSV File", type=["xlsx", "xls", "csv"])

        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith(".csv"):
                    new_df = pd.read_csv(uploaded_file)
                else:
                    new_df = pd.read_excel(uploaded_file)

                new_df.columns = new_df.columns.str.strip()
                required_cols = ["Student ID", "Name", "Session", "Academic Year"]
                missing_cols = [col for col in required_cols if col not in new_df.columns]

                if missing_cols:
                    st.error(f"আপনার এক্সেল ফাইলে নিচের কলামগুলো অনুপস্থিত: {', '.join(missing_cols)}")
                else:
                    new_df = new_df[required_cols].dropna(subset=["Student ID", "Name"])
                    new_df["Student ID"] = new_df["Student ID"].astype(str).str.strip()
                    new_df["Name"] = new_df["Name"].astype(str).str.strip()
                    new_df["Session"] = new_df["Session"].astype(str).str.strip()
                    new_df["Academic Year"] = new_df["Academic Year"].astype(str).str.strip()

                    st.write("### Uploaded Data Preview:")
                    st.dataframe(new_df, use_container_width=True)

                    if st.button("Import All Students to Google Sheets", type="primary"):
                        existing_ids = []
                        if not df_students.empty and "Student ID" in df_students.columns:
                            existing_ids = df_students["Student ID"].astype(str).str.strip().tolist()

                        filtered_new_df = new_df[~new_df["Student ID"].isin(existing_ids)]
                        duplicate_count = len(new_df) - len(filtered_new_df)

                        if filtered_new_df.empty:
                            st.warning("আপলোড করা এক্সেল ফাইলের সকল স্টুডেন্ট আইডি আগেই গুগল শিটে বিদ্যমান আছে!")
                        else:
                            rows_to_append = filtered_new_df.values.tolist()
                            students_worksheet.append_rows(rows_to_append)
                            st.cache_data.clear()
                            st.success(f"সফলভাবে **{len(filtered_new_df)}** জন নতুন শিক্ষার্থী যুক্ত করা হয়েছে!")
                            if duplicate_count > 0:
                                st.info(f"{duplicate_count} জন স্টুডেন্ট আইডি আগে থেকেই থাকার কারণে বাদ দেওয়া হয়েছে।")
                            st.rerun()

            except Exception as e:
                st.error(f"Error processing file: {e}")

# -------------------------------------------------------------
# MENU 4: MANAGE STUDENTS (PROMOTION & SMART DELETE TOGETHER)
# -------------------------------------------------------------
elif menu == "Manage Students":
    st.header("Student Directory & Management")

    df_students = load_students()

    if df_students.empty or "Student ID" not in df_students.columns:
        st.info("No students registered yet or missing 'Student ID' column header in Google Sheets.")
    else:
        # =========================================================
        # PART 1: BULK PROMOTION SECTION
        # =========================================================
        st.subheader("Bulk Promote Selected Students")

        raw_years = (
            df_students["Academic Year"].dropna().unique().tolist()
            if "Academic Year" in df_students.columns
            else ["1st Year", "2nd Year", "3rd Year", "4th Year"]
        )
        
        filter_options = ["-- Select Academic Year --"] + raw_years
        selected_filter_year = st.selectbox(
            "Filter Students by Academic Year to Promote", 
            filter_options,
            index=0
        )

        if selected_filter_year == "-- Select Academic Year --":
            st.info("প্রমোট করার জন্য স্টুডেন্ট লিস্ট দেখতে উপরে একটি **Academic Year** সিলেক্ট করুন।")
        else:
            filtered_df = df_students[df_students["Academic Year"] == selected_filter_year].copy()

            st.write(f"Showing **{len(filtered_df)}** student(s) for **{selected_filter_year}**")

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
                    h_col1, h_col2, h_col3, h_col4, h_col5 = st.columns([1, 2, 3, 2, 2])
                    with h_col1: st.markdown("**Select**")
                    with h_col2: st.markdown("**Student ID**")
                    with h_col3: st.markdown("**Name**")
                    with h_col4: st.markdown("**Session**")
                    with h_col5: st.markdown("**Current Year**")

                    st.markdown("---")

                    selected_student_ids = []

                    for index, row in filtered_df.iterrows():
                        s_id = str(row["Student ID"]).strip()
                        s_name = str(row["Name"]).strip()
                        s_session = str(row.get("Session", "")).strip()
                        curr_year = str(row.get("Academic Year", "")).strip()

                        col1, col2, col3, col4, col5 = st.columns([1, 2, 3, 2, 2])
                        
                        with col1:
                            is_selected = st.checkbox("Select", value=False, key=f"promote_chk_{s_id}", label_visibility="collapsed")
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
                        submit_promote = st.form_submit_button("Promote Selected Students", type="primary", use_container_width=True)

                    if submit_promote:
                        if not selected_student_ids:
                            st.warning("অনুগ্রহ করে অন্তত একজন স্টুডেন্ট সিলেক্ট করুন যাকে প্রমোট করতে চান।")
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
                                st.success(f"Successfully promoted {len(selected_student_ids)} student(s) to **{promote_to_year}**!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error updating Google Sheets: {e}")

        # =========================================================
        # PART 2: DELETE STUDENT SECTION (WITH PREVIEW & CONFIRMATION)
        # =========================================================
        st.markdown("---")
        st.subheader("Delete a Student")
        
        del_id_input = st.text_input(
            "Enter Student ID / Roll to Search for Deletion", 
            placeholder="e.g., 210101",
            key="del_search_input"
        )

        clean_del_id = del_id_input.strip()

        if clean_del_id:
            matched_student = df_students[
                df_students["Student ID"].astype(str).str.strip() == clean_del_id
            ]

            if not matched_student.empty:
                student_info = matched_student.iloc[0]
                s_id = str(student_info["Student ID"]).strip()
                s_name = str(student_info["Name"]).strip()
                s_session = str(student_info.get("Session", "N/A")).strip()
                s_year = str(student_info.get("Academic Year", "N/A")).strip()

                st.success("Student Found!")

                with st.container():
                    st.markdown(
                        f"""
                        <div style="border:1px solid #ff4b4b; padding: 15px; border-radius: 8px; background-color: #fff5f5; margin-bottom: 15px;">
                            <h4 style="margin-top:0; color: #ff4b4b;">Student Details Preview</h4>
                            <p><b>Student ID / Roll:</b> {s_id}</p>
                            <p><b>Name:</b> {s_name}</p>
                            <p><b>Session:</b> {s_session}</p>
                            <p><b>Academic Year:</b> {s_year}</p>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )

                st.warning(f"Are you sure you want to delete **{s_name}** (ID: {s_id}) permanently?")
                
                if st.button("Confirm Delete Student", type="primary"):
                    try:
                        cell = students_worksheet.find(s_id)
                        if cell:
                            students_worksheet.delete_rows(cell.row)
                            st.cache_data.clear()
                            st.success(f"Student ID '{s_id}' ({s_name}) has been deleted successfully!")
                            st.rerun()
                        else:
                            st.error("Student ID cell could not be located in Google Sheets.")
                    except Exception as e:
                        st.error(f"Error deleting student: {e}")
            else:
                st.error(f"No student found with ID/Roll: '{clean_del_id}'")
