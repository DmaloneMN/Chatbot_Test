// Chatbot Test Application Logic

const displayArea = document.getElementById('messageDisplay');
const inputField = document.getElementById('userInputField');
const sendButton = document.getElementById('sendMessageBtn');

let conversationHistory = [];

function appendMessageToDisplay(sender, content) {
    const timestamp = new Date().toLocaleTimeString();
    const messageBlock = document.createElement('div');
    messageBlock.style.marginBottom = '10px';
    messageBlock.style.padding = '8px';
    messageBlock.style.borderRadius = '4px';
    
    if (sender === 'user') {
        messageBlock.style.backgroundColor = '#e3f2fd';
        messageBlock.style.textAlign = 'right';
    } else {
        messageBlock.style.backgroundColor = '#f1f8e9';
        messageBlock.style.textAlign = 'left';
    }
    
    const senderLabel = document.createElement('strong');
    senderLabel.textContent = sender + ':';
    
    const messageText = document.createTextNode(' ' + content + ' ');
    
    const timeStamp = document.createElement('small');
    timeStamp.textContent = '(' + timestamp + ')';
    
    messageBlock.appendChild(senderLabel);
    messageBlock.appendChild(messageText);
    messageBlock.appendChild(timeStamp);
    
    displayArea.appendChild(messageBlock);
    displayArea.scrollTop = displayArea.scrollHeight;
}

function generateBotResponse(userMessage) {
    const responses = [
        `I received your message: "${userMessage}"`,
        `That's interesting! You said: "${userMessage}"`,
        `Processing your input: "${userMessage}"`,
        `Thank you for sharing: "${userMessage}"`
    ];
    return responses[Math.floor(Math.random() * responses.length)];
}

function handleUserMessage() {
    const userText = inputField.value.trim();
    
    if (userText === '') {
        return;
    }
    
    conversationHistory.push({ role: 'user', message: userText });
    appendMessageToDisplay('user', userText);
    
    inputField.value = '';
    
    setTimeout(() => {
        const botReply = generateBotResponse(userText);
        conversationHistory.push({ role: 'bot', message: botReply });
        appendMessageToDisplay('bot', botReply);
    }, 500);
}

sendButton.addEventListener('click', handleUserMessage);

inputField.addEventListener('keypress', (event) => {
    if (event.key === 'Enter') {
        handleUserMessage();
    }
});

appendMessageToDisplay('bot', 'Welcome to the Chatbot Test Application! Send a message to get started.');
