import paho.mqtt.client as mqtt
import json
from jinja2 import Template
import asyncio
from pyppeteer import launch
import os
import subprocess
import time

MQTT_BROKER = "127.0.0.1"  # Địa chỉ broker
MQTT_TOPIC = "printer/topic"

queue = asyncio.Queue()  # Hàng đợi in


def on_connect(client, userdata, flags, rc):
    print("Connected with result code", rc)
    client.subscribe(MQTT_TOPIC)


def create_html(data):
    with open("template.html", "r", encoding="utf-8") as file:
        template = Template(file.read())

    rendered_html = template.render(data)

    with open("output.html", "w", encoding="utf-8") as file:
        file.write(rendered_html)

    print("Generated output.html")


async def print_html():
    browser = await launch(
        headless=True,
        executablePath="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
    )
    page = await browser.newPage()

    file_path = f"file://{os.path.abspath('output.html')}"
    await page.goto(file_path)

    # Xuất HTML thành PDF
    pdf_path = os.path.abspath("output.pdf")
    await page.pdf({'path': pdf_path, 'format': 'A4', 'printBackground': True})
    await browser.close()

    print("PDF created successfully:", pdf_path)

    # **Chờ 1 giây để đảm bảo file được tạo**
    time.sleep(1)

    # Kiểm tra xem file PDF có tồn tại trước khi in không
    if not os.path.exists(pdf_path):
        print("Error: PDF file not found!")
        return

    # **Gửi lệnh in**
    try:
        if os.name == "nt":  # Windows
            subprocess.run(
                ["powershell", "-Command", f"Start-Process -FilePath '{pdf_path}' -Verb Print"], check=True)
        else:  # Linux/macOS
            subprocess.run(["lp", pdf_path], check=True)

        print("Printed successfully")
    except Exception as e:
        print("Print failed:", e)

    queue.task_done()  # Đánh dấu hoàn thành

    # **Chờ 1 giây trước khi xóa file**
    time.sleep(1)

    # **Xóa file sau khi in**
    if os.path.exists("output.html"):
        os.remove("output.html")

    if os.path.exists(pdf_path):
        os.remove(pdf_path)


# ✅ Chạy từng lệnh in theo thứ tự
async def process_queue():
    while True:
        data = await queue.get()  # Chờ đến khi có dữ liệu
        print("Processing:", data)

        # Tạo file HTML từ JSON
        create_html(data)

        # ✅ Chỉ cần `await`, không dùng `asyncio.run()`
        await print_html()


def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode("utf-8"))
        print("Received MQTT message:", data)

        # ✅ Đưa vào queue trong event loop chính
        asyncio.run_coroutine_threadsafe(queue.put(data), loop)

    except Exception as e:
        print("Error processing message:", e)


async def mqtt_subscribe():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, 1883, 60)
    client.loop_start()  # Chạy MQTT trong luồng riêng
    print("MQTT client started...")


async def main():
    global loop
    loop = asyncio.get_running_loop()  # ✅ Lưu event loop chính
    await asyncio.gather(
        mqtt_subscribe(),
        process_queue()
    )


# ✅ Kiểm tra nếu có event loop, tránh lỗi "asyncio.run() cannot be called..."
try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

loop.run_until_complete(main())  # ✅ Chạy chương trình an toàn
