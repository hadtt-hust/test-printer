import paho.mqtt.client as mqtt
import json
from jinja2 import Template
import asyncio
from pyppeteer import launch
import aiofiles
import os
import logging
import threading
import sys
import win32print
import win32api
from process_y import process_type_y  # Import the function

# Configure logging to write to a file
logging.basicConfig(filename="log.txt", level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

MQTT_BROKER = "127.0.0.1"  # Broker address
MQTT_TOPIC = "printer/topic"

queue = asyncio.Queue()  # Print queue

# Get the selected printer from command-line arguments
selected_printer = sys.argv[1] if len(sys.argv) > 1 else None
logging.info(f"Selected printer: {selected_printer}")

def is_printer_ready(printer_name):
    try:
        hPrinter = win32print.OpenPrinter(printer_name)
        try:
            printer_info = win32print.GetPrinter(hPrinter, 2)
            status = printer_info["Status"]
            if status == 0:
                return True
            else:
                logging.error(f"Printer status is not ready: {status}")
                return False
        finally:
            win32print.ClosePrinter(hPrinter)
    except Exception as e:
        logging.error(f"Error checking printer status: {e}")
        return False

def on_connect(client, userdata, flags, rc, properties=None):
    logging.info(f"Connected with result code {rc}")
    client.subscribe(MQTT_TOPIC)

async def create_html(data):
    try:
        async with aiofiles.open("template.html", "r", encoding="utf-8") as file:
            template_content = await file.read()
            template = Template(template_content)

        rendered_html = template.render(data)

        async with aiofiles.open("output.html", "w", encoding="utf-8") as file:
            await file.write(rendered_html)

        logging.info("Generated output.html")
    except Exception as e:
        logging.error(f"Error creating HTML: {e}")
        raise

def print_action(printer, filename):
    try:
        PRINTER_DEFAULTS = {"DesiredAccess": win32print.PRINTER_ALL_ACCESS}
        pHandle = win32print.OpenPrinter(printer, PRINTER_DEFAULTS)
        properties = win32print.GetPrinter(pHandle, 2)
        properties['pDevMode'].Copies = 1
        win32print.SetPrinter(pHandle, 2, properties, 0)

        win32api.ShellExecute(0, "print", filename, None, ".", 0)
        win32print.ClosePrinter(pHandle)
        logging.info("Printed successfully")
    except Exception as e:
        logging.error(f"Error printing the file: {e}")

async def print_html(browser):
    try:
        page = await browser.newPage()

        file_path = f"file://{os.path.abspath('output.html')}"
        await page.goto(file_path)

        # Export HTML to PDF
        pdf_path = os.path.abspath("output.pdf")
        await page.pdf({'path': pdf_path, 'format': 'A4', 'printBackground': True})
        await page.close()

        logging.info(f"PDF created successfully: {pdf_path}")

        # Wait 1 second to ensure the file is created
        await asyncio.sleep(1)

        # Check if the PDF file exists before printing
        if not os.path.exists(pdf_path):
            logging.error("Error: PDF file not found!")
            return

        # Check if the printer is ready
        if not is_printer_ready(selected_printer):
            logging.error("Printer is not ready")
            return

        # Send print command using win32print
        print_action(selected_printer, pdf_path)

        queue.task_done()  # Mark as done

        # Wait 1 second before deleting the file
        await asyncio.sleep(1)

        # Delete files after printing
        if os.path.exists("output.html"):
            os.remove("output.html")

        if os.path.exists(pdf_path):
            os.remove(pdf_path)
    except Exception as e:
        logging.error(f"Error in print_html: {e}")
        raise

# Process each print job in order
async def process_queue(browser):
    while True:
        data = await queue.get()  # Wait until data is available
        logging.info(f"Processing: {data}")

        try:
            data_type = data.get("type")
            if data_type == "x":
                await create_html(data["value"])
            elif data_type == "y":
                await process_type_y(data["value"])
            else:
                logging.error(f"Unknown data type: {data_type}")
                continue

            # Await print_html coroutine
            await print_html(browser)
        except Exception as e:
            logging.error(f"Error processing queue: {e}")

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode("utf-8"))
        logging.info(f"Received MQTT message: {data}")

        # Put data into the queue in the main event loop
        asyncio.run_coroutine_threadsafe(queue.put(data), loop)

    except Exception as e:
        logging.error(f"Error processing message: {e}")

def mqtt_thread_exception_handler(args):
    logging.error(f"Exception in thread {args.thread.name}: {args.exc_type.__name__}: {args.exc_value}")

# Register the custom exception handler
threading.excepthook = mqtt_thread_exception_handler

async def mqtt_subscribe():
    client = mqtt.Client(protocol=mqtt.MQTTv5)  # Use MQTT version 5
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, 1883, 60)
    client.loop_start()  # Run MQTT in a separate thread
    logging.info("MQTT client started...")

async def main():
    global loop
    loop = asyncio.get_running_loop()  # Save the main event loop

    # Launch browser once and reuse it
    browser = await launch(
        headless=True,
        executablePath="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
    )

    try:
        await asyncio.gather(
            mqtt_subscribe(),
            process_queue(browser)
        )
    except Exception as e:
        logging.error(f"Error in main: {e}")
    finally:
        await browser.close()

# Check if there is an event loop, avoid "asyncio.run() cannot be called..."
try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

try:
    loop.run_until_complete(main())  # Run the program safely
except Exception as e:
    logging.error(f"Error running event loop: {e}")
finally:
    loop.close()