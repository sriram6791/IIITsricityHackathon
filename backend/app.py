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

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(save_path)

        try:
            # Perform OCR on the uploaded file and save the text to a .txt file
            extracted_text = perform_ocr(save_path, filename)
            print("extracted text is : ",extracted_text)
            print("text",extracted_text)
            prompt = f"""You are a document analysis assistant. Analyze the provided text and perform the following tasks:
                analyse this text : "{extracted_text}"
                I need output in this format :
                1. Summary: Generate a concise summary of the given text in exactly 4 to 5 lines.  
                2. Sentiment: Determine the overall sentiment of the geiven text (e.g., positive, negative, neutral).  
                3. Class: Classify the given text strictly as one of the following: invoices, contracts, resume, document.  
                4. Tags: Extract relevant keywords (tags) that capture the main topics of the document.  

                Output your result strictly in the following format and nothing else:  

                summary: [Your 4-5 line summary]  
                sentiment: [Your sentiment]  
                class: [Your classification]  
                tags: [Your tags]  """
            
            client = genai.Client(api_key="AIzaSyDmGsZVGp5bzKuXLHxiCMD9-BzqmHYGwcA")
            response = client.models.generate_content(
                model="gemini-2.0-flash", 
                contents=prompt
            )
            print("gemini response is : ",response.text)
        except Exception as e:
            # Log the error and return an error message
            print("Error during OCR processing:", e)
            return jsonify({"error": "OCR processing failed: " + str(e)}), 500

        return jsonify({
            "message": "File uploaded and processed successfully!",
            "filename": filename,
            "extracted_text": extracted_text[:500]  # Preview: first 500 characters
        }), 200
    else:
        return jsonify({"error": "File type not allowed"}), 400


def perform_ocr(filepath, filename):
    extracted_text = ""
    
    # Check if the file is a PDF
    if filename.lower().endswith('.pdf'):
        try:
            # Update this path to point to your Poppler bin directory
            POPPLER_PATH = r'C:\Users\govin\Downloads\Release-24.08.0-0\poppler-24.08.0\Library\bin'
            images = convert_from_path(filepath, poppler_path=POPPLER_PATH)
        except Exception as e:
            print("Error converting PDF to images:", e)
            raise e  # Re-raise the exception so the error is handled in your Flask route
        
        reader = easyocr.Reader(['en'], gpu=False)
        for image in images:
            # Convert the PIL image to a numpy array for EasyOCR
            img_np = np.array(image)
            result = reader.readtext(img_np, detail=0)  # Extract text without bounding boxes
            extracted_text += "\n".join(result) + "\n"
    else:
        # For non-PDF files, use EasyOCR directly
        reader = easyocr.Reader(['en'], gpu=False)
        result = reader.readtext(filepath, detail=0)
        extracted_text = "\n".join(result)
    
    # Save the extracted text to a .txt file with the same base name as the uploaded file
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


if __name__ == '__main__':
    app.run(debug=True)
