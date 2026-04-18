import socket

import threading

import time



class Connection:

    def __init__(self, server_ip, port=8888):
        self.server_ip = server_ip
        self.port = port
        self.client_socket = None
        self.is_connected = False
        self.on_message_received = None
        self.on_disconnected = None
        self._send_lock = threading.Lock()

    def connect(self):
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.server_ip, self.port))
            self.is_connected = True
            # Start listening thread
            listener_thread = threading.Thread(target=self._listen_for_messages)
            listener_thread.daemon = True
            listener_thread.start()
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False


    def disconnect(self):
        if self.client_socket:
            self.client_socket.close()
            self.is_connected = False
            if self.on_disconnected:
                self.on_disconnected()


    def send_message(self, message):
        if not self.is_connected or not self.client_socket:
            return
        line = message if message.endswith("\n") else message + "\n"
        data = line.encode("utf-8")
        with self._send_lock:
            if not self.is_connected or not self.client_socket:
                return
            try:
                self.client_socket.sendall(data)
            except Exception:
                self.disconnect()


    def _listen_for_messages(self):
        buffer = ""
        while self.is_connected:
            try:
                data = self.client_socket.recv(1024)
                if not data:
                    self.disconnect()
                    break
                buffer += data.decode('utf-8')
                while '\n' in buffer:
                    message, buffer = buffer.split('\n', 1)
                    if self.on_message_received:
                        self.on_message_received(message.strip())
            except:
                self.disconnect()
                break

    def send_status(self, status):
        self.send_message(f"STATUS:{status}\n")
    def send_usage_time(self, usage_seconds):
        self.send_message(f"USAGE:{usage_seconds}\n")
    def send_chat_text(self, text: str):
        from mvc.ui.chat_codec import encode_chat
        self.send_message(f"CHAT:{encode_chat(text)}")

