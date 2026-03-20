## Overview

This project is an end-to-end automation pipeline designed to extract structured identity data from customer-submitted images in a chat system.

It automates the full workflow — from logging into the platform and downloading images, to processing them using AI models and exporting clean, structured results.

---

## Key Features

* Automated login and scraping of chat data using Selenium
* Bulk image extraction from conversations
* Local tracking system using SQLite to prevent duplicate processing
* AI-powered data extraction from images (ID cards, documents)
* Batch processing with Vertex AI / Gemini models
* JSONL result parsing and transformation into Excel format
* Fully automated pipeline with minimal human interaction

---

## System Architecture

```
Ringo Chat Platform
        ↓
Image Extraction (Selenium)
        ↓
Local Storage + SQLite Tracking
        ↓
Batch Preparation
        ↓
Vertex AI (Gemini Processing)
        ↓
JSONL Results
        ↓
Data Processing
        ↓
Excel Output
```

---

## Project Structure

```
.
├── main.py                 # Main automation entry point
├── batch_prepare.py        # Prepares image batches for AI processing
├── vertex_ai.py            # Handles Vertex AI integration
├── json_to_excel.py        # Converts AI results into Excel
├── free_id_finder.py       # Additional data handling utilities
├── check_gemini_models.py  # Model validation / testing
├── saved_data.db           # SQLite database for tracking processed files (auto generated)
├── run_automation.bat      # Script to run the pipeline
```

---

## How It Works

1. The script logs into the Ringo chat platform using automated browser control
2. It scans chats and downloads all relevant images
3. Images are stored locally and tracked in SQLite to avoid duplicates
4. Images are grouped into batches for processing
5. Batches are sent to Vertex AI (Gemini models) for data extraction
6. The AI returns structured results in JSONL format
7. Results are parsed and converted into a clean Excel file
8. Duplicate entries are filtered automatically

---

## Output

The final output is a structured Excel file containing:

* Full Name
* ID Number
* Date of Birth
* Date of Issue
* Expiry Date
* Age
* Phone number (based on the received conversation)

---

## Technologies Used

* Python
* Selenium (Web Automation)
* SQLite (Local Database)
* Vertex AI / Gemini (AI Processing)
* Pandas (Data Processing)
* PIL (Image Handling)

---

## Notes

* This project interacts with sensitive data and private systems
* Intended for internal / demonstration purposes only


## Running the program

First you should edit run_automation.bat using a text editor like notepad to change the variables for your own needs.
On default all the credentials have a temporary text that needs to be replaced before running.

After filling the right credentials you can simply run the "run_automation.bat" and wait for the code to finish and run in the background.

Flags :
* SILENT_LOG - Removes unnecessary log from the terminal window.
* CLEAR_IMAGE_FOLDER - If true, deletes the folder set as SAVE_FOLDER entirely, use with causion.
* CLEAR_DATABASE - Clears the sqlite database, basically removing the memory of already 'found' images.

Chat Logic Settings :
* CHAT_MESSAGE_COUNT - How many messages to load.
* CHAT_LOAD_PER_SESSION - How many conversations are pulled each time.
* CHAT_START_INDEX - Where to start the conversation from.
* CHAT_LOAD_ITERATIONS - How many times new conversations are loaded befor stopping the search.

Note that there is GSUTIL, this is not needed if gsutil is set up as path correctly on your pc, if the code fails when trying to run gsutil commands, set the variable to the location where gsutil is installed on your pc.
