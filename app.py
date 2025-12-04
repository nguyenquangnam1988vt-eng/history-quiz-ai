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
    .filter-tag {
        display: inline-block;
        background-color: #e0f7fa;
        padding: 5px 10px;
        margin: 2px;
        border-radius: 15px;
        font-size: 0.9em;
    }
</style>
""", unsafe_allow_html=True)

# ==================== KHỞI TẠO DATABASE (CẬP NHẬT) ====================
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
    
    # CẬP NHẬT: Thêm cột class_name
    c.execute('''CREATE TABLE IF NOT EXISTS results
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  quiz_code TEXT,
                  student_name TEXT,
                  class_name TEXT,  -- Thêm cột lớp học
                  student_id TEXT,   -- Thêm cột mã học sinh
                  score INTEGER,
                  total_questions INTEGER,
                  percentage REAL,
                  grade TEXT,
                  submitted_at TIMESTAMP)''')
    
    conn.commit()
    conn.close()

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

# ==================== GIAO DIỆN CHÍNH ====================
def main():
    st.markdown('<h1 class="main-header">📚 Quiz Lịch Sử - Quản lý Lớp học</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/2237/2237288.png", width=100)
        st.title("🎮 Menu")
        
        menu = st.radio(
            "Chọn chức năng:",
            ["🏠 Trang chủ", "📤 Tạo Quiz mới", "🎯 Tham gia Quiz", "📊 Thống kê & Tra cứu", "👨‍🎓 Quản lý Học sinh"]
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
    
    # Trang chủ
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
            
            ### 📋 Thông tin lưu trữ:
            1. **Mỗi quiz**: Mã, tiêu đề, câu hỏi, đáp án
            2. **Mỗi học sinh**: Tên, lớp, mã học sinh (tùy chọn)
            3. **Kết quả**: Điểm, phần trăm, xếp loại, thời gian
            """)
        
        with col2:
            st.markdown("### 📈 Thống kê nhanh")
            
            conn = sqlite3.connect('quiz_system.db')
            
            # Tổng quiz
            c = conn.cursor()
            c.execute('SELECT COUNT(*) FROM quizzes')
            total_quizzes = c.fetchone()[0]
            
            # Tổng học sinh
            c.execute('SELECT COUNT(DISTINCT student_name) FROM results')
            total_students = c.fetchone()[0]
            
            # Tổng bài thi
            c.execute('SELECT COUNT(*) FROM results')
            total_tests = c.fetchone()[0]
            
            # Tổng lớp học
            c.execute("SELECT COUNT(DISTINCT class_name) FROM results WHERE class_name != ''")
            total_classes = c.fetchone()[0]
            
            conn.close()
            
            st.metric("📝 Tổng Quiz", total_quizzes)
            st.metric("👨‍🎓 Tổng Học sinh", total_students)
            st.metric("📊 Tổng Bài thi", total_tests)
            st.metric("🏫 Tổng Lớp", total_classes)
    
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
    
    # Tham gia Quiz - CẬP NHẬT THÊM THÔNG TIN HỌC SINH
    elif menu == "🎯 Tham gia Quiz":
        st.header("🎯 Tham gia làm Quiz")
        
        tab1, tab2 = st.tabs(["📝 Làm bài mới", "🔍 Xem lại bài đã làm"])
        
        with tab1:
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
                                help="Nhập họ tên đầy đủ"
                            )
                        
                        with col2:
                            class_name = st.text_input(
                                "Lớp:",
                                placeholder="10A1, 11B2,...",
                                help="Nhập tên lớp"
                            )
                        
                        with col3:
                            student_id = st.text_input(
                                "Mã học sinh (tùy chọn):",
                                placeholder="HS001",
                                help="Mã số học sinh nếu có"
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
                                
                                # Lưu kết quả VỚI ĐẦY ĐỦ THÔNG TIN
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
                                    <p>Tỉ lệ: {percentage:.1f}% | Xếp loại: {grade}</p>
                                    <p><small>Mã bài thi: {result_id}</small></p>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                # Thông tin học sinh
                                st.markdown(f"""
                                <div class="student-info">
                                    <strong>✅ Đã lưu kết quả:</strong><br>
                                    <strong>👨‍🎓 Học sinh:</strong> {student_name}<br>
                                    <strong>🏫 Lớp:</strong> {class_name}<br>
                                    <strong>📋 Mã Quiz:</strong> {quiz_code}<br>
                                    <strong>🆔 Mã bài thi:</strong> {result_id}
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
                                st.info("💡 Ghi nhớ mã bài thi để tra cứu lại sau!")
                        
                        elif quiz_code and (not student_name or not class_name):
                            st.warning("⚠️ Vui lòng nhập đầy đủ họ tên và lớp!")
        
        with tab2:
            st.subheader("🔍 Tra cứu bài đã làm")
            
            col1, col2 = st.columns(2)
            with col1:
                search_name = st.text_input("Tìm theo tên học sinh:", placeholder="Nguyễn Văn A")
            with col2:
                search_class = st.text_input("Tìm theo lớp:", placeholder="10A1")
            
            if search_name or search_class:
                conn = sqlite3.connect('quiz_system.db')
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
                
                query = "SELECT * FROM results WHERE 1=1"
                params = []
                
                if search_name:
                    query += " AND student_name LIKE ?"
                    params.append(f"%{search_name}%")
                
                if search_class:
                    query += " AND class_name LIKE ?"
                    params.append(f"%{search_class}%")
                
                query += " ORDER BY submitted_at DESC LIMIT 20"
                
                c.execute(query, params)
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
                                st.metric("Xếp loại", r['grade'])
                            
                            st.info(f"**Mã bài thi:** {r['id']} | **Mã Quiz:** {r['quiz_code']}")
                else:
                    st.info("📭 Không tìm thấy bài thi nào")
    
    # Thống kê & Tra cứu - CẬP NHẬT ĐA CHIỀU
    elif menu == "📊 Thống kê & Tra cứu":
        st.header("📊 Thống kê & Tra cứu đa chiều")
        
        tab1, tab2, tab3, tab4 = st.tabs(["🔍 Tra cứu chi tiết", "📈 Thống kê tổng quan", "🏆 Bảng xếp hạng", "📥 Xuất Excel"])
        
        with tab1:
            st.subheader("🔍 Tra cứu theo nhiều tiêu chí")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                search_type = st.radio(
                    "Tra cứu theo:",
                    ["Tên học sinh", "Lớp học", "Mã Quiz", "Mã bài thi"]
                )
            
            with col2:
                if search_type == "Tên học sinh":
                    search_value = st.text_input("Nhập tên học sinh:", placeholder="Nguyễn Văn A")
                elif search_type == "Lớp học":
                    search_value = st.text_input("Nhập tên lớp:", placeholder="10A1")
                elif search_type == "Mã Quiz":
                    search_value = st.text_input("Nhập mã Quiz:", placeholder="ABC123").upper()
                else:  # Mã bài thi
                    search_value = st.text_input("Nhập mã bài thi:", placeholder="1, 2, 3...")
            
            with col3:
                min_score = st.number_input("Điểm tối thiểu:", min_value=0, value=0)
                date_range = st.date_input("Khoảng thời gian:", [])
            
            if st.button("🔎 Tìm kiếm", type="primary"):
                if search_value:
                    conn = sqlite3.connect('quiz_system.db')
                    conn.row_factory = sqlite3.Row
                    c = conn.cursor()
                    
                    # Xây dựng query động
                    query = "SELECT * FROM results WHERE 1=1"
                    params = []
                    
                    if search_type == "Tên học sinh":
                        query += " AND student_name LIKE ?"
                        params.append(f"%{search_value}%")
                    elif search_type == "Lớp học":
                        query += " AND class_name LIKE ?"
                        params.append(f"%{search_value}%")
                    elif search_type == "Mã Quiz":
                        query += " AND quiz_code = ?"
                        params.append(search_value)
                    elif search_type == "Mã bài thi":
                        query += " AND id = ?"
                        params.append(int(search_value))
                    
                    if min_score > 0:
                        query += " AND score >= ?"
                        params.append(min_score)
                    
                    if len(date_range) == 2:
                        query += " AND DATE(submitted_at) BETWEEN ? AND ?"
                        params.extend([date_range[0].isoformat(), date_range[1].isoformat()])
                    
                    query += " ORDER BY submitted_at DESC"
                    
                    c.execute(query, params)
                    results = c.fetchall()
                    conn.close()
                    
                    if results:
                        st.success(f"✅ Tìm thấy {len(results)} kết quả")
                        
                        # Hiển thị kết quả dạng bảng
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
                        
                        # Thống kê nhanh
                        if len(results) > 0:
                            avg_percentage = sum(r['percentage'] for r in results) / len(results)
                            max_score = max(r['score'] for r in results)
                            
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Điểm TB", f"{avg_percentage:.1f}%")
                            with col2:
                                st.metric("Điểm cao nhất", max_score)
                            with col3:
                                st.metric("Số bài thi", len(results))
                    else:
                        st.info("📭 Không tìm thấy kết quả nào")
        
        with tab2:
            st.subheader("📈 Thống kê tổng quan")
            
            conn = sqlite3.connect('quiz_system.db')
            conn.row_factory = sqlite3.Row
            
            # Thống kê tổng quan
            c = conn.cursor()
            
            # Tổng số bài thi theo lớp
            c.execute("""
                SELECT class_name, COUNT(*) as count, 
                       AVG(percentage) as avg_score,
                       MAX(percentage) as max_score,
                       MIN(percentage) as min_score
                FROM results 
                WHERE class_name != '' 
                GROUP BY class_name 
                ORDER BY count DESC
            """)
            class_stats = c.fetchall()
            
            # Tổng số bài thi theo quiz
            c.execute("""
                SELECT quiz_code, COUNT(*) as count,
                       AVG(percentage) as avg_score
                FROM results 
                GROUP BY quiz_code 
                ORDER BY count DESC
            """)
            quiz_stats = c.fetchall()
            
            # Phân bố điểm
            c.execute("""
                SELECT grade, COUNT(*) as count
                FROM results 
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
            """)
            grade_dist = c.fetchall()
            
            conn.close()
            
            # Hiển thị thống kê
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 🏫 Thống kê theo lớp")
                if class_stats:
                    class_data = []
                    for stat in class_stats:
                        class_data.append({
                            "Lớp": stat['class_name'] or "Không có",
                            "Số bài": stat['count'],
                            "Điểm TB": f"{stat['avg_score']:.1f}%",
                            "Cao nhất": f"{stat['max_score']:.1f}%",
                            "Thấp nhất": f"{stat['min_score']:.1f}%"
                        })
                    st.dataframe(pd.DataFrame(class_data), use_container_width=True)
                else:
                    st.info("📭 Chưa có dữ liệu theo lớp")
            
            with col2:
                st.markdown("### 📝 Thống kê theo Quiz")
                if quiz_stats:
                    quiz_data = []
                    for stat in quiz_stats:
                        quiz_data.append({
                            "Mã Quiz": stat['quiz_code'],
                            "Số bài": stat['count'],
                            "Điểm TB": f"{stat['avg_score']:.1f}%"
                        })
                    st.dataframe(pd.DataFrame(quiz_data), use_container_width=True)
                else:
                    st.info("📭 Chưa có dữ liệu theo quiz")
            
            # Phân bố điểm
            st.markdown("### 📊 Phân bố xếp loại")
            if grade_dist:
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
        
        with tab3:
            st.subheader("🏆 Bảng xếp hạng")
            
            rank_type = st.radio(
                "Xếp hạng theo:",
                ["Toàn trường", "Theo lớp", "Theo Quiz"],
                horizontal=True
            )
            
            if rank_type == "Theo lớp":
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
                        st.success(f"🏫 Bảng xếp hạng lớp {selected_class}")
                        
                        for i, r in enumerate(rankings):
                            if i == 0:
                                medal = "🥇"
                                color = "#FFD700"
                            elif i == 1:
                                medal = "🥈"
                                color = "#C0C0C0"
                            elif i == 2:
                                medal = "🥉"
                                color = "#CD7F32"
                            else:
                                medal = f"#{i+1}"
                                color = "#f0f0f0"
                            
                            st.markdown(f"""
                            <div style="background-color: {color}; padding: 10px; border-radius: 5px; margin: 5px 0;">
                                <strong>{medal} {r['student_name']}</strong><br>
                                Điểm: {r['score']}/{r['total_questions']} ({r['percentage']:.1f}%) - {r['grade']}<br>
                                <small>Quiz: {r['quiz_code']} | {r['submitted_at'][:16]}</small>
                            </div>
                            """, unsafe_allow_html=True)
            
            elif rank_type == "Theo Quiz":
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
                        st.success(f"📝 Bảng xếp hạng Quiz {selected_quiz}")
                        
                        for i, r in enumerate(rankings):
                            if i == 0:
                                medal = "🥇"
                                color = "#FFD700"
                            elif i == 1:
                                medal = "🥈"
                                color = "#C0C0C0"
                            elif i == 2:
                                medal = "🥉"
                                color = "#CD7F32"
                            else:
                                medal = f"#{i+1}"
                                color = "#f0f0f0"
                            
                            st.markdown(f"""
                            <div style="background-color: {color}; padding: 10px; border-radius: 5px; margin: 5px 0;">
                                <strong>{medal} {r['student_name']}</strong> - {r['class_name']}<br>
                                Điểm: {r['score']}/{r['total_questions']} ({r['percentage']:.1f}%) - {r['grade']}<br>
                                <small>{r['submitted_at'][:16]}</small>
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
                    st.success("🏆 Bảng xếp hạng toàn trường (Top 20)")
                    
                    for i, r in enumerate(rankings):
                        if i == 0:
                            medal = "🥇"
                            color = "#FFD700"
                        elif i == 1:
                            medal = "🥈"
                            color = "#C0C0C0"
                        elif i == 2:
                            medal = "🥉"
                            color = "#CD7F32"
                        else:
                            medal = f"#{i+1}"
                            color = "#f0f0f0"
                        
                        st.markdown(f"""
                        <div style="background-color: {color}; padding: 10px; border-radius: 5px; margin: 5px 0;">
                            <strong>{medal} {r['student_name']}</strong> - {r['class_name']}<br>
                            Điểm: {r['score']}/{r['total_questions']} ({r['percentage']:.1f}%) - {r['grade']}<br>
                            <small>Quiz: {r['quiz_code']} | {r['submitted_at'][:16]}</small>
                        </div>
                        """, unsafe_allow_html=True)
        
        with tab4:
            st.subheader("📥 Xuất dữ liệu Excel")
            
            export_type = st.radio(
                "Xuất dữ liệu:",
                ["Toàn bộ kết quả", "Theo lớp", "Theo Quiz", "Theo khoảng thời gian"]
            )
            
            if export_type == "Theo lớp":
                conn = sqlite3.connect('quiz_system.db')
                c = conn.cursor()
                c.execute("SELECT DISTINCT class_name FROM results WHERE class_name != '' ORDER BY class_name")
                classes = [row[0] for row in c.fetchall()]
                conn.close()
                
                export_class = st.selectbox("Chọn lớp để xuất:", classes)
                
                if export_class and st.button("📊 Xuất Excel cho lớp"):
                    conn = sqlite3.connect('quiz_system.db')
                    conn.row_factory = sqlite3.Row
                    c = conn.cursor()
                    c.execute('''
                        SELECT * FROM results 
                        WHERE class_name = ?
                        ORDER BY submitted_at DESC
                    ''', (export_class,))
                    results = c.fetchall()
                    conn.close()
                    
                    if results:
                        # Chuẩn bị dữ liệu
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
                        
                        # Tạo Excel
                        excel_buffer = io.BytesIO()
                        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                            df.to_excel(writer, index=False, sheet_name='Kết quả')
                            
                            # Thêm sheet thống kê
                            stats = {
                                'Tổng bài thi': [len(results)],
                                'Điểm TB': [f"{df['Tỉ lệ (%)'].mean():.1f}%"],
                                'Điểm cao nhất': [f"{df['Tỉ lệ (%)'].max():.1f}%"],
                                'Điểm thấp nhất': [f"{df['Tỉ lệ (%)'].min():.1f}%"]
                            }
                            pd.DataFrame(stats).to_excel(writer, index=False, sheet_name='Thống kê')
                        
                        excel_buffer.seek(0)
                        
                        st.success(f"✅ Đã xuất {len(results)} kết quả của lớp {export_class}")
                        
                        # Nút download
                        st.download_button(
                            label="📥 Tải file Excel",
                            data=excel_buffer,
                            file_name=f"ket_qua_lop_{export_class}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
            
            elif st.button("📤 Xuất toàn bộ kết quả"):
                conn = sqlite3.connect('quiz_system.db')
                conn.row_factory = sqlite3.Row
                c = conn.cursor()
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
                        file_name=f"toan_bo_ket_qua_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
    
    # Quản lý Học sinh
    elif menu == "👨‍🎓 Quản lý Học sinh":
        st.header("👨‍🎓 Quản lý thông tin học sinh")
        
        tab1, tab2 = st.tabs(["📋 Danh sách học sinh", "📊 Thống kê học sinh"])
        
        with tab1:
            conn = sqlite3.connect('quiz_system.db')
            conn.row_factory = sqlite3.Row
            
            # Lấy danh sách học sinh duy nhất
            c = conn.cursor()
            c.execute('''
                SELECT student_name, class_name, student_id,
                       COUNT(*) as total_tests,
                       AVG(percentage) as avg_score,
                       MAX(percentage) as max_score,
                       MIN(percentage) as min_score,
                       MAX(submitted_at) as last_test
                FROM results 
                GROUP BY student_name, class_name, student_id
                ORDER BY class_name, student_name
            ''')
            students = c.fetchall()
            conn.close()
            
            if students:
                st.success(f"✅ Tổng số học sinh: {len(students)}")
                
                # Filter
                col1, col2 = st.columns(2)
                with col1:
                    filter_class = st.selectbox(
                        "Lọc theo lớp:",
                        ["Tất cả"] + sorted(set(s['class_name'] for s in students if s['class_name']))
                    )
                
                with col2:
                    search_name = st.text_input("Tìm theo tên:", placeholder="Nhập tên học sinh")
                
                # Áp dụng filter
                filtered_students = students
                if filter_class != "Tất cả":
                    filtered_students = [s for s in filtered_students if s['class_name'] == filter_class]
                
                if search_name:
                    filtered_students = [s for s in filtered_students if search_name.lower() in s['student_name'].lower()]
                
                # Hiển thị danh sách
                for student in filtered_students:
                    with st.expander(f"👨‍🎓 {student['student_name']} - {student['class_name'] or 'Chưa có lớp'}"):
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.metric("Số bài thi", student['total_tests'])
                        
                        with col2:
                            st.metric("Điểm TB", f"{student['avg_score']:.1f}%")
                        
                        with col3:
                            st.metric("Điểm cao nhất", f"{student['max_score']:.1f}%")
                        
                        st.info(f"**Mã học sinh:** {student['student_id'] or 'Chưa có'} | **Bài thi gần nhất:** {student['last_test'][:16]}")
                        
                        # Hiển thị chi tiết bài thi
                        conn = sqlite3.connect('quiz_system.db')
                        conn.row_factory = sqlite3.Row
                        c = conn.cursor()
                        c.execute('''
                            SELECT quiz_code, score, total_questions, percentage, grade, submitted_at
                            FROM results 
                            WHERE student_name = ? AND (class_name = ? OR ? IS NULL)
                            ORDER BY submitted_at DESC
                            LIMIT 5
                        ''', (student['student_name'], student['class_name'], student['class_name']))
                        recent_tests = c.fetchall()
                        conn.close()
                        
                        if recent_tests:
                            st.markdown("**📝 5 bài thi gần nhất:**")
                            for test in recent_tests:
                                st.markdown(f"- **{test['quiz_code']}:** {test['score']}/{test['total_questions']} ({test['percentage']:.1f}%) - {test['grade']} - {test['submitted_at'][:16]}")
            else:
                st.info("📭 Chưa có dữ liệu học sinh")
        
        with tab2:
            st.subheader("📊 Phân tích học tập")
            
            conn = sqlite3.connect('quiz_system.db')
            
            # Biểu đồ tiến bộ
            st.markdown("### 📈 Biểu đồ tiến bộ (theo thời gian)")
            
            # Chọn học sinh để phân tích
            c = conn.cursor()
            c.execute("SELECT DISTINCT student_name, class_name FROM results ORDER BY class_name, student_name")
            all_students = c.fetchall()
            
            if all_students:
                student_options = [f"{s[0]} - {s[1]}" for s in all_students]
                selected_student = st.selectbox("Chọn học sinh để phân tích:", student_options)
                
                if selected_student:
                    student_name, class_name = selected_student.split(" - ")
                    
                    c.execute('''
                        SELECT submitted_at, percentage, score, total_questions, quiz_code
                        FROM results 
                        WHERE student_name = ? AND class_name = ?
                        ORDER BY submitted_at
                    ''', (student_name, class_name))
                    student_data = c.fetchall()
                    
                    if student_data:
                        # Tạo DataFrame
                        progress_data = []
                        for row in student_data:
                            progress_data.append({
                                "Thời gian": row[0][:10],
                                "Tỉ lệ (%)": row[1],
                                "Điểm": row[2],
                                "Quiz": row[4]
                            })
                        
                        df_progress = pd.DataFrame(progress_data)
                        
                        # Hiển thị biểu đồ
                        st.line_chart(df_progress.set_index("Thời gian")["Tỉ lệ (%)"])
                        
                        # Thống kê
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Số bài thi", len(student_data))
                        with col2:
                            avg_score = df_progress["Tỉ lệ (%)"].mean()
                            st.metric("Điểm TB", f"{avg_score:.1f}%")
                        with col3:
                            improvement = df_progress["Tỉ lệ (%)"].iloc[-1] - df_progress["Tỉ lệ (%)"].iloc[0] if len(student_data) > 1 else 0
                            st.metric("Tiến bộ", f"{improvement:+.1f}%")
            
            conn.close()

if __name__ == "__main__":
    main()
