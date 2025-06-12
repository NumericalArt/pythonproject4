#!/usr/bin/env python3
"""
process_and_extract.py

Cкрипт для пакетной обработки документов и извлечения объектов описи в структурированный JSON.

Шаги:
 1. Запуск script_only_send.py для скачивания файлов в downloaded_files/
 2. Batch-процессинг всех файлов через batch_process_folder из document_processor.py
 3. Для каждого документа вызов GPT модели для извлечения объектов описи с response_format=json_object
 4. Формирование итогового JSON с session_id, date, time и списком документов
"""
import os
import sys
import time
import json
from datetime import datetime
import subprocess
from dotenv import load_dotenv
from openai import OpenAI
import logging
import hashlib

from document_processor_rar_zip import batch_process_folder

# Cache for extract_objects: maps SHA256(text) to extraction result dict
_extract_cache = {}

# CLASS list truncated for brevity in this version. Full list present locally.
CLASS = ["Прочее"]

logger = logging.getLogger('process_and_extract')
logger.setLevel(logging.INFO)

DOWNLOAD_DIR = "downloaded_files"
OUTPUT_JSON = "session_extract.json"
MODEL = "gpt-4.1-mini"
TIMEOUT = 120


def extract_objects(client: OpenAI, text: str) -> dict:
    key = hashlib.sha256(text.encode('utf-8')).hexdigest()
    if key in _extract_cache:
        return _extract_cache[key]
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": text}],
            temperature=0,
            timeout=TIMEOUT,
        )
        content = resp.choices[0].message.content
        result = json.loads(content) if isinstance(content, str) else content
        _extract_cache[key] = result
        return result
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return {"objects": []}


def main():
    start_time = datetime.now()
    load_dotenv()
    api_key = os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OpenAI API key not set", file=sys.stderr)
        sys.exit(1)
    client = OpenAI(api_key=api_key)

    docs_data = batch_process_folder(DOWNLOAD_DIR, None, return_docs=True)
    docs = []
    for idx, info in enumerate(docs_data, 1):
        fname = os.path.basename(info.get("absolute_path", ""))
        text = info.get("text_content", "")
        objects = extract_objects(client, text).get("objects", [])
        docs.append({
            "doc_id": f"doc_{idx:03d}",
            "original_name": fname,
            "objects": objects,
        })
    end_time = datetime.now()
    result = {
        "session_id": f"session_{int(time.time())}",
        "date": end_time.strftime("%Y-%m-%d"),
        "start_time": start_time.strftime("%H:%M:%S"),
        "end_time": end_time.strftime("%H:%M:%S"),
        "documents": docs,
    }
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"Session JSON saved to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()