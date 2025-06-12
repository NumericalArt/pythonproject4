#!/usr/bin/env python3

import requests
import os

# URL для скачивания
url = "http://46.161.7.142/files/18358768/18370066_12_Сведения о результатах инвентаризации имущества должника_Акт списания 1 от 09.06.2025 суммы дебиторской задолженности без ИНН .pdf "

# Скачиваем
print(f"Скачиваем {url}")
response = requests.get(url)

# Сохраняем  
filename = "downloaded_file.xlsx"
with open(filename, 'wb') as f:
    f.write(response.content)

print(f"Готово! Файл: {filename}, размер: {len(response.content)} байт")