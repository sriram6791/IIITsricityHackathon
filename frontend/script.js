function uploadFile() {
    var fileInput = document.getElementById('fileInput');
    var file = fileInput.files[0];
  
    if (!file) {
      alert("Please select a file to upload.");
      return;
    }
  
    var formData = new FormData();
    formData.append("file", file);
  
    fetch("http://127.0.0.1:5000/upload", {
      method: "POST",
      body: formData
    })
    .then(response => response.json())
    .then(data => {
      var responseMessage = document.getElementById('responseMessage');
      if (data.error) {
        responseMessage.innerText = "Error: " + data.error;
        responseMessage.style.color = "red";
      } else {
        responseMessage.innerText = "Success: " + data.message + " (Filename: " + data.filename + ")";
        responseMessage.style.color = "green";
      }
    })
    .catch(error => {
      console.error("Error uploading file:", error);
      document.getElementById('responseMessage').innerText = "Error uploading file.";
    });
  }
  