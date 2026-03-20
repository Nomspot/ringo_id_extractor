@echo off
title Ringo AI Pipeline

echo =====================================
echo   Ringo AI Automation Pipeline
echo =====================================

:: --- 1. Flags (Booleans) ---
set CLEAR_DATABASE=False
set CLEAR_IMAGE_FOLDER=True
set SILENT_LOG=True

:: --- 2. Credentials (REQUIRED) ---
set RINGO_EMAIL=enter_your_email_here
set RINGO_PASSWORD=enter_your_password_here

:: --- 3. Chat Logic Settings ---
set CHAT_MESSAGE_COUNT=100
set CHAT_LOAD_PER_SESSION=50
set CHAT_START_INDEX=0
set CHAT_LOAD_ITERATIONS=5

:: --- 4. File System & DB Paths ---
set SAVE_FOLDER=downloaded_images
set RESULTS_NAME=results.jsonl

:: --- 5. Google Cloud & AI Settings ---
set GC_PROJECT_ID=your_project_id
set GC_LOCATION=global
set GC_BUCKET_ID=your_bucket_id
set AI_MODEL=gemini-3.1-pro-preview

:: --- 6. Virtual Environment Setup ---
IF NOT EXIST venv (
    echo [SETUP] Creating virtual environment...
    python -m venv venv

    call venv\Scripts\activate

    echo [SETUP] Installing dependencies...
    pip install --upgrade pip
    pip install -r requirements.txt
) ELSE (
    echo [SETUP] Using existing environment...
    call venv\Scripts\activate
)

:: --- EXECUTION ---
echo [RINGO] Launching pipeline...
python main.py

pause
