# Internet Cafe Server

Ứng dụng server Python với giao diện đẹp cho quản lý clients trong quán net.

## Chức năng
- Chấp nhận kết nối từ clients
- Hiển thị danh sách clients với trạng thái, thời gian sử dụng
- Gửi lệnh đến client: LOCK, UNLOCK, SHUTDOWN

## Giao diện
- Sử dụng CustomTkinter với theme dark/blue
- Giao diện hiện đại với bảng danh sách clients

## Cách chạy
1. Cài đặt dependencies: `pip install -r requirements.txt`
2. Chạy `python server_main.py`

## Files
- `server_connection.py`: Logic server socket
- `server_main.py`: Điểm khởi đầu (MVC pattern)
- `requirements.txt`: Dependencies (customtkinter)
- `mvc/view/server_view.py`: Giao diện server
- `mvc/controller/server_controller.py`: Controller server