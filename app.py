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
    }
    .quiz-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        border-left: 5px solid #3B82F6;
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
    }
    .stButton > button:hover {
        background-color: #2563EB;
        color: white;
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

# ==================== KHỞI TẠO GEMINI AI ====================
def init_ai_model():
    try:
        # Lấy API key từ secrets hoặc môi trường
        api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
        
        if not api_key:
            st.warning("⚠️ Chưa cấu hình Gemini API Key. Sẽ sử dụng câu hỏi mẫu.")
            return None
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Test connection
        test_response = model.generate_content("Test", generation_config={"max_output_tokens": 5})
        if test_response.text:
            st.success("✅ Gemini AI đã sẵn sàng!")
            return model
        return None
    except Exception as e:
        st.error(f"❌ Lỗi khởi tạo Gemini: {str(e)[:100]}")
        return None

# Khởi tạo model
gemini_model = init_ai_model()

# ==================== HÀM HELPER ====================
def extract_text_from_file(uploaded_file):
    """Trích xuất text từ file upload"""
    file_type = uploaded_file.name.split('.')[-1].lower()
    
    if file_type == 'txt':
        return uploaded_file.read().decode('utf-8')
    
    elif file_type == 'pdf':
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(uploaded_file.read()))
            text = ""
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text
        except:
            return f"[PDF File: {uploaded_file.name}]"
    
    elif file_type == 'docx':
        try:
            doc = docx.Document(io.BytesIO(uploaded_file.read()))
            text = ""
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text += paragraph.text + "\n"
            return text
        except:
            return f"[DOCX File: {uploaded_file.name}]"
    
    return ""

def get_sample_questions():
    """Câu hỏi mẫu"""
    return {
        "questions": [
            {
                "question": "Chiến thắng Điện Biên Phủ diễn ra vào năm nào?",
                "options": {"A": "1953", "B": "1954", "C": "1975", "D": "1945"},
                "correct_answer": "B",
                "explanation": "Chiến dịch Điện Biên Phủ kết thúc thắng lợi vào ngày 7/5/1954."
            },
            {
                "question": "Ai là tác giả của Bản Tuyên ngôn Độc lập 2/9/1945?",
                "options": {"A": "Hồ Chí Minh", "B": "Trường Chinh", "C": "Phạm Văn Đồng", "D": "Võ Nguyên Giáp"},
                "correct_answer": "A",
                "explanation": "Chủ tịch Hồ Chí Minh đọc bản Tuyên ngôn Độc lập tại Quảng trường Ba Đình."
            }
        ]
    }

def generate_quiz_questions_gemini(text, num_questions=5):
    """Tạo câu hỏi bằng Gemini AI"""
    if not gemini_model:
        return None
    
    try:
        prompt = f"""Bạn là giáo viên lịch sử. Tạo {num_questions} câu hỏi trắc nghiệm từ tài liệu sau:

{text[:3000]}

YÊU CẦU:
1. {num_questions} câu trắc nghiệm 4 đáp án
2. Chỉ một đáp án đúng
3. Có giải thích ngắn
4. Trả về JSON format:
{{
    "questions": [
        {{
            "question": "...",
            "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
            "correct_answer": "A",
            "explanation": "..."
        }}
    ]
}}

CHỈ TRẢ VỀ JSON, không thêm text khác."""
        
        response = gemini_model.generate_content(
            prompt,
            generation_config={"max_output_tokens": 2000}
        )
        
        if response.text:
            result_text = response.text.strip()
            result_text = result_text.replace('```json', '').replace('```', '').strip()
            
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                quiz_data = json.loads(json_match.group())
                if "questions" in quiz_data:
                    return {"questions": quiz_data["questions"][:num_questions]}
    except:
        pass
    
    return None

def generate_quiz_questions(text, num_questions=5):
    """Tạo câu hỏi (AI hoặc mẫu)"""
    if len(text.strip()) < 50:
        sample = get_sample_questions()
        sample["questions"] = sample["questions"][:num_questions]
        return sample
    
    ai_result = generate_quiz_questions_gemini(text, num_questions)
    if ai_result:
        return ai_result
    
    sample = get_sample_questions()
    sample["questions"] = sample["questions"][:num_questions]
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
            ["🏠 Trang chủ", "📤 Tạo Quiz mới", "🎯 Tham gia Quiz", "📊 Xem kết quả", "🤖 Test AI"]
        )
        
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
        st.success("🎉 Chào mừng đến với hệ thống Quiz Lịch Sử thông minh!")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            <div class="quiz-card">
                <h3>📤 Tạo Quiz</h3>
                <p>Upload file giáo án, AI tự động tạo câu hỏi</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div class="quiz-card">
                <h3>🎯 Tham gia</h3>
                <p>Nhập mã quiz để làm bài</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
            <div class="quiz-card">
                <h3>📊 Kết quả</h3>
                <p>Xem bảng xếp hạng real-time</p>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.subheader("📋 Quiz đang hoạt động")
        
        # Hiển thị quiz gần đây
        conn = sqlite3.connect('quiz_system.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM quizzes WHERE is_active = 1 ORDER BY created_at DESC LIMIT 5')
        recent_quizzes = c.fetchall()
        conn.close()
        
        for quiz in recent_quizzes:
            st.markdown(f"""
            <div class="quiz-card">
                <h4>{quiz['title']}</h4>
                <p>Mã: <strong>{quiz['quiz_code']}</strong> | Số câu: {quiz['question_count']}</p>
                <small>Tạo: {quiz['created_at'][:10]}</small>
            </div>
            """, unsafe_allow_html=True)
    
    # Tạo Quiz mới
    elif menu == "📤 Tạo Quiz mới":
        st.header("📤 Tạo Quiz mới từ file giáo án")
        
        with st.form("create_quiz_form"):
            uploaded_file = st.file_uploader(
                "Chọn file giáo án (.txt, .pdf, .docx)",
                type=['txt', 'pdf', 'docx']
            )
            
            num_questions = st.slider("Số lượng câu hỏi", 3, 20, 5)
            quiz_title = st.text_input("Tiêu đề quiz", "Quiz Lịch Sử")
            
            submitted = st.form_submit_button("🚀 Tạo Quiz", use_container_width=True)
            
            if submitted and uploaded_file:
                with st.spinner("🤖 AI đang tạo câu hỏi..."):
                    # Đọc file
                    text = extract_text_from_file(uploaded_file)
                    
                    if len(text) < 100:
                        st.error("File quá ngắn. Vui lòng upload file có nội dung đầy đủ.")
                    else:
                        # Tạo câu hỏi
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
                        st.success(f"✅ Đã tạo quiz thành công!")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.info(f"**Mã Quiz:** `{quiz_code}`")
                        with col2:
                            st.info(f"**Số câu hỏi:** {len(quiz_data['questions'])}")
                        
                        # Xem trước câu hỏi
                        with st.expander("👁️ Xem trước câu hỏi"):
                            for i, q in enumerate(quiz_data['questions']):
                                st.markdown(f"**Câu {i+1}:** {q['question']}")
                                st.markdown(f"A. {q['options']['A']}")
                                st.markdown(f"B. {q['options']['B']}")
                                st.markdown(f"C. {q['options']['C']}")
                                st.markdown(f"D. {q['options']['D']}")
                                st.markdown(f"✅ Đáp án đúng: **{q['correct_answer']}**")
                                st.markdown("---")
    
    # Tham gia Quiz
    elif menu == "🎯 Tham gia Quiz":
        st.header("🎯 Tham gia làm Quiz")
        
        quiz_code = st.text_input("Nhập mã Quiz:", placeholder="VD: ABC123").strip().upper()
        
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
                    student_name = st.text_input("Tên của bạn:", placeholder="Nhập tên hoặc biệt danh")
                    
                    if student_name:
                        st.markdown("---")
                        st.subheader("📝 Bắt đầu làm bài")
                        
                        answers = {}
                        for i, q in enumerate(questions):
                            st.markdown(f"**Câu {i+1}:** {q['question_text']}")
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button(f"A: {q['option_a']}", key=f"q{i}_A", use_container_width=True):
                                    answers[str(q['id'])] = "A"
                                if st.button(f"B: {q['option_b']}", key=f"q{i}_B", use_container_width=True):
                                    answers[str(q['id'])] = "B"
                            with col2:
                                if st.button(f"C: {q['option_c']}", key=f"q{i}_C", use_container_width=True):
                                    answers[str(q['id'])] = "C"
                                if st.button(f"D: {q['option_d']}", key=f"q{i}_D", use_container_width=True):
                                    answers[str(q['id'])] = "D"
                            
                            # Hiển thị đã chọn
                            if str(q['id']) in answers:
                                st.info(f"✅ Bạn đã chọn: **{answers[str(q['id'])]}**")
                            
                            st.markdown("---")
                        
                        # Nộp bài
                        if st.button("📤 Nộp bài", type="primary", use_container_width=True):
                            if len(answers) < len(questions):
                                st.warning(f"⚠️ Bạn mới trả lời {len(answers)}/{len(questions)} câu. Vẫn nộp?")
                            
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
    
    # Xem kết quả
    elif menu == "📊 Xem kết quả":
        st.header("📊 Bảng xếp hạng")
        
        quiz_code = st.text_input("Nhập mã Quiz để xem kết quả:", placeholder="VD: ABC123").strip().upper()
        
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
                    avg_score = sum(r['score'] for r in results) / total_participants
                    
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
                        percentage = (r['score'] / r['total_questions']) * 100
                        
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
    
    # Test AI
    elif menu == "🤖 Test AI":
        st.header("🤖 Kiểm tra Gemini AI")
        
        if gemini_model:
            st.success("✅ Gemini AI đã kết nối thành công!")
            
            test_text = st.text_area("Nhập văn bản để test AI:", 
                                     "Chiến thắng Điện Biên Phủ năm 1954 là một sự kiện lịch sử quan trọng của Việt Nam.")
            
            if st.button("🎯 Tạo câu hỏi test", type="primary"):
                with st.spinner("AI đang xử lý..."):
                    result = generate_quiz_questions_gemini(test_text, 2)
                    
                    if result:
                        st.success("✅ AI tạo câu hỏi thành công!")
                        for q in result['questions']:
                            st.markdown(f"**{q['question']}**")
                            st.markdown(f"A. {q['options']['A']}")
                            st.markdown(f"B. {q['options']['B']}")
                            st.markdown(f"C. {q['options']['C']}")
                            st.markdown(f"D. {q['options']['D']}")
                            st.markdown(f"✅ **Đáp án:** {q['correct_answer']}")
                            st.markdown(f"💡 **Giải thích:** {q['explanation']}")
                            st.markdown("---")
                    else:
                        st.warning("⚠️ Không thể tạo câu hỏi bằng AI. Kiểm tra API Key.")
        else:
            st.warning("⚠️ Gemini AI chưa được cấu hình.")
            st.info("""
            **Cấu hình API Key:**
            1. Lấy API Key từ: https://makersuite.google.com/app/apikey
            2. Thêm vào Streamlit Secrets (.streamlit/secrets.toml)
            ```
            GEMINI_API_KEY = "your_api_key_here"
            ```
            3. Hoặc thêm vào biến môi trường
            """)

if __name__ == "__main__":
    main()
