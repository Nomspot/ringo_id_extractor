import json
import csv

headers = [
    'full_name',
    'id_number',
    'date_of_issue_gregorian',
    'age',
    'date_of_birth_gregorian',
    'phone_number',
    'given_name_hebrew', 
    'surname_hebrew', 
    'expiry_date_gregorian',
    'original_image',
]

# Change this to match your actual filename
def run(input_file):
    output_csv = "final_israeli_ids.csv"

    processed_data = []

    print(f"📂 Reading {input_file}...")

    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                item = json.loads(line)
                image_id = item.get('key', 'unknown')

                try:
                    # First split by underscore, then take the first part and split by dot
                    # This handles both "phone_0.jpg" and "phone.jpg"
                    phone_number = image_id.split('_')[0].split('.')[0]
                except Exception:
                    phone_number = image_id
                
                # Extract AI text
                raw_text = item['response']['candidates'][0]['content']['parts'][0]['text']
                clean_text = raw_text.replace("```json", "").replace("```", "").strip()
                data = json.loads(clean_text)

                # Only proceed if the AI confirmed it's a valid Israeli ID
                if not data.get('is_valid_id'):
                    continue
                elif len(data.get('id_number')) < 7:
                    continue
                elif not data.get('given_name_hebrew'):
                    continue
                elif not data.get('date_of_birth_gregorian'):
                    continue
                elif "null" in data.get('date_of_birth_gregorian'):
                    continue
                elif "/" in data.get('date_of_birth_gregorian'): # Sometimes passports are confused with id, they have '/' in the date instead of '.' like ID cards
                    continue
                elif "-" in data.get('date_of_birth_gregorian'):
                    continue
                elif not data.get('date_of_issue_gregorian'):
                    continue
                elif "-" in data.get('date_of_issue_gregorian'):
                    continue
                elif "null" in data.get('date_of_issue_gregorian'):
                    continue

                given = data.get('given_name_hebrew', '').strip()
                surname = data.get('surname_hebrew', '').strip()
                # We use 'full_name' to match your 'headers' list exactly
                data['full_name'] = f"{given} {surname}".strip()
                
                data['original_image'] = image_id
                data['phone_number'] = phone_number

                id_num = data.get('id_number', '')

                data['id_number'] = str(id_num).replace(" ", "")
                
                # 2. IMPORTANT: Remove any "extra" keys the AI might have hallucinated 
                # that aren't in our headers list to prevent the ValueError
                clean_data = {k: v for k, v in data.items() if k in headers}
                
                processed_data.append(clean_data)
                
            except Exception:
                continue

    if processed_data:
        # 1. Helper function to check if a cell actually has "real" data
        def count_real_data(row):
            count = 0
            for key, value in row.items():
                # Skip the 'age' and 'original_image' columns for the count 
                # as they are usually always "filled" by your script
                if key in ['age', 'original_image']:
                    continue
                
                val_str = str(value).strip().lower()
                if val_str and val_str != 'none' and val_str != 'null' and val_str != 'nan':
                    count += 1
            return count

        # 2. Group records by phone_number
        grouped_by_phone = {}
        for row in processed_data:
            phone = row.get('phone_number')
            if phone not in grouped_by_phone:
                grouped_by_phone[phone] = []
            grouped_by_phone[phone].append(row)

        # 3. For each group, pick the winner
        unique_data = []
        for phone, records in grouped_by_phone.items():
            # Sort this specific group by the real data count (Highest first)
            records.sort(key=count_real_data, reverse=True)
            
            # The first one is now the most "filled" one in that phone group
            winner = records[0]
            unique_data.append(winner)
        
        # 4. Final step: Assign Excel Row Numbers for the 'age' formula
        # We do this AFTER deduplication so the E{index} matches the final file
        for index, row_dict in enumerate(unique_data, start=2):
            row_dict['age'] = f'=ROUNDDOWN(YEARFRAC(TODAY(), SUBSTITUTE(SUBSTITUTE(E{index}, "00.", "01."), ".", "/")), 0)'
        
        processed_data = unique_data


    # 5. Write to CSV with "utf-8-sig" (essential for Hebrew in Excel)
    if processed_data:
        with open(output_csv, 'w', newline='', encoding='utf-8-sig') as f:
            # Setting extrasaction='ignore' is a safety net 
            # that skips any keys not in our list
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(processed_data)

        print(f"✅ Done! {len(processed_data)} records saved to {output_csv}")
    else:
        print("❌ No data was processed. Check your file format.")

run("results.jsonl")