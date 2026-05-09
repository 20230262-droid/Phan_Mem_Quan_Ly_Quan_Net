import customtkinter as ctk
from tkinter import messagebox
import threading
import time

class ClientView(ctk.CTk):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.title("Quản lý máy client")
        self.geometry("400x300")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        if self.controller:
            self.create_widgets()
        self.start_time = None
        self.usage_timer_running = False

    def create_widgets(self):
        # Title
        self.lbl_title = ctk.CTkLabel(self, text="Quản lý máy client", font=ctk.CTkFont(size=20, weight="bold"))
        self.lbl_title.pack(pady=20)

        # Server IP input
        self.lbl_ip = ctk.CTkLabel(self, text="IP Server:")
        self.lbl_ip.pack(pady=5)
        self.txt_server_ip = ctk.CTkEntry(self, placeholder_text="Nhập IP Server (ví dụ 127.0.0.1)")
        self.txt_server_ip.pack(pady=5)

        # Connect button
        self.btn_connect = ctk.CTkButton(self, text="Kết nối", command=self.controller.connect_to_server)
        self.btn_connect.pack(pady=10)

        # Status label
        self.lbl_status = ctk.CTkLabel(self, text="Trạng thái: Đã ngắt kết nối", font=ctk.CTkFont(size=14))
        self.lbl_status.pack(pady=10)

        # Usage time label
        self.lbl_usage = ctk.CTkLabel(self, text="Thời gian sử dụng: 00:00:00", font=ctk.CTkFont(size=12))
        self.lbl_usage.pack(pady=5)

        # User management frame
        self.frame_user = ctk.CTkFrame(self)
        self.frame_user.pack(fill="x", padx=20, pady=10)

        self.lbl_user_title = ctk.CTkLabel(self.frame_user, text="Quản lý tài khoản", font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_user_title.pack(pady=10)

        # Username
        self.lbl_username = ctk.CTkLabel(self.frame_user, text="Tên đăng nhập:")
        self.lbl_username.pack(pady=2)
        self.txt_username = ctk.CTkEntry(self.frame_user, placeholder_text="Nhập tên đăng nhập")
        self.txt_username.pack(pady=2)

        # Password
        self.lbl_password = ctk.CTkLabel(self.frame_user, text="Mật khẩu:")
        self.lbl_password.pack(pady=2)
        self.txt_password = ctk.CTkEntry(self.frame_user, placeholder_text="Nhập mật khẩu", show="*")
        self.txt_password.pack(pady=2)

        # Buttons
        self.btn_login = ctk.CTkButton(self.frame_user, text="Đăng nhập", command=self.controller.login)
        self.btn_login.pack(pady=5)

        # Top up
        self.lbl_amount = ctk.CTkLabel(self.frame_user, text="Số tiền nạp:")
        self.lbl_amount.pack(pady=2)
        self.txt_amount = ctk.CTkEntry(self.frame_user, placeholder_text="Nhập số tiền")
        self.txt_amount.pack(pady=2)

        self.btn_topup = ctk.CTkButton(self.frame_user, text="Nạp tiền", command=self.controller.top_up)
        self.btn_topup.pack(pady=5)

        # User info
        self.lbl_user_info = ctk.CTkLabel(self.frame_user, text="Chưa đăng nhập", font=ctk.CTkFont(size=12))
        self.lbl_user_info.pack(pady=5)

    def update_user_info(self, info):
        self.lbl_user_info.configure(text=info)

    def update_status(self, status):
        self.lbl_status.configure(text=f"Trạng thái: {status}")

    def update_usage(self, usage_seconds):
        self.lbl_usage.configure(text=f"Thời gian sử dụng: {self._format_duration(usage_seconds)}")

    def _format_duration(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def show_message(self, title, message):
        messagebox.showinfo(title, message)

    def set_connect_button_text(self, text):
        self.btn_connect.configure(text=text)