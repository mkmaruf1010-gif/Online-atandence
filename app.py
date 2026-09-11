import streamlit as st
import pandas as pd
import datetime
import gspread
from google.oauth2.service_account import Credentials
import face_recognition
import numpy as np
from PIL import Image
import urllib.parse

# ---------------------------------------------------------
# ১. গুগল শিট কানেকশন সেটআপ (Google Sheets Authentication)
# ---------------------------------------------------------
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource
def init_connection():
    # Streamlit Secrets থেকে কাস্টম গুগল সার্ভিস একাউন্ট কি রিড করবে
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPE
    )
    client = gspread.authorize(creds)
    return client

try:
    client = init_connection()
    # আপনার গুগল শিটের আইডি ব্যবহার করে কানেক্ট করা হচ্ছে
    SHEET_ID = "1asAmEY9uhQG-Z8kCGdvSTJ9CfKB1qTHbVVLNz1CzykQ"
    sheet = client.open_by_key(SHEET_ID).sheet1
except Exception as e:
    st.error("গুগল শিটে কানেক্ট করতে সমস্যা হচ্ছে। কৃপা করে আপনার API Key/Secrets চেক করুন।")

# ---------------------------------------------------------
# ২. ইউআরএল প্যারামিটার রিড করা (Dynamic Link Check)
# ---------------------------------------------------------
query_params = st.query_params

course_param = query_params.get("course", None)
student_id_param = query_params.get("student_id", None)

# Page Title
st.title("🎓 অনলাইন অটোমেটিক অ্যাটেনডেন্স সিস্টেম")

# ---------------------------------------------------------
# ৩. ডিরেক্ট লিংক দিয়ে ঢুকলে (Student Camera Attendance Mode)
# ---------------------------------------------------------
if course_param and student_id_param:
    st.subheader(f"📌 কোর্স: {course_param} | স্টুডেন্ট আইডি: {student_id_param}")
    st.info("আপনার ফেস স্ক্যান করার জন্য নিচের ক্যামেরাটি অন করুন এবং ছবি তুলুন।")

    # স্টুডেন্টের আগের সেভ করা ছবি লোকাল/ড্রাইভ থেকে লোড করা (Sample Demo)
    # বাস্তবে আপনি স্টুডেন্টের আইডি অনুযায়ী আগে থেকে সেভ করা ছবি লোড করবেন
    try:
        known_image = face_recognition.load_image_file(f"known_faces/{student_id_param}.jpg")
        known_encoding = face_recognition.face_encodings(known_image)[0]
    except Exception:
        st.error("আপনার নিবন্ধিত ফেস ডাটাবেজে পাওয়া যায়নি! অ্যাডমিনের সাথে যোগাযোগ করুন।")
        known_encoding = None

    # ফোনের ক্যামেরা ইনপুট
    img_file_buffer = st.camera_input("ফেস স্ক্যান করার জন্য ক্লিক করুন")

    if img_file_buffer is not None and known_encoding is not None:
        # ছবি প্রসেসিং
        bytes_data = img_file_buffer.getvalue()
        unknown_image = face_recognition.load_image_file(img_file_buffer)
        
        # ফেস এনকোডিং বের করা
        unknown_encodings = face_recognition.face_encodings(unknown_image)

        if len(unknown_encodings) > 0:
            match = face_recognition.compare_faces([known_encoding], unknown_encodings[0])

            if match[0]:
                st.success("✅ ফেস ম্যাচ করেছে! আপনার উপস্থিতি রেকর্ড করা হচ্ছে...")
                
                # গুগল শিটে ডাটা পাঠানো
                now = datetime.datetime.now()
                date_str = now.strftime("%Y-%m-%d")
                time_str = now.strftime("%H:%M:%S")
                
                # Sheet-এ নতুন সারি যোগ করা: [Date, Time, Student_ID, Course, Status]
                sheet.append_row([date_str, time_str, student_id_param, course_param, "Present"])
                st.balloons()
            else:
                st.error("❌ ফেস ম্যাচ করেনি! অনুগ্রহ করে সঠিকভাবে ক্যামেরার সামনে দাঁড়ান।")
        else:
            st.warning("⚠️ কোণো ফেস সনাক্ত করা যায়নি। আবার চেষ্টা করুন।")

# ---------------------------------------------------------
# ৪. শিক্ষক/অ্যাডমিন মোড (Dashboard & Link Generator)
# ---------------------------------------------------------
else:
    st.sidebar.header("⚙️ অ্যাডমিন কন্ট্রোল")
    page = st.sidebar.radio("অপশন সিলেক্ট করুন:", ["লিঙ্ক জেনারেট করুন", "অ্যাটেনডেন্স ড্যাশবোর্ড"])

    if page == "লিঙ্ক জেনারেট করুন":
        st.subheader("🔗 স্টুডেন্টের জন্য ইউনিক অ্যাটেনডেন্স লিঙ্ক তৈরি করুন")
        
        selected_course = st.selectbox("কোর্স সিলেক্ট করুন:", ["GEO101", "ENV201", "GBC301"])
        student_id = st.text_input("স্টুডেন্ট আইডি দিন:")

        if st.button("লিঙ্ক তৈরি করুন"):
            if student_id:
                base_url = "https://geoenvgbcattendence.streamlit.app/"
                encoded_course = urllib.parse.quote(selected_course)
                generated_link = f"{base_url}?course={encoded_course}&student_id={student_id}"
                
                st.success("ইউনিক লিঙ্ক সফলভাবে তৈরি হয়েছে:")
                st.code(generated_link, language="markdown")
                st.info("এই লিঙ্কটি নির্দিষ্ট শিক্ষার্থীর কাছে পাঠান। লিঙ্কটিতে ক্লিক করলে সরাসরি ক্যামেরা অন হবে।")
            else:
                st.warning("অনুগ্রহ করে একটি স্টুডেন্ট আইডি প্রদান করুন।")

    elif page == "অ্যাটেনডেন্স ড্যাশবোর্ড":
        st.subheader("📊 লাইভ অ্যাটেনডেন্স রিপোর্ট ও পার্সেন্টেজ")

        try:
            # গুগল শিট থেকে সমস্ত ডাটা নিয়ে আসা
            data = sheet.get_all_records()
            df = pd.DataFrame(data)

            if not df.empty:
                # কোর্স ফিল্টার
                courses = df['Course'].unique() if 'Course' in df.columns else []
                selected_course_filter = st.selectbox("কোর্স অনুযায়ী রিপোর্ট দেখুন:", ["All"] + list(courses))

                if selected_course_filter != "All":
                    filtered_df = df[df['Course'] == selected_course_filter]
                else:
                    filtered_df = df.copy()

                st.write("### বিস্তারিত অ্যাটেনডেন্স লগ:")
                st.dataframe(filtered_df)

                # পার্সেন্টেজ হিসাব (ধরে নিচ্ছি মোট ক্লাস ২০ টি)
                st.write("### 📈 শিক্ষার্থীভিত্তিক উপস্থিতি (Percentage):")
                if 'Student_ID' in filtered_df.columns:
                    summary = filtered_df.groupby('Student_ID').size().reset_index(name='Total Present')
                    total_classes = st.number_input("মোট ক্লাসের সংখ্যা দিন:", min_value=1, value=10)
                    summary['Attendance (%)'] = (summary['Total Present'] / total_classes) * 100
                    
                    st.table(summary)
            else:
                st.info("এখনো কোনো অ্যাটেনডেন্স রেকর্ড জমা হয়নি।")

        except Exception as e:
            st.error("ডাটাবেজ থেকে তথ্য লোড করতে সমস্যা হচ্ছে।")
