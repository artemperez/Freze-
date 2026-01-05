#!/usr/bin/env python3
# Установщик зависимостей

import subprocess
import sys

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

print("Установка зависимостей для Further BoTнЕт...")

try:
    install("telethon")
    print("✅ Telethon установлен")
    
    print("\n✅ Все зависимости установлены!")
    print("Запустите бота: python further_bot.py")
    
except Exception as e:
    print(f"❌ Ошибка установки: {e}")
    print("Установите вручную: pip install telethon")