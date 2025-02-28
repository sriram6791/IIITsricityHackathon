from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from werkzeug.utils import secure_filename
import easyocr
from pdf2image import convert_from_path
import numpy as np
from google import genai
import json
import re
import os

app = Flask(__name__)
CORS(app)
file_names_response = []  # Global list to store response file paths
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    files = request.files.getlist('file')  # Get multiple files

    if not files:
        return jsonify({"error": "No files selected"}), 400

    response_data = []

    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(save_path)

            try:
                # Perform OCR on the uploaded file and save the text (with metadata) to a .txt file
                extracted_text = perform_ocr(save_path, filename)

                # Generate Gemini AI response
                gemini_response = process_with_gemini(extracted_text)

                # Save the Gemini response to a new file
                response_filename = f"{os.path.splitext(filename)[0]}_response.txt"
                response_filepath = os.path.join(app.config['UPLOAD_FOLDER'], response_filename)

                file_names_response.append(response_filepath)

                with open(response_filepath, 'w', encoding='utf-8') as f:
                    f.write(gemini_response)

                response_data.append({
                    "filename": filename,
                    # First 500 characters of the extracted text
                    "ocr_text_preview": extracted_text[:500],
                    "gemini_response_file": response_filename
                })

            except Exception as e:
                print("Error during processing:", e)
                return jsonify({"error": "Processing failed: " + str(e)}), 500
        else:
            response_data.append({"error": f"File type not allowed for {file.filename}"})

    return jsonify({
        "message": "Files uploaded and processed successfully!",
        "files": response_data
    }), 200


def perform_ocr(filepath, filename):
    extracted_text = ""
    file_extension = filename.rsplit('.', 1)[1].lower()

    if filename.lower().endswith('.pdf'):
        try:
            # Update this path to point to your Poppler bin directory
            POPPLER_PATH = r'C:\Users\govin\Downloads\Release-24.08.0-0\poppler-24.08.0\Library\bin'
            images = convert_from_path(filepath, poppler_path=POPPLER_PATH)
        except Exception as e:
            print("Error converting PDF to images:", e)
            raise e

        reader = easyocr.Reader(['en'], gpu=False)
        for image in images:
            img_np = np.array(image)
            result = reader.readtext(img_np, detail=0)
            extracted_text += "\n".join(result) + "\n"
    else:
        reader = easyocr.Reader(['en'], gpu=False)
        result = reader.readtext(filepath, detail=0)
        extracted_text = "\n".join(result)

    # Prepare metadata and prepend it to the extracted text
    metadata = f"MetaData : {{\nFileName: {filename}\nFileType: {file_extension}\n}}\n\n"
    final_text = metadata + extracted_text

    # Save the final text with metadata to a .txt file
    base_name = os.path.splitext(filename)[0]
    txt_filename = base_name + ".txt"
    txt_filepath = os.path.join(os.path.dirname(filepath), txt_filename)
    try:
        with open(txt_filepath, 'w', encoding='utf-8') as f:
            f.write(final_text)
        print(f"OCR text with metadata saved to: {txt_filepath}")
    except Exception as e:
        print("Error saving text file:", e)

    return final_text


def process_with_gemini(extracted_text):
    prompt = f"""You are a document analysis assistant. Analyze the provided text and perform the following tasks:
    Analyse this text: "{extracted_text}"
    I need output in this format:
    1. MetaData : Keep whats there in file as it is don't change anything.
    2. Summary: Generate a concise summary of the given text , keep it as small as possible and dont exceed more than 5 lines.  
    3. Sentiment: Determine the overall sentiment of the given text (positive, negative, neutral).  
    4. Class: Classify the given text strictly as one of the following: invoices, contracts, resume, document.  
    5. Tags: Extract relevant keywords (tags) that capture the main topics of the document order them in most important to least , only give top five tags.  
    6. DataType : Numerical/Text/both  Give kind of data present in the document.
    7. Importance : Rate the importance of a given file on a scale of 0 to 5, where 0 is least important and 5 requires urgent attention. Assign ratings based on the document's significance in its field. For example, medical files with abnormalities should be rated 5, unpaid bills near their deadline should be rated 4 (adjusted based on time left), and serious legal issues should receive high priority. Apply this logic across all domains—prioritizing documents containing critical or time-sensitive information.
    ---------------------------
    If the given file has Medical data then only keep this section else skip this complete below section
    Medical data:
    Paitent Name:[
        Patient Identification: [This should contain full Patient information,Insurance Details,his/her Address and demographics]
        
        Clinical Data : [This section should contain primary diagnosis information, if any abnormals are present in the report just indicate show them here , for example RBC: count is very less ,Also mention and important sympotms found in the report if mentioned]
        
        Billing : [Analize the bills of the patient, Take important Dates and Times,Total amount to be paid,and important imformation from bills]
        
    ]
    the above three are not must , if a file has patient information you can skip clinical data and Billing sections and only keep Patient Identification, if the file only contains Billing then only keep  Billing information and you can skip Patient Identification and Clinical Data fileds.
    
    NOTE : KEEP THE PATIENT NAME AS IT IS BECAUSE IT WILL BE HELPING US IN MAPPING DIFFERENT FILES OF SAME PATIENT,FOR NOW PATIENT NAME IS UNIQUE AND NO DUBLICATES WILL BE THERE,ALSO DONT ADD ANY NEW DATA JUST PRESENT THE MEDICAL DATA AS IT IS GIVEN IN FILE, NO SUGGESTIONS OR PREDICTIONS,BECAUSE THIS IS A VERY SENSITIVE APPLICATION.
    ---------------------------

    Output your result strictly in the following format only give just txt no json format :

    MetaData:[Same as given in extracted file no changes]
    summary: [Your 4-5 line summary]  
    sentiment: [Your sentiment]  
    class: [Your classification]  
    tags: [Your tags]
    datatype: [Numerical/Text/both Numerical and Text]
    importance: [rating on a scale of 0 to 5]
    
    ---------------------------------
    (THE BELOW SECTION ONLY APPLICABLE FOR MEDICAL FILES FOR OTHER FILES SKIP THIS SECTION)
    Medical data:
    PatientName:[
        Patient Identification: (if applicable)
        Clinical Data : (if applicable)
        Billing : (if applicable)
    ]
    ----------------------------------
    """
    client = genai.Client(api_key="AIzaSyDmGsZVGp5bzKuXLHxiCMD9-BzqmHYGwcA")
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
    )
    return response.text


def process_with_gemini2(extracted_text):
    client = genai.Client(api_key="AIzaSyDmGsZVGp5bzKuXLHxiCMD9-BzqmHYGwcA")
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=extracted_text
    )
    return response.text


def extract_summary_tags(file_path):
    """Extracts the first sentence of the summary and the tags from a response file."""
    summary = ""
    tags = ""

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines:
                if line.startswith("summary:"):
                    summary = line.replace("summary:", "").strip()
                    # Take only first sentence
                    summary = summary.split(".")[0] + "."
                elif line.startswith("tags:"):
                    tags = line.replace("tags:", "").strip()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")

    return summary, tags

# NEED TO CHANGE THIS BELOW FUNCTION
def extract_fields(file_path):
    """
    Extracts fields from the given file's content.
    Supports both plain text responses and JSON formatted files.
    Returns a dictionary with keys:
    MetaData, summary, sentiment, class, tags, datatype, importance, Medical data.
    """
    fields = {
        "MetaData": "",
        "summary": "",
        "sentiment": "",
        "class": "",
        "tags": "",
        "datatype": "",
        "importance": "",
        "Medical data": ""
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Attempt JSON parsing if the content appears to be JSON formatted
        content_strip = content.strip()
        if content_strip.startswith("{") and content_strip.endswith("}"):
            try:
                data = json.loads(content_strip)
                # Extract fields from JSON keys, converting lists/dicts to strings if needed
                fields["MetaData"] = json.dumps(data.get("MetaData", {}), indent=2)
                fields["summary"] = data.get("summary", "")
                fields["sentiment"] = data.get("sentiment", "")
                fields["class"] = data.get("class", "")
                tags_val = data.get("tags", "")
                if isinstance(tags_val, list):
                    fields["tags"] = ", ".join(tags_val)
                else:
                    fields["tags"] = tags_val
                fields["datatype"] = data.get("datatype", "")
                fields["importance"] = str(data.get("importance", ""))
                if "Medical data" in data:
                    fields["Medical data"] = json.dumps(data.get("Medical data", {}), indent=2)
                return fields
            except Exception as e:
                # If JSON parsing fails, fall back to regex-based extraction
                print(f"JSON parsing failed for {file_path}: {e}")
        
        # Regex-based extraction for plain text files
        
        # Capture MetaData block between the starting "MetaData" and the next field marker (assumed "summary:")
        meta_pattern = re.compile(r"MetaData\s*[:]*\s*(\{[\s\S]+?\})", re.IGNORECASE)
        summary_pattern = re.compile(r"summary\s*:\s*([\s\S]+?)(?=\n(?:sentiment:|class:|tags:|datatype:|importance:|Medical data:|$))", re.IGNORECASE)
        sentiment_pattern = re.compile(r"sentiment\s*:\s*(.+)", re.IGNORECASE)
        class_pattern = re.compile(r"class\s*:\s*(.+)", re.IGNORECASE)
        tags_pattern = re.compile(r"tags\s*:\s*(.+)", re.IGNORECASE)
        datatype_pattern = re.compile(r"datatype\s*:\s*(.+)", re.IGNORECASE)
        importance_pattern = re.compile(r"importance\s*:\s*(.+)", re.IGNORECASE)
        medical_pattern = re.compile(r"Medical data\s*:\s*([\s\S]+?)(?=\n[-]+|$)", re.IGNORECASE)
        
        meta_match = meta_pattern.search(content)
        if meta_match:
            fields["MetaData"] = meta_match.group(1).strip()
        
        summary_match = summary_pattern.search(content)
        if summary_match:
            fields["summary"] = summary_match.group(1).strip()
        
        sentiment_match = sentiment_pattern.search(content)
        if sentiment_match:
            fields["sentiment"] = sentiment_match.group(1).strip()
        
        class_match = class_pattern.search(content)
        if class_match:
            fields["class"] = class_match.group(1).strip()
        
        tags_match = tags_pattern.search(content)
        if tags_match:
            fields["tags"] = tags_match.group(1).strip()
        
        datatype_match = datatype_pattern.search(content)
        if datatype_match:
            fields["datatype"] = datatype_match.group(1).strip()
        
        importance_match = importance_pattern.search(content)
        if importance_match:
            fields["importance"] = importance_match.group(1).strip()
        
        medical_match = medical_pattern.search(content)
        if medical_match:
            fields["Medical data"] = medical_match.group(1).strip()
    
    except Exception as e:
        print(f"Error extracting fields from {file_path}: {e}")
    
    return fields


def generate_llm_input(file_names_response):
    """
    Generates the formatted input string for the LLM API by extracting and formatting
    all required fields (MetaData, summary, sentiment, class, tags, datatype, importance,
    and Medical data if available) from each response file.
    """
    llm_input = ""

    for file_path in file_names_response:
        filename = os.path.basename(file_path)
        fields = extract_fields(file_path)
        
        llm_input += f"{filename}:\n"
        llm_input += f"MetaData: {fields.get('MetaData', '')}\n"
        llm_input += f"summary: {fields.get('summary', '')}\n"
        # llm_input += f"sentiment: {fields.get('sentiment', '')}\n"
        llm_input += f"class: {fields.get('class', '')}\n"
        llm_input += f"tags: {fields.get('tags', '')}\n"
        # llm_input += f"datatype: {fields.get('datatype', '')}\n"
        llm_input += f"importance: {fields.get('importance', '')}\n"
        if fields.get("Medical data", ""):
            llm_input += f"Medical data: {fields.get('Medical data', '')}\n"
        llm_input += "\n"
    
    return llm_input

@app.route('/group', methods=['GET'])
def group_files():
    # Debug print to see current response file list
    print("file_names_response:", file_names_response)

    # Generate the input string from all response files
    llm_input_string = generate_llm_input(file_names_response)

    # Create the grouping prompt
    final_prompt = f"""{llm_input_string}
This is the details of the files.
The format is of form:

MetaData:(Which contain FileName,FileType) [EXTRACT FileName from here this is the original file name]
summary:
class:
tags:
importance:
Medical data: (very very important)
---------
SO MetaData is the starting point of any file

Now your task is to group the files according to their tags. Create groups with meaningful group names based on the tags.
For example, if some files are related to medical topics, group them under 'medical'; if some are legal documents, group them under 'legal';
if some are bills, group them under 'bills'.Also if we dive deep into Medical data , our dataset is scattered , a patient can have any number of files for example a person named amit can have patientdetails file,clinicaldata file,bills related to him you should identify the files belonging to a person by the Name of the patient provided in each file , so in out case all files contain name amit , sometimes if name is neha sharma , but files have first name Neha and second name shema its still considered files of same person, we can have scattered files of many files belonging to many different people, we should group like

Amit Verma : {{amitbilldata.pdf,amitclinicaldata.pdf,amitpatientdetails.pdf}}

Final output should look like:
Groups :
"medical" : {{file1, file2, file3}}
"legal" : {{file4, file5, file6}}
"bills" : {{file7, file8, file9}}
"patient name":{{all his files}}
----
After this our task is to provide summary of medical data of all patients
it should be of format:
"Medical Data":
[
    "patient1 name":[
        Patient Identification: [This should contain full Patient information,Insurance Details,his/her Address and demographics]
        
        Clinical Data : [This section should contain primary diagnosis information, if any abnormals are present in the report just indicate show them here , for example RBC: count is very less ,Also mention and important sympotms found in the report if mentioned]
        
        Billing : [Analize the bills of the patient, Take important Dates and Times,Total amount to be paid,and important imformation from bills]
    ]
    
    "patient2 name":[
        Patient Identification: [This should contain full Patient information,Insurance Details,his/her Address and demographics]
        
        Clinical Data : [This section should contain primary diagnosis information, if any abnormals are present in the report just indicate show them here , for example RBC: count is very less ,Also mention and important sympotms found in the report if mentioned]
        
        Billing : [Analize the bills of the patient, Take important Dates and Times,Total amount to be paid,and important imformation from bills]
    ]
]
as given, previously person1's Patient Identification is in one file,Clinical Data is in other file,Billing is in other file and soo on , now we are gathering all the information belong to a person from scattered data and showing at one place.

NOTE :PATIENT NAME IS UNIQUE AND CAN BE USED IN MAPPING DIFFERENT FILES OF SAME PATIENT,FOR NOW PATIENT NAME IS UNIQUE AND NO DUBLICATES WILL BE THERE,ALSO DONT ADD ANY NEW DATA JUST PRESENT THE MEDICAL DATA AS IT IS GIVEN IN FILE, NO SUGGESTIONS OR PREDICTIONS,BECAUSE THIS IS A VERY SENSITIVE APPLICATION.

NOTE : GIVE PATIENT NAME TO GROUP AND in MEDICAL DATA SUMMARY SO THEY BOTH CAN BE EASYLY MAPPED.

Output should be strictly in the following json format:

"Groups":[
"group_name1" : [file names]]
"group_name2" : [[file names]]
"patient1 name": [[all his files]]
--------------------------------------
"Medical Data" : [
    "patient1 name":[
        "Patient Identification": [....]
        "Clinical Data" : [...]
        "Billing" : [...]
    ]
    ... and all peoples data
]
--------------------------------------
"""

    print("Iam in group\n")
    grouped_filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'grouped.txt')
    grouped_text = process_with_gemini2(final_prompt)  # Ensure this returns the expected string
    
    # Save the grouped output
    with open(grouped_filepath, 'w', encoding='utf-8') as f:
        f.write(grouped_text)
        
    print("grouped.txt created at:", grouped_filepath)

    return jsonify({"message": "Grouped prompt generated successfully!", "grouped_prompt": grouped_text}), 200


if __name__ == '__main__':
    # Disable auto-reloader to ensure global variables are preserved.
    app.run(debug=True, use_reloader=False)
