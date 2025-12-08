import json
from pathlib import Path

# Define the path to the schema mapping file
SCHEMA_FILE = Path("schema_mapping.json")

# Function to save schema mapping
def save_schema(bank_name: str,mapping: dict):


    if not bank_name or not mapping:
        raise ValueError("bank_name and mapping are required")

    # Load existing data if file exists
    if SCHEMA_FILE.exists():
        data = json.loads(SCHEMA_FILE.read_text())
    else:
        data = {}

    # Save the schema for the specific bank
    data[bank_name] = {
        "is_default": True,
        "mapping": mapping,
    }
    print("Saving schema:", mapping)        # Debug

    # Write back to the file
    SCHEMA_FILE.write_text(json.dumps(data, indent=4))
    print("Schema saved to:", SCHEMA_FILE)  # Debug

    return True

# Function to load schema mapping
def load_schema(bank_name: str):
    
    # Load existing data
    if not SCHEMA_FILE.exists():
        print("Schema file does not exist")  # Debug
        return None

    # Load the schema data
    data = json.loads(SCHEMA_FILE.read_text())
    print("Loaded schema data:", data)  # Debug

    # Return the schema for the specific bank if it exists
    if bank_name in data:
        print("Returning schema for bank:", bank_name)  # Debug
        return data[bank_name]["mapping"]


    print(f"No schema found for bank: {bank_name}")  # Debug
    return None