# test_import.py
try:
    print("Importing telegram...")
    from telegram.ext import Updater
    print("Import successful!")
except Exception as e:
    print(f"Error importing: {e}")