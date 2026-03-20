import json
import os

system_instruction = """
You are a specialized Israeli Document Processor.
Extract data only from Israeli Identity Cards.
ORIENTATION: The image may be rotated 90, 180, or 270 degrees.
Your first step is to identify the orientation of the Hebrew text.
Ignore non-ID objects.
Infer blurry digits.
"""

response_schema = {
    "type": "OBJECT",
    "properties": {
        "is_valid_id": {"type": "BOOLEAN"},
        "id_number": {"type": "STRING"},
        "surname_hebrew": {"type": "STRING"},
        "given_name_hebrew": {"type": "STRING"},
        "date_of_birth_gregorian": {"type": "STRING"},
        "date_of_issue_gregorian": {"type": "STRING"},
        "expiry_date_gregorian": {"type": "STRING"},
    },
    "required": ["is_valid_id", "id_number"]
}

def create_jsonl(bucket_name, local_folder, file_name):
    try:
        with open(file_name, "w", encoding="utf-8") as f:
            for filename in os.listdir(local_folder):
                if filename.lower().endswith((".jpg", ".jpeg", ".png")):
                    # BATCH JOBS MUST HAVE A 'KEY' AT THE TOP LEVEL
                    line = {
                        "key": filename.replace(".", "_"), # Unique ID for this specific row
                        "request": {
                            "system_instruction": {"parts": [{"text": system_instruction}]},
                            "contents": [{
                                "role": "user",
                                "parts": [
                                    {"text": "Extract data from this image."},
                                    {"file_data": {"mime_type": "image/jpeg", "file_uri": f"gs://{bucket_name}/{local_folder}/{filename}"}}
                                ]
                            }],
                            "generation_config": {
                                "response_mime_type": "application/json",
                                "response_schema": response_schema
                            }
                        }
                    }
                    f.write(json.dumps(line, ensure_ascii=False) + "\n")

        print(f"✅ {file_name} created succesfully.")
        return True
    except Exception as e:
        print(f"❌ An error occured while trying to write {file_name}\n---\n{e}")
        return False