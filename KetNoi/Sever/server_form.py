import tkinter as tk
from tkinter import ttk, messagebox
from server_connection import Server
import threading

class ServerForm:
    def __init__(self, root):
        self.root = root
        self.root.title("Quản lý máy chủ quán net")
        self.root.geometry("600x400")

        self.server = Server()
        self.server.on_client_update = self.update_clients_list

        # UI Elements
        self.btn_start = tk.Button(root, text="Bật server", command=self.start_server)
        self.btn_start.pack(pady=10)

        self.lbl_status = tk.Label(root, text="Máy chủ: Đã dừng")
        self.lbl_status.pack(pady=5)

        # Clients list
        self.tree = ttk.Treeview(root, columns=("ID", "Status", "Usage", "Last Seen"), show="headings")
        self.tree.heading("ID", text="Mã máy")
        self.tree.heading("Status", text="Trạng thái")
        self.tree.heading("Usage", text="Thời gian")
        self.tree.heading("Last Seen", text="Lần cuối (giây)")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Buttons for commands
        self.btn_lock = tk.Button(root, text="Khóa máy", command=self.lock_selected)
        self.btn_lock.pack(side=tk.LEFT, padx=10)

        self.btn_unlock = tk.Button(root, text="Mở khóa máy", command=self.unlock_selected)
        self.btn_unlock.pack(side=tk.LEFT, padx=10)

        self.btn_shutdown = tk.Button(root, text="Tắt máy", command=self.shutdown_selected)
        self.btn_shutdown.pack(side=tk.LEFT, padx=10)

        self.btn_refresh = tk.Button(root, text="Làm mới", command=self.update_clients_list)
        self.btn_refresh.pack(side=tk.RIGHT, padx=10)

    def start_server(self):
        if not self.server.running:
            self.server.start()
            self.lbl_status.config(text="Máy chủ: Đang chạy")
            self.btn_start.config(text="Tắt server", command=self.stop_server)
        else:
            self.stop_server()

    def stop_server(self):
        self.server.stop()
        self.lbl_status.config(text="Máy chủ: Đã dừng")
        self.btn_start.config(text="Bật server", command=self.start_server)
        self.update_clients_list()

    def update_clients_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        clients = self.server.get_clients_info()
        for client in clients:
            self.tree.insert("", tk.END, values=(client['id'], client['status'], self._format_duration(client['usage']), f"{client['last_seen']:.1f}"))

    def get_selected_client(self):
        selected = self.tree.selection()
        if selected:
            item = self.tree.item(selected[0])
            client_id = int(item['values'][0]) - 1
            clients = list(self.server.clients.keys())
            if client_id < len(clients):
                return clients[client_id]
        return None

    def _format_duration(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def lock_selected(self):
        client = self.get_selected_client()
        if client:
            self.server.send_command(client, "LOCK")
            messagebox.showinfo("Thông báo", "Đã gửi lệnh khóa đến máy được chọn")

    def unlock_selected(self):
        client = self.get_selected_client()
        if client:
            self.server.send_command(client, "UNLOCK")
            messagebox.showinfo("Thông báo", "Đã gửi lệnh mở khóa đến máy được chọn")

    def shutdown_selected(self):
        client = self.get_selected_client()
        if client:
            self.server.send_command(client, "SHUTDOWN")
            messagebox.showinfo("Thông báo", "Đã gửi lệnh tắt máy đến máy được chọn")