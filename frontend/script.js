// Function to handle file upload and trigger grouping automatically
function uploadFile() {
  var fileInput = document.getElementById('fileInput');
  var files = fileInput.files;

  if (files.length === 0) {
    alert("Please select files to upload.");
    return;
  }

  var formData = new FormData();
  
  // Append all selected files to formData
  for (let i = 0; i < files.length; i++) {
    formData.append("file", files[i]);
  }

  fetch("http://127.0.0.1:5000/upload", {
    method: "POST",
    body: formData
  })
  .then(response => response.json())
  .then(data => {
    var responseMessage = document.getElementById('responseMessage');
    if (data.error) {
      console.log("Entered into if block of grouping\n");
      responseMessage.innerText = "Error: " + data.error;
      responseMessage.style.color = "red";
    } else {
      responseMessage.innerText = "Success! Files uploaded and processed.";
      responseMessage.style.color = "green";
      // Automatically trigger grouping after upload is successful
      console.log("Entered into else block of grouping\n");
      groupFiles();
    }
  })
  .catch(error => {
    console.error("Error uploading files:", error);
    document.getElementById('responseMessage').innerText = "Error uploading file.";
  });
}

// Function to trigger grouping of files based on tags automatically
function groupFiles() {
  console.log("Grouped in script is called\n");
  fetch("http://127.0.0.1:5000/group")
    .then(response => response.json())
    .then(data => {
      console.log("Grouping prompt generated:", data.grouped_prompt);
      alert("Grouped prompt generated! Check the uploads folder for grouped.txt");
    })
    .catch(error => {
      console.error("Error grouping files:", error);
      alert("Error generating grouped prompt.");
    });
}

// Attach event listener to the upload button
document.getElementById('uploadButton').addEventListener('click', uploadFile);
