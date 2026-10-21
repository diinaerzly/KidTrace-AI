KidTrace AI — HTML + Python Hybrid

WHY THIS VERSION
----------------
The landing/login/dashboard use normal HTML/CSS/JavaScript, so the Claude design can be
kept almost exactly. Python is used as the backend for your real search functionality,
database, scoring, movement trail, dispatch and resolved status.

FILES
-----
app.py                  Flask backend
database.py             Your existing SQLite case database functions
templates/index.html    Claude-style frontend
requirements.txt
data/                   COPY YOUR EXISTING DATA FOLDER HERE

Your data folder should contain:
data/
  cctv_metadata.csv
  cctv_videos/
  floor_plan/
    floor plan elmina.png
  kidtrace.db  (created automatically if missing)

HOW TO RUN
----------
Open VS Code terminal inside this project folder.

1. Create / use a venv:
   py -3.11 -m venv venv
   venv\Scripts\activate

2. Install packages:
   pip install -r requirements.txt

3. Run:
   python app.py

4. Open:
   http://127.0.0.1:8501

LOGIN
-----
Staff ID: SEC001
Password: kidtrace123

IMPORTANT
---------
- The HTML/CSS layout is no longer constrained by Streamlit.
- Search similarity and movement trail remain prototype/simulated logic.
- Human verification is still required.
- The official Elmina directory is loaded from Sime Darby Property at runtime,
  so keep internet access on during the demo.
