import multiprocessing
import subprocess
import sys
import os

def run_server():
    # Chạy server
    server_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Ket_noi', 'Sever', 'server_main.py')
    subprocess.run([sys.executable, server_path])

def run_client():
    # Chạy client
    client_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Ket_noi', 'Client', 'main.py')
    subprocess.run([sys.executable, client_path])
    
if __name__ == "__main__":
    # Tạo processes cho server và client
    server_process = multiprocessing.Process(target=run_server)
    client_process = multiprocessing.Process(target=run_client)

    # Khởi động server trước
    server_process.start()

    # Đợi một chút để server khởi động
    import time
    time.sleep(2)

    # Khởi động client
    client_process.start()

    # Đợi cả hai kết thúc
    server_process.join()
    client_process.join()
