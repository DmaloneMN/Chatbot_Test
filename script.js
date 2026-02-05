const API_ENDPOINT = "https://apim-multiagent-research.azure-api.net/research";

const statusMessage = document.getElementById("status-message");
const result = document.getElementById("result");
const button = document.getElementById("generate-button");
const questionBox = document.getElementById("research-question");

button.addEventListener("click", async () => {
    const researchQuestion = questionBox.value.trim();
    if (!researchQuestion) {
        alert("Please enter a research question.");
        return;
    }

    statusMessage.textContent = "Generating report, please wait...";
    result.innerHTML = "";
    button.disabled = true;

    try {
        const response = await fetch(API_ENDPOINT, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ question: researchQuestion }),
        });

        if (!response.ok) throw new Error(`Error: ${response.statusText}`);

        const data = await response.json();
        statusMessage.textContent = "Report generated successfully!";
        result.innerHTML = `
            <p><strong>Research Question:</strong> ${data.question}</p>
            <p><strong>Download Report:</strong> 
               <a href="${data.document_url}" target="_blank">Download</a></p>`;
    } catch (error) {
        statusMessage.textContent = `Error: ${error.message}`;
    } finally {
        button.disabled = false;
    }

});
