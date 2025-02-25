from flask import Flask, render_template, request, jsonify, session
import google.generativeai as genai
import tensorflow as tf
from PIL import Image, ImageOps
import numpy as np
import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'uploads'  # Folder where images will be stored
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = "secure_key"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

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
7️⃣ Make them aware of any risk if they have any (e.g., likelihood of heart disease).
---
Example Input:
"Age: 25, Weight: 70kg, Height: 170cm, Symptoms: Fever, sore throat, body aches"

Example Output:
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

# Load the saved Keras model
img_model = tf.keras.models.load_model('/Users/jana/Documents/Github/diagnostic_assistant/malaria_detect_model.keras')
print("Model loaded successfully")

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/diagnose', methods=['POST'])
def diagnose():
    # Get form data
    age = request.form.get("age")
    weight = request.form.get("weight")
    height = request.form.get("height")
    symptoms = request.form.get("symptoms").split(",")  # Split symptoms by comma

    # Handle image upload
    file = request.files.get("imageUpload")
    file_path = None
    img_response = None

    if file and file.filename:
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], secure_filename(file.filename))
        file.save(file_path)
        print(f"File saved at {file_path}")

        # Process the uploaded image if available
        img_response = image_analyse(file_path)

    input_text = f"Age: {age}, Weight: {weight}kg, Height: {height}cm, Symptoms: {', '.join(symptoms)}"
    response = model.generate_content(input_text)

    diagnosis_data = response.text
    if img_response:
        diagnosis_data += f"\nImage Analysis Result: {img_response}"

    session['diagnosis_data'] = diagnosis_data  # Store in session for review page

    return jsonify({"diagnosis": diagnosis_data})


@app.route('/review')
def review():
    return render_template("review.html", diagnosis=session.get('diagnosis_data', 'No diagnosis available'))


@app.route('/print')
def print_page():
    return render_template("print.html", diagnosis=session.get('diagnosis_data', 'No diagnosis available'))


def preprocess_image(image_path):
    img = Image.open(image_path)
    
    # Convert image to RGB if it has an alpha channel (RGBA)
    if img.mode == 'RGBA':
        img = img.convert('RGB')
    
    # Resize and normalize the image
    img = img.resize((64, 64))
    img_array = np.array(img) / 255.0
    img_array = np.expand_dims(img_array, axis=0)  # Add batch dimension
    
    return img_array

def image_analyse(image_path):
    # Preprocess the image
    image = preprocess_image(image_path)
    if image is not None:
        # Perform prediction using the loaded model
        prediction = img_model.predict(image)
        result = "Non-Parasitic" if prediction[0][0] < 0.5 else "Parasitic"
        return result
    return None  # Return None if image processing fails

if __name__ == '__main__':
    app.run(debug=True)
