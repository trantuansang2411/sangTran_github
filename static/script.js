const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const chatMessages = document.getElementById('chat-messages');
const sendBtn = document.getElementById('send-btn');

chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = userInput.value.trim();
    if (!message) return;

    // Add user message to UI
    addMessage(message, 'user');
    userInput.value = '';
    
    // Show typing indicator
    const typingId = showTypingIndicator();
    sendBtn.disabled = true;

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message })
        });

        const data = await response.json();
        
        // Remove typing indicator
        removeMessage(typingId);
        
        if (response.ok) {
            addMessage(data.answer, 'bot', true);
        } else {
            addMessage("❌ Error: " + (data.error || "Failed to get response"), 'bot');
        }
    } catch (error) {
        removeMessage(typingId);
        addMessage("❌ Network Error: Could not connect to the server.", 'bot');
    } finally {
        sendBtn.disabled = false;
        userInput.focus();
    }
});

function addMessage(text, sender, isHTML = false) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${sender}-message`;
    
    const avatarDiv = document.createElement('div');
    avatarDiv.className = `avatar ${sender}-avatar`;
    avatarDiv.textContent = sender === 'user' ? '👤' : '🤖';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    if (isHTML) {
        contentDiv.innerHTML = text;
    } else {
        contentDiv.textContent = text;
    }
    
    msgDiv.appendChild(avatarDiv);
    msgDiv.appendChild(contentDiv);
    
    chatMessages.appendChild(msgDiv);
    scrollToBottom();
}

function showTypingIndicator() {
    const id = 'typing-' + Date.now();
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message bot-message';
    msgDiv.id = id;
    
    const avatarDiv = document.createElement('div');
    avatarDiv.className = 'avatar bot-avatar';
    avatarDiv.textContent = '🤖';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content typing-indicator';
    contentDiv.innerHTML = `
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
    `;
    
    msgDiv.appendChild(avatarDiv);
    msgDiv.appendChild(contentDiv);
    chatMessages.appendChild(msgDiv);
    scrollToBottom();
    
    return id;
}

function removeMessage(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function clearChat() {
    chatMessages.innerHTML = `
        <div class="message bot-message">
            <div class="avatar bot-avatar">🤖</div>
            <div class="message-content">
                Chat cleared. How can I help you?
            </div>
        </div>
    `;
}
