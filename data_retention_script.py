import os, json
from datetime import datetime, timedelta

DATA_DIR = "user_data"

def delete_old_data():
    for filename in os.listdir(DATA_DIR):
        file_path = os.path.join(DATA_DIR, filename)
        with open(file_path, "r") as f:
            data = json.load(f)
        
        timestamp = datetime.fromisoformat(data.get("timestamp"))
        if datetime.now() - timestamp > timedelta(days=30):
            os.remove(file_path)

if __name__ == "__main__":
    delete_old_data()
