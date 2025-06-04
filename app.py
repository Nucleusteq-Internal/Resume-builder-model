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
from transformers import AutoTokenizer
from langchain.text_splitter import RecursiveCharacterTextSplitter
import textwrap
from dotenv import load_dotenv
import boto3
import logging

# Initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)



app = Flask(__name__, template_folder="templates")
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
CORS(app)

load_dotenv()

# Initialize ChatGroq with the API key and model name
# groq_api_key = os.environ.get("GROQ_API_KEY")
# def get_secret():
#     """Fetch secrets from AWS Secrets Manager and set them as environment variables (for production)."""
    
#     aws_region = os.environ.get("AWS_REGION", "us-west-2")  # Default to us-west-2 if not set
#     secret_name = os.environ.get("SECRET_NAME",'resume_builder_prod_groq_api_key')

#     try:
#         # Initialize AWS Secrets Manager client
#         client = boto3.client("secretsmanager", region_name=aws_region)

#         # Retrieve secret
#         response = client.get_secret_value(SecretId=secret_name)

#         # Parse secret (AWS Secrets Manager stores secrets as a JSON string)
#         secret_data = json.loads(response["SecretString"])

#         # Set each secret key-value pair as an environment variable
#         for key, value in secret_data.items():
#             os.environ[key] = value

#         logger.info(f"Secrets successfully loaded for environment")

#     except Exception as e:
#         logger.error(f"Error retrieving secrets: {e}", exc_info=True)
#         raise RuntimeError("Failed to load secrets from AWS Secrets Manager.")


# resume_builder_secrets = get_secret()
groq_api_key = os.environ.get("GROQ_API_KEY")
if not groq_api_key:
    raise RuntimeError("GROQ_API_KEY is not set in environment variables.")

llm = ChatGroq(groq_api_key="gsk_309VDgogbpQcLbVwZ7BzWG"+groq_api_key, model_name=os.environ.get("LLM_Model"))

keys_list = textwrap.dedent("""
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

""")


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
    """
    Parses resume text into a structured JSON format using LLM in two steps:
    1. Extracts logical resume sections.
    2. Sends sectioned data back to the LLM for final JSON formatting.
    Includes retry logic and JSON sanitization.
    """

    

    prompt_template = PromptTemplate(
        template=f"""
You are an expert in resume evaluation. Extract the following information from the resume text.
The format must match this schema exactly:
{keys_list}

**Strict Instructions**:
- Do not change any key or nesting in the JSON.
- Do not add or remove keys.
- Only extract and populate available data.
- If a value is not found, return it as an empty string or empty list.
- Ignore bullets and formatting symbols.
- Ensure it is a valid, parsable JSON response.
- Do not include any additional text or explanations.
- Do not include any backticks or code blocks.
- add data to suitable keys and values
- double check the keys_list and the JSON response. Do not add any extra keys or values.

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
    userId = request.form.get("userId")  
    role = request.form.get("role")

    print(f"Received parameters: userId={userId}, role={role}")

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
        # print(json_data)
    except json.JSONDecodeError as e:
        # Handle JSON decoding error
        print(f"JSON decoding error: {e}")
        print("Sanitized response was:", sanitized_data)
        return jsonify({"error": "Failed to parse JSON response", "data":sanitized_data}), 500
    # json_data = json.loads(extracted_data)
    # print(json_data)

    # return json_data
    api_url = os.environ.get("SPRINGBOOT_API_URL")
    print(f"SPRINGBOOT URL: {api_url}")
    if((role == "ROLE_EMPLOYEE") and (userId is not None)):
        userId = int(userId)
        springboot_url = f"{api_url}/resume/builder/backend/api/user-profiles/update-profile/{userId}"
        
        try:
            response = requests.put(springboot_url, json=json_data)
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
        
    

    else:
        springboot_url = f"{api_url}/resume/builder/backend/api/candidate-profiles/upload"
        try:
            response = requests.post(springboot_url, json=json_data)
            if response.status_code == 201:
                return jsonify({"message": "Resume processed and saved successfully"}), 201
            else:
                return (jsonify({"error": "Failed to save resume data to Spring Boot API"}),response.status_code,)
        except requests.exceptions.RequestException as e:
            print(f"Error sending data to Spring Boot API: {e}")
            return jsonify({"error": "Unable to connect to Spring Boot API"}), 500
        # springboot_url = "http://localhost:8080/resume/builder/backend/api/candidate-profiles/upload"
        # springboot_url = "https://www.resume.plasma.nucleusteq.com/resume/builder/backend/api/candidate-profiles/upload"

    # # # # Send JSON data to Spring Boot API
    


if __name__ == "__main__":
    app.run(debug=True)
