import sys
import os
import subprocess
import json
import time
import datetime
import traceback
from urllib.parse import urljoin, unquote

import requests

# --------------------------------------------------------------------------- #
#                         CONSTANTS & MAPPINGS                              #
# --------------------------------------------------------------------------- #

TYPE_MAP = {
    1: 'Иное сообщение',
    2: 'Иное сообщение (аннулировано)',
    3: ('Об определении начальной продажной цены, утверждении порядка и условий '
        'проведения торгов по реализации предмета залога, порядка и условий '
        'обеспечения сохранности предмета залога'),
    4: ('Об определении начальной продажной цены, утверждении порядка и условий '
        'проведения торгов по реализации предмета залога, порядка и условий '
        'обеспечения сохранности предмета залога (аннулировано)'),
    5: 'Объявление о проведении торгов',
    6: 'Объявление о проведении торгов (аннулировано, отменено)',
    7: 'Объявление о проведении торгов (аннулировано)',
    8: 'Объявление о проведении торгов (изменено)',
    9: 'Объявление о проведении торгов (отменено)',
    10: 'Отчет оценщика об оценке имущества должника',
    11: 'Отчет оценщика об оценке имущества должника (аннулировано)',
    12: 'Сведения о результатах инвентаризации имущества должника',
    13: 'Сведения о результатах инвентаризации имущества должника (аннулировано)',
    14: ('Сведения об утверждении положения о порядке, об условиях и о сроках '
         'реализации имущества гражданина'),
    15: ('Сведения об утверждении положения о порядке, об условиях и о сроках '
         'реализации имущества гражданина (аннулировано)'),
    16: 'Сообщение об изменении объявления о проведении торгов',
    17: 'Сообщение об изменении объявления о проведении торгов (аннулировано, изменено)',
    18: 'Сообщение об изменении объявления о проведении торгов (аннулировано)',
    19: 'Сообщение об изменении объявления о проведении торгов (изменено)',
    20: 'Сообщение об изменении объявления о проведении торгов (отменено)',
}
TYPE_TO_CODE = {v: k for k, v in TYPE_MAP.items()}

# ------------------------  Runtime configuration  -------------------------- #

TOKEN = "2|1IUnsfuriYszIT9tdx8zgAQozPFUUc4JR47002SKa79a4292"

# API endpoints
FILES_API = "https://torgibot.ru/api/files/after"
IMPORT_API = "https://torgibot.ru/api/import-inventory"
BASE_FILE_URL = "http://46.161.7.142/"

# Local housekeeping
CHECK_INTERVAL = 600           # 10 min between polls when no new data
RETRY_MAX = 3              # number of attempts on flaky operations
RETRY_DELAY = 10           # seconds to wait between retries
START_HOUR = 22               # 10:00 local time
END_HOUR = 23                 # 20:00 local time
LOG_FILE = "error.log"
LAST_MSG_FILE = "last_message_no.txt"
BAN_LIST_FILE = "fail_list.txt"     # message_no | filename

# --------------------------------------------------------------------------- #
#                             UTILITY  HELPERS                                #
# --------------------------------------------------------------------------- #

def log_error(message_no, filename, err):
    """Append one line to the central error log."""
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    with open(LOG_FILE, "a", encoding="utf-8") as lf:
        lf.write(f"{stamp} | {message_no} | {filename} | {err}\n")


def clear_error_log() -> None:
    """Clear the error log file."""
    try:
        with open(LOG_FILE, "w", encoding="utf-8") as lf:
            lf.write("")  # Clear the file
        print(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} — Очищен файл ошибок: {LOG_FILE}")
    except Exception as e:
        print(f"Не удалось очистить {LOG_FILE}: {e}")


def clear_fail_list() -> None:
    """Clear the fail list file."""
    try:
        with open(BAN_LIST_FILE, "w", encoding="utf-8") as bf:
            bf.write("")  # Clear the file
        print(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} — Очищен список неудач: {BAN_LIST_FILE}")
    except Exception as e:
        print(f"Не удалось очистить {BAN_LIST_FILE}: {e}")


# Ban-list helper
def add_to_ban_list(message_no: int, filename: str) -> None:
    with open(BAN_LIST_FILE, "a", encoding="utf-8") as bf:
        bf.write(f"{message_no}|{filename}\n")


def load_last_message_no(default: int = 0) -> int:
    """Read the last processed message number from disk (or default)."""
    try:
        with open(LAST_MSG_FILE, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return default


def save_last_message_no(number: int) -> None:
    with open(LAST_MSG_FILE, "w", encoding="utf-8") as f:
        f.write(str(number))


def cleanup_temp_dirs() -> None:
    """Call cleanup_processed_documents.py to wipe temp folders."""
    try:
        subprocess.run([sys.executable, "cleanup_processed_documents.py"],
                       check=True,
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError as e:
        log_error("—", "cleanup_processed_documents.py",
                  f"Cleanup script failed: {e}")


# --------------------------------------------------------------------------- #
#                              DOWNLOAD FUNCTION                               #
# --------------------------------------------------------------------------- #

def download_file(base_url: str, file_path: str, token: str,
                  original_name: str) -> str:
    """
    Download a single file and return its local path.
    May raise requests.HTTPError or IOError.
    """
    # Normalize path and compose full URL
    normalized_path = file_path.lstrip("./")
    file_url = urljoin(base_url, normalized_path)

    headers = {"Authorization": f"Bearer {token}"}

    print(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} — GET {file_url}")
    resp = requests.get(file_url, headers=headers, stream=True, timeout=60)
    resp.raise_for_status()

    safe_name = "".join(c for c in original_name if c not in "\\/:*?\"<>|")
    os.makedirs("downloaded_files", exist_ok=True)
    local_path = os.path.join("downloaded_files", safe_name)

    with open(local_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    return local_path


# --------------------------------------------------------------------------- #
#                         HIGH-LEVEL PROCESSING STEPS                         #
# --------------------------------------------------------------------------- #

def fetch_messages(after_no: int) -> list:
    """Pull list of new messages after «after_no» and save raw JSON."""
    headers = {"Authorization": f"Bearer {TOKEN}"}
    payload = {"nomer_soobsheniya": str(after_no), "type_message": "12"}

    try:
        resp = requests.post(FILES_API, data=payload, headers=headers,
                             timeout=60)
        resp.raise_for_status()
    except Exception as exc:
        log_error(after_no, "fetch_messages", traceback.format_exc())
        return []

    raw = resp.json()
    # Save full response for debugging
    with open("response.json", "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)

    return raw.get("data", [])

# --------------------------------------------------------------------------- #
# The rest of the file remains identical to the local implementation with
# process_single_message, webhook and polling modes, and main entry point.
# --------------------------------------------------------------------------- #