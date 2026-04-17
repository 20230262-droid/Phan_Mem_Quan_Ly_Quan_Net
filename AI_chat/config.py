# Cấu hình Groq — điền key tại đây (https://console.groq.com/keys)
# Nếu vẫn nhận lỗi 403, kiểm tra lại GROQ_API_KEY và GROQ_API_URL.
GROQ_API_KEY = "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"

# Bật/tắt trả lời tự động khi không có nhân viên trả lời trong khoảng thời gian chờ
ENABLE_AUTO_REPLY = True

# Thời gian chờ (ms) sau tin nhắn từ máy trạm trước khi gọi AI
AUTO_REPLY_DELAY_MS = 10_000

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"

SYSTEM_PROMPT = (
    "Bạn là nhân viên hỗ trợ quán internet (quán net) tại Việt Nam. "
    "Trả lời ngắn gọn, lịch sự, tiếng Việt. "
    "Nếu khách hỏi giá hoặc dịch vụ mà bạn không chắc, hãy đề nghị họ chờ nhân viên hoặc liên hệ quầy."
)

# Số tin gần nhất đưa vào ngữ cảnh (tránh prompt quá dài)
MAX_HISTORY_MESSAGES = 24

# In lỗi Groq ra console (hữu ích khi không thấy tin AI)
LOG_AUTO_REPLY_ERRORS = True
