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
    .answer-correct {
        background-color: #d4edda !important;
        border-left: 5px solid #28a745 !important;
    }
    .answer-wrong {
        background-color: #f8d7da !important;
        border-left: 5px solid #dc3545 !important;
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

# ==================== KHỞI TẠO GEMINI AI (SỬA LỖI) ====================
def init_ai_model():
    try:
        # Lấy API key từ Streamlit secrets hoặc biến môi trường
        api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
        
        if not api_key:
            st.warning("⚠️ Chưa cấu hình Gemini API Key")
            return None
        
        # Cấu hình với API key
        genai.configure(api_key=api_key)
        
        # DÙNG MODEL ĐÚNG CỦA GEMINI
        # Các model có sẵn: gemini-1.5-pro, gemini-1.5-flash, gemini-pro
        model_name = 'gemini-1.5-flash'  # Model nhanh và miễn phí
        print(f"🤖 Sử dụng model: {model_name}")
        
        # Tạo model
        model = genai.GenerativeModel(model_name)
        
        # Test kết nối
        try:
            response = model.generate_content(
                "Xin chào! Hãy trả lời ngắn gọn: Bạn là ai?",
                generation_config={"max_output_tokens": 50}
            )
            
            if response and response.text:
                print(f"✅ Gemini AI đã sẵn sàng! Model: {model_name}")
                return model
            else:
                print("❌ Model không trả về kết quả")
                return None
                
        except Exception as e:
            print(f"❌ Lỗi test model: {str(e)}")
            # Thử model khác nếu model đầu không hoạt động
            try:
                model_name = 'gemini-pro'
                print(f"🔄 Thử model: {model_name}")
                model = genai.GenerativeModel(model_name)
                
                response = model.generate_content("Test")
                if response.text:
                    print(f"✅ Gemini AI đã sẵn sàng với model: {model_name}")
                    return model
            except:
                return None
                
    except Exception as e:
        print(f"❌ Lỗi khởi tạo Gemini: {str(e)[:200]}")
        return None

# Khởi tạo model (chỉ một lần)
@st.cache_resource
def get_gemini_model():
    return init_ai_model()

gemini_model = get_gemini_model()

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
    """
    Tạo câu hỏi trắc nghiệm bằng Google Gemini API
    """
    if not gemini_model:
        print("⚠️ Gemini không khả dụng, dùng câu hỏi mẫu")
        return None
    
    try:
        # Giới hạn độ dài văn bản
        text = text[:3000]
        
        prompt = f"""Bạn là giáo viên lịch sử. Tạo {num_questions} câu hỏi trắc nghiệm từ tài liệu sau:

TÀI LIỆU:
{text}

YÊU CẦU:
1. Tạo {num_questions} câu hỏi TRẮC NGHIỆM về lịch sử
2. Mỗi câu có 4 đáp án A, B, C, D
3. Chỉ MỘT đáp án đúng duy nhất
4. Có giải thích ngắn gọn cho đáp án đúng
5. Câu hỏi phải liên quan trực tiếp đến nội dung tài liệu

ĐỊNH DẠNG OUTPUT - PHẢI LÀ JSON:
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
            "explanation": "Giải thích tại sao đáp án A đúng"
        }}
    ]
}}

CHÚ Ý: Chỉ trả về JSON, không thêm bất kỳ text nào khác."""
        
        # Cấu hình generation
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.8,
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
        print(f"📝 Gemini response (first 300 chars): {result_text[:300]}...")
        
        # Làm sạch response
        result_text = result_text.replace('```json', '').replace('```', '').strip()
        
        # Tìm JSON trong response
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if not json_match:
            print(f"❌ Không tìm thấy JSON trong response")
            return None
            
        json_str = json_match.group()
        
        # Parse JSON
        quiz_data = json.loads(json_str)
        
        # Validate dữ liệu
        if "questions" not in quiz_data:
            print("❌ JSON không có key 'questions'")
            return None
            
        questions = quiz_data["questions"]
        if not isinstance(questions, list) or len(questions) == 0:
            print("❌ Questions không phải list hoặc rỗng")
            return None
            
        # Validate từng câu hỏi
        valid_questions = []
        for i, q in enumerate(questions):
            try:
                if ("question" in q and "options" in q and 
                    "correct_answer" in q):
                    # Đảm bảo có explanation
                    if "explanation" not in q:
                        q["explanation"] = "Không có giải thích"
                    
                    # Kiểm tra options
                    options = q["options"]
                    if isinstance(options, dict) and all(key in options for key in ["A", "B", "C", "D"]):
                        # Kiểm tra correct_answer
                        if q["correct_answer"] in ["A", "B", "C", "D"]:
                            valid_questions.append(q)
                        else:
                            print(f"⚠️ Câu {i+1}: correct_answer không hợp lệ")
                    else:
                        print(f"⚠️ Câu {i+1}: thiếu options đầy đủ")
                else:
                    print(f"⚠️ Câu {i+1}: thiếu trường bắt buộc")
            except Exception as e:
                print(f"⚠️ Lỗi validate câu {i+1}: {e}")
        
        if len(valid_questions) > 0:
            print(f"✅ Gemini tạo thành công {len(valid_questions)} câu hỏi")
            return {"questions": valid_questions[:num_questions]}
        else:
            print("❌ Không có câu hỏi nào hợp lệ từ Gemini")
            return None
            
    except json.JSONDecodeError as e:
        print(f"❌ Lỗi parse JSON từ Gemini: {e}")
        return None
    except Exception as e:
        print(f"❌ Lỗi Gemini API: {type(e).__name__}: {e}")
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
    
    # Thử dùng Gemini
    print("🤖 Đang sử dụng Gemini AI để tạo câu hỏi...")
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
    st.markdown('<h1 class="main-header">📚 Quiz Lịch Sử Tương Tác với AI</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/2237/2237288.png", width=100)
        st.title("🎮 Menu")
        
        menu = st.radio(
            "Chọn chức năng:",
            ["🏠 Trang chủ", "📤 Tạo Quiz mới", "🎯 Tham gia Quiz", "📊 Xem kết quả", "⚙️ Cấu hình AI"]
        )
        
        st.markdown("---")
        
        # Hiển thị trạng thái AI
        if gemini_model:
            st.success("✅ Gemini AI: ĐÃ KẾT NỐI")
        else:
            st.warning("⚠️ Gemini AI: CHƯA KẾT NỐI")
            st.info("Thêm API Key vào file `.streamlit/secrets.toml`")
        
        st.markdown("---")
        st.info("""
        **Hướng dẫn:**
        1. Upload file giáo án (.txt, .pdf, .docx)
        2. AI tự tạo câu hỏi
        3. Chia sẻ mã quiz
        4. Học sinh tham gia
        5. Xem kết quả real-time
        """)
    
    # Trang chủ
    if menu == "🏠 Trang chủ":
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.success("🎉 Chào mừng đến với hệ thống Quiz Lịch Sử thông minh!")
            st.markdown("""
            ### ✨ Tính năng nổi bật:
            
            - 🤖 **AI Tạo Câu Hỏi**: Tự động tạo câu hỏi từ giáo án lịch sử
            - 📤 **Hỗ Trợ Nhiều Định Dạng**: TXT, PDF, DOCX
            - 🎯 **Tham Gian Dễ Dàng**: Chỉ cần mã quiz 6 ký tự
            - 📊 **Kết Quả Real-time**: Bảng xếp hạng cập nhật ngay lập tức
            - 📱 **Responsive**: Hoạt động tốt trên điện thoại
            
            ### 🚀 Bắt đầu ngay:
            1. Chọn **"Tạo Quiz mới"** ở menu bên trái
            2. Upload file giáo án lịch sử
            3. AI sẽ tự động tạo câu hỏi
            4. Chia sẻ mã quiz cho học sinh
            """)
        
        with col2:
            st.markdown("### 📋 Quiz đang hoạt động")
            
            # Hiển thị quiz gần đây
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
                st.info("📭 Chưa có quiz nào được tạo")
    
    # Tạo Quiz mới
    elif menu == "📤 Tạo Quiz mới":
        st.header("📤 Tạo Quiz mới từ file giáo án")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            uploaded_file = st.file_uploader(
                "📁 Chọn file giáo án (.txt, .pdf, .docx)",
                type=['txt', 'pdf', 'docx'],
                help="Upload file giáo án lịch sử để AI tạo câu hỏi tự động"
            )
            
            if uploaded_file:
                # Xem trước file
                with st.expander("👁️ Xem trước nội dung file"):
                    text = extract_text_from_file(uploaded_file)
                    if len(text) > 1000:
                        st.text_area("Nội dung", text[:1000] + "...", height=200)
                    else:
                        st.text_area("Nội dung", text, height=200)
        
        with col2:
            num_questions = st.slider(
                "Số lượng câu hỏi",
                min_value=3,
                max_value=20,
                value=5,
                help="Chọn số câu hỏi muốn tạo"
            )
            
            quiz_title = st.text_input(
                "Tiêu đề quiz",
                value=f"Quiz Lịch Sử",
                help="Đặt tên cho quiz của bạn"
            )
        
        if uploaded_file and st.button("🚀 Tạo Quiz", type="primary", use_container_width=True):
            with st.spinner("🤖 AI đang tạo câu hỏi..."):
                # Đọc file
                text = extract_text_from_file(uploaded_file)
                
                if len(text) < 100:
                    st.error("❌ File quá ngắn. Vui lòng upload file có nội dung đầy đủ (ít nhất 100 ký tự).")
                else:
                    # Tạo câu hỏi
                    quiz_data = generate_quiz_questions(text, num_questions)
                    
                    # Tạo mã quiz
                    quiz_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                    
                    # Lưu vào database
                    conn = sqlite3.connect('quiz_system.db')
                    c = conn.cursor()
                    
                    # Lưu thông tin quiz
                    c.execute('''INSERT INTO quizzes (quiz_code, title, created_at, question_count) 
                                 VALUES (?, ?, ?, ?)''',
                             (quiz_code, quiz_title, datetime.now(), len(quiz_data['questions'])))
                    quiz_id = c.lastrowid
                    
                    # Lưu các câu hỏi
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
                    st.success(f"✅ Đã tạo quiz thành công!")
                    
                    col_code, col_count = st.columns(2)
                    with col_code:
                        st.info(f"**Mã Quiz:** `{quiz_code}`")
                    with col_count:
                        st.info(f"**Số câu hỏi:** {len(quiz_data['questions'])}")
                    
                    # Nút sao chép mã
                    st.code(quiz_code)
                    
                    # Xem trước câu hỏi
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
                            st.markdown(f"✅ **Đáp án đúng:** {q['correct_answer']}")
                            st.markdown(f"💡 **Giải thích:** {q.get('explanation', 'Không có giải thích')}")
                            st.markdown("---")
    
    # Tham gia Quiz
    elif menu == "🎯 Tham gia Quiz":
        st.header("🎯 Tham gia làm Quiz")
        
        quiz_code = st.text_input(
            "Nhập mã Quiz:",
            placeholder="VD: ABC123",
            help="Nhập mã 6 ký tự mà giáo viên cung cấp"
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
                    # Form làm bài
                    student_name = st.text_input(
                        "Tên của bạn:",
                        placeholder="Nhập tên hoặc biệt danh",
                        help="Tên sẽ hiển thị trên bảng xếp hạng"
                    )
                    
                    if student_name:
                        st.markdown("---")
                        st.subheader(f"📝 Bài thi: {quiz['title']}")
                        st.write(f"**Số câu:** {len(questions)}")
                        
                        # Lưu câu trả lời trong session state
                        if 'answers' not in st.session_state:
                            st.session_state.answers = {}
                        
                        answers = st.session_state.answers
                        
                        for i, q in enumerate(questions):
                            st.markdown(f"### Câu {i+1}: {q['question_text']}")
                            
                            # Tạo các nút lựa chọn
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
                            
                            # Hiển thị đã chọn
                            if str(q['id']) in answers:
                                selected = answers[str(q['id'])]
                                option_text = {
                                    'A': q['option_a'],
                                    'B': q['option_b'],
                                    'C': q['option_c'],
                                    'D': q['option_d']
                                }
                                st.info(f"✅ Bạn đã chọn: **{selected}** - {option_text[selected]}")
                            
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
                                grade = "Cần cố gắng hơn"
                            
                            st.markdown(f"""
                            <div class="score-card">
                                <h1>{emoji}</h1>
                                <h2>{grade}</h2>
                                <h3>Điểm: {score}/{len(questions)}</h3>
                                <p>Tỉ lệ: {percentage:.1f}%</p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Chi tiết từng câu
                            with st.expander("📋 Xem chi tiết từng câu"):
                                for i, detail in enumerate(details):
                                    if detail['is_correct']:
                                        st.success(f"**Câu {i+1}:** {detail['question']}")
                                        st.markdown(f"✅ Bạn chọn: **{detail['user_answer']}** (Đúng)")
                                    else:
                                        st.error(f"**Câu {i+1}:** {detail['question']}")
                                        st.markdown(f"❌ Bạn chọn: **{detail['user_answer']}**")
                                        st.markdown(f"✅ Đáp án đúng: **{detail['correct_answer']}**")
                                    
                                    st.markdown(f"💡 Giải thích: {detail['explanation']}")
                                    st.markdown("---")
                            
                            # Xóa session state
                            if 'answers' in st.session_state:
                                del st.session_state.answers
                            
                            st.balloons()
    
    # Xem kết quả
    elif menu == "📊 Xem kết quả":
        st.header("📊 Bảng xếp hạng")
        
        quiz_code = st.text_input(
            "Nhập mã Quiz để xem kết quả:",
            placeholder="VD: ABC123",
            help="Nhập mã quiz để xem bảng xếp hạng"
        ).strip().upper()
        
        if quiz_code:
            conn = sqlite3.connect('quiz_system.db')
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            
            # Kiểm tra quiz
            c.execute('SELECT title, question_count FROM quizzes WHERE quiz_code = ?', (quiz_code,))
            quiz = c.fetchone()
            
            if not quiz:
                st.error("❌ Quiz không tồn tại!")
            else:
                st.success(f"📚 Quiz: **{quiz['title']}**")
                
                # Lấy kết quả
                c.execute('''SELECT 
                                student_name, 
                                score, 
                                total_questions,
                                strftime('%d/%m/%Y %H:%M', submitted_at) as submitted_at
                             FROM results 
                             WHERE quiz_code = ? 
                             ORDER BY score DESC, submitted_at''', (quiz_code,))
                results = c.fetchall()
                
                if not results:
                    st.info("📭 Chưa có ai làm bài quiz này.")
                else:
                    # Thống kê
                    total_participants = len(results)
                    avg_score = sum(r['score'] for r in results) / total_participants if total_participants > 0 else 0
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Tổng thí sinh", total_participants)
                    with col2:
                        st.metric("Điểm trung bình", f"{avg_score:.1f}")
                    with col3:
                        st.metric("Tổng câu hỏi", quiz['question_count'])
                    
                    # Bảng xếp hạng
                    st.subheader("🏆 Bảng xếp hạng")
                    
                    for i, r in enumerate(results):
                        percentage = (r['score'] / r['total_questions']) * 100 if r['total_questions'] > 0 else 0
                        
                        if i == 0:
                            st.markdown(f"""
                            <div style="background-color: #FFD700; padding: 15px; border-radius: 10px; margin: 10px 0;">
                                <h4>🥇 Hạng {i+1}: {r['student_name']}</h4>
                                <p>Điểm: {r['score']}/{r['total_questions']} ({percentage:.1f}%)</p>
                                <small>Thời gian: {r['submitted_at']}</small>
                            </div>
                            """, unsafe_allow_html=True)
                        elif i == 1:
                            st.markdown(f"""
                            <div style="background-color: #C0C0C0; padding: 15px; border-radius: 10px; margin: 10px 0;">
                                <h4>🥈 Hạng {i+1}: {r['student_name']}</h4>
                                <p>Điểm: {r['score']}/{r['total_questions']} ({percentage:.1f}%)</p>
                                <small>Thời gian: {r['submitted_at']}</small>
                            </div>
                            """, unsafe_allow_html=True)
                        elif i == 2:
                            st.markdown(f"""
                            <div style="background-color: #CD7F32; padding: 15px; border-radius: 10px; margin: 10px 0;">
                                <h4>🥉 Hạng {i+1}: {r['student_name']}</h4>
                                <p>Điểm: {r['score']}/{r['total_questions']} ({percentage:.1f}%)</p>
                                <small>Thời gian: {r['submitted_at']}</small>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                            <div style="background-color: #f0f0f0; padding: 10px; border-radius: 5px; margin: 5px 0;">
                                <strong>#{i+1}: {r['student_name']}</strong> - {r['score']} điểm ({percentage:.1f}%)
                                <br><small>{r['submitted_at']}</small>
                            </div>
                            """, unsafe_allow_html=True)
            
            conn.close()
    
    # Cấu hình AI
    elif menu == "⚙️ Cấu hình AI":
        st.header("⚙️ Cấu hình Gemini AI")
        
        if gemini_model:
            st.success("✅ Gemini AI đã kết nối thành công!")
            
            # Test AI
            st.subheader("🤖 Test AI")
            test_text = st.text_area(
                "Nhập văn bản để test AI:", 
                "Chiến thắng Điện Biên Phủ năm 1954 là một sự kiện lịch sử quan trọng của Việt Nam.",
                height=100
            )
            
            if st.button("🎯 Tạo câu hỏi test"):
                with st.spinner("AI đang xử lý..."):
                    result = generate_quiz_questions_gemini(test_text, 2)
                    
                    if result:
                        st.success("✅ AI tạo câu hỏi thành công!")
                        for i, q in enumerate(result['questions']):
                            st.markdown(f"**Câu {i+1}:** {q['question']}")
                            cols = st.columns(2)
                            with cols[0]:
                                st.markdown(f"**A.** {q['options']['A']}")
                                st.markdown(f"**B.** {q['options']['B']}")
                            with cols[1]:
                                st.markdown(f"**C.** {q['options']['C']}")
                                st.markdown(f"**D.** {q['options']['D']}")
                            st.markdown(f"✅ **Đáp án:** {q['correct_answer']}")
                            st.markdown(f"💡 **Giải thích:** {q['explanation']}")
                            st.markdown("---")
                    else:
                        st.warning("⚠️ Không thể tạo câu hỏi bằng AI.")
        else:
            st.error("❌ Gemini AI chưa được cấu hình!")
            
            st.markdown("""
            ### 📝 Hướng dẫn cấu hình:
            
            1. **Lấy API Key từ Google AI Studio:**
               - Truy cập: https://makersuite.google.com/app/apikey
               - Đăng nhập bằng tài khoản Google
               - Tạo API key mới
            
            2. **Thêm API Key vào Streamlit:**
               - Tạo file `.streamlit/secrets.toml`
               - Thêm dòng sau:
            ```
            GEMINI_API_KEY = "your_api_key_here"
            ```
            
            3. **Hoặc thêm vào biến môi trường:**
               - Trên Streamlit Cloud: Settings → Secrets
               - Thêm biến: `GEMINI_API_KEY`
            
            4. **Model hỗ trợ:**
               - `gemini-1.5-flash` (nhanh, miễn phí)
               - `gemini-1.5-pro` (chất lượng cao)
               - `gemini-pro` (phiên bản cũ)
            """)
            
            # Manual API Key input (for testing)
            with st.expander("🔧 Nhập API Key thủ công (chỉ để test)"):
                manual_key = st.text_input("Nhập API Key:", type="password")
                if manual_key and st.button("Test kết nối"):
                    try:
                        genai.configure(api_key=manual_key)
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        response = model.generate_content("Test")
                        if response.text:
                            st.success("✅ Kết nối thành công!")
                        else:
                            st.error("❌ Kết nối thất bại")
                    except Exception as e:
                        st.error(f"❌ Lỗi: {str(e)}")

if __name__ == "__main__":
    main()
