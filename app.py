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
    .ai-status {
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .ai-active {
        background-color: #d4edda;
        border-left: 5px solid #28a745;
    }
    .ai-inactive {
        background-color: #f8d7da;
        border-left: 5px solid #dc3545;
    }
</style>
""", unsafe_allow_html=True)

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
    
    c.execute('''CREATE TABLE IF NOT EXISTS results
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  quiz_code TEXT,
                  student_name TEXT,
                  score INTEGER,
                  total_questions INTEGER,
                  submitted_at TIMESTAMP)''')
    
    conn.commit()
    conn.close()

init_db()

# ==================== KHỞI TẠO GEMINI AI (DÙNG MODEL GEMMA 3-4B) ====================
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
        
        # 3. Từ key trực tiếp (CHO TEST - XÓA KHI DEPLOY)
        if not api_key:
            api_key = "AIzaSyAXneM58drczCgMfm-Ihx0mzxIpiy8TmvQ"  # API KEY CỦA BẠN
        
        if not api_key or api_key == "your_api_key_here":
            st.warning("⚠️ Chưa cấu hình Gemini API Key")
            return None
        
        # Configure với API key
        genai.configure(api_key=api_key)
        
        # DÙNG MODEL GEMMA 3-4B (model bạn đã test thành công)
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
        
        # Hiển thị lỗi chi tiết
        if "API_KEY_INVALID" in error_msg:
            st.error("❌ API Key không hợp lệ. Vui lòng kiểm tra lại.")
        elif "quota" in error_msg.lower():
            st.error("❌ Đã hết quota API. Vui lòng kiểm tra billing.")
        elif "model" in error_msg.lower():
            st.error(f"❌ Model không khả dụng. Lỗi: {error_msg}")
        else:
            st.error(f"❌ Lỗi kết nối Gemini: {error_msg}")
        
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
    """
    Tạo câu hỏi trắc nghiệm bằng Google Gemini API với model Gemma
    """
    if not gemini_model:
        print("⚠️ Gemini không khả dụng, dùng câu hỏi mẫu")
        return None
    
    try:
        # Giới hạn độ dài văn bản
        text = text[:3000]
        
        # PROMPT cho Gemma model (đơn giản hơn)
        prompt = f"""Bạn là giáo viên lịch sử. Tạo {num_questions} câu hỏi trắc nghiệm từ tài liệu:

{text}

Tạo {num_questions} câu hỏi trắc nghiệm với 4 đáp án A,B,C,D. Chỉ một đáp án đúng.
Trả về JSON format:
{{
  "questions": [
    {{
      "question": "Câu hỏi",
      "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
      "correct_answer": "A",
      "explanation": "Giải thích"
    }}
  ]
}}

Chỉ trả về JSON."""
        
        # Cấu hình generation cho Gemma
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.9,
            "top_k": 40,
            "max_output_tokens": 2000,
        }
        
        response = gemini_model.generate_content(
            prompt,
            generation_config=generation_config
        )
        
        if not response or not response.text:
            print("❌ Gemini không trả về kết quả")
            return None
            
        result_text = response.text.strip()
        print(f"📝 Gemini response: {result_text[:300]}...")
        
        # Làm sạch response
        result_text = result_text.replace('```json', '').replace('```', '').strip()
        
        # Tìm JSON
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if not json_match:
            print(f"❌ Không tìm thấy JSON trong response")
            return None
            
        json_str = json_match.group()
        
        # Parse JSON
        quiz_data = json.loads(json_str)
        
        if "questions" not in quiz_data:
            print("❌ JSON không có key 'questions'")
            return None
            
        questions = quiz_data["questions"]
        if not isinstance(questions, list) or len(questions) == 0:
            print("❌ Questions không phải list hoặc rỗng")
            return None
            
        # Validate và fix dữ liệu
        valid_questions = []
        for i, q in enumerate(questions):
            try:
                if not isinstance(q, dict):
                    continue
                    
                # Đảm bảo có đủ các trường
                if "question" not in q:
                    q["question"] = f"Câu hỏi {i+1}"
                
                if "options" not in q or not isinstance(q["options"], dict):
                    q["options"] = {"A": "Đáp án A", "B": "Đáp án B", "C": "Đáp án C", "D": "Đáp án D"}
                
                if "correct_answer" not in q or q["correct_answer"] not in ["A", "B", "C", "D"]:
                    q["correct_answer"] = "A"
                
                if "explanation" not in q:
                    q["explanation"] = "Không có giải thích"
                
                # Đảm bảo options có đủ 4 đáp án
                options = q["options"]
                for key in ["A", "B", "C", "D"]:
                    if key not in options:
                        options[key] = f"Đáp án {key}"
                
                valid_questions.append(q)
                
            except Exception as e:
                print(f"⚠️ Lỗi xử lý câu {i+1}: {e}")
                continue
        
        if len(valid_questions) > 0:
            print(f"✅ Gemma tạo thành công {len(valid_questions)} câu hỏi")
            return {"questions": valid_questions[:num_questions]}
        else:
            print("❌ Không có câu hỏi nào hợp lệ từ Gemma")
            return None
            
    except json.JSONDecodeError as e:
        print(f"❌ Lỗi parse JSON từ Gemma: {e}")
        print(f"Response: {result_text[:200] if 'result_text' in locals() else 'N/A'}")
        return None
    except Exception as e:
        print(f"❌ Lỗi Gemma API: {type(e).__name__}: {e}")
        return None

def generate_quiz_questions(text, num_questions=5):
    """
    Tổng hợp: Thử Gemini trước, nếu không được thì dùng câu hỏi mẫu
    """
    print(f"📄 Đang xử lý văn bản ({len(text)} ký tự)...")
    
    # Kiểm tra xem text có nội dung không
    if len(text.strip()) < 50:
        print("⚠️ Văn bản quá ngắn, dùng câu hỏi mẫu")
        sample = get_sample_questions()
        sample["questions"] = sample["questions"][:min(num_questions, len(sample["questions"]))]
        return sample
    
    # Thử dùng Gemma AI
    print("🤖 Đang sử dụng Gemma AI để tạo câu hỏi...")
    gemini_result = generate_quiz_questions_gemini(text, num_questions)
    
    if gemini_result and "questions" in gemini_result and len(gemini_result["questions"]) > 0:
        print(f"✅ Đã tạo {len(gemini_result['questions'])} câu hỏi bằng AI")
        return gemini_result
    
    # Fallback: dùng câu hỏi mẫu
    print("⚠️ Không thể tạo câu hỏi bằng AI, dùng câu hỏi mẫu")
    sample = get_sample_questions()
    sample["questions"] = sample["questions"][:min(num_questions, len(sample["questions"]))]
    return sample

# ==================== GIAO DIỆN CHÍNH ====================
def main():
    st.markdown('<h1 class="main-header">📚 Quiz Lịch Sử Tương Tác với Gemma AI</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/2237/2237288.png", width=100)
        st.title("🎮 Menu")
        
        menu = st.radio(
            "Chọn chức năng:",
            ["🏠 Trang chủ", "📤 Tạo Quiz mới", "🎯 Tham gia Quiz", "📊 Xem kết quả", "🤖 Trạng thái AI"]
        )
        
        st.markdown("---")
        
        # Hiển thị trạng thái AI
        if gemini_model:
            st.markdown('<div class="ai-status ai-active"><strong>✅ Gemma AI:</strong> ĐÃ KẾT NỐI</div>', unsafe_allow_html=True)
            st.info(f"Model: models/gemma-3-4b-it")
        else:
            st.markdown('<div class="ai-status ai-inactive"><strong>⚠️ Gemma AI:</strong> CHƯA KẾT NỐI</div>', unsafe_allow_html=True)
            st.warning("Sử dụng câu hỏi mẫu")
        
        st.markdown("---")
        st.info("""
        **Hướng dẫn:**
        1. Upload file giáo án
        2. AI tự tạo câu hỏi
        3. Chia sẻ mã quiz
        4. Học sinh tham gia
        5. Xem kết quả
        """)
    
    # Trang chủ
    if menu == "🏠 Trang chủ":
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.success("🎉 Chào mừng đến với hệ thống Quiz Lịch Sử!")
            
            if gemini_model:
                st.markdown("""
                ### ✨ Tính năng nổi bật:
                
                - 🤖 **Gemma AI 3-4B**: Tạo câu hỏi thông minh từ giáo án
                - 📤 **Hỗ Trợ Nhiều Định Dạng**: TXT, PDF, DOCX
                - 🎯 **Tham Gian Dễ Dàng**: Chỉ cần mã quiz
                - 📊 **Kết Quả Real-time**: Bảng xếp hạng
                - 📱 **Responsive**: Hoạt động trên mọi thiết bị
                """)
            else:
                st.warning("""
                ### ⚠️ Chế độ dùng câu hỏi mẫu:
                
                - 📝 **Câu hỏi mẫu**: Sử dụng bộ câu hỏi có sẵn
                - 📤 **Vẫn upload file**: Nhưng sẽ dùng câu hỏi mẫu
                - 🎯 **Đầy đủ tính năng**: Vẫn có quiz, kết quả, xếp hạng
                
                **Để dùng AI:** Thêm API Key Gemini vào file `.streamlit/secrets.toml`
                """)
            
            st.markdown("""
            ### 🚀 Bắt đầu ngay:
            1. Chọn **"Tạo Quiz mới"** ở menu
            2. Upload file giáo án lịch sử
            3. AI sẽ tự động tạo câu hỏi
            4. Chia sẻ mã quiz cho học sinh
            """)
        
        with col2:
            st.markdown("### 📋 Quiz đang hoạt động")
            
            conn = sqlite3.connect('quiz_system.db')
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('SELECT * FROM quizzes WHERE is_active = 1 ORDER BY created_at DESC LIMIT 5')
            recent_quizzes = c.fetchall()
            conn.close()
            
            if recent_quizzes:
                for quiz in recent_quizzes:
                    st.markdown(f"""
                    <div class="quiz-card">
                        <h4>{quiz['title']}</h4>
                        <p>Mã: <strong>{quiz['quiz_code']}</strong></p>
                        <p>Số câu: {quiz['question_count']}</p>
                        <small>Tạo: {quiz['created_at'][:10] if quiz['created_at'] else 'N/A'}</small>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("📭 Chưa có quiz nào")
    
    # Tạo Quiz mới
    elif menu == "📤 Tạo Quiz mới":
        st.header("📤 Tạo Quiz mới")
        
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
                max_value=15,
                value=5
            )
            
            quiz_title = st.text_input(
                "Tiêu đề quiz",
                value="Quiz Lịch Sử"
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
                             (quiz_code, quiz_title, datetime.now(), len(quiz_data['questions'])))
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
                    
                    # Hiển thị kết quả
                    st.success("✅ Đã tạo quiz thành công!")
                    
                    col_code, col_count = st.columns(2)
                    with col_code:
                        st.info(f"**Mã Quiz:** `{quiz_code}`")
                    with col_count:
                        st.info(f"**Số câu:** {len(quiz_data['questions'])}")
                    
                    if gemini_model:
                        st.success("🤖 Đã sử dụng Gemma AI để tạo câu hỏi")
                    else:
                        st.info("📝 Đã sử dụng câu hỏi mẫu")
                    
                    # Xem trước
                    with st.expander("📋 Xem trước câu hỏi"):
                        for i, q in enumerate(quiz_data['questions']):
                            st.markdown(f"**Câu {i+1}:** {q['question']}")
                            cols = st.columns(2)
                            with cols[0]:
                                st.markdown(f"**A.** {q['options']['A']}")
                                st.markdown(f"**B.** {q['options']['B']}")
                            with cols[1]:
                                st.markdown(f"**C.** {q['options']['C']}")
                                st.markdown(f"**D.** {q['options']['D']}")
                            st.markdown(f"✅ **Đáp án:** {q['correct_answer']}")
                            st.markdown(f"💡 {q.get('explanation', 'Không có giải thích')}")
                            st.markdown("---")
    
    # Tham gia Quiz
    elif menu == "🎯 Tham gia Quiz":
        st.header("🎯 Tham gia Quiz")
        
        quiz_code = st.text_input("Nhập mã Quiz:", placeholder="VD: ABC123").strip().upper()
        
        if quiz_code:
            conn = sqlite3.connect('quiz_system.db')
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            c.execute('SELECT * FROM quizzes WHERE quiz_code = ? AND is_active = 1', (quiz_code,))
            quiz = c.fetchone()
            
            if not quiz:
                st.error("❌ Mã Quiz không tồn tại!")
            else:
                st.success(f"✅ Quiz: {quiz['title']}")
                
                c.execute('SELECT * FROM questions WHERE quiz_id = ? ORDER BY id', (quiz['id'],))
                questions = c.fetchall()
                conn.close()
                
                if not questions:
                    st.error("Quiz chưa có câu hỏi!")
                else:
                    student_name = st.text_input("Tên của bạn:", placeholder="Nhập tên")
                    
                    if student_name:
                        st.markdown("---")
                        st.subheader(f"📝 Bài thi: {len(questions)} câu")
                        
                        # Lưu câu trả lời
                        if 'answers' not in st.session_state:
                            st.session_state.answers = {}
                        
                        answers = st.session_state.answers
                        
                        for i, q in enumerate(questions):
                            st.markdown(f"**Câu {i+1}:** {q['question_text']}")
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                if st.button(f"A: {q['option_a']}", key=f"q{i}_A", use_container_width=True):
                                    answers[str(q['id'])] = "A"
                                    st.rerun()
                                if st.button(f"B: {q['option_b']}", key=f"q{i}_B", use_container_width=True):
                                    answers[str(q['id'])] = "B"
                                    st.rerun()
                            
                            with col2:
                                if st.button(f"C: {q['option_c']}", key=f"q{i}_C", use_container_width=True):
                                    answers[str(q['id'])] = "C"
                                    st.rerun()
                                if st.button(f"D: {q['option_d']}", key=f"q{i}_D", use_container_width=True):
                                    answers[str(q['id'])] = "D"
                                    st.rerun()
                            
                            if str(q['id']) in answers:
                                st.info(f"✅ Đã chọn: {answers[str(q['id'])]}")
                            
                            st.markdown("---")
                        
                        # Nộp bài
                        if st.button("📤 Nộp bài", type="primary", use_container_width=True):
                            score = 0
                            details = []
                            
                            for q in questions:
                                user_answer = answers.get(str(q['id']), '')
                                is_correct = (user_answer == q['correct_answer'])
                                if is_correct:
                                    score += 1
                                
                                details.append({
                                    'question': q['question_text'],
                                    'user_answer': user_answer,
                                    'correct_answer': q['correct_answer'],
                                    'is_correct': is_correct,
                                    'explanation': q['explanation']
                                })
                            
                            # Lưu kết quả
                            conn = sqlite3.connect('quiz_system.db')
                            c = conn.cursor()
                            c.execute('''INSERT INTO results 
                                         (quiz_code, student_name, score, total_questions, submitted_at)
                                         VALUES (?, ?, ?, ?, ?)''',
                                     (quiz_code, student_name, score, len(questions), datetime.now()))
                            conn.commit()
                            conn.close()
                            
                            # Hiển thị kết quả
                            percentage = (score / len(questions)) * 100
                            
                            if percentage >= 90:
                                emoji = "🏆"
                                grade = "Xuất sắc!"
                            elif percentage >= 70:
                                emoji = "🎉"
                                grade = "Giỏi!"
                            elif percentage >= 50:
                                emoji = "👍"
                                grade = "Khá"
                            else:
                                emoji = "💪"
                                grade = "Cố gắng hơn"
                            
                            st.markdown(f"""
                            <div class="score-card">
                                <h1>{emoji}</h1>
                                <h2>{grade}</h2>
                                <h3>Điểm: {score}/{len(questions)}</h3>
                                <p>Tỉ lệ: {percentage:.1f}%</p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            with st.expander("📋 Xem chi tiết"):
                                for i, detail in enumerate(details):
                                    if detail['is_correct']:
                                        st.success(f"**Câu {i+1}:** {detail['question']}")
                                        st.markdown(f"✅ Đã chọn: {detail['user_answer']}")
                                    else:
                                        st.error(f"**Câu {i+1}:** {detail['question']}")
                                        st.markdown(f"❌ Đã chọn: {detail['user_answer']}")
                                        st.markdown(f"✅ Đáp án: {detail['correct_answer']}")
                                    
                                    st.markdown(f"💡 {detail['explanation']}")
                                    st.markdown("---")
                            
                            if 'answers' in st.session_state:
                                del st.session_state.answers
    
    # Xem kết quả
    elif menu == "📊 Xem kết quả":
        st.header("📊 Bảng xếp hạng")
        
        quiz_code = st.text_input("Nhập mã Quiz để xem kết quả:", placeholder="VD: ABC123").strip().upper()
        
        if quiz_code:
            conn = sqlite3.connect('quiz_system.db')
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            c.execute('SELECT title, question_count FROM quizzes WHERE quiz_code = ?', (quiz_code,))
            quiz = c.fetchone()
            
            if not quiz:
                st.error("❌ Quiz không tồn tại!")
            else:
                st.success(f"📚 {quiz['title']}")
                
                c.execute('''SELECT student_name, score, total_questions,
                             strftime('%d/%m/%Y %H:%M', submitted_at) as submitted_at
                             FROM results WHERE quiz_code = ? 
                             ORDER BY score DESC, submitted_at''', (quiz_code,))
                results = c.fetchall()
                conn.close()
                
                if not results:
                    st.info("📭 Chưa có kết quả")
                else:
                    total = len(results)
                    avg = sum(r['score'] for r in results) / total if total > 0 else 0
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Tổng thí sinh", total)
                    with col2:
                        st.metric("Điểm TB", f"{avg:.1f}")
                    with col3:
                        st.metric("Số câu", quiz['question_count'])
                    
                    st.subheader("🏆 Bảng xếp hạng")
                    
                    for i, r in enumerate(results):
                        percent = (r['score'] / r['total_questions']) * 100
                        
                        if i == 0:
                            color = "#FFD700"
                            medal = "🥇"
                        elif i == 1:
                            color = "#C0C0C0"
                            medal = "🥈"
                        elif i == 2:
                            color = "#CD7F32"
                            medal = "🥉"
                        else:
                            color = "#f0f0f0"
                            medal = f"#{i+1}"
                        
                        st.markdown(f"""
                        <div style="background-color: {color}; padding: 10px; border-radius: 5px; margin: 5px 0;">
                            <strong>{medal} {r['student_name']}</strong> - {r['score']} điểm ({percent:.1f}%)
                            <br><small>{r['submitted_at']}</small>
                        </div>
                        """, unsafe_allow_html=True)
    
    # Trạng thái AI
    elif menu == "🤖 Trạng thái AI":
        st.header("🤖 Trạng thái Gemma AI")
        
        if gemini_model:
            st.success("✅ Gemma AI đã kết nối!")
            st.info("**Model:** models/gemma-3-4b-it")
            
            # Test AI
            st.subheader("🎯 Test AI")
            test_text = st.text_area("Nhập văn bản test:", "Chiến thắng Điện Biên Phủ 1954", height=100)
            
            if st.button("Tạo câu hỏi test"):
                with st.spinner("AI đang xử lý..."):
                    result = generate_quiz_questions_gemini(test_text, 1)
                    
                    if result:
                        st.success("✅ AI hoạt động tốt!")
                        q = result['questions'][0]
                        st.markdown(f"**Câu hỏi:** {q['question']}")
                        st.markdown(f"**A.** {q['options']['A']}")
                        st.markdown(f"**B.** {q['options']['B']}")
                        st.markdown(f"**C.** {q['options']['C']}")
                        st.markdown(f"**D.** {q['options']['D']}")
                        st.markdown(f"✅ **Đáp án:** {q['correct_answer']}")
                    else:
                        st.warning("⚠️ AI không tạo được câu hỏi")
        else:
            st.error("❌ Gemma AI chưa kết nối")
            
            st.markdown("""
            ### 🔧 Cấu hình API Key:
            
            1. **Lấy API Key:**
               - https://makersuite.google.com/app/apikey
               - Tạo API key mới
            
            2. **Thêm vào Streamlit:**
            ```toml
            # File .streamlit/secrets.toml
            GEMINI_API_KEY = "your_api_key_here"
            ```
            
            3. **Model sử dụng:** `models/gemma-3-4b-it`
            
            4. **Redeploy app** sau khi thêm key
            """)

if __name__ == "__main__":
    main()
