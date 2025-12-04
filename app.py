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
    .stButton > button {
        width: 100%;
        background-color: #3B82F6;
        color: white;
        font-weight: bold;
        border: none;
        padding: 10px;
        border-radius: 5px;
    }
    .stButton > button:hover {
        background-color: #2563EB;
        color: white;
    }
    .student-info {
        background-color: #e3f2fd;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
        border-left: 5px solid #2196F3;
    }
    .search-box {
        background-color: #f1f8e9;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
        border-left: 5px solid #8BC34A;
    }
</style>
""", unsafe_allow_html=True)

# ==================== DATABASE MIGRATION ====================
def migrate_database():
    """Cập nhật cấu trúc database khi có thay đổi"""
    conn = sqlite3.connect('quiz_system.db')
    c = conn.cursor()
    
    try:
        # Kiểm tra xem cột class_name đã tồn tại chưa
        c.execute("PRAGMA table_info(results)")
        columns = [col[1] for col in c.fetchall()]
        
        # Thêm các cột mới nếu chưa có
        if 'class_name' not in columns:
            print("🔄 Thêm cột class_name vào bảng results...")
            c.execute("ALTER TABLE results ADD COLUMN class_name TEXT DEFAULT ''")
        
        if 'student_id' not in columns:
            print("🔄 Thêm cột student_id vào bảng results...")
            c.execute("ALTER TABLE results ADD COLUMN student_id TEXT DEFAULT ''")
        
        if 'percentage' not in columns:
            print("🔄 Thêm cột percentage vào bảng results...")
            c.execute("ALTER TABLE results ADD COLUMN percentage REAL DEFAULT 0")
        
        if 'grade' not in columns:
            print("🔄 Thêm cột grade vào bảng results...")
            c.execute("ALTER TABLE results ADD COLUMN grade TEXT DEFAULT ''")
        
        print("✅ Database migration completed!")
        
    except Exception as e:
        print(f"⚠️ Lỗi migration database: {e}")
        # Nếu lỗi, tạo bảng mới
        try:
            c.execute('DROP TABLE IF EXISTS results')
            print("🔄 Tạo lại bảng results...")
        except:
            pass
    
    conn.commit()
    conn.close()

# ==================== KHỞI TẠO DATABASE ====================
def init_db():
    conn = sqlite3.connect('quiz_system.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS quizzes
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  quiz_code TEXT UNIQUE,
                  title TEXT,
                  created_at TIMESTAMP,
                  question_count INTEGER,
                  is_active BOOLEAN DEFAULT 1)''')
    
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
                  FOREIGN KEY (quiz_id) REFERENCES quizzes(id))''')
    
    # Tạo bảng results với đầy đủ cột mới
    c.execute('''CREATE TABLE IF NOT EXISTS results
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
    
    conn.commit()
    conn.close()

# Chạy migration trước
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
        
        # 3. Từ key trực tiếp (CHO TEST)
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
        error_msg = str(e)
        print(f"❌ Lỗi khởi tạo AI Model: {error_msg[:200]}")
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
            }
        ]
    }

def generate_quiz_questions_gemini(text, num_questions=5):
    """Tạo câu hỏi bằng Gemini API"""
    if not gemini_model:
        return None
    
    try:
        text = text[:3000]
        
        prompt = f"""Tạo {num_questions} câu hỏi trắc nghiệm lịch sử từ tài liệu:
{text}

Trả về JSON:
{{
  "questions": [
    {{
      "question": "...",
      "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
      "correct_answer": "A",
      "explanation": "..."
    }}
  ]
}}"""
        
        response = gemini_model.generate_content(
            prompt,
            generation_config={"max_output_tokens": 2000, "temperature": 0.7}
        )
        
        if not response.text:
            return None
            
        result_text = response.text.strip()
        result_text = result_text.replace('```json', '').replace('```', '').strip()
        
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if not json_match:
            return None
            
        quiz_data = json.loads(json_match.group())
        
        if "questions" not in quiz_data:
            return None
            
        return {"questions": quiz_data["questions"][:num_questions]}
            
    except:
        return None

def generate_quiz_questions(text, num_questions=5):
    """Tổng hợp: Thử Gemini trước, nếu không được thì dùng câu hỏi mẫu"""
    if len(text.strip()) < 50:
        sample = get_sample_questions()
        sample["questions"] = sample["questions"][:num_questions]
        return sample
    
    gemini_result = generate_quiz_questions_gemini(text, num_questions)
    
    if gemini_result and "questions" in gemini_result and len(gemini_result["questions"]) > 0:
        return gemini_result
    
    sample = get_sample_questions()
    sample["questions"] = sample["questions"][:num_questions]
    return sample

def calculate_grade(percentage):
    """Tính điểm chữ"""
    if percentage >= 90:
        return "A+", "🏆 Xuất sắc"
    elif percentage >= 80:
        return "A", "🎉 Giỏi"
    elif percentage >= 70:
        return "B", "👍 Khá"
    elif percentage >= 60:
        return "C", "📚 Trung bình khá"
    elif percentage >= 50:
        return "D", "💪 Trung bình"
    else:
        return "F", "🔄 Cần cố gắng"

# ==================== GIAO DIỆN CHÍNH (SỬA LỖI) ====================
def main():
    st.markdown('<h1 class="main-header">📚 Quiz Lịch Sử - Quản lý Lớp học</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/2237/2237288.png", width=100)
        st.title("🎮 Menu")
        
        menu = st.radio(
            "Chọn chức năng:",
            ["🏠 Trang chủ", "📤 Tạo Quiz mới", "🎯 Tham gia Quiz", "📊 Thống kê & Tra cứu"]
        )
        
        st.markdown("---")
        
        if gemini_model:
            st.success("✅ Gemma AI: ĐÃ KẾT NỐI")
        else:
            st.warning("⚠️ Gemma AI: CHƯA KẾT NỐI")
        
        st.markdown("---")
        st.info("""
        **Hướng dẫn:**
        1. Tạo quiz từ giáo án
        2. Học sinh tham gia (cần tên & lớp)
        3. Tra cứu kết quả theo tên/mã quiz
        4. Xuất báo cáo Excel
        """)
    
    # Trang chủ - SỬA LỖI QUERY
    if menu == "🏠 Trang chủ":
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.success("🎉 Chào mừng đến với Hệ thống Quiz Lịch Sử!")
            
            st.markdown("""
            ### ✨ Tính năng mới:
            
            - 👨‍🎓 **Thông tin học sinh đầy đủ**: Tên, lớp, mã học sinh
            - 🔍 **Tra cứu đa chiều**: Theo tên, lớp, mã quiz, điểm số
            - 📊 **Thống kê chi tiết**: Báo cáo theo lớp, theo quiz
            - 📥 **Xuất Excel**: Tải kết quả về máy
            - 📱 **Mobile-friendly**: Hoạt động trên điện thoại
            """)
        
        with col2:
            st.markdown("### 📈 Thống kê nhanh")
            
            conn = sqlite3.connect('quiz_system.db')
            
            try:
                # Tổng quiz - SỬA: dùng try-except
                c = conn.cursor()
                c.execute('SELECT COUNT(*) FROM quizzes')
                total_quizzes = c.fetchone()[0]
                
                # Tổng học sinh - SỬA: kiểm tra cột tồn tại
                try:
                    c.execute('SELECT COUNT(DISTINCT student_name) FROM results')
                    total_students = c.fetchone()[0]
                except:
                    total_students = 0
                
                # Tổng bài thi
                try:
                    c.execute('SELECT COUNT(*) FROM results')
                    total_tests = c.fetchone()[0]
                except:
                    total_tests = 0
                
                # Tổng lớp học - SỬA: kiểm tra cột class_name
                try:
                    c.execute("SELECT COUNT(DISTINCT class_name) FROM results WHERE class_name IS NOT NULL AND class_name != ''")
                    result = c.fetchone()
                    total_classes = result[0] if result else 0
                except:
                    total_classes = 0
                
                conn.close()
                
                st.metric("📝 Tổng Quiz", total_quizzes)
                st.metric("👨‍🎓 Tổng Học sinh", total_students)
                st.metric("📊 Tổng Bài thi", total_tests)
                st.metric("🏫 Tổng Lớp", total_classes)
                
            except Exception as e:
                st.error(f"Lỗi load thống kê: {str(e)}")
                conn.close()
    
    # Tạo Quiz mới
    elif menu == "📤 Tạo Quiz mới":
        st.header("📤 Tạo Quiz mới từ giáo án")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            uploaded_file = st.file_uploader(
                "📁 Chọn file giáo án (.txt, .pdf, .docx)",
                type=['txt', 'pdf', 'docx']
            )
            
            if uploaded_file:
                with st.expander("👁️ Xem trước nội dung"):
                    text = extract_text_from_file(uploaded_file)
                    if len(text) > 500:
                        st.text_area("Nội dung", text[:500] + "...", height=150)
                    else:
                        st.text_area("Nội dung", text, height=150)
        
        with col2:
            num_questions = st.slider(
                "Số câu hỏi",
                min_value=3,
                max_value=20,
                value=5
            )
            
            quiz_title = st.text_input(
                "Tiêu đề quiz",
                value="Quiz Lịch Sử"
            )
            
            subject = st.selectbox(
                "Môn học",
                ["Lịch Sử", "Địa Lý", "Giáo Dục Công Dân", "Khác"]
            )
        
        if uploaded_file and st.button("🚀 Tạo Quiz", type="primary", use_container_width=True):
            with st.spinner("🤖 AI đang tạo câu hỏi..." if gemini_model else "📝 Đang tạo quiz..."):
                text = extract_text_from_file(uploaded_file)
                
                if len(text) < 50:
                    st.error("❌ File quá ngắn!")
                else:
                    quiz_data = generate_quiz_questions(text, num_questions)
                    
                    # Tạo mã quiz
                    quiz_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                    
                    # Lưu vào database
                    conn = sqlite3.connect('quiz_system.db')
                    c = conn.cursor()
                    
                    c.execute('''INSERT INTO quizzes (quiz_code, title, created_at, question_count) 
                                 VALUES (?, ?, ?, ?)''',
                             (quiz_code, f"{subject} - {quiz_title}", datetime.now(), len(quiz_data['questions'])))
                    quiz_id = c.lastrowid
                    
                    for q in quiz_data['questions']:
                        c.execute('''INSERT INTO questions 
                                     (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_answer, explanation)
                                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                                 (quiz_id, 
                                  q['question'],
                                  q['options']['A'],
                                  q['options']['B'],
                                  q['options']['C'],
                                  q['options']['D'],
                                  q['correct_answer'],
                                  q.get('explanation', 'Không có giải thích')))
                    
                    conn.commit()
                    conn.close()
                    
                    st.success("✅ Đã tạo quiz thành công!")
                    
                    col_code, col_count = st.columns(2)
                    with col_code:
                        st.info(f"**Mã Quiz:** `{quiz_code}`")
                        st.code(quiz_code)
                    with col_count:
                        st.info(f"**Số câu:** {len(quiz_data['questions'])}")
                        st.info(f"**Môn:** {subject}")
                    
                    if gemini_model:
                        st.success("🤖 Đã sử dụng AI để tạo câu hỏi")
                    else:
                        st.info("📝 Đã sử dụng câu hỏi mẫu")
    
    # Tham gia Quiz
    elif menu == "🎯 Tham gia Quiz":
        st.header("🎯 Tham gia làm Quiz")
        
        quiz_code = st.text_input(
            "Nhập mã Quiz:",
            placeholder="VD: ABC123",
            key="quiz_code_input"
        ).strip().upper()
        
        if quiz_code:
            conn = sqlite3.connect('quiz_system.db')
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            c.execute('SELECT * FROM quizzes WHERE quiz_code = ? AND is_active = 1', (quiz_code,))
            quiz = c.fetchone()
            
            if not quiz:
                st.error("❌ Mã Quiz không tồn tại hoặc đã bị khóa!")
            else:
                st.success(f"✅ Tìm thấy Quiz: **{quiz['title']}**")
                
                # Lấy câu hỏi
                c.execute('SELECT * FROM questions WHERE quiz_id = ? ORDER BY id', (quiz['id'],))
                questions = c.fetchall()
                conn.close()
                
                if not questions:
                    st.error("Quiz chưa có câu hỏi!")
                else:
                    # THÔNG TIN HỌC SINH
                    st.markdown("### 👨‍🎓 Thông tin học sinh")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        student_name = st.text_input(
                            "Họ và tên:",
                            placeholder="Nguyễn Văn A",
                            help="Nhập họ tên đầy đủ",
                            key="student_name"
                        )
                    
                    with col2:
                        class_name = st.text_input(
                            "Lớp:",
                            placeholder="10A1, 11B2,...",
                            help="Nhập tên lớp",
                            key="class_name"
                        )
                    
                    with col3:
                        student_id = st.text_input(
                            "Mã học sinh (tùy chọn):",
                            placeholder="HS001",
                            help="Mã số học sinh nếu có",
                            key="student_id"
                        )
                    
                    if student_name and class_name:
                        st.markdown(f"""
                        <div class="student-info">
                            <strong>👨‍🎓 Học sinh:</strong> {student_name}<br>
                            <strong>🏫 Lớp:</strong> {class_name}<br>
                            <strong>📋 Mã Quiz:</strong> {quiz_code}<br>
                            <strong>📝 Số câu:</strong> {len(questions)}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        st.markdown("---")
                        st.subheader(f"📝 Bài thi: {quiz['title']}")
                        
                        # Lưu câu trả lời
                        if 'answers' not in st.session_state:
                            st.session_state.answers = {}
                        
                        answers = st.session_state.answers
                        
                        for i, q in enumerate(questions):
                            st.markdown(f"**Câu {i+1}:** {q['question_text']}")
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                if st.button(f"A: {q['option_a']}", key=f"new_q{i}_A", use_container_width=True):
                                    answers[str(q['id'])] = "A"
                                    st.rerun()
                                if st.button(f"B: {q['option_b']}", key=f"new_q{i}_B", use_container_width=True):
                                    answers[str(q['id'])] = "B"
                                    st.rerun()
                            
                            with col2:
                                if st.button(f"C: {q['option_c']}", key=f"new_q{i}_C", use_container_width=True):
                                    answers[str(q['id'])] = "C"
                                    st.rerun()
                                if st.button(f"D: {q['option_d']}", key=f"new_q{i}_D", use_container_width=True):
                                    answers[str(q['id'])] = "D"
                                    st.rerun()
                            
                            if str(q['id']) in answers:
                                selected = answers[str(q['id'])]
                                option_text = {
                                    'A': q['option_a'],
                                    'B': q['option_b'],
                                    'C': q['option_c'],
                                    'D': q['option_d']
                                }
                                st.info(f"✅ Đã chọn: **{selected}** - {option_text[selected]}")
                            
                            st.markdown("---")
                        
                        # Nút nộp bài
                        if st.button("📤 Nộp bài", type="primary", use_container_width=True):
                            if len(answers) < len(questions):
                                st.warning(f"⚠️ Bạn mới trả lời {len(answers)}/{len(questions)} câu")
                            
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
                            grade, evaluation = calculate_grade(percentage)
                            
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
                            conn.close()
                            
                            # Hiển thị kết quả
                            st.markdown(f"""
                            <div class="score-card">
                                <h1>{evaluation.split()[-1]}</h1>
                                <h2>{evaluation}</h2>
                                <h3>Điểm: {score}/{len(questions)}</h3>
                                <p>Tỉ lệ: {percentage:.1f}% | Xếp loại: {grade}</p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Thông tin học sinh
                            st.markdown(f"""
                            <div class="student-info">
                                <strong>✅ Đã lưu kết quả:</strong><br>
                                <strong>👨‍🎓 Học sinh:</strong> {student_name}<br>
                                <strong>🏫 Lớp:</strong> {class_name}<br>
                                <strong>📋 Mã Quiz:</strong> {quiz_code}
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Chi tiết từng câu
                            with st.expander("📋 Xem chi tiết từng câu"):
                                for i, detail in enumerate(details):
                                    if detail['is_correct']:
                                        st.success(f"**Câu {i+1}:** {detail['question']}")
                                        st.markdown(f"✅ Đã chọn: **{detail['user_answer']}**")
                                    else:
                                        st.error(f"**Câu {i+1}:** {detail['question']}")
                                        st.markdown(f"❌ Đã chọn: **{detail['user_answer']}**")
                                        st.markdown(f"✅ Đáp án đúng: **{detail['correct_answer']}**")
                                    
                                    st.markdown(f"💡 **Giải thích:** {detail['explanation']}")
                                    st.markdown("---")
                            
                            # Xóa session state
                            if 'answers' in st.session_state:
                                del st.session_state.answers
                            
                            st.balloons()
                    
                    elif quiz_code and (not student_name or not class_name):
                        st.warning("⚠️ Vui lòng nhập đầy đủ họ tên và lớp!")
    
    # Thống kê & Tra cứu
    elif menu == "📊 Thống kê & Tra cứu":
        st.header("📊 Thống kê & Tra cứu")
        
        tab1, tab2, tab3 = st.tabs(["🔍 Tra cứu", "📈 Thống kê", "📥 Xuất Excel"])
        
        with tab1:
            st.subheader("🔍 Tra cứu kết quả")
            
            col1, col2 = st.columns(2)
            
            with col1:
                search_type = st.selectbox(
                    "Tìm theo:",
                    ["Tên học sinh", "Lớp học", "Mã Quiz"]
                )
            
            with col2:
                if search_type == "Tên học sinh":
                    search_value = st.text_input("Nhập tên học sinh:", placeholder="Nguyễn Văn A")
                elif search_type == "Lớp học":
                    search_value = st.text_input("Nhập tên lớp:", placeholder="10A1")
                else:  # Mã Quiz
                    search_value = st.text_input("Nhập mã Quiz:", placeholder="ABC123").upper()
            
            if st.button("🔎 Tìm kiếm", type="primary"):
                if search_value:
                    conn = sqlite3.connect('quiz_system.db')
                    conn.row_factory = sqlite3.Row
                    c = conn.cursor()
                    
                    # Xây dựng query an toàn
                    if search_type == "Tên học sinh":
                        c.execute('''
                            SELECT * FROM results 
                            WHERE student_name LIKE ? 
                            ORDER BY submitted_at DESC
                        ''', (f'%{search_value}%',))
                    elif search_type == "Lớp học":
                        c.execute('''
                            SELECT * FROM results 
                            WHERE class_name LIKE ? 
                            ORDER BY submitted_at DESC
                        ''', (f'%{search_value}%',))
                    else:  # Mã Quiz
                        c.execute('''
                            SELECT * FROM results 
                            WHERE quiz_code = ? 
                            ORDER BY submitted_at DESC
                        ''', (search_value,))
                    
                    results = c.fetchall()
                    conn.close()
                    
                    if results:
                        st.success(f"✅ Tìm thấy {len(results)} kết quả")
                        
                        # Hiển thị kết quả
                        data = []
                        for r in results:
                            data.append({
                                "ID": r['id'],
                                "Họ tên": r['student_name'],
                                "Lớp": r['class_name'],
                                "Mã HS": r['student_id'],
                                "Mã Quiz": r['quiz_code'],
                                "Điểm": f"{r['score']}/{r['total_questions']}",
                                "Tỉ lệ": f"{r['percentage']:.1f}%",
                                "Xếp loại": r['grade'],
                                "Thời gian": r['submitted_at'][:16]
                            })
                        
                        df = pd.DataFrame(data)
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info("📭 Không tìm thấy kết quả nào")
        
        with tab2:
            st.subheader("📈 Thống kê tổng quan")
            
            conn = sqlite3.connect('quiz_system.db')
            
            try:
                # Thống kê cơ bản
                c = conn.cursor()
                
                # Tổng số bài thi
                c.execute("SELECT COUNT(*) FROM results")
                total_tests = c.fetchone()[0]
                
                # Điểm trung bình
                c.execute("SELECT AVG(percentage) FROM results WHERE percentage > 0")
                avg_score = c.fetchone()[0] or 0
                
                # Phân bố điểm
                c.execute('''
                    SELECT grade, COUNT(*) as count
                    FROM results 
                    WHERE grade != ''
                    GROUP BY grade 
                    ORDER BY 
                        CASE grade
                            WHEN 'A+' THEN 1
                            WHEN 'A' THEN 2
                            WHEN 'B' THEN 3
                            WHEN 'C' THEN 4
                            WHEN 'D' THEN 5
                            WHEN 'F' THEN 6
                            ELSE 7
                        END
                ''')
                grade_dist = c.fetchall()
                
                conn.close()
                
                # Hiển thị thống kê
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("📊 Tổng bài thi", total_tests)
                with col2:
                    st.metric("📈 Điểm TB", f"{avg_score:.1f}%")
                
                # Phân bố điểm
                if grade_dist:
                    st.markdown("### 📊 Phân bố xếp loại")
                    cols = st.columns(len(grade_dist))
                    for idx, (grade, count) in enumerate(grade_dist):
                        with cols[idx]:
                            color = {
                                'A+': '#FFD700', 'A': '#C0C0C0', 'B': '#CD7F32',
                                'C': '#4CAF50', 'D': '#FF9800', 'F': '#F44336'
                            }.get(grade, '#9E9E9E')
                            
                            st.markdown(f"""
                            <div style="text-align: center; padding: 10px; background-color: {color}; border-radius: 10px;">
                                <h3>{grade}</h3>
                                <h2>{count}</h2>
                            </div>
                            """, unsafe_allow_html=True)
                
            except Exception as e:
                st.error(f"Lỗi thống kê: {str(e)}")
                conn.close()
        
        with tab3:
            st.subheader("📥 Xuất dữ liệu Excel")
            
            if st.button("📤 Xuất toàn bộ kết quả"):
                conn = sqlite3.connect('quiz_system.db')
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                
                try:
                    c.execute('SELECT * FROM results ORDER BY submitted_at DESC')
                    results = c.fetchall()
                    conn.close()
                    
                    if results:
                        data = []
                        for r in results:
                            data.append({
                                "ID": r['id'],
                                "Họ tên": r['student_name'],
                                "Lớp": r['class_name'],
                                "Mã HS": r['student_id'],
                                "Mã Quiz": r['quiz_code'],
                                "Điểm": r['score'],
                                "Tổng câu": r['total_questions'],
                                "Tỉ lệ (%)": r['percentage'],
                                "Xếp loại": r['grade'],
                                "Thời gian": r['submitted_at']
                            })
                        
                        df = pd.DataFrame(data)
                        excel_buffer = io.BytesIO()
                        df.to_excel(excel_buffer, index=False, engine='openpyxl')
                        excel_buffer.seek(0)
                        
                        st.success(f"✅ Đã xuất {len(results)} kết quả")
                        
                        st.download_button(
                            label="📥 Tải file Excel",
                            data=excel_buffer,
                            file_name=f"ket_qua_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    else:
                        st.info("📭 Chưa có dữ liệu để xuất")
                        
                except Exception as e:
                    st.error(f"Lỗi xuất Excel: {str(e)}")
                    conn.close()

if __name__ == "__main__":
    main()
