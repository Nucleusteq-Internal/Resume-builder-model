from flask import Flask, request, jsonify, render_template
import fitz  # PyMuPDF
import os
from langchain_groq import ChatGroq
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
import json, requests
import re
from flask_cors import cross_origin, CORS
from docx import Document



app = Flask(__name__, template_folder="templates")
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
CORS(app)

# Initialize ChatGroq with the API key and model name
groq_api_key = "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"
llm = ChatGroq(groq_api_key=groq_api_key, model_name="Gemma2-9b-it")


def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with fitz.open(pdf_path) as pdf:
            for page in pdf:
                text += page.get_text()

        text = text.replace("\n", " ")
        # print(text)
        # print("tetx extracted sucessfyllu")
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")

    return text

def extract_text_from_word(docx_path):
    """
    Extracts text from a Word (.docx) file and saves it into a new Word file.

    Args:
        docx_path (str): Path to the .docx file.

    Returns:
        str: Extracted text from the document.
    """
    text = ""
    try:
        # Open the Word document
        document = Document(docx_path)
        
        # Extract text from each paragraph
        for paragraph in document.paragraphs:
            text += paragraph.text + "\n"

        text = text.replace("\n", "")

        
        
        print(f"Extracted text:", text)
    except Exception as e:
        print(f"Error extracting text from Word document: {e}")
    
    return text

def sanitize_json_string(json_string):
    """
    Sanitize the JSON string by replacing invalid characters and fixing encoding issues.
    """
    # Replace invalid characters (e.g., â) with a space or remove them
    sanitized_string = re.sub(r"[^\x20-\x7E]", "", json_string)  # Remove non-ASCII characters
    sanitized_string = sanitized_string.replace("\\n", " ")  # Replace newlines with spaces
    sanitized_string = sanitized_string.replace("\\t", " ")  # Replace tabs with spaces
    return sanitized_string
def parse_resume(pdf_text):

    keys_list = """
name

email

contactNo

objective

profileData 
  - professionalSummary 
  - certificates (type : list)
  - technicalSkills 
      - technology (type : list)
      - programming (type : list)
      - tools (type : list)
  - professionalExperience
      - jobTitle
      - companyName
      - projectName
      - startDate
      - endDate
      - techStack (type : str)
      - details (type : str)
  - education (type : list of dictionaries)
      - course
      - collegeName
      - duration

"""

    prompt_template = PromptTemplate(
        template=f"""
    You are an expert in resume evaluation. Extract the following information from the provided resume text and format it as a JSON object and make sure not affect the json keys, all keys must be same and also nesting must be same not change the structure of it:

    {keys_list}
    **Note**: "At the time of returning the response please do not change the keys. Please make sure it would be same after generating response in json. Also not change in the nested keys or nested json or dictonary it would also be same as mentioned in keys list. 
    Only fetch information that i mentioned in the keylist from the resume not more than that. Please verify it a correct and valid json format. Also make sure that the json keys are not changed and also the nested keys are not changed. Please do not change any keys or nested keys in the json format.
    If you find any invalid characters or encoding issues, please fix them before returning the JSON response. The JSON should be well-formed and valid."
    **Bro! You don't get what I said? I told not change any json keys and also nested keys"
    **Ignore any bullet points in response but give full info
    Resume:
    {{resume_text}}
    """,
        input_variables=["resume_text"],
    )

    # Create an LLMChain with the prompt
    qa_chain = LLMChain(llm=llm, prompt=prompt_template)

    try:
        # Call the chain with the resume text
        response = qa_chain.run({"resume_text": pdf_text})

        # Remove unwanted backticks and extra formatting around JSON
        clean_response = re.sub(r"```json|```", "", response).strip()

        # Parse the string into a JSON object
        # json_data = json.loads(clean_response)

        return clean_response

    except json.JSONDecodeError as e:
        print(f"JSON decoding error: {e}")
        print("Response was:", response)
        return None
    except Exception as e:
        print(f"An error occurred while parsing the resume: {e}")
        return None


@app.route("/resume/builder/model/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/resume/builder/model/upload", methods=["POST"])
@cross_origin(origin='*')
def upload_file():
    if "resume" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["resume"]
    if file.filename == "":
        return jsonify({"error": "Invalid file format, only PDF accepted"}), 400

    # Check for valid file formats
    if not (file.filename.endswith(".pdf") or file.filename.endswith(".docx")):
        return jsonify({"error": "Invalid file format. Only PDF and Word (.docx) accepted"}), 400


    # Save and extract text from PDF
    upload_folder = os.path.join(os.getcwd(), "uploads")
    os.makedirs(upload_folder, exist_ok=True)
    file_path = os.path.join(upload_folder, file.filename)
    file.save(file_path)

    extracted_text = ""
    # Extract text based on file type
    if file.filename.endswith(".pdf"):
        pdf_text = extract_text_from_pdf(file_path)
        extracted_text = pdf_text
    elif file.filename.endswith(".docx"):
        word_text = extract_text_from_word(file_path)
        extracted_text = word_text
    else:
        return jsonify({"error": "Unsupported file format"}), 400

    # Send text to Groq AI to parse into structured JSON
    extracted_data = parse_resume(extracted_text)
    print("Raw extracted data:", extracted_data)
    if not extracted_data:
        return jsonify({"error": "Failed to process resume text"}), 500
    try:
        
        sanitized_data = sanitize_json_string(extracted_data)
        json_data = json.loads(sanitized_data)
        print(json_data)
    except json.JSONDecodeError as e:
        # Handle JSON decoding error
        print(f"JSON decoding error: {e}")
        print("Sanitized response was:", sanitized_data)
        return jsonify({"error": "Failed to parse JSON response", "data":sanitized_data}), 500
    json_data = json.loads(extracted_data)
    print(json_data)

    # return json_data

    # springboot_url = "http://localhost:8080/resume/builder/backend/api/candidate-profiles/upload"
    springboot_url = "https://www.resume.plasma.nucleusteq.com/resume/builder/backend/api/candidate-profiles/upload"

    # # # # Send JSON data to Spring Boot API
    try:
        response = requests.post(springboot_url, json=json_data)
        if response.status_code == 201:
            return jsonify({"message": "Resume processed and saved successfully"}), 201
        else:
            return (
                jsonify({"error": "Failed to save resume data to Spring Boot API"}),
                response.status_code,
            )
    except requests.exceptions.RequestException as e:
        print(f"Error sending data to Spring Boot API: {e}")
        return jsonify({"error": "Unable to connect to Spring Boot API"}), 500


if __name__ == "__main__":
    app.run(debug=True)
