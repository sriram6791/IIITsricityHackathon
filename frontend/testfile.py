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

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
file_names_response = []  # List to store response file paths

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload', methods=['POST'])
def upload_file():
    global file_names_response
    file_names_response = []  # Reset for new uploads

    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    files = request.files.getlist('file')
    if not files:
        return jsonify({"error": "No files selected"}), 400

    response_data = []
    
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(save_path)

            try:
                extracted_text = perform_ocr(save_path, filename)
                gemini_response = process_with_gemini(extracted_text)

                response_filename = f"{os.path.splitext(filename)[0]}_response.txt"
                response_filepath = os.path.join(app.config['UPLOAD_FOLDER'], response_filename)
                
                with open(response_filepath, 'w', encoding='utf-8') as f:
                    f.write(gemini_response)

                file_names_response.append(response_filepath)  # Store processed file

                response_data.append({
                    "filename": filename,
                    "ocr_text_preview": extracted_text[:500],
                    "gemini_response_file": response_filename
                })

            except Exception as e:
                return jsonify({"error": f"Processing failed: {str(e)}"}), 500
        else:
            response_data.append({"error": f"File type not allowed: {file.filename}"})
    
    return jsonify({
        "message": "Files uploaded and processed successfully!",
        "files": response_data
    }), 200


def perform_ocr(filepath, filename):
    extracted_text = ""

    if filename.lower().endswith('.pdf'):
        try:
            POPPLER_PATH = r'C:\Users\govin\Downloads\Release-24.08.0-0\poppler-24.08.0\Library\bin'
            images = convert_from_path(filepath, poppler_path=POPPLER_PATH)
        except Exception as e:
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

    txt_filename = os.path.splitext(filename)[0] + ".txt"
    txt_filepath = os.path.join(os.path.dirname(filepath), txt_filename)

    with open(txt_filepath, 'w', encoding='utf-8') as f:
        f.write(extracted_text)

    return extracted_text


def process_with_gemini(extracted_text):
    prompt = f"""You are a document analysis assistant. Analyze the text and output strictly in the format:

    summary: [Your 4-5 line summary]  
    sentiment: [positive, negative, neutral]  
    class: [invoices, contracts, resume, document]  
    tags: [keyword1, keyword2, keyword3]  

    Text: "{extracted_text}"
    """
    client = genai.Client(api_key="AIzaSyDmGsZVGp5bzKuXLHxiCMD9-BzqmHYGwcA")
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt
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
    global file_names_response

    if not file_names_response:
        return jsonify({"error": "No response files found to group."}), 400

    llm_input_string = generate_llm_input(file_names_response)

    final_prompt = f"""{llm_input_string}
Group the files according to their tags. Output strictly in the format:

category_name : {{file1, file2, file3}}
category_name : {{file4, file5}}
"""
    
    grouped_filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'grouped.txt')
    grouped_text = process_with_gemini(final_prompt)

    with open(grouped_filepath, 'w', encoding='utf-8') as f:
        f.write(grouped_text)

    return jsonify({"message": "Grouped file created successfully!", "grouped_prompt": grouped_text}), 200


if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
