let symptoms = [];

function addSymptom() {
    let symptomInput = document.getElementById("symptomInput");
    let symptom = symptomInput.value.trim();

    if (symptom !== "") {
        symptoms.push(symptom);
        document.getElementById("selectedSymptoms").innerHTML = symptoms.join(", ");
        symptomInput.value = "";
    }
}

function getDiagnosis() {
    let age = document.getElementById("age").value;
    let weight = document.getElementById("weight").value;
    let height = document.getElementById("height").value;

    if (!age || !weight || !height || symptoms.length === 0) {
        alert("Please fill in all fields and add symptoms.");
        return;
    }

    fetch("/diagnose", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ age, weight, height, symptoms })
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById("result").innerHTML = `<strong>Diagnosis:</strong> ${data.diagnosis}`;
        document.getElementById("proceedButton").style.display = "block";
    })
    .catch(error => console.error("Error:", error));
}

function proceedToReview() {
    window.location.href = "/review";
}
