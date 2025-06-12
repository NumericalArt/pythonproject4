import os
import io
import logging
import shutil
import base64
import zipfile
# Optional dependency for .rar support
try:
    import rarfile  # needs `pip install rarfile` and unrar/bsdtar on system
except ImportError:
    rarfile = None
import subprocess
from datetime import datetime
from typing import List, Dict, Optional

import fitz  # PyMuPDF
import pandas as pd
from PIL import Image, ExifTags
from PIL import ImageOps  # ← for auto-rotating images by EXIF
from striprtf.striprtf import rtf_to_text
import strip_markdown
import openpyxl
import pytesseract
from dotenv import load_dotenv

from openai import OpenAI   # ⬅️ new-style SDK (≥ 1.0.0)  ✅

# ----------------------------------------------------------------------
# Configuration constants
# ----------------------------------------------------------------------
MIN_IMG_PIXELS = 200 * 200
MAX_VISION_CALLS_PER_PAGE = 50
MAX_IMAGE_DIM = 3000
MAX_IMAGE_SIZE = 10 * 1024 * 1024

SUPPORTED_IMAGE_FORMATS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".gif", ".tiff", ".tif", ".bmp"}

# ----------------------------------------------------------------------
# ZIP archive limits
# ----------------------------------------------------------------------
MAX_ZIP_SIZE = 100 * 1024 * 1024        # 100 MB
MAX_ZIP_FILES = 50                      # process at most 50 files per archive

# ----------------------------------------------------------------------
# RAR archive limits (same policy as ZIP)
# ----------------------------------------------------------------------
MAX_RAR_SIZE = 100 * 1024 * 1024      # 100 MB
MAX_RAR_FILES = 50                    # max members to process

###############################################################################
# Logging configuration
###############################################################################
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

LOG_DIR = "processed_documents"
os.makedirs(LOG_DIR, exist_ok=True)
file_handler = logging.FileHandler(os.path.join(LOG_DIR, "processing.log"))
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(file_handler)


###############################################################################
# Helper utilities
###############################################################################
def _ensure_dirs() -> None:
    """Ensure that standard output directories exist."""
    for d in ("images", "tables", LOG_DIR, "extracted_images"):
        os.makedirs(d, exist_ok=True)


def _save_binary(content: bytes, dest_path: str) -> None:
    """Write binary data to a destination path, creating parent dirs if needed."""
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, "wb") as f:
        f.write(content)

# ----------------------------------------------------------------------
# Utility to save image data (bytes or fitz.Pixmap or PIL.Image)
# ----------------------------------------------------------------------
def _save_image_data(data, dest_path: str) -> None:
    """Save image data (bytes or fitz.Pixmap or PIL.Image) to disk, ensuring parent dirs exist."""
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    # fitz.Pixmap
    if hasattr(data, "save") and callable(data.save):
        data.save(dest_path)
    # PIL.Image.Image
    elif hasattr(data, "save") and hasattr(data, "format"):
        data.save(dest_path)
    else:
        with open(dest_path, "wb") as f:
            f.write(data)

def _find_soffice() -> str:
    """
    Locate LibreOffice 'soffice' executable.

    Order:
    1. Env variable SOFFICE_PATH
    2. In PATH (`shutil.which`)
    3. macOS default location
    """
    candidates = [
        os.getenv("SOFFICE_PATH"),
        shutil.which("soffice"),
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]
    for p in candidates:
        if p and os.path.isfile(p):
            return p
    raise FileNotFoundError(
        "LibreOffice 'soffice' executable not found. "
        "Install LibreOffice or set env var SOFFICE_PATH."
    )


###############################################################################
# Document class
###############################################################################
class Document:
    """Universal document processor extracting text / images from many formats."""

    _IMAGE_EXTS = SUPPORTED_IMAGE_FORMATS

    def __init__(self, file_path: str, *, media_dir: str = "media_for_processing") -> None:
        self.media_dir = media_dir
        os.makedirs(self.media_dir, exist_ok=True)

        if not file_path.startswith(self.media_dir):
            self.file_path = os.path.join(self.media_dir, os.path.basename(file_path))
        else:
            self.file_path = file_path

        self.file_name = os.path.basename(self.file_path)
        self.file_ext = os.path.splitext(self.file_name)[1].lower()
        self.file_size = os.path.getsize(self.file_path) if os.path.exists(self.file_path) else 0

        self.metadata: Dict[str, str] = {}
        self.text_content: str = ""
        self.tables: List[str] = []
        self.images: List[str] = []

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def process(self) -> None:
        """Detect file type and dispatch to the correct private handler."""
        if self.file_name.startswith("~$"):
            raise ValueError(f"Temporary file detected ('{self.file_name}'). Skipping processing.")

        _ensure_dirs()

        # ─────────────────────────────────────────────────────────────────────
        # Диспетчер: расширения → методы
        # ─────────────────────────────────────────────────────────────────────
        HANDLERS = {
                        ".pdf": self._process_pdf,
                        ".txt": self._process_txt,
                        ".pages": self._process_pages,
                        ".numbers": self._process_numbers,
                        ".xlsx": self._process_spreadsheet,
                        ".xls": self._process_spreadsheet,
                        ".csv": self._process_csv,
                        ".json": self._process_generic_text,
                        ".py": self._process_generic_text,
                        ".html": self._process_generic_text,
                        ".cms": self._process_generic_text,
                        ".css": self._process_generic_text,
                        ".eml": self._process_email,
                        ".mbox": self._process_email,
                        ".rtf": self._process_rtf,
                        ".md": self._process_markdown,
                        ".markdown": self._process_markdown,
                        ".odt": self._process_odt,
                        ".epub": self._process_epub,
                        ".zip": self._process_generic_zip,
                        ".rar": self._process_generic_rar,
            }

        ext = self.file_ext

        # выбор обработчика

        if ext in self._IMAGE_EXTS:
            handler = self._process_image
        elif ext in {".docx", ".doc", ".pptx", ".ppt"}:
            # сначала конвертация Office → PDF
            pdf_path = self._convert_to_pdf(self.file_path)
            self.file_path, self.file_name, self.file_ext = pdf_path, os.path.basename(pdf_path), ".pdf"
            handler = self._process_pdf
        else:
            handler = HANDLERS.get(ext)

        if not handler:
            raise ValueError(f"Unsupported file format: {ext}")
        # вызываем нужный метод
        handler()


    # ------------------------------------------------------------------
    # Format-specific processing methods
    # ------------------------------------------------------------------

    def _process_pdf(self) -> None:
        """
        Извлекает текст и изображения из PDF:
        – текст через page.get_text("dict"), как в «старой» версии;
        – изображения сохраняет, но описывает (Vision) только
          крупные и пока не превысили MAX_VISION_CALLS.
        """

        print(F"Обработка PDF документа {self.file_path}")

        doc = fitz.open(self.file_path)
        self.metadata.update(doc.metadata or {})
        parts: List[str] = []

        for page_number in range(len(doc)):
            page = doc[page_number]
            vision_calls = 0
            image_counter = 1

            # a) если на странице есть векторная графика/фон, снимем превью-пиксмап
            if page.get_drawings():
                print(F"Обработка страницы {page_number + 1} с графикой")
                try:
                    pix = page.get_pixmap()
                    img_path = os.path.join(
                        "images",
                        f"{os.path.splitext(self.file_name)[0]}_page{page_number + 1}.png",
                    )
                    _save_image_data(pix, img_path)
                    # print(F"Сохранение образа страницы {page_number + 1} с графикой")
                    self.images.append(img_path)
                    desc = self._generate_image_description(img_path)
                    # print(F"Обработка образа страницы {page_number + 1} с графикой завершена")
                    parts.append(f"[========[Страница {page_number + 1} с графикой]======== \n {desc}]\n")
                    print(F"Описание страницы {page_number + 1} с графикой добавлено")
                except Exception as e:
                    logger.error("Pixmap error p.%s: %s", page_number + 1, e)
                    print(F"Ошибка обработки образа страницы {page_number + 1} с графикой")

            else:  # b) обычный текст + встроенные растр-картинки
                print(F"Обработка страницы {page_number + 1}: обычный текст + встроенные растр-картинки")
                parts.append(f"========[Страница {page_number + 1} обычный текст + встроенные растр-картинки]========\n")
                page_dict = page.get_text("dict")
                if not page_dict.get("blocks", []):
                    print(F"На странице {page_number + 1} не обнаружено текста и изображений")
                for block in page_dict.get("blocks", []):
                    if block.get("type") == 0:  # текстовый блок
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                parts.append(span.get("text", ""))

                    elif block.get("type") == 1:  # image-блок
                        parts.append(f"========[Изображение {image_counter}]========\n")
                        img_bytes = block.get("image")
                        w = block.get("width", 0)
                        h = block.get("height", 0)
                        if w * h < MIN_IMG_PIXELS:
                            continue  # мелочь — пропускаем
                        img_ext = block.get("ext", "png")
                        img_name = f"{os.path.splitext(self.file_name)[0]}_img{image_counter}.{img_ext}"
                        img_path = os.path.join("images", img_name)
                        try:
                            _save_image_data(img_bytes, img_path)
                            self.images.append(img_path)
                            if vision_calls < MAX_VISION_CALLS_PER_PAGE:
                                desc = self._generate_image_description(img_path)
                                vision_calls += 1
                            else:
                                desc = "(описание пропущено — лимит Vision)"
                            parts.append(f"[Изображение {image_counter}: {desc}]")
                            image_counter += 1
                        except Exception as e:
                            logger.error("Save/describe image error: %s", e)

            parts.append("\n---\n")

        self.text_content = "".join(parts)
        doc.close()

    def _process_txt(self) -> None:
        with open(self.file_path, "r", encoding="utf-8", errors="ignore") as f:
            self.text_content = f.read()
        self._inject_basic_metadata()

    def _process_image(self) -> None:
        print(F"Начало обработки растрового файла: {self.file_path}")
        try:
            img = Image.open(self.file_path)
        except Exception as e:
            raise ValueError(f"Cannot open image '{self.file_name}': {e}")

        # — auto-rotate image based on EXIF orientation before resizing
        try:
            exif = img.getexif()
            if exif and exif.get(274):  # 274 is the EXIF Orientation tag
                img = ImageOps.exif_transpose(img)
        except Exception:
            pass

        if max(img.size) > MAX_IMAGE_DIM or self.file_size > MAX_IMAGE_SIZE:
            img.thumbnail((MAX_IMAGE_DIM, MAX_IMAGE_DIM))

        fmt = "JPEG" if img.format and img.format.lower() in {"tiff", "tif"} else (img.format or "PNG")
        out_name = f"{os.path.splitext(self.file_name)[0]}.{fmt.lower()}"
        out_path = os.path.join("images", out_name)
        _save_image_data(img, out_path)
        self.images.append(out_path)

        exif_data: Dict[str, str] = {}
        try:
            exif = img.getexif() or {}
            for tag, value in exif.items():
                exif_data[ExifTags.TAGS.get(tag, tag)] = value
            if "Orientation" in exif_data:
                exif_data["Orientation"] = 1
            self.metadata.update(exif_data)
        except Exception:
            logger.debug("No EXIF metadata or failed to parse for '%s'", self.file_name)

        self.text_content = self._generate_image_description(out_path)

    # Other processing methods continue here (omitted for brevity)
