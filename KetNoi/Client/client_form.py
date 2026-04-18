import tkinter as tk
from tkinter import messagebox
import threading
from connection import Connection
import time

class ClientForm:
    def __init__(self, root):
        self.root = root
        self.root.title("Quản lý máy client")
        self.root.geometry("350x150")

        self.connection = None
        self.start_time = None
        self.usage_timer_running = False

        # UI Elements
        self.lbl_ip = tk.Label(root, text="IP Server:")
        self.lbl_ip.pack(pady=5)

        self.txt_server_ip = tk.Entry(root, width=30)
        self.txt_server_ip.insert(0, "Nhập IP Server")
        self.txt_server_ip.pack(pady=5)

        self.btn_connect = tk.Button(root, text="Kết nối", command=self.btn_connect_click)
        self.btn_connect.pack(pady=5)

        self.lbl_status = tk.Label(root, text="Trạng thái: Đã ngắt kết nối")
        self.lbl_status.pack(pady=5)

        # Timer for usage
        self.usage_timer = threading.Timer(60.0, self.send_usage_time)
        self.usage_timer.daemon = True

    def btn_connect_click(self):
        ip = self.txt_server_ip.get().strip()
        if not ip or ip == "Nhập IP Server":
            messagebox.showerror("Lỗi", "Vui lòng nhập IP server hợp lệ")
            return

        if self.connection and self.connection.is_connected:
            self.connection.disconnect()
            self.lbl_status.config(text="Trạng thái: Đã ngắt kết nối")
            self.btn_connect.config(text="Kết nối")
            self.stop_usage_timer()
        else:
            self.connection = Connection(ip)
            self.connection.on_message_received = self.on_message_received
            self.connection.on_disconnected = self.on_disconnected

            if self.connection.connect():
                self.lbl_status.config(text="Trạng thái: Đã kết nối")
                self.btn_connect.config(text="Ngắt kết nối")
                self.start_time = time.time()
                self.start_usage_timer()
                self.connection.send_status("AVAILABLE")
            else:
                self.lbl_status.config(text="Trạng thái: Kết nối thất bại")

    def on_message_received(self, message):
        if message == "LOCK":
            messagebox.showinfo("Đã khóa", "Máy đã bị khóa bởi server")
            self.connection.send_status("LOCKED")
        elif message == "UNLOCK":
            messagebox.showinfo("Đã mở khóa", "Máy đã được mở khóa")
            self.connection.send_status("AVAILABLE")
        elif message == "SHUTDOWN":
            messagebox.showinfo("Tắt máy", "Máy sẽ tắt ngay bây giờ")
            self.root.quit()

    def on_disconnected(self):
        self.lbl_status.config(text="Trạng thái: Đã ngắt kết nối")
        self.btn_connect.config(text="Kết nối")
        self.stop_usage_timer()

    def start_usage_timer(self):
        if not self.usage_timer_running:
            self.usage_timer_running = True
            self.send_usage_time()

    def stop_usage_timer(self):
        self.usage_timer_running = False
        if self.usage_timer.is_alive():
            self.usage_timer.cancel()

    def send_usage_time(self):
        if self.connection and self.connection.is_connected and self.start_time:
            usage_seconds = time.time() - self.start_time
            usage_minutes = usage_seconds / 60
            self.connection.send_usage_time(usage_minutes)
        if self.usage_timer_running:
            self.usage_timer = threading.Timer(60.0, self.send_usage_time)
            self.usage_timer.daemon = True
            self.usage_timer.start()