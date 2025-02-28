#%%
import json
import re
import os

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


# %%
file_paths = [
        r"I:\IIITSricityHackathon\backend\uploads\billdata_response.txt",
        r"I:\IIITSricityHackathon\backend\uploads\clinicaldata_response.txt",
        r"I:\IIITSricityHackathon\backend\uploads\Sriram_Govindaram_1_response.txt",
        r"I:\IIITSricityHackathon\backend\uploads\patientdetails_response.txt"
    ]
llm_input_string = generate_llm_input(file_paths)
print(llm_input_string)
# %%
