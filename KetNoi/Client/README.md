# Internet Cafe Client

Ứng dụng client Python với giao diện đẹp cho quản lý máy trong quán net.

## Chức năng
- Kết nối đến server qua IP
- Theo dõi trạng thái máy (AVAILABLE, LOCKED)
- Gửi thời gian sử dụng mỗi phút
- Nhận lệnh từ server: LOCK, UNLOCK, SHUTDOWN

## Giao diện
- Sử dụng CustomTkinter với theme dark/blue
- Giao diện hiện đại, responsive

## Cách chạy
1. Đảm bảo Python 3.x đã cài đặt.
2. Cài đặt dependencies: `pip install -r requirements.txt`
3. Để test trên 1 máy, chạy `python main/main.py` từ thư mục root để khởi động cả server và client.
4. Hoặc chạy riêng `python main.py` trong thư mục Client (nhập IP server là 127.0.0.1).

## Files
- `connection.py`: Logic kết nối TCP
- `main.py`: Điểm khởi đầu (MVC pattern)
- `requirements.txt`: Dependencies (customtkinter)
- `mvc/view/client_view.py`: Giao diện client
- `mvc/controller/client_controller.py`: Controller client