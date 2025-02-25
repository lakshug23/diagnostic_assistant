from flask import Flask, render_template, request, jsonify, session
import google.generativeai as genai
from pymongo import MongoClient
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secure_key"

# Configure MongoDB
client = MongoClient("mongodb://localhost:27017/")  # Update with your MongoDB URI if needed
db = client["medical_diagnostic_db"]
patients_collection = db["patients"]

# Configure Google Generative AI
genai.configure(api_key="AIzaSyA3lru2fpCUn7SXL1EUCJd8juIR-k7xIps")

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

system_instruction = """
You are a medical diagnostic assistant trained in clinical reasoning. Your task is to predict possible diseases based on the symptoms provided and recommend medicines.

Instructions:
1️⃣ Analyze symptoms along with age, weight, and height.
2️⃣ Provide the **most likely diagnosis**.
3️⃣ Suggest **alternative conditions** if symptoms match multiple conditions.
4️⃣ Recommend **tests for confirmation**.
5️⃣ Suggest **medicines** commonly used for the diagnosed condition (ensure doctor verification).
6️⃣ Keep responses **concise & accurate**.
7️⃣ Warn the patient about any potential health risks.

Example Input:
---
"Age: 25, Weight: 70kg, Height: 170cm, Symptoms: Fever, sore throat, body aches"

Example Output:
---
"Diagnosis: Influenza (flu).  
Alternatives: Common cold, COVID-19.  
Recommended tests: RT-PCR, throat culture.  
Suggested medicines: Paracetamol, Ibuprofen, plenty of fluids, and rest."

---
Follow this structured format strictly.
"""

# Initialize the model
model = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    generation_config=generation_config,
    system_instruction=system_instruction,
)

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/diagnose', methods=['POST'])
def diagnose():
    data = request.json
    name = data.get("name")
    age = data.get("age")
    weight = data.get("weight")
    height = data.get("height")
    symptoms = data.get("symptoms")
    
    input_text = f"Age: {age}, Weight: {weight}kg, Height: {height}cm, Symptoms: {', '.join(symptoms)}"
    response = model.generate_content(input_text)
    
    diagnosis_data = response.text
    session['diagnosis_data'] = diagnosis_data  # Store in session for review page

    # Store patient data in MongoDB
    patient_record = {
        "name": name,
        "age": age,
        "weight": weight,
        "height": height,
        "symptoms": symptoms,
        "diagnosis": diagnosis_data,
        "date": datetime.utcnow()
    }
    patients_collection.insert_one(patient_record)

    return jsonify({"diagnosis": diagnosis_data})

@app.route('/review')
def review():
    return render_template("review.html", diagnosis=session.get('diagnosis_data', 'No diagnosis available'))

@app.route('/patients', methods=['GET'])
def get_patients():
    patients = list(patients_collection.find({}, {"_id": 0}))  # Exclude MongoDB's default _id field
    return jsonify({"patients": patients})

if __name__ == '__main__':
    app.run(debug=True)
