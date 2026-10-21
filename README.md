
# KidTrace-AI by The Cyberspark
AI-assisted CCTV search prototype for missing-child incidents, developed for Sime Darby Property University Hackathon 2026.

**AI-Assisted CCTV Search for Missing-Child Incidents**

KidTrace AI is a security-support prototype designed to help authorised mall security personnel prioritise relevant CCTV footage during missing-child incidents.

## Key Features

- Create a missing-child incident profile using a recent photo and visual details
- Record clothing, approximate height, last-seen time and location
- Display ranked CCTV candidate sightings
- Show similarity indicators, camera location and timestamp
- Support human verification before action is taken
- Generate a movement timeline and latest probable location
- Support officer dispatch workflow
- Provide incident analytics and search history

## Current Prototype

The current prototype demonstrates the complete search and response workflow using AI-generated simulated CCTV footage, stored similarity scores, contextual information and human verification.

The similarity scores shown in the prototype are demonstration indicators and are not verified probabilities of identity.

## Proposed AI Implementation

The proposed full implementation will integrate:

- YOLO-based person detection
- Person Re-Identification (Re-ID)
- Deep-learning visual embeddings
- Clothing and contextual attribute matching
- Multi-factor candidate ranking

The goal is to automatically generate and rank potential sightings from CCTV footage while keeping authorised security personnel responsible for final verification.

## Technology Stack

- Python
- Flask
- HTML
- CSS
- JavaScript
- pandas
- SQLite

## How to Run the Prototype

### 1. Clone the repository

```bash
git clone https://github.com/diinaerzly/KidTrace-AI.git
```

### 2. Open the project folder

```bash
cd KidTrace-AI
```

### 3. Create a virtual environment

```bash
python -m venv venv
```

### 4. Activate the virtual environment

For Windows:

```bash
venv\Scripts\activate
```

### 5. Install the required packages

```bash
pip install -r requirements.txt
```

### 6. Run the application

```bash
python app.py
```

### 7. Open the system

Open a browser and go to:

```text
http://127.0.0.1:8501
```

## How to Use KidTrace AI

1. Log in to the KidTrace AI security dashboard.
2. Open the **Search** page.
3. Upload a recent photo of the missing child.
4. Enter the available information, including:
   - Clothing colour
   - Approximate height
   - Last-seen date
   - Last-seen time
   - Last-seen location
5. Start the CCTV search.
6. Review the ranked candidate sightings presented by the system.
7. Open the candidate CCTV clips and compare the possible matches.
8. Use the **Human Verification** step to verify the most relevant sighting.
9. Review the movement timeline showing the sequence of possible sightings.
10. Check the latest probable location identified by the system.
11. Dispatch security personnel to the relevant area.
12. Use the **Dashboard** to monitor incident history, case status, resolution information and search analytics.

## Prototype Workflow

**Report → Search → Rank → Verify → Track → Dispatch**

## Developed For

**Sime Darby Property University Hackathon 2026**

**Team CyberSpark**

**Theme:** People  
**Category:** Safety & Security

## Disclaimer

This prototype was developed for demonstration purposes. The CCTV footage used in the system is AI-generated simulated footage and does not represent real missing-child surveillance footage.

The current prototype uses stored similarity scores to demonstrate the intended AI-assisted search workflow. The proposed full implementation will integrate automated person detection and visual re-identification technologies.

---

**Finding Lost Children Faster, Bringing Loved Ones Back Together with KidTrace AI.**

