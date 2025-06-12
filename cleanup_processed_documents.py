#!/usr/bin/env python3
"""
cleanup_processed_documents.py

Удаляет временные каталоги и файлы, созданные во время обработки документов.
"""
import os
import shutil
import argparse


def clean_directory(path: str) -> None:
    if not os.path.isdir(path):
        print(f"Каталог не найден: {path}")
        return
    for entry in os.listdir(path):
        full_path = os.path.join(path, entry)
        try:
            if os.path.isdir(full_path):
                shutil.rmtree(full_path)
            else:
                os.remove(full_path)
        except Exception as e:
            print(f"Не удалось удалить {full_path}: {e}")
    print(f"Очистка завершена: {path}")


def main():
    parser = argparse.ArgumentParser(description="Очистить временные каталоги.")
    parser.add_argument("--dir", "-d", default="processed_documents", help="Какой каталог чистить")
    args = parser.parse_args()
    dirs_to_clean = [
        args.dir,
        "images",
        "extracted_images",
        "tables",
        "downloaded_files",
        "media_for_processing",
    ]
    for d in dirs_to_clean:
        clean_directory(d)
    for f in ("session_extract.json", "response.json"):
        if os.path.isfile(f):
            try:
                os.remove(f)
                print(f"Удалён файл: {f}")
            except Exception as e:
                print(f"Не удалось удалить {f}: {e}")


if __name__ == "__main__":
    main()