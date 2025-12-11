import json
import sys

def export_data(user_id):
    try:
        with open(f"user_data/{user_id}.json", "r") as f:
            data = json.load(f)
        print(json.dumps(data, indent=4))
    except FileNotFoundError:
        print("No data found for user:", user_id)

if __name__ == "__main__":
    export_data(sys.argv[1])
