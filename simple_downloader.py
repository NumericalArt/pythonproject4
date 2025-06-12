#!/usr/bin/env python3
"""
Простейший скрипт для скачивания файлов
"""

import os
import requests
from urllib.parse import unquote


def simple_download(url, folder="downloads"):
    """Простое скачивание файла"""
    try:
        print(f"Скачиваем: {url}")
        
        # Создаем папку
        os.makedirs(folder, exist_ok=True)
        
        # Запрос
        response = requests.get(url)
        response.raise_for_status()
        
        # Имя файла из URL
        filename = os.path.basename(unquote(url))
        filepath = os.path.join(folder, filename)
        
        # Сохраняем
        with open(filepath, 'wb') as f:
            f.write(response.content)
        
        print(f"✅ Сохранено: {filepath}")
        print(f"📊 Размер: {len(response.content)} байт")
        
        return filepath
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None


if __name__ == "__main__":
    # Тестовый URL
    test_url = "http://46.161.7.142/files/18358768/ИНВ № 1 от 09.06.2025 г.xlsx"
    
    print("🚀 Простой тест скачивания")
    result = simple_download(test_url)
    
    if result:
        print(f"🎉 Успех! Файл: {result}")
    else:
        print("💥 Неудача!")