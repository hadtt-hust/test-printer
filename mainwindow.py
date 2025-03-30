import tkinter as tk
from tkinter import messagebox
import win32print
import subprocess
import logging
import threading
import time
import os

class TextHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        self.text_widget.insert(tk.END, msg + '\n')
        self.text_widget.see(tk.END)

def get_printers():
    printers = [printer[2] for printer in win32print.EnumPrinters(2)]
    return printers

def on_select():
    global mqtt_process
    selected_printer = printer_var.get()
    messagebox.showinfo("Máy in đã chọn", f"Bạn đã chọn: {selected_printer}")
    
    # Create the log file if it does not exist
    if not os.path.exists("log.txt"):
        with open("log.txt", "w") as file:
            file.write("")
    
    # Start mqtt_listener.py with the selected printer as a command-line argument
    mqtt_process = subprocess.Popen(["python", "mqtt_listener.py", selected_printer])
    
    # Disable the confirm button and enable the stop button
    confirm_button.config(state=tk.DISABLED)
    stop_button.config(state=tk.NORMAL)

def on_stop():
    global mqtt_process
    if mqtt_process:
        mqtt_process.terminate()
        mqtt_process = None
        messagebox.showinfo("Stopped", "MQTT listener has been stopped.")
    
    # Enable the confirm button and disable the stop button
    confirm_button.config(state=tk.NORMAL)
    stop_button.config(state=tk.DISABLED)

def read_log():
    with open("log.txt", "r") as file:
        lines = file.readlines()
        log_text.delete(1.0, tk.END)
        for line in lines:
            log_text.insert(tk.END, line)
        log_text.see(tk.END)
    root.after(1000, read_log)  # Schedule the function to run every second

def clear_log():
    with open("log.txt", "w") as file:
        file.write("")

def on_close():
    global mqtt_process
    if mqtt_process:
        mqtt_process.terminate()
    clear_log()
    root.destroy()

# Tạo cửa sổ chính
root = tk.Tk()
root.title("Chọn máy in")
root.geometry("500x400")

# Clear the log file when the program starts
clear_log()

# Lấy danh sách máy in
printers = get_printers()

# Tạo biến StringVar để lưu lựa chọn
printer_var = tk.StringVar(root)
printer_var.set(printers[0] if printers else "Không có máy in")

# Tạo nhãn và menu chọn máy in
label = tk.Label(root, text="Chọn máy in:")
label.pack(pady=5)

dropdown = tk.OptionMenu(root, printer_var, *printers)
dropdown.pack(pady=5)

# Tạo nút bấm xác nhận
confirm_button = tk.Button(root, text="Xác nhận", command=on_select)
confirm_button.pack(pady=10)

# Tạo nút bấm dừng
stop_button = tk.Button(root, text="Dừng", command=on_stop, state=tk.DISABLED)
stop_button.pack(pady=10)

# Tạo Text widget để hiển thị log
log_text = tk.Text(root, wrap='word', height=10, width=50)
log_text.pack(pady=10)

# Đọc log từ file và hiển thị trong Text widget
root.after(1000, read_log)  # Schedule the function to run every second

# Bind the on_close function to the window close event
root.protocol("WM_DELETE_WINDOW", on_close)

# Chạy chương trình
mqtt_process = None
root.mainloop()