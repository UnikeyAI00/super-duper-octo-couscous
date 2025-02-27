import json

def load_data():
    try:
        with open('mediremind_data.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"medications": [], "appointments": []}

def save_data(data):
    with open('mediremind_data.json', 'w') as f:
        json.dump(data, f, indent=4)