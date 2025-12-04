import streamlit as st
import json
import sqlite3
import random
import string
import re
from datetime import datetime
import io
import docx
import PyPDF2
import google.generativeai as genai
import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ==================== CẤU HÌNH ====================
st.set_page_config(
    page_title="Quiz Lịch Sử AI",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS tùy chỉnh
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 2rem;
        padding: 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
    }
    .quiz-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        border-left: 5px solid #3B82F6;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .score-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        padding: 2rem;
        text-align: center;
        margin: 1rem 0;
    }
    .student-info-card {
        background-color: #e3f2fd;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
        border-left: 5px solid #2196F3;
    }
    .search-card {
        background-color: #f1f8e9;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
        border-left: 5px solid #8BC34A;
    }
    .stButton > button {
        width: 100%;
        background-color: #3B82F6;
        color: white;
        font-weight: bold;
        border: none;
        padding: 12px;
        border-radius: 8px;
        font-size: 1.1em;
    }
    .stButton > button:hover {
        background-color: #2563EB;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    .rank-1 { background-color: #FFD700 !important; color: black; }
    .rank-2 { background-color: #C0C0C0 !important; color: black; }
    .rank-3 { background-color: #CD7F32 !important; color: white; }
    .answer-selected {
        background-color: #d1e7ff !important;
        border: 2px solid #0d6efd !important;
    }
    .info-box {
        background-color: #fff3cd;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #ffc107;
        margin: 10px 0;
    }
    .success-box {
        background-color: #d1e7dd;
        padding: 15px;
        border-radius: 8px;
        border-left: 5px solid #198754;
        margin: 10px 0;
    }
    .badge {
        display: inline-block;
        padding: 5px 10px;
        border-radius: 20px;
        font-size: 0.9em;
        font-weight: bold;
        margin: 2px;
    }
    .badge-success { background-color: #198754; color: white; }
    .badge-warning { background-color: #ffc107; color: black; }
    .badge-danger { background-color: #dc3545; color: white; }
    .badge-info { background-color: #0dcaf0; color: white; }
</style>
""", unsafe_allow_html=True)

# ==================== DATABASE MIGRATION ====================
def migrate_database():
    """Cập nhật cấu trúc database khi có thay đổi"""
    conn = sqlite3.connect('quiz_system.db')
    c = conn.cursor()
    
    try:
        # Kiểm tra xem bảng results đã tồn tại chưa
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='results'")
        if not c.fetchone():
            # Tạo bảng mới với đầy đủ cột
            c.execute('''CREATE TABLE results
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          quiz_code TEXT,
                          student_name TEXT,
                          class_name TEXT DEFAULT '',
                          student_id TEXT DEFAULT '',
                          score INTEGER,
                          total_questions INTEGER,
                          percentage REAL DEFAULT 0,
                          grade TEXT DEFAULT '',
                          submitted_at TIMESTAMP)''')
            print("✅ Tạo bảng results mới")
        else:
            # Kiểm tra và thêm cột nếu thiếu
            c.execute("PRAGMA table_info(results)")
            columns = [col[1] for col in c.fetchall()]
            
            columns_to_add = [
                ('class_name', 'TEXT DEFAULT ""'),
                ('student_id', 'TEXT DEFAULT ""'),
                ('percentage', 'REAL DEFAULT 0'),
                ('grade', 'TEXT DEFAULT ""')
            ]
            
            for col_name, col_type in columns_to_add:
                if col_name not in columns:
                    print(f"🔄 Thêm cột {col_name}...")
                    c.execute(f"ALTER TABLE results ADD COLUMN {col_name} {col_type}")
            
            print("✅ Database migration hoàn tất!")
        
    except Exception as e:
        print(f"⚠️ Lỗi migration: {e}")
        # Nếu lỗi nặng, tạo lại bảng
        try:
            c.execute('DROP TABLE IF EXISTS results')
            c.execute('''CREATE TABLE results
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          quiz_code TEXT,
                          student_name TEXT,
                          class_name TEXT DEFAULT '',
                          student_id TEXT DEFAULT '',
                          score INTEGER,
                          total_questions INTEGER,
                          percentage REAL DEFAULT 0,
                          grade TEXT DEFAULT '',
                          submitted_at TIMESTAMP)''')
            print("🔄 Tạo lại bảng results...")
        except Exception as e2:
            print(f"❌ Lỗi nặng: {e2}")
    
    conn.commit()
    conn.close()

# ==================== KHỞI TẠO DATABASE ====================
def init_db():
    conn = sqlite3.connect('quiz_system.db')
    c = conn.cursor()
    
    # Bảng quizzes
    c.execute('''CREATE TABLE IF NOT EXISTS quizzes
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  quiz_code TEXT UNIQUE,
                  title TEXT,
                  subject TEXT DEFAULT 'Lịch Sử',
                  created_at TIMESTAMP,
                  question_count INTEGER,
                  is_active BOOLEAN DEFAULT 1)''')
    
    # Bảng questions
    c.execute('''CREATE TABLE IF NOT EXISTS questions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  quiz_id INTEGER,
                  question_text TEXT,
                  option_a TEXT,
                  option_b TEXT,
                  option_c TEXT,
                  option_d TEXT,
                  correct_answer TEXT,
                  explanation TEXT,
                  question_type TEXT DEFAULT 'multiple_choice',
                  difficulty TEXT DEFAULT 'medium',
                  FOREIGN KEY (quiz_id) REFERENCES quizzes(id))''')
    
    # Bảng students (lưu thông tin học sinh)
    c.execute('''CREATE TABLE IF NOT EXISTS students
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  student_name TEXT,
                  class_name TEXT,
                  student_id TEXT UNIQUE,
                  email TEXT,
                  phone TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    conn.close()

# Chạy migration và init
migrate_database()
init_db()

# ==================== KHỞI TẠO GEMINI AI ====================
@st.cache_resource
def init_ai_model():
    try:
        # Lấy API key từ nhiều nguồn
        api_key = None
        
        # 1. Từ Streamlit secrets
        try:
            if hasattr(st, 'secrets'):
                api_key = st.secrets.get("GEMINI_API_KEY")
        except:
            pass
        
        # 2. Từ biến môi trường
        if not api_key:
            api_key = os.environ.get("GEMINI_API_KEY")
        
        # 3. Từ key trực tiếp
        if not api_key:
            api_key = "AIzaSyAXneM58drczCgMfm-Ihx0mzxIpiy8TmvQ"
        
        if not api_key or api_key == "your_api_key_here":
            st.warning("⚠️ Chưa cấu hình Gemini API Key")
            return None
        
        # Configure với API key
        genai.configure(api_key=api_key)
        
        # DÙNG MODEL GEMMA 3-4B
        model_name = 'models/gemma-3-4b-it'
        
        print(f"🤖 Đang khởi tạo model: {model_name}")
        
        # Tạo model
        model = genai.GenerativeModel(model_name)
        
        # Test ngắn
        test_response = model.generate_content(
            "Xin chào",
            generation_config={"max_output_tokens": 5}
        )
        
        if test_response.text:
            print(f"✅ AI Model đã sẵn sàng: {model_name}")
            return model
        else:
            print("❌ Model không trả về kết quả")
            return None
            
    except Exception as e:
        print(f"❌ Lỗi khởi tạo AI Model: {str(e)[:200]}")
        return None

# Khởi tạo Gemini model
gemini_model = init_ai_model()

# ==================== HÀM HELPER ====================
def extract_text_from_file(uploaded_file):
    """Trích xuất text từ file upload"""
    file_type = uploaded_file.name.split('.')[-1].lower()
    
    try:
        if file_type == 'txt':
            return uploaded_file.read().decode('utf-8')
        
        elif file_type == 'pdf':
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(uploaded_file.read()))
            text = ""
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text
        
        elif file_type == 'docx':
            doc = docx.Document(io.BytesIO(uploaded_file.read()))
            text = ""
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text += paragraph.text + "\n"
            return text
        
    except Exception as e:
        print(f"❌ Lỗi đọc file: {e}")
        return f"[File: {uploaded_file.name}] - Lỗi đọc nội dung"

def get_sample_questions():
    """Câu hỏi mẫu khi không thể tạo bằng AI"""
    return {
        "questions": [
            {
                "question": "Chiến thắng Điện Biên Phủ diễn ra vào năm nào?",
                "options": {
                    "A": "1953",
                    "B": "1954",
                    "C": "1975",
                    "D": "1945"
                },
                "correct_answer": "B",
                "explanation": "Chiến dịch Điện Biên Phủ kết thúc thắng lợi vào ngày 7/5/1954, đánh dấu thắng lợi quyết định của quân dân Việt Nam trong kháng chiến chống Pháp."
            },
            {
                "question": "Ai là tác giả của Bản Tuyên ngôn Độc lập 2/9/1945?",
                "options": {
                    "A": "Hồ Chí Minh",
                    "B": "Trường Chinh",
                    "C": "Phạm Văn Đồng",
                    "D": "Võ Nguyên Giáp"
                },
                "correct_answer": "A",
                "explanation": "Chủ tịch Hồ Chí Minh đọc bản Tuyên ngôn Độc lập tại Quảng trường Ba Đình, Hà Nội, khai sinh nước Việt Nam Dân chủ Cộng hòa."
            },
            {
                "question": "Vua nào dựng nước Văn Lang - nhà nước đầu tiên của Việt Nam?",
                "options": {
                    "A": "An Dương Vương",
                    "B": "Vua Hùng",
                    "C": "Lý Thái Tổ",
                    "D": "Quang Trung"
                },
                "correct_answer": "B",
                "explanation": "Các Vua Hùng là những người có công dựng nước Văn Lang, đặt nền móng cho sự hình thành và phát triển của dân tộc Việt Nam."
            }
        ]
    }

def generate_quiz_questions_gemini(text, num_questions=5):
    """Tạo câu hỏi bằng Gemini API"""
    if not gemini_model:
        return None
    
    try:
        text = text[:3000]
        
        prompt = f"""Bạn là giáo viên lịch sử xuất sắc. Tạo {num_questions} câu hỏi trắc nghiệm từ tài liệu sau:

{text}

YÊU CẦU:
1. Tạo {num_questions} câu hỏi TRẮC NGHIỆM 4 lựa chọn (A, B, C, D)
2. Chỉ MỘT đáp án đúng duy nhất
3. Mỗi câu hỏi phải có giải thích ngắn gọn
4. Câu hỏi phải đa dạng: sự kiện, nhân vật, niên đại, địa điểm

ĐỊNH DẠNG JSON:
{{
  "questions": [
    {{
      "question": "Câu hỏi 1",
      "options": {{
        "A": "Đáp án A",
        "B": "Đáp án B",
        "C": "Đáp án C", 
        "D": "Đáp án D"
      }},
      "correct_answer": "A",
      "explanation": "Giải thích tại sao A đúng"
    }}
  ]
}}

Chỉ trả về JSON, không thêm bất kỳ text nào khác."""
        
        response = gemini_model.generate_content(
            prompt,
            generation_config={
                "max_output_tokens": 2000,
                "temperature": 0.7,
                "top_p": 0.8
            }
        )
        
        if not response.text:
            return None
            
        result_text = response.text.strip()
        result_text = result_text.replace('```json', '').replace('```', '').strip()
        
        # Tìm JSON trong response
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if not json_match:
            return None
            
        quiz_data = json.loads(json_match.group())
        
        if "questions" not in quiz_data:
            return None
            
        # Validate và fix dữ liệu
        valid_questions = []
        for q in quiz_data["questions"]:
            if not isinstance(q, dict):
                continue
                
            # Đảm bảo có đủ các trường
            if "question" not in q or not q["question"].strip():
                continue
                
            if "options" not in q or not isinstance(q["options"], dict):
                continue
                
            # Đảm bảo có đủ 4 đáp án
            for key in ["A", "B", "C", "D"]:
                if key not in q["options"]:
                    q["options"][key] = f"Đáp án {key}"
            
            if "correct_answer" not in q or q["correct_answer"] not in ["A", "B", "C", "D"]:
                q["correct_answer"] = "A"
            
            if "explanation" not in q:
                q["explanation"] = "Không có giải thích"
            
            valid_questions.append(q)
        
        return {"questions": valid_questions[:num_questions]}
            
    except Exception as e:
        print(f"❌ Lỗi Gemini: {e}")
        return None

def generate_quiz_questions(text, num_questions=5):
    """Tổng hợp: Thử Gemini trước, nếu không được thì dùng câu hỏi mẫu"""
    if len(text.strip()) < 50:
        sample = get_sample_questions()
        sample["questions"] = sample["questions"][:min(num_questions, len(sample["questions"]))]
        return sample
    
    gemini_result = generate_quiz_questions_gemini(text, num_questions)
    
    if gemini_result and "questions" in gemini_result and len(gemini_result["questions"]) > 0:
        print(f"✅ AI đã tạo {len(gemini_result['questions'])} câu hỏi")
        return gemini_result
    
    sample = get_sample_questions()
    sample["questions"] = sample["questions"][:min(num_questions, len(sample["questions"]))]
    return sample

def calculate_grade(percentage):
    """Tính điểm chữ"""
    if percentage >= 90:
        return "A+", "🏆 Xuất sắc!", "#FFD700"
    elif percentage >= 80:
        return "A", "🎉 Giỏi!", "#C0C0C0"
    elif percentage >= 70:
        return "B", "👍 Khá!", "#CD7F32"
    elif percentage >= 60:
        return "C", "📚 Trung bình khá", "#4CAF50"
    elif percentage >= 50:
        return "D", "💪 Trung bình", "#FF9800"
    else:
        return "F", "🔄 Cần cố gắng hơn", "#F44336"

def register_student(student_name, class_name, student_id="", email="", phone=""):
    """Đăng ký thông tin học sinh"""
    conn = sqlite3.connect('quiz_system.db')
    c = conn.cursor()
    
    try:
        c.execute('''INSERT OR REPLACE INTO students 
                     (student_name, class_name, student_id, email, phone, created_at)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                 (student_name, class_name, student_id, email, phone, datetime.now()))
        conn.commit()
        student_db_id = c.lastrowid
        conn.close()
        return student_db_id
    except Exception as e:
        print(f"❌ Lỗi đăng ký học sinh: {e}")
        conn.close()
        return None

# ==================== GIAO DIỆN CHÍNH HOÀN CHỈNH ====================
def main():
    st.markdown('<h1 class="main-header">📚 HỆ THỐNG QUIZ LỊCH SỬ - QUẢN LÝ LỚP HỌC</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/2237/2237288.png", width=100)
        st.title("🎮 MENU CHÍNH")
        
        menu_options = [
            "🏠 TRANG CHỦ",
            "👨‍🎓 ĐĂNG KÝ HỌC SINH", 
            "📤 TẠO QUIZ MỚI",
            "🎯 THAM GIA QUIZ",
            "🔍 TRA CỨU KẾT QUẢ",
            "📊 THỐNG KÊ CHI TIẾT",
            "🏆 BẢNG XẾP HẠNG",
            "📥 XUẤT BÁO CÁO"
        ]
        
        menu = st.radio("CHỌN CHỨC NĂNG:", menu_options)
        
        st.markdown("---")
        
        # Hiển thị thông tin AI
        if gemini_model:
            st.success("**🤖 GEMINI AI:** ĐÃ KẾT NỐI")
            st.caption("Sẵn sàng tạo câu hỏi thông minh")
        else:
            st.warning("**⚠️ GEMINI AI:** CHƯA KẾT NỐI")
            st.caption("Đang dùng câu hỏi mẫu")
        
        st.markdown("---")
        
        # Thông tin nhanh
        try:
            conn = sqlite3.connect('quiz_system.db')
            c = conn.cursor()
            
            c.execute("SELECT COUNT(*) FROM quizzes")
            quiz_count = c.fetchone()[0]
            
            c.execute("SELECT COUNT(DISTINCT student_name) FROM results")
            student_count = c.fetchone()[0]
            
            c.execute("SELECT COUNT(*) FROM results")
            test_count = c.fetchone()[0]
            
            conn.close()
            
            st.info(f"""
            **📊 THỐNG KÊ NHANH:**
            - 📝 **Quiz:** {quiz_count}
            - 👨‍🎓 **Học sinh:** {student_count}
            - 📋 **Bài thi:** {test_count}
            """)
        except:
            st.info("📊 Đang khởi tạo hệ thống...")
        
        st.markdown("---")
        st.caption("© 2024 Hệ thống Quiz Lịch Sử")
    
    # ==================== TRANG CHỦ ====================
    if menu == "🏠 TRANG CHỦ":
        st.success("🎉 **CHÀO MỪNG ĐẾN VỚI HỆ THỐNG QUIZ LỊCH SỬ THÔNG MINH**")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("""
            ### ✨ **TÍNH NĂNG NỔI BẬT:**
            
            **👨‍🎓 QUẢN LÝ HỌC SINH TOÀN DIỆN:**
            - Đăng ký thông tin học sinh chi tiết
            - Quản lý theo lớp, theo mã học sinh
            - Lưu trữ lịch sử bài thi đầy đủ
            
            **📚 TẠO QUIZ THÔNG MINH:**
            - 🤖 AI tự động tạo câu hỏi từ giáo án
            - 📤 Hỗ trợ đa định dạng: TXT, PDF, DOCX
            - 🎯 Tùy chỉnh số câu hỏi, độ khó
            
            **📊 THỐNG KÊ CHI TIẾT:**
            - Báo cáo theo lớp, theo học sinh
            - Biểu đồ tiến bộ học tập
            - Xếp hạng toàn trường & theo lớp
            
            **🔍 TRA CỨU LINH HOẠT:**
            - Tìm kiếm theo tên, lớp, mã quiz
            - Lọc theo điểm số, thời gian
            - Xuất báo cáo Excel chi tiết
            
            **📱 TÍCH HỢP ĐA NỀN TẢNG:**
            - Hoạt động trên điện thoại & máy tính
            - Giao diện thân thiện, dễ sử dụng
            - Tự động lưu trữ & backup
            """)
        
        with col2:
            st.markdown("### 🚀 **BẮT ĐẦU NHANH**")
            
            # Card hướng dẫn
            st.markdown("""
            <div class="info-box">
                <h4>📋 HƯỚNG DẪN SỬ DỤNG:</h4>
                <ol>
                    <li><strong>Đăng ký học sinh</strong> (bắt buộc)</li>
                    <li><strong>Tạo quiz</strong> từ file giáo án</li>
                    <li><strong>Chia sẻ mã quiz</strong> cho học sinh</li>
                    <li><strong>Theo dõi kết quả</strong> real-time</li>
                    <li><strong>Xuất báo cáo</strong> Excel</li>
                </ol>
            </div>
            """, unsafe_allow_html=True)
            
            # Nút điều hướng nhanh
            if st.button("👨‍🎓 ĐĂNG KÝ HỌC SINH NGAY", use_container_width=True):
                st.session_state.menu = "👨‍🎓 ĐĂNG KÝ HỌC SINH"
                st.rerun()
            
            if st.button("📤 TẠO QUIZ MỚI", use_container_width=True):
                st.session_state.menu = "📤 TẠO QUIZ MỚI"
                st.rerun()
            
            if st.button("🔍 TRA CỨU KẾT QUẢ", use_container_width=True):
                st.session_state.menu = "🔍 TRA CỨU KẾT QUẢ"
                st.rerun()
        
        # Hiển thị quiz mới nhất
        st.markdown("---")
        st.subheader("📝 **QUIZ MỚI NHẤT**")
        
        try:
            conn = sqlite3.connect('quiz_system.db')
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM quizzes ORDER BY created_at DESC LIMIT 5')
            recent_quizzes = c.fetchall()
            conn.close()
            
            if recent_quizzes:
                cols = st.columns(len(recent_quizzes))
                for idx, quiz in enumerate(recent_quizzes):
                    with cols[idx]:
                        st.markdown(f"""
                        <div class="quiz-card">
                            <h4>{quiz['title'][:20]}...</h4>
                            <p><strong>Mã:</strong> {quiz['quiz_code']}</p>
                            <p><strong>Số câu:</strong> {quiz['question_count']}</p>
                            <small>{quiz['created_at'][:10]}</small>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info("📭 Chưa có quiz nào được tạo")
        except:
            st.info("📭 Đang tải dữ liệu...")
    
    # ==================== ĐĂNG KÝ HỌC SINH ====================
    elif menu == "👨‍🎓 ĐĂNG KÝ HỌC SINH":
        st.header("👨‍🎓 ĐĂNG KÝ THÔNG TIN HỌC SINH")
        
        tab1, tab2, tab3 = st.tabs(["📝 Đăng ký mới", "📋 Danh sách học sinh", "🔍 Tìm kiếm học sinh"])
        
        with tab1:
            st.markdown("### 📝 NHẬP THÔNG TIN HỌC SINH")
            
            col1, col2 = st.columns(2)
            
            with col1:
                student_name = st.text_input(
                    "**Họ và tên:**",
                    placeholder="Nguyễn Văn A",
                    help="Nhập họ tên đầy đủ của học sinh"
                )
                
                class_name = st.text_input(
                    "**Lớp:**",
                    placeholder="10A1, 11B2, 12C3...",
                    help="Nhập tên lớp theo quy định của trường"
                )
                
                student_id = st.text_input(
                    "**Mã học sinh (nếu có):**",
                    placeholder="HS001, 2024001...",
                    help="Mã số học sinh trong sổ điểm"
                )
            
            with col2:
                email = st.text_input(
                    "**Email (tùy chọn):**",
                    placeholder="student@school.edu.vn",
                    help="Email để nhận thông báo kết quả"
                )
                
                phone = st.text_input(
                    "**Số điện thoại (tùy chọn):**",
                    placeholder="0987654321",
                    help="SĐT liên hệ trong trường hợp cần"
                )
            
            if st.button("✅ ĐĂNG KÝ HỌC SINH", type="primary", use_container_width=True):
                if student_name and class_name:
                    student_db_id = register_student(student_name, class_name, student_id, email, phone)
                    
                    if student_db_id:
                        st.success(f"✅ **ĐÃ ĐĂNG KÝ THÀNH CÔNG!**")
                        
                        st.markdown(f"""
                        <div class="success-box">
                            <h4>📋 THÔNG TIN ĐÃ ĐĂNG KÝ:</h4>
                            <p><strong>👨‍🎓 Họ tên:</strong> {student_name}</p>
                            <p><strong>🏫 Lớp:</strong> {class_name}</p>
                            <p><strong>🆔 Mã HS:</strong> {student_id if student_id else 'Chưa có'}</p>
                            <p><strong>📧 Email:</strong> {email if email else 'Chưa có'}</p>
                            <p><strong>📞 SĐT:</strong> {phone if phone else 'Chưa có'}</p>
                            <p><strong>🆔 ID trong hệ thống:</strong> {student_db_id}</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Reset form
                        st.session_state.student_name = ""
                        st.session_state.class_name = ""
                        st.session_state.student_id = ""
                else:
                    st.error("❌ **VUI LÒNG NHẬP ĐẦY ĐỦ HỌ TÊN VÀ LỚP!**")
        
        with tab2:
            st.markdown("### 📋 DANH SÁCH HỌC SINH ĐÃ ĐĂNG KÝ")
            
            try:
                conn = sqlite3.connect('quiz_system.db')
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                
                # Lọc theo lớp nếu có
                c.execute("SELECT DISTINCT class_name FROM students ORDER BY class_name")
                classes = [row[0] for row in c.fetchall()]
                
                selected_class = st.selectbox("Chọn lớp để xem:", ["Tất cả"] + classes)
                
                if selected_class == "Tất cả":
                    c.execute('''
                        SELECT s.*, 
                               COUNT(r.id) as test_count,
                               AVG(r.percentage) as avg_score
                        FROM students s
                        LEFT JOIN results r ON s.student_name = r.student_name 
                            AND s.class_name = r.class_name
                        GROUP BY s.id
                        ORDER BY s.class_name, s.student_name
                    ''')
                else:
                    c.execute('''
                        SELECT s.*, 
                               COUNT(r.id) as test_count,
                               AVG(r.percentage) as avg_score
                        FROM students s
                        LEFT JOIN results r ON s.student_name = r.student_name 
                            AND s.class_name = r.class_name
                        WHERE s.class_name = ?
                        GROUP BY s.id
                        ORDER BY s.student_name
                    ''', (selected_class,))
                
                students = c.fetchall()
                conn.close()
                
                if students:
                    st.success(f"✅ Tìm thấy {len(students)} học sinh")
                    
                    # Hiển thị dạng bảng
                    student_data = []
                    for s in students:
                        student_data.append({
                            "ID": s['id'],
                            "Họ tên": s['student_name'],
                            "Lớp": s['class_name'],
                            "Mã HS": s['student_id'] or "",
                            "Số bài thi": s['test_count'] or 0,
                            "Điểm TB": f"{s['avg_score']:.1f}%" if s['avg_score'] else "Chưa có"
                        })
                    
                    df = pd.DataFrame(student_data)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    
                    # Xuất Excel
                    excel_buffer = io.BytesIO()
                    df.to_excel(excel_buffer, index=False, engine='openpyxl')
                    excel_buffer.seek(0)
                    
                    st.download_button(
                        label="📥 Tải danh sách Excel",
                        data=excel_buffer,
                        file_name=f"danh_sach_hoc_sinh_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.info("📭 Chưa có học sinh nào đăng ký")
                    
            except Exception as e:
                st.error(f"❌ Lỗi: {str(e)}")
    
    # ==================== TẠO QUIZ MỚI ====================
    elif menu == "📤 TẠO QUIZ MỚI":
        st.header("📤 TẠO QUIZ MỚI TỪ GIÁO ÁN")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            uploaded_file = st.file_uploader(
                "**📁 CHỌN FILE GIÁO ÁN:**",
                type=['txt', 'pdf', 'docx'],
                help="Tải lên file giáo án lịch sử (TXT, PDF hoặc DOCX)"
            )
            
            if uploaded_file:
                with st.expander("👁️ **XEM TRƯỚC NỘI DUNG**", expanded=False):
                    text = extract_text_from_file(uploaded_file)
                    if len(text) > 1000:
                        st.text_area("Nội dung", text[:1000] + "...", height=200, disabled=True)
                    else:
                        st.text_area("Nội dung", text, height=200, disabled=True)
        
        with col2:
            num_questions = st.slider(
                "**SỐ CÂU HỎI:**",
                min_value=3,
                max_value=20,
                value=10,
                help="Chọn số lượng câu hỏi muốn tạo"
            )
            
            quiz_title = st.text_input(
                "**TIÊU ĐỀ QUIZ:**",
                value="Kiểm tra Lịch Sử",
                help="Đặt tên cho quiz của bạn"
            )
            
            subject = st.selectbox(
                "**MÔN HỌC:**",
                ["Lịch Sử", "Địa Lý", "Giáo Dục Công Dân", "Toán", "Ngữ Văn", "Tiếng Anh", "Vật Lý", "Hóa Học", "Sinh Học", "Khác"]
            )
            
            difficulty = st.select_slider(
                "**ĐỘ KHÓ:**",
                options=["Dễ", "Trung bình", "Khó"],
                value="Trung bình"
            )
        
        if uploaded_file and st.button("🚀 TẠO QUIZ BẰNG AI", type="primary", use_container_width=True):
            with st.spinner("🤖 **AI ĐANG TẠO CÂU HỎI...**" if gemini_model else "📝 **ĐANG TẠO QUIZ...**"):
                text = extract_text_from_file(uploaded_file)
                
                if len(text) < 100:
                    st.error("❌ **FILE QUÁ NGẮN!** Vui lòng upload file có nội dung đầy đủ (ít nhất 100 ký tự).")
                else:
                    quiz_data = generate_quiz_questions(text, num_questions)
                    
                    # Tạo mã quiz ngẫu nhiên
                    quiz_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
                    
                    # Lưu vào database
                    conn = sqlite3.connect('quiz_system.db')
                    c = conn.cursor()
                    
                    # Lưu thông tin quiz
                    c.execute('''INSERT INTO quizzes (quiz_code, title, subject, created_at, question_count) 
                                 VALUES (?, ?, ?, ?, ?)''',
                             (quiz_code, f"{subject} - {quiz_title}", subject, datetime.now(), len(quiz_data['questions'])))
                    quiz_id = c.lastrowid
                    
                    # Lưu các câu hỏi
                    for q in quiz_data['questions']:
                        c.execute('''INSERT INTO questions 
                                     (quiz_id, question_text, option_a, option_b, option_c, option_d, 
                                      correct_answer, explanation, difficulty)
                                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                 (quiz_id, 
                                  q['question'],
                                  q['options']['A'],
                                  q['options']['B'],
                                  q['options']['C'],
                                  q['options']['D'],
                                  q['correct_answer'],
                                  q.get('explanation', 'Không có giải thích'),
                                  difficulty))
                    
                    conn.commit()
                    conn.close()
                    
                    # Hiển thị kết quả
                    st.success("🎉 **QUIZ ĐÃ ĐƯỢC TẠO THÀNH CÔNG!**")
                    
                    col_code, col_info = st.columns(2)
                    with col_code:
                        st.markdown(f"""
                        <div class="student-info-card">
                            <h3>📋 THÔNG TIN QUIZ</h3>
                            <p><strong>🏷️ Tiêu đề:</strong> {quiz_title}</p>
                            <p><strong>📚 Môn học:</strong> {subject}</p>
                            <p><strong>📊 Độ khó:</strong> {difficulty}</p>
                            <p><strong>🔢 Số câu:</strong> {len(quiz_data['questions'])}</p>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col_info:
                        st.markdown(f"""
                        <div class="student-info-card">
                            <h3>🎯 MÃ QUIZ</h3>
                            <h1 style="text-align: center; color: #3B82F6;">{quiz_code}</h1>
                            <p style="text-align: center; font-size: 0.9em;">Chia sẻ mã này cho học sinh</p>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Hiển thị mã quiz lớn để copy
                    st.code(quiz_code, language="text")
                    
                    # Nút copy
                    if st.button("📋 Sao chép mã quiz"):
                        st.info(f"✅ Đã sao chép mã: {quiz_code}")
                    
                    # Xem trước câu hỏi
                    with st.expander("📝 **XEM TRƯỚC CÂU HỎI**", expanded=False):
                        for i, q in enumerate(quiz_data['questions']):
                            st.markdown(f"### ❓ **Câu {i+1}:** {q['question']}")
                            
                            cols = st.columns(2)
                            with cols[0]:
                                st.markdown(f"**A.** {q['options']['A']}")
                                st.markdown(f"**B.** {q['options']['B']}")
                            with cols[1]:
                                st.markdown(f"**C.** {q['options']['C']}")
                                st.markdown(f"**D.** {q['options']['D']}")
                            
                            st.markdown(f"✅ **Đáp án đúng:** {q['correct_answer']}")
                            st.markdown(f"💡 **Giải thích:** {q.get('explanation', 'Không có giải thích')}")
                            st.markdown("---")
    
    # ==================== THAM GIA QUIZ ====================
    elif menu == "🎯 THAM GIA QUIZ":
        st.header("🎯 THAM GIA LÀM BÀI QUIZ")
        
        tab1, tab2 = st.tabs(["📝 Làm bài mới", "📋 Xem lại bài đã làm"])
        
        with tab1:
            st.markdown("### 📋 NHẬP MÃ QUIZ")
            
            quiz_code = st.text_input(
                "**Nhập mã Quiz nhận từ giáo viên:**",
                placeholder="VD: ABC123XYZ",
                help="Nhập mã 8 ký tự mà giáo viên đã cung cấp",
                key="take_quiz_code"
            ).strip().upper()
            
            if quiz_code:
                conn = sqlite3.connect('quiz_system.db')
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                
                c.execute('SELECT * FROM quizzes WHERE quiz_code = ? AND is_active = 1', (quiz_code,))
                quiz = c.fetchone()
                
                if not quiz:
                    st.error("❌ **MÃ QUIZ KHÔNG TỒN TẠI HOẶC ĐÃ BỊ KHÓA!**")
                else:
                    st.success(f"✅ **ĐÃ TÌM THẤY QUIZ:** {quiz['title']}")
                    
                    # Lấy câu hỏi
                    c.execute('SELECT * FROM questions WHERE quiz_id = ? ORDER BY id', (quiz['id'],))
                    questions = c.fetchall()
                    conn.close()
                    
                    if not questions:
                        st.error("❌ **QUIZ NÀY CHƯA CÓ CÂU HỎI!**")
                    else:
                        # THÔNG TIN HỌC SINH
                        st.markdown("### 👨‍🎓 **THÔNG TIN HỌC SINH**")
                        
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            student_name = st.text_input(
                                "**Họ và tên:**",
                                placeholder="Nguyễn Văn A",
                                help="Nhập họ tên đầy đủ",
                                key="take_student_name"
                            )
                        
                        with col2:
                            class_name = st.text_input(
                                "**Lớp:**",
                                placeholder="10A1",
                                help="Nhập tên lớp",
                                key="take_class_name"
                            )
                        
                        with col3:
                            student_id = st.text_input(
                                "**Mã học sinh:**",
                                placeholder="HS001",
                                help="Mã số học sinh (nếu có)",
                                key="take_student_id"
                            )
                        
                        if student_name and class_name:
                            st.markdown(f"""
                            <div class="student-info-card">
                                <h4>📋 THÔNG TIN BÀI THI</h4>
                                <p><strong>👨‍🎓 Học sinh:</strong> {student_name}</p>
                                <p><strong>🏫 Lớp:</strong> {class_name}</p>
                                <p><strong>📝 Mã Quiz:</strong> {quiz_code}</p>
                                <p><strong>🔢 Số câu:</strong> {len(questions)}</p>
                                <p><strong>⏱️ Thời gian bắt đầu:</strong> {datetime.now().strftime('%H:%M %d/%m/%Y')}</p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            st.markdown("---")
                            st.subheader("📝 **BẮT ĐẦU LÀM BÀI**")
                            
                            # Lưu câu trả lời trong session state
                            if 'quiz_answers' not in st.session_state:
                                st.session_state.quiz_answers = {}
                            
                            answers = st.session_state.quiz_answers
                            
                            for i, q in enumerate(questions):
                                st.markdown(f"### **Câu {i+1}:** {q['question_text']}")
                                
                                # Hiển thị các lựa chọn
                                options = [
                                    ("A", q['option_a']),
                                    ("B", q['option_b']),
                                    ("C", q['option_c']),
                                    ("D", q['option_d'])
                                ]
                                
                                selected = answers.get(str(q['id']))
                                
                                # Tạo các nút lựa chọn
                                cols = st.columns(4)
                                for idx, (opt_key, opt_text) in enumerate(options):
                                    with cols[idx]:
                                        if st.button(
                                            f"{opt_key}: {opt_text[:30]}..." if len(opt_text) > 30 else f"{opt_key}: {opt_text}",
                                            key=f"opt_{q['id']}_{opt_key}",
                                            type="primary" if selected == opt_key else "secondary",
                                            use_container_width=True
                                        ):
                                            answers[str(q['id'])] = opt_key
                                            st.rerun()
                                
                                # Hiển thị đã chọn
                                if selected:
                                    option_texts = {
                                        'A': q['option_a'],
                                        'B': q['option_b'],
                                        'C': q['option_c'],
                                        'D': q['option_d']
                                    }
                                    st.info(f"✅ **Bạn đã chọn:** **{selected}** - {option_texts[selected]}")
                                
                                st.markdown("---")
                            
                            # Nút nộp bài
                            if st.button("📤 **NỘP BÀI THI**", type="primary", use_container_width=True):
                                if len(answers) < len(questions):
                                    st.warning(f"⚠️ **BẠN MỚI TRẢ LỜI {len(answers)}/{len(questions)} CÂU!** Vẫn nộp bài?")
                                
                                # Tính điểm
                                score = 0
                                details = []
                                
                                for q in questions:
                                    question_id = str(q['id'])
                                    user_answer = answers.get(question_id, '').upper()
                                    is_correct = (user_answer == q['correct_answer'])
                                    
                                    if is_correct:
                                        score += 1
                                    
                                    details.append({
                                        'question': q['question_text'],
                                        'user_answer': user_answer if user_answer else 'Không trả lời',
                                        'correct_answer': q['correct_answer'],
                                        'is_correct': is_correct,
                                        'explanation': q['explanation']
                                    })
                                
                                # Tính phần trăm và xếp loại
                                percentage = (score / len(questions)) * 100
                                grade, evaluation, grade_color = calculate_grade(percentage)
                                
                                # Lưu kết quả
                                conn = sqlite3.connect('quiz_system.db')
                                c = conn.cursor()
                                c.execute('''INSERT INTO results 
                                             (quiz_code, student_name, class_name, student_id, 
                                              score, total_questions, percentage, grade, submitted_at)
                                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                         (quiz_code, student_name, class_name, student_id,
                                          score, len(questions), percentage, grade, datetime.now()))
                                conn.commit()
                                
                                # Lấy ID kết quả vừa lưu
                                result_id = c.lastrowid
                                conn.close()
                                
                                # Hiển thị kết quả
                                st.markdown(f"""
                                <div class="score-card">
                                    <h1>{evaluation.split()[-1]}</h1>
                                    <h2>{evaluation}</h2>
                                    <h3>Điểm: {score}/{len(questions)}</h3>
                                    <p>Tỉ lệ: {percentage:.1f}% | Xếp loại: <span style="color: {grade_color}">{grade}</span></p>
                                    <p><small>Mã bài thi: {result_id}</small></p>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                # Thông tin lưu trữ
                                st.markdown(f"""
                                <div class="success-box">
                                    <h4>✅ ĐÃ LƯU KẾT QUẢ</h4>
                                    <p><strong>🆔 Mã bài thi:</strong> {result_id} (Ghi nhớ để tra cứu sau)</p>
                                    <p><strong>📋 Mã Quiz:</strong> {quiz_code}</p>
                                    <p><strong>👨‍🎓 Học sinh:</strong> {student_name}</p>
                                    <p><strong>🏫 Lớp:</strong> {class_name}</p>
                                    <p><strong>📅 Thời gian:</strong> {datetime.now().strftime('%H:%M %d/%m/%Y')}</p>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                # Chi tiết từng câu
                                with st.expander("📋 **XEM CHI TIẾT TỪNG CÂU**", expanded=False):
                                    for i, detail in enumerate(details):
                                        if detail['is_correct']:
                                            st.success(f"**Câu {i+1}:** {detail['question']}")
                                            st.markdown(f"✅ **Bạn chọn:** **{detail['user_answer']}** (Đúng)")
                                        else:
                                            st.error(f"**Câu {i+1}:** {detail['question']}")
                                            st.markdown(f"❌ **Bạn chọn:** **{detail['user_answer']}**")
                                            st.markdown(f"✅ **Đáp án đúng:** **{detail['correct_answer']}**")
                                        
                                        st.markdown(f"💡 **Giải thích:** {detail['explanation']}")
                                        st.markdown("---")
                                
                                # Xóa session state
                                if 'quiz_answers' in st.session_state:
                                    del st.session_state.quiz_answers
                                
                                st.balloons()
                                st.info("💡 **LƯU Ý:** Ghi nhớ mã bài thi để tra cứu lại kết quả sau này!")
                        
                        elif quiz_code and (not student_name or not class_name):
                            st.warning("⚠️ **VUI LÒNG NHẬP ĐẦY ĐỦ HỌ TÊN VÀ LỚP TRƯỚC KHI LÀM BÀI!**")
        
        with tab2:
            st.markdown("### 🔍 **TRA CỨU BÀI ĐÃ LÀM**")
            
            search_option = st.radio(
                "Tìm kiếm theo:",
                ["Tên học sinh", "Mã bài thi", "Mã Quiz"],
                horizontal=True
            )
            
            if search_option == "Tên học sinh":
                col1, col2 = st.columns(2)
                with col1:
                    search_name = st.text_input("Nhập tên học sinh:", placeholder="Nguyễn Văn A")
                with col2:
                    search_class = st.text_input("Nhập lớp:", placeholder="10A1")
                
                if search_name:
                    conn = sqlite3.connect('quiz_system.db')
                    conn.row_factory = sqlite3.Row
                    c = conn.cursor()
                    
                    if search_class:
                        c.execute('''
                            SELECT * FROM results 
                            WHERE student_name LIKE ? AND class_name LIKE ?
                            ORDER BY submitted_at DESC
                            LIMIT 20
                        ''', (f'%{search_name}%', f'%{search_class}%'))
                    else:
                        c.execute('''
                            SELECT * FROM results 
                            WHERE student_name LIKE ?
                            ORDER BY submitted_at DESC
                            LIMIT 20
                        ''', (f'%{search_name}%',))
                    
                    results = c.fetchall()
                    conn.close()
                    
                    if results:
                        st.success(f"✅ Tìm thấy {len(results)} bài thi")
                        
                        for r in results:
                            with st.expander(f"📝 {r['student_name']} - {r['class_name']} - {r['quiz_code']} ({r['submitted_at'][:16]})"):
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("Điểm", f"{r['score']}/{r['total_questions']}")
                                with col2:
                                    st.metric("Tỉ lệ", f"{r['percentage']:.1f}%")
                                with col3:
                                    grade_color = {
                                        'A+': '#FFD700', 'A': '#C0C0C0', 'B': '#CD7F32',
                                        'C': '#4CAF50', 'D': '#FF9800', 'F': '#F44336'
                                    }.get(r['grade'], '#000000')
                                    st.markdown(f"**Xếp loại:** <span style='color: {grade_color}'>{r['grade']}</span>", unsafe_allow_html=True)
                                
                                st.info(f"**Mã bài thi:** {r['id']} | **Mã Quiz:** {r['quiz_code']}")
                    else:
                        st.info("📭 Không tìm thấy bài thi nào")
    
    # ==================== TRA CỨU KẾT QUẢ ====================
    elif menu == "🔍 TRA CỨU KẾT QUẢ":
        st.header("🔍 TRA CỨU KẾT QUẢ CHI TIẾT")
        
        st.markdown("""
        <div class="search-card">
            <h4>🎯 TÌM KIẾM THEO NHIỀU TIÊU CHÍ</h4>
            <p>Tìm kiếm linh hoạt theo tên học sinh, lớp, mã quiz, hoặc khoảng điểm</p>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            search_type = st.selectbox(
                "Tiêu chí chính:",
                ["Tên học sinh", "Lớp", "Mã Quiz", "Khoảng điểm"]
            )
        
        with col2:
            if search_type == "Tên học sinh":
                search_value = st.text_input("Nhập tên học sinh:", placeholder="Nguyễn Văn A")
            elif search_type == "Lớp":
                search_value = st.text_input("Nhập tên lớp:", placeholder="10A1")
            elif search_type == "Mã Quiz":
                search_value = st.text_input("Nhập mã Quiz:", placeholder="ABC123XYZ").upper()
            else:  # Khoảng điểm
                min_score = st.number_input("Điểm tối thiểu (%):", 0, 100, 0)
                max_score = st.number_input("Điểm tối đa (%):", 0, 100, 100)
        
        with col3:
            date_from = st.date_input("Từ ngày:", value=None)
            date_to = st.date_input("Đến ngày:", value=None)
            show_all = st.checkbox("Hiển thị tất cả", value=False)
        
        if st.button("🔎 **TÌM KIẾM**", type="primary", use_container_width=True) or show_all:
            conn = sqlite3.connect('quiz_system.db')
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            # Xây dựng query động
            query = "SELECT * FROM results WHERE 1=1"
            params = []
            
            if not show_all:
                if search_type == "Tên học sinh" and search_value:
                    query += " AND student_name LIKE ?"
                    params.append(f'%{search_value}%')
                elif search_type == "Lớp" and search_value:
                    query += " AND class_name LIKE ?"
                    params.append(f'%{search_value}%')
                elif search_type == "Mã Quiz" and search_value:
                    query += " AND quiz_code = ?"
                    params.append(search_value)
                elif search_type == "Khoảng điểm":
                    query += " AND percentage BETWEEN ? AND ?"
                    params.extend([min_score, max_score])
                
                if date_from:
                    query += " AND DATE(submitted_at) >= ?"
                    params.append(date_from.isoformat())
                
                if date_to:
                    query += " AND DATE(submitted_at) <= ?"
                    params.append(date_to.isoformat())
            
            query += " ORDER BY submitted_at DESC LIMIT 100"
            
            c.execute(query, params)
            results = c.fetchall()
            conn.close()
            
            if results:
                st.success(f"✅ **TÌM THẤY {len(results)} KẾT QUẢ**")
                
                # Tạo DataFrame để hiển thị
                data = []
                for r in results:
                    data.append({
                        "Mã bài": r['id'],
                        "Họ tên": r['student_name'],
                        "Lớp": r['class_name'],
                        "Mã HS": r['student_id'] or "",
                        "Mã Quiz": r['quiz_code'],
                        "Điểm": f"{r['score']}/{r['total_questions']}",
                        "Tỉ lệ": f"{r['percentage']:.1f}%",
                        "Xếp loại": r['grade'],
                        "Thời gian": r['submitted_at'][:16]
                    })
                
                df = pd.DataFrame(data)
                
                # Hiển thị bảng với định dạng đẹp
                st.dataframe(
                    df,
                    use_container_width=True,
                    column_config={
                        "Tỉ lệ": st.column_config.ProgressColumn(
                            "Tỉ lệ %",
                            help="Tỉ lệ điểm đạt được",
                            format="%.1f%%",
                            min_value=0,
                            max_value=100,
                        ),
                        "Xếp loại": st.column_config.TextColumn(
                            "Xếp loại",
                            help="Điểm chữ",
                        )
                    },
                    hide_index=True
                )
                
                # Thống kê nhanh
                if len(results) > 0:
                    avg_percentage = sum(r['percentage'] for r in results) / len(results)
                    max_percentage = max(r['percentage'] for r in results)
                    min_percentage = min(r['percentage'] for r in results)
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("📊 Điểm TB", f"{avg_percentage:.1f}%")
                    with col2:
                        st.metric("🏆 Điểm cao nhất", f"{max_percentage:.1f}%")
                    with col3:
                        st.metric("📉 Điểm thấp nhất", f"{min_percentage:.1f}%")
                    with col4:
                        st.metric("📋 Số bài", len(results))
                
                # Nút xuất Excel
                excel_buffer = io.BytesIO()
                df.to_excel(excel_buffer, index=False, engine='openpyxl')
                excel_buffer.seek(0)
                
                st.download_button(
                    label="📥 **TẢI KẾT QUẢ EXCEL**",
                    data=excel_buffer,
                    file_name=f"ket_qua_tra_cuu_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            else:
                st.info("📭 **KHÔNG TÌM THẤY KẾT QUẢ NÀO PHÙ HỢP**")
    
    # ==================== THỐNG KÊ CHI TIẾT ====================
    elif menu == "📊 THỐNG KÊ CHI TIẾT":
        st.header("📊 THỐNG KÊ & PHÂN TÍCH CHI TIẾT")
        
        tab1, tab2, tab3 = st.tabs(["📈 Tổng quan", "🏫 Theo lớp", "📝 Theo Quiz"])
        
        with tab1:
            st.markdown("### 📈 **THỐNG KÊ TỔNG QUAN HỆ THỐNG**")
            
            try:
                conn = sqlite3.connect('quiz_system.db')
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                
                # Lấy dữ liệu thống kê
                c.execute("SELECT COUNT(*) as total FROM results")
                total_tests = c.fetchone()['total']
                
                c.execute("SELECT COUNT(DISTINCT student_name) as total FROM results")
                total_students = c.fetchone()['total']
                
                c.execute("SELECT COUNT(DISTINCT class_name) as total FROM results WHERE class_name != ''")
                total_classes = c.fetchone()['total']
                
                c.execute("SELECT COUNT(DISTINCT quiz_code) as total FROM results")
                total_quizzes = c.fetchone()['total']
                
                c.execute("SELECT AVG(percentage) as avg FROM results")
                avg_score = c.fetchone()['avg'] or 0
                
                # Hiển thị metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("📋 Tổng bài thi", f"{total_tests:,}")
                with col2:
                    st.metric("👨‍🎓 Tổng học sinh", f"{total_students:,}")
                with col3:
                    st.metric("🏫 Tổng lớp", f"{total_classes:,}")
                with col4:
                    st.metric("📚 Tổng Quiz", f"{total_quizzes:,}")
                
                st.metric("📊 Điểm trung bình", f"{avg_score:.1f}%", delta=f"{avg_score-50:+.1f}%")
                
                # Phân bố điểm
                st.markdown("### 📊 **PHÂN BỐ ĐIỂM SỐ**")
                c.execute('''
                    SELECT 
                        CASE 
                            WHEN percentage >= 90 THEN 'A+ (90-100%)'
                            WHEN percentage >= 80 THEN 'A (80-89%)'
                            WHEN percentage >= 70 THEN 'B (70-79%)'
                            WHEN percentage >= 60 THEN 'C (60-69%)'
                            WHEN percentage >= 50 THEN 'D (50-59%)'
                            ELSE 'F (<50%)'
                        END as grade_range,
                        COUNT(*) as count,
                        ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM results), 1) as percentage
                    FROM results 
                    GROUP BY grade_range
                    ORDER BY 
                        CASE grade_range
                            WHEN 'A+ (90-100%)' THEN 1
                            WHEN 'A (80-89%)' THEN 2
                            WHEN 'B (70-79%)' THEN 3
                            WHEN 'C (60-69%)' THEN 4
                            WHEN 'D (50-59%)' THEN 5
                            ELSE 6
                        END
                ''')
                grade_dist = c.fetchall()
                
                if grade_dist:
                    # Tạo biểu đồ
                    grade_data = pd.DataFrame(grade_dist)
                    
                    fig = px.pie(
                        grade_data, 
                        values='count', 
                        names='grade_range',
                        title='Phân bố điểm theo khoảng',
                        color_discrete_sequence=px.colors.sequential.RdBu
                    )
                    fig.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Hiển thị bảng
                    st.dataframe(grade_data, use_container_width=True, hide_index=True)
                
                # Top 10 học sinh xuất sắc
                st.markdown("### 🏆 **TOP 10 HỌC SINH XUẤT SẮC**")
                c.execute('''
                    SELECT student_name, class_name,
                           COUNT(*) as test_count,
                           ROUND(AVG(percentage), 1) as avg_score,
                           MAX(percentage) as best_score
                    FROM results 
                    GROUP BY student_name, class_name
                    HAVING COUNT(*) >= 3
                    ORDER BY avg_score DESC
                    LIMIT 10
                ''')
                top_students = c.fetchall()
                
                if top_students:
                    top_data = []
                    for i, s in enumerate(top_students):
                        top_data.append({
                            "Hạng": i+1,
                            "Họ tên": s['student_name'],
                            "Lớp": s['class_name'],
                            "Số bài": s['test_count'],
                            "Điểm TB": f"{s['avg_score']}%",
                            "Điểm cao nhất": f"{s['best_score']}%"
                        })
                    
                    df_top = pd.DataFrame(top_data)
                    st.dataframe(df_top, use_container_width=True, hide_index=True)
                
                conn.close()
                
            except Exception as e:
                st.error(f"❌ Lỗi thống kê: {str(e)}")
    
    # ==================== BẢNG XẾP HẠNG ====================
    elif menu == "🏆 BẢNG XẾP HẠNG":
        st.header("🏆 BẢNG XẾP HẠNG TOÀN TRƯỜNG")
        
        rank_type = st.radio(
            "Xếp hạng theo:",
            ["📊 Toàn trường", "🏫 Theo lớp", "📝 Theo Quiz"],
            horizontal=True
        )
        
        if rank_type == "🏫 Theo lớp":
            conn = sqlite3.connect('quiz_system.db')
            c = conn.cursor()
            c.execute("SELECT DISTINCT class_name FROM results WHERE class_name != '' ORDER BY class_name")
            classes = [row[0] for row in c.fetchall()]
            conn.close()
            
            selected_class = st.selectbox("Chọn lớp:", classes)
            
            if selected_class:
                conn = sqlite3.connect('quiz_system.db')
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute('''
                    SELECT student_name, class_name, quiz_code, 
                           score, total_questions, percentage, grade, submitted_at
                    FROM results 
                    WHERE class_name = ? 
                    ORDER BY percentage DESC, submitted_at 
                    LIMIT 20
                ''', (selected_class,))
                rankings = c.fetchall()
                conn.close()
                
                if rankings:
                    st.success(f"🏫 **BẢNG XẾP HẠNG LỚP {selected_class}**")
                    
                    for i, r in enumerate(rankings):
                        if i == 0:
                            medal = "🥇"
                            rank_class = "rank-1"
                        elif i == 1:
                            medal = "🥈"
                            rank_class = "rank-2"
                        elif i == 2:
                            medal = "🥉"
                            rank_class = "rank-3"
                        else:
                            medal = f"#{i+1}"
                            rank_class = ""
                        
                        st.markdown(f"""
                        <div class="quiz-card {rank_class}" style="margin: 10px 0;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <h4 style="margin: 0;">{medal} {r['student_name']}</h4>
                                    <p style="margin: 5px 0 0 0; font-size: 0.9em;">
                                        {r['class_name']} | Quiz: {r['quiz_code']}
                                    </p>
                                </div>
                                <div style="text-align: right;">
                                    <h3 style="margin: 0; color: #3B82F6;">{r['percentage']:.1f}%</h3>
                                    <p style="margin: 5px 0 0 0; font-size: 0.9em;">
                                        {r['score']}/{r['total_questions']} | {r['grade']}
                                    </p>
                                </div>
                            </div>
                            <p style="margin: 10px 0 0 0; font-size: 0.8em; color: #666;">
                                📅 {r['submitted_at'][:16]}
                            </p>
                        </div>
                        """, unsafe_allow_html=True)
        
        elif rank_type == "📝 Theo Quiz":
            conn = sqlite3.connect('quiz_system.db')
            c = conn.cursor()
            c.execute("SELECT DISTINCT quiz_code FROM results ORDER BY quiz_code")
            quizzes = [row[0] for row in c.fetchall()]
            conn.close()
            
            selected_quiz = st.selectbox("Chọn mã Quiz:", quizzes)
            
            if selected_quiz:
                conn = sqlite3.connect('quiz_system.db')
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                c.execute('''
                    SELECT student_name, class_name, quiz_code, 
                           score, total_questions, percentage, grade, submitted_at
                    FROM results 
                    WHERE quiz_code = ? 
                    ORDER BY percentage DESC, submitted_at 
                    LIMIT 20
                ''', (selected_quiz,))
                rankings = c.fetchall()
                conn.close()
                
                if rankings:
                    st.success(f"📝 **BẢNG XẾP HẠNG QUIZ {selected_quiz}**")
                    
                    for i, r in enumerate(rankings):
                        if i == 0:
                            medal = "🥇"
                            rank_class = "rank-1"
                        elif i == 1:
                            medal = "🥈"
                            rank_class = "rank-2"
                        elif i == 2:
                            medal = "🥉"
                            rank_class = "rank-3"
                        else:
                            medal = f"#{i+1}"
                            rank_class = ""
                        
                        st.markdown(f"""
                        <div class="quiz-card {rank_class}" style="margin: 10px 0;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <h4 style="margin: 0;">{medal} {r['student_name']}</h4>
                                    <p style="margin: 5px 0 0 0; font-size: 0.9em;">
                                        {r['class_name']}
                                    </p>
                                </div>
                                <div style="text-align: right;">
                                    <h3 style="margin: 0; color: #3B82F6;">{r['percentage']:.1f}%</h3>
                                    <p style="margin: 5px 0 0 0; font-size: 0.9em;">
                                        {r['score']}/{r['total_questions']} | {r['grade']}
                                    </p>
                                </div>
                            </div>
                            <p style="margin: 10px 0 0 0; font-size: 0.8em; color: #666;">
                                📅 {r['submitted_at'][:16]}
                            </p>
                        </div>
                        """, unsafe_allow_html=True)
        
        else:  # Toàn trường
            conn = sqlite3.connect('quiz_system.db')
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('''
                SELECT student_name, class_name, quiz_code, 
                       score, total_questions, percentage, grade, submitted_at
                FROM results 
                ORDER BY percentage DESC, submitted_at 
                LIMIT 20
            ''')
            rankings = c.fetchall()
            conn.close()
            
            if rankings:
                st.success("🏆 **BẢNG XẾP HẠNG TOÀN TRƯỜNG (TOP 20)**")
                
                for i, r in enumerate(rankings):
                    if i == 0:
                        medal = "🥇"
                        rank_class = "rank-1"
                    elif i == 1:
                        medal = "🥈"
                        rank_class = "rank-2"
                    elif i == 2:
                        medal = "🥉"
                        rank_class = "rank-3"
                    else:
                        medal = f"#{i+1}"
                        rank_class = ""
                    
                    st.markdown(f"""
                    <div class="quiz-card {rank_class}" style="margin: 10px 0;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <h4 style="margin: 0;">{medal} {r['student_name']}</h4>
                                <p style="margin: 5px 0 0 0; font-size: 0.9em;">
                                    {r['class_name']} | Quiz: {r['quiz_code']}
                                </p>
                            </div>
                            <div style="text-align: right;">
                                <h3 style="margin: 0; color: #3B82F6;">{r['percentage']:.1f}%</h3>
                                <p style="margin: 5px 0 0 0; font-size: 0.9em;">
                                    {r['score']}/{r['total_questions']} | {r['grade']}
                                </p>
                            </div>
                        </div>
                        <p style="margin: 10px 0 0 0; font-size: 0.8em; color: #666;">
                            📅 {r['submitted_at'][:16]}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
    
    # ==================== XUẤT BÁO CÁO ====================
    elif menu == "📥 XUẤT BÁO CÁO":
        st.header("📥 XUẤT BÁO CÁO EXCEL")
        
        report_type = st.selectbox(
            "Chọn loại báo cáo:",
            [
                "📋 Toàn bộ kết quả",
                "🏫 Kết quả theo lớp",
                "📝 Kết quả theo Quiz", 
                "👨‍🎓 Kết quả học sinh",
                "📊 Thống kê tổng hợp"
            ]
        )
        
        if report_type == "🏫 Kết quả theo lớp":
            conn = sqlite3.connect('quiz_system.db')
            c = conn.cursor()
            c.execute("SELECT DISTINCT class_name FROM results WHERE class_name != '' ORDER BY class_name")
            classes = [row[0] for row in c.fetchall()]
            conn.close()
            
            if classes:
                selected_classes = st.multiselect("Chọn lớp (có thể chọn nhiều):", classes)
                
                if selected_classes and st.button("📤 **XUẤT BÁO CÁO LỚP**", use_container_width=True):
                    conn = sqlite3.connect('quiz_system.db')
                    conn.row_factory = sqlite3.Row
                    c = conn.cursor()
                    
                    # Lấy dữ liệu
                    placeholders = ','.join(['?'] * len(selected_classes))
                    c.execute(f'''
                        SELECT * FROM results 
                        WHERE class_name IN ({placeholders})
                        ORDER BY class_name, student_name, submitted_at
                    ''', selected_classes)
                    
                    results = c.fetchall()
                    conn.close()
                    
                    if results:
                        # Chuẩn bị dữ liệu
                        data = []
                        for r in results:
                            data.append({
                                "Mã bài": r['id'],
                                "Họ tên": r['student_name'],
                                "Lớp": r['class_name'],
                                "Mã HS": r['student_id'] or "",
                                "Mã Quiz": r['quiz_code'],
                                "Điểm": r['score'],
                                "Tổng câu": r['total_questions'],
                                "Tỉ lệ %": r['percentage'],
                                "Xếp loại": r['grade'],
                                "Thời gian": r['submitted_at']
                            })
                        
                        df = pd.DataFrame(data)
                        
                        # Tạo Excel với nhiều sheet
                        excel_buffer = io.BytesIO()
                        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                            # Sheet chi tiết
                            df.to_excel(writer, index=False, sheet_name='Chi tiết')
                            
                            # Sheet thống kê
                            stats_data = []
                            for class_name in selected_classes:
                                class_df = df[df['Lớp'] == class_name]
                                if not class_df.empty:
                                    stats_data.append({
                                        "Lớp": class_name,
                                        "Số bài thi": len(class_df),
                                        "Số học sinh": class_df['Họ tên'].nunique(),
                                        "Điểm TB": f"{class_df['Tỉ lệ %'].mean():.1f}%",
                                        "Điểm cao nhất": f"{class_df['Tỉ lệ %'].max():.1f}%",
                                        "Điểm thấp nhất": f"{class_df['Tỉ lệ %'].min():.1f}%"
                                    })
                            
                            if stats_data:
                                pd.DataFrame(stats_data).to_excel(writer, index=False, sheet_name='Thống kê')
                        
                        excel_buffer.seek(0)
                        
                        st.success(f"✅ **ĐÃ XUẤT {len(results)} KẾT QUẢ CỦA {len(selected_classes)} LỚP**")
                        
                        # Nút download
                        st.download_button(
                            label="📥 **TẢI FILE EXCEL**",
                            data=excel_buffer,
                            file_name=f"bao_cao_lop_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
        
        elif st.button("📤 **XUẤT TOÀN BỘ KẾT QUẢ**", use_container_width=True):
            conn = sqlite3.connect('quiz_system.db')
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM results ORDER BY submitted_at DESC')
            results = c.fetchall()
            conn.close()
            
            if results:
                # Chuẩn bị dữ liệu
                data = []
                for r in results:
                    data.append({
                        "Mã bài": r['id'],
                        "Họ tên": r['student_name'],
                        "Lớp": r['class_name'],
                        "Mã HS": r['student_id'] or "",
                        "Mã Quiz": r['quiz_code'],
                        "Điểm": r['score'],
                        "Tổng câu": r['total_questions'],
                        "Tỉ lệ %": r['percentage'],
                        "Xếp loại": r['grade'],
                        "Thời gian": r['submitted_at']
                    })
                
                df = pd.DataFrame(data)
                excel_buffer = io.BytesIO()
                df.to_excel(excel_buffer, index=False, engine='openpyxl')
                excel_buffer.seek(0)
                
                st.success(f"✅ **ĐÃ XUẤT {len(results)} KẾT QUẢ**")
                
                st.download_button(
                    label="📥 **TẢI FILE EXCEL**",
                    data=excel_buffer,
                    file_name=f"toan_bo_ket_qua_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

if __name__ == "__main__":
    main()
