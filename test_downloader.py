#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Простой тестовый скрипт для скачивания файлов по HTTP ссылкам
"""

import os
import requests
import datetime
from urllib.parse import urlparse, unquote


def download_file(url, output_dir="downloads", timeout=60):
    """
    Скачивает файл по указанной ссылке
    
    Args:
        url (str): URL для скачивания
        output_dir (str): Папка для сохранения (по умолчанию 'downloads')
        timeout (int): Таймаут запроса в секундах
    
    Returns:
        str: Путь к скачанному файлу или None при ошибке
    """
    try:
        print(f"🌐 Начинаем скачивание: {url}")
        start_time = datetime.datetime.now()
        
        # Создаем папку если не существует
        os.makedirs(output_dir, exist_ok=True)
        
        # Выполняем GET запрос
        response = requests.get(url, stream=True, timeout=timeout)
        response.raise_for_status()
        
        # Извлекаем имя файла из URL
        parsed_url = urlparse(url)
        filename = os.path.basename(unquote(parsed_url.path))
        
        # Если имя файла пустое, генерируем автоматически
        if not filename or filename == "/":
            filename = f"downloaded_file_{int(datetime.datetime.now().timestamp())}"
        
        # Полный путь для сохранения
        filepath = os.path.join(output_dir, filename)
        
        # Получаем размер файла если доступен
        content_length = response.headers.get('content-length')
        total_size = int(content_length) if content_length else None
        
        print(f"📁 Сохраняем как: {filepath}")
        if total_size:
            print(f"📊 Размер файла: {total_size / 1024 / 1024:.2f} MB")
        
        # Скачиваем файл по частям
        downloaded_size = 0
        with open(filepath, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)
                    downloaded_size += len(chunk)
                    
                    # Показываем прогресс если знаем размер
                    if total_size:
                        progress = (downloaded_size / total_size) * 100
                        print(f"\r📥 Прогресс: {progress:.1f}% ({downloaded_size / 1024 / 1024:.2f} MB)", end="")
        
        # Завершение
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print(f"\n✅ Скачивание завершено!")
        print(f"📁 Файл сохранен: {filepath}")
        print(f"📊 Размер: {os.path.getsize(filepath) / 1024 / 1024:.2f} MB")
        print(f"⏱️  Время: {duration:.2f} секунд")
        
        return filepath
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка HTTP запроса: {e}")
        return None
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return None


def main():
    """Основная функция для тестирования"""
    
    print("🚀 Тестовый скрипт скачивания файлов")
    print("=" * 50)
    
    # Тестовая ссылка
    test_url = "http://46.161.7.142/files/18370066/Акт списания 1 от 09.06.2025 суммы дебиторской задолженности без ИНН .pdf"
    
    print(f"🎯 Тестируем скачивание:")
    print(f"URL: {test_url}")
    print("-" * 50)
    
    # Выполняем скачивание
    result = download_file(test_url)
    
    if result:
        print(f"\n🎉 Тест успешен! Файл скачан: {result}")
        
        # Дополнительная информация о файле
        file_size = os.path.getsize(result)
        print(f"📋 Дополнительная информация:")
        print(f"   • Размер: {file_size} байт ({file_size / 1024:.2f} KB)")
        print(f"   • Расширение: {os.path.splitext(result)[1]}")
        
    else:
        print(f"\n💥 Тест неудачен! Файл не был скачан")


if __name__ == "__main__":
    main()