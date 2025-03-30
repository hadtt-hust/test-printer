# process_y.py

import aiofiles
from jinja2 import Template
import logging

async def process_type_y(data):
    try:
        async with aiofiles.open("template_y.html", "r", encoding="utf-8") as file:
            template_content = await file.read()
            template = Template(template_content)

        rendered_html = template.render(data)

        async with aiofiles.open("output_y.html", "w", encoding="utf-8") as file:
            await file.write(rendered_html)

        logging.info("Generated output_y.html")
    except Exception as e:
        logging.error(f"Error creating HTML for type Y: {e}")
        raise