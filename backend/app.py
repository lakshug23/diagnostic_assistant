from flask import Flask, render_template, request, jsonify, session
import google.generativeai as genai
import tensorflow as tf
from PIL import Image, ImageOps
import numpy as np
import cv2
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

# Updated system instruction to include medicine recommendations
system_instruction = """
You are a medical diagnostic assistant trained in clinical reasoning. Your task is to predict possible diseases based on the symptoms provided and recommend medicines.

Instructions:
1️⃣ Analyze symptoms along with age, weight, and height.
2️⃣ Provide the **most likely diagnosis**.
3️⃣ Suggest **alternative conditions** if symptoms match multiple conditions.
4️⃣ Recommend **tests for confirmation**.
5️⃣ Suggest **medicines** commonly used for the diagnosed condition (ensure doctor verification).
6️⃣ Keep responses **concise & accurate**.
7.Make them aware of any risk if they have any (eg.likely to get heart attack)
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

# Load the saved Keras model
#img_model = tf.keras.models.load_model('/Users/lakshanagopu/Desktop/diagnostic_tool/malaria_detect_model.keras')
print("Model loaded successfully")

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/diagnose', methods=['POST'])
def diagnose():
    # if "file" not in request.files:
    #     return jsonify({"error": "No file uploaded"}), 400

    # file = request.files["file"]

    # if file.filename == "":
    #     return jsonify({"error": "No selected file"}), 400

    # # Save file
    # file_path = os.path.join(app.config["UPLOAD_FOLDER"], secure_filename(file.filename))
    # file.save(file_path)

    # # Process image using OpenCV
    # #img = cv2.imread(file_path)  # Read image

    
    #img_model = 
    data = request.json
    age = data.get("age")
    weight = data.get("weight")
    height = data.get("height")
    symptoms = data.get("symptoms")
    image_path = data.get("imageUpload")
    print(image_path)
    #insert input stmet for blood image
    
    input_text = f"Age: {age}, Weight: {weight}kg, Height: {height}cm, Symptoms: {', '.join(symptoms)}"
    response = model.generate_content(input_text)
    
    #img_response = image_analyse(image_path)
    diagnosis_data = response.text
    session['diagnosis_data'] = diagnosis_data  # Store in session for review page

    return jsonify({"diagnosis": diagnosis_data})

@app.route('/review')
def review():
    return render_template("review.html", diagnosis=session.get('diagnosis_data', 'No diagnosis available'))


@app.route('/print')
def print_page():
    return render_template("print.html", diagnosis=session.get('diagnosis_data', 'No diagnosis available'))


    

def preprocess_image(file_path):
    try:
        # Load the image and preprocess it
        image = Image.open(file_path)
        # Resize the image to the expected input size (e.g., 64x64 or 224x224 based on model)
        image = image.resize((64, 64), resample=Image.Resampling.LANCZOS)  # Change to 224 if needed
        image = np.array(image) / 255.0  # Normalize to [0, 1]
        image = np.expand_dims(image, axis=0)  # Add batch dimension
        return image
    except Exception as e:
        print(f"Error loading image: {e}")

def image_analyse(image_path):


    # Preprocess the image
    image = preprocess_image(image_path)
    if image is not None:

        # Perform prediction using the loaded model
        prediction = img_model.predict(image)
        result = "Non-Parasitic" if prediction[0][0] < 0.5 else "Parasitic"
        return result
    
if __name__ == '__main__':
    app.run(debug=True)
