import customtkinter as ctk
from tkinter import messagebox

class ServerView(ctk.CTk):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.title("Quản lý máy chủ quán net")
        self.geometry("1000x650")
        self.resizable(True, True)
        self.minsize(1000, 650)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.selected_client_index = None
        self.client_cards = []
        self.detail_window = None
        if self.controller:
            self.create_widgets()

    def create_widgets(self):
        # Title
        self.lbl_title = ctk.CTkLabel(self, text="Quản lý máy chủ", font=ctk.CTkFont(size=26, weight="bold"))
        self.lbl_title.pack(pady=20)

        # Server control frame
        self.frame_top = ctk.CTkFrame(self)
        self.frame_top.pack(fill="x", padx=20, pady=(0, 10))

        self.btn_start = ctk.CTkButton(self.frame_top, text="Bật server", command=self.controller.start_server, width=180, height=40)
        self.btn_start.pack(side="left", padx=(0, 10))

        self.lbl_status = ctk.CTkLabel(self.frame_top, text="Máy chủ: Đã dừng", font=ctk.CTkFont(size=16))
        self.lbl_status.pack(side="left", padx=10)

        self.btn_refresh = ctk.CTkButton(self.frame_top, text="Làm mới", command=self.controller.update_clients_list, width=120, height=40)
        self.btn_refresh.pack(side="right", padx=(10, 0))

        # Main content split using grid for stable layout
        self.frame_main = ctk.CTkFrame(self)
        self.frame_main.pack(fill="both", expand=True, padx=20, pady=10)
        self.frame_main.rowconfigure(0, weight=1)
        self.frame_main.columnconfigure(0, weight=3)
        self.frame_main.columnconfigure(1, weight=1)

        self.frame_grid = ctk.CTkFrame(self.frame_main)
        self.frame_grid.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=10)

        self.frame_detail = ctk.CTkFrame(self.frame_main, width=320)
        self.frame_detail.grid(row=0, column=1, sticky="nsew", pady=10)
        self.frame_detail.grid_propagate(False)

        self.lbl_clients = ctk.CTkLabel(self.frame_grid, text="Các máy đang kết nối", font=ctk.CTkFont(size=18, weight="bold"))
        self.lbl_clients.pack(pady=(0, 10))

        self.cards_container = ctk.CTkScrollableFrame(self.frame_grid)
        self.cards_container.pack(fill="both", expand=True)

        self.lbl_no_clients = ctk.CTkLabel(self.cards_container, text="Chưa có máy nào kết nối", font=ctk.CTkFont(size=14))
        self.lbl_no_clients.pack(expand=True)

        self.lbl_detail_title = ctk.CTkLabel(self.frame_detail, text="Chi tiết máy", font=ctk.CTkFont(size=18, weight="bold"))
        self.lbl_detail_title.pack(pady=(0, 10))

        self.detail_info = ctk.CTkLabel(self.frame_detail, text="Chọn máy để xem chi tiết", justify="left", anchor="w", font=ctk.CTkFont(size=14))
        self.detail_info.pack(fill="x", padx=10, pady=10)

        self.frame_status = ctk.CTkFrame(self.frame_detail)
        self.frame_status.pack(fill="x", padx=10, pady=10)

        self.lbl_selected_id = ctk.CTkLabel(self.frame_status, text="Máy: -", anchor="w")
        self.lbl_selected_id.pack(fill="x", pady=(0, 5))

        self.lbl_selected_status = ctk.CTkLabel(self.frame_status, text="Trạng thái: -", anchor="w")
        self.lbl_selected_status.pack(fill="x", pady=(0, 5))

        self.lbl_selected_usage = ctk.CTkLabel(self.frame_status, text="Thời gian: -", anchor="w")
        self.lbl_selected_usage.pack(fill="x", pady=(0, 5))

        self.lbl_selected_seen = ctk.CTkLabel(self.frame_status, text="Lần cuối: -", anchor="w")
        self.lbl_selected_seen.pack(fill="x", pady=(0, 5))

        self.lbl_selected_ip = ctk.CTkLabel(self.frame_status, text="IP: -", anchor="w")
        self.lbl_selected_ip.pack(fill="x", pady=(0, 5))

        self.frame_actions = ctk.CTkFrame(self.frame_detail)
        self.frame_actions.pack(fill="x", padx=10, pady=10)

        self.btn_lock = ctk.CTkButton(self.frame_actions, text="Khóa", command=self.controller.lock_selected, width=120, state="disabled")
        self.btn_lock.pack(pady=5)

        self.btn_unlock = ctk.CTkButton(self.frame_actions, text="Mở khóa", command=self.controller.unlock_selected, width=120, state="disabled")
        self.btn_unlock.pack(pady=5)

        self.btn_shutdown = ctk.CTkButton(self.frame_actions, text="Tắt máy", command=self.controller.shutdown_selected, width=120, state="disabled")
        self.btn_shutdown.pack(pady=5)

    def update_status(self, status):
        self.lbl_status.configure(text=f"Máy chủ: {status}")

    def set_start_button_text(self, text, command):
        self.btn_start.configure(text=text, command=command)

    def update_clients_grid(self, clients):
        for widget in self.cards_container.winfo_children():
            widget.destroy()
        self.client_cards = []

        if not clients:
            self.lbl_no_clients = ctk.CTkLabel(self.cards_container, text="Chưa có máy nào kết nối", font=ctk.CTkFont(size=14))
            self.lbl_no_clients.pack(expand=True)
            self.show_client_detail(None)
            return

        max_columns = 6
        for index, client in enumerate(clients):
            row = index // max_columns
            column = index % max_columns
            status_color = self._status_color(client["status"])
            is_vip = (client.get("user_type") or "").lower() == "vip"
            wrap = ctk.CTkFrame(
                self.cards_container,
                width=100,
                height=100,
                fg_color=status_color,
                corner_radius=12,
                border_width=0,
            )
            wrap.grid(row=row, column=column, padx=10, pady=10, sticky="nsew")
            wrap._bg_color = status_color
            card = ctk.CTkButton(
                wrap,
                text=f"🖥️\nPC {client['id']}",
                width=100,
                height=100,
                fg_color="transparent",
                hover_color="#ffffff33",
                corner_radius=12,
                command=lambda idx=index: self.controller.select_client(idx),
            )
            card.place(relx=0.5, rely=0.5, anchor="center", relwidth=1.0, relheight=1.0)
            if is_vip:
                vl = ctk.CTkLabel(
                    wrap,
                    text="VIP",
                    font=ctk.CTkFont(size=10, weight="bold"),
                    text_color="#1b5e20",
                    fg_color="#e8f5e9",
                    corner_radius=6,
                    width=34,
                    height=22,
                )
                vl.place(relx=1.0, rely=0.0, anchor="ne", x=-6, y=6)
            dbl = lambda event, c=client: self.open_machine_detail(c)
            wrap.bind("<Double-Button-1>", dbl)
            card.bind("<Double-Button-1>", dbl)
            self.client_cards.append(wrap)

        for col in range(max_columns):
            self.cards_container.grid_columnconfigure(col, weight=1)

        for r in range(row + 1):
            self.cards_container.grid_rowconfigure(r, weight=1)

        if self.selected_client_index is not None and self.selected_client_index < len(clients):
            self.show_client_detail(clients[self.selected_client_index])
            self.highlight_selected_card(self.selected_client_index)
        else:
            self.show_client_detail(None)

    def show_client_detail(self, client):
        if client is None:
            self.selected_client_index = None
            self.lbl_selected_id.configure(text="Máy: -")
            self.lbl_selected_status.configure(text="Trạng thái: -")
            self.lbl_selected_usage.configure(text="Thời gian: -")
            self.lbl_selected_seen.configure(text="Lần cuối: -")
            self.lbl_selected_ip.configure(text="IP: -")
            self.detail_info.configure(text="Chọn máy để xem chi tiết")
            self.btn_lock.configure(state="disabled")
            self.btn_unlock.configure(state="disabled")
            self.btn_shutdown.configure(state="disabled")
            if self.detail_window is not None and self.detail_window.winfo_exists():
                self.detail_window.destroy()
                self.detail_window = None
            return

        status_text = self._status_display(client['status'])
        self.selected_client_index = client['id'] - 1
        self.lbl_selected_id.configure(text=f"Máy: {client['id']}")
        self.lbl_selected_status.configure(text=f"Trạng thái: {status_text}")
        self.lbl_selected_usage.configure(text=f"Thời gian: {self._format_duration(client['usage'])}")
        self.lbl_selected_seen.configure(text=f"Lần cuối: {client['last_seen']:.1f} giây trước")
        self.lbl_selected_ip.configure(text=f"IP: {client.get('ip', '127.0.0.1')}")
        self.detail_info.configure(text=f"Đang xem chi tiết PC {client['id']}")
        if self.detail_window is not None and self.detail_window.winfo_exists():
            self.update_detail_window(client)
        self.btn_lock.configure(state="normal")
        self.btn_unlock.configure(state="normal")
        self.btn_shutdown.configure(state="normal")


    def highlight_selected_card(self, index):
        for idx, card in enumerate(self.client_cards):
            card.configure(
                border_width=2 if idx == index else 0,
                border_color="#4d7cff",
            )

    def open_machine_detail(self, client):
        if self.detail_window is not None and self.detail_window.winfo_exists():
            self.update_detail_window(client)
            self.detail_window.lift()
            return

        self.detail_window = ctk.CTkToplevel(self)
        self.detail_window.title(f"Chi tiết máy {client['id']}")
        self.detail_window.geometry("360x320")
        self.detail_window.resizable(True, True)
        self.detail_window.minsize(360, 320)

        lbl_title = ctk.CTkLabel(self.detail_window, text=f"Chi tiết PC {client['id']}", font=ctk.CTkFont(size=18, weight="bold"))
        lbl_title.pack(pady=20)

        self.detail_window_labels = {}
        self.detail_window_labels['id'] = ctk.CTkLabel(self.detail_window, text="Mã máy: -", anchor="w")
        self.detail_window_labels['id'].pack(fill="x", padx=20, pady=5)

        self.detail_window_labels['status'] = ctk.CTkLabel(self.detail_window, text="Trạng thái: -", anchor="w")
        self.detail_window_labels['status'].pack(fill="x", padx=20, pady=5)

        self.detail_window_labels['usage'] = ctk.CTkLabel(self.detail_window, text="Thời gian: -", anchor="w")
        self.detail_window_labels['usage'].pack(fill="x", padx=20, pady=5)

        self.detail_window_labels['seen'] = ctk.CTkLabel(self.detail_window, text="Lần cuối: -", anchor="w")
        self.detail_window_labels['seen'].pack(fill="x", padx=20, pady=5)

        self.detail_window_labels['ip'] = ctk.CTkLabel(self.detail_window, text="IP: -", anchor="w")
        self.detail_window_labels['ip'].pack(fill="x", padx=20, pady=5)

        self.btn_detail_lock = ctk.CTkButton(self.detail_window, text="Khóa", command=self.controller.lock_selected, width=120)
        self.btn_detail_lock.pack(pady=(15, 5))

        self.btn_detail_unlock = ctk.CTkButton(self.detail_window, text="Mở khóa", command=self.controller.unlock_selected, width=120)
        self.btn_detail_unlock.pack(pady=5)

        self.btn_detail_shutdown = ctk.CTkButton(self.detail_window, text="Tắt máy", command=self.controller.shutdown_selected, width=120)
        self.btn_detail_shutdown.pack(pady=5)

        self.update_detail_window(client)

    def update_detail_window(self, client):
        status_text = self._status_display(client['status'])
        self.detail_window_labels['id'].configure(text=f"Mã máy: {client['id']}")
        self.detail_window_labels['status'].configure(text=f"Trạng thái: {status_text}")
        self.detail_window_labels['usage'].configure(text=f"Thời gian: {self._format_duration(client['usage'])}")
        self.detail_window_labels['seen'].configure(text=f"Lần cuối: {client['last_seen']:.1f} giây trước")
        self.detail_window_labels['ip'].configure(text=f"IP: {client.get('ip', '127.0.0.1')}")

    def _status_color(self, status):
        if status == "AVAILABLE":
            return "#2e7d32"
        return "#c62828"

    def _status_display(self, status):
        if status == "AVAILABLE":
            return "Sẵn sàng"
        if status == "LOCKED":
            return "Đã khóa"
        if status == "CONNECTED":
            return "Đang kết nối"
        return status

    def _format_duration(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def show_message(self, title, message):
        messagebox.showinfo(title, message)
