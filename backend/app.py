from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from werkzeug.utils import secure_filename
import easyocr
from pdf2image import convert_from_path
import numpy as np
from google import genai

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
                # Perform OCR on the uploaded file and save the text to a .txt file
                extracted_text = perform_ocr(save_path, filename)

                # Generate Gemini AI response
                gemini_response = process_with_gemini(extracted_text)

                # Save the Gemini response to a new file
                response_filename = f"{os.path.splitext(filename)[0]}_response.txt"
                response_filepath = os.path.join(
                    app.config['UPLOAD_FOLDER'], response_filename)

                file_names_response.append(response_filepath)

                with open(response_filepath, 'w', encoding='utf-8') as f:
                    f.write(gemini_response)

                response_data.append({
                    "filename": filename,
                    # First 500 characters
                    "ocr_text_preview": extracted_text[:500],
                    "gemini_response_file": response_filename
                })

            except Exception as e:
                print("Error during processing:", e)
                return jsonify({"error": "Processing failed: " + str(e)}), 500
        else:
            response_data.append(
                {"error": f"File type not allowed for {file.filename}"})
    

    return jsonify({
        "message": "Files uploaded and processed successfully!",
        "files": response_data
    }), 200


def perform_ocr(filepath, filename):
    extracted_text = ""

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

    # Save the extracted text to a .txt file
    base_name = os.path.splitext(filename)[0]
    txt_filename = base_name + ".txt"
    txt_filepath = os.path.join(os.path.dirname(filepath), txt_filename)
    try:
        with open(txt_filepath, 'w', encoding='utf-8') as f:
            f.write(extracted_text)
        print(f"OCR text saved to: {txt_filepath}")
    except Exception as e:
        print("Error saving text file:", e)

    return extracted_text


def process_with_gemini(extracted_text):
    prompt = f"""You are a document analysis assistant. Analyze the provided text and perform the following tasks:
    Analyse this text: "{extracted_text}"
    I need output in this format:
    1. Summary: Generate a concise summary of the given text in exactly 4 to 5 lines.  
    2. Sentiment: Determine the overall sentiment of the given text (positive, negative, neutral).  
    3. Class: Classify the given text strictly as one of the following: invoices, contracts, resume, document.  
    4. Tags: Extract relevant keywords (tags) that capture the main topics of the document.  

    Output your result strictly in the following format:

    summary: [Your 4-5 line summary]  
    sentiment: [Your sentiment]  
    class: [Your classification]  
    tags: [Your tags]  
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


def generate_llm_input(file_names_response):
    """Generates the formatted input string for the LLM API."""
    llm_input = ""

    for file_path in file_names_response:
        filename = os.path.basename(file_path)
        summary, tags = extract_summary_tags(file_path)

        llm_input += f"{filename}:\n"
        llm_input += f"summary: {summary}\n"
        llm_input += f"tags: {tags}\n\n"

    return llm_input

@app.route('/group', methods=['GET'])
def group_files():
    # Debug print to see current response file list
    print("file_names_response:", file_names_response)

    # Generate the input string from all response files
    llm_input_string = generate_llm_input(file_names_response)

    # Create the grouping prompt
    final_prompt = f"""{llm_input_string}
This is the details of the files, and these contain filename, summary, and tags.

Now your task is to group the files according to their tags. Create groups with meaningful group names based on the tags.
For example, if some files are related to medical topics, group them under 'medical'; if some are legal documents, group them under 'legal';
if some are bills, group them under 'bills'.

Final output should look like:

medical : {{file1, file2, file3}}
legal : {{file4, file5, file6}}
bills : {{file7, file8, file9}}

Output should be strictly in the following format:

group_name : {{file names}}
group_name : {{file names}}"""

    print("Iam in group\n")
    grouped_filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'grouped.txt')
    grouped_text = process_with_gemini2(final_prompt)  # Ensure this returns the expected string
    
    # Now, open the file and write the response
    with open(grouped_filepath, 'w', encoding='utf-8') as f:
        f.write(grouped_text)
        
    print("grouped.txt created at:", grouped_filepath)

    return jsonify({"message": "Grouped prompt generated successfully!", "grouped_prompt": grouped_text}), 200


if __name__ == '__main__':
    # Disable auto-reloader to ensure global variables are preserved.
    app.run(debug=True, use_reloader=False)