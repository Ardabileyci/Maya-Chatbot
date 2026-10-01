/**
 * Maya Academic Assistant - Frontend Application
 * Handles chat UI interactions, API communication, and chat history persistence
 */

// Configuration
const CONFIG = {
    API_BASE_URL: '',
    ENDPOINTS: {
        CHAT: '/api/chat',
        NEW_CHAT: '/api/new-chat',
        CHAT_HISTORY: '/api/chat-history',
        USER_CHAT_HISTORY: '/api/user-chat-history'
    }
};

// Storage keys
const STORAGE_KEY = 'maya_session_id';

// DOM Elements - will be set in init()
let elements = {};

// State
let isLoading = false;
let sessionId = null;
let selectedImage = null; // { base64: string, mimeType: string, file: File }
let historyLoaded = false; // Prevent double-loading

/**
 * Get user_id from URL parameters (passed by PHP)
 */
function getUserId() {
    const params = new URLSearchParams(window.location.search);
    return params.get('user_id') || params.get('userId') || null;
}

/**
 * Get user_name from URL parameters (passed by PHP)
 */
function getUserName() {
    const params = new URLSearchParams(window.location.search);
    return params.get('user_name') || params.get('userName') || null;
}

/**
 * Get user_email from URL parameters (passed by PHP)
 */
function getUserEmail() {
    const params = new URLSearchParams(window.location.search);
    return params.get('user_email') || params.get('email') || null;
}

/**
 * Load session ID from localStorage (per user)
 */
function loadSessionId() {
    const uid = getUserId();
    const key = uid ? STORAGE_KEY + '_' + uid : STORAGE_KEY;
    const saved = localStorage.getItem(key);
    if (saved) {
        sessionId = saved;
        console.log('[Maya] Loaded session from storage:', sessionId);
    }
}

/**
 * Save session ID to localStorage (per user)
 */
function saveSessionId(id) {
    sessionId = id;
    const uid = getUserId();
    const key = uid ? STORAGE_KEY + '_' + uid : STORAGE_KEY;
    localStorage.setItem(key, id);
}

/**
 * Load chat history from server
 */
async function loadChatHistory() {
    if (historyLoaded) return;
    historyLoaded = true;

    let url = null;
    const userId = getUserId();

    if (userId) {
        url = `${CONFIG.API_BASE_URL}${CONFIG.ENDPOINTS.USER_CHAT_HISTORY}/${userId}`;
    } else if (sessionId) {
        url = `${CONFIG.API_BASE_URL}${CONFIG.ENDPOINTS.CHAT_HISTORY}/${sessionId}`;
    }

    if (!url) return;

    try {
        const response = await fetch(url);
        if (!response.ok) return;

        const data = await response.json();

        if (data.messages && data.messages.length > 0) {
            const welcomeMsg = elements.messagesWrapper.querySelector('.maya-message');
            if (welcomeMsg) {
                welcomeMsg.remove();
            }

            for (const msg of data.messages) {
                if (msg.role === 'user') {
                    addMessageToUI(msg.content, 'user', false, null, msg.created_at);
                } else if (msg.role === 'assistant') {
                    addMessageToUI(msg.content, 'maya', false, null, msg.created_at);
                }
            }
            console.log('[Maya] Loaded chat history:', data.messages.length, 'messages');
        }
    } catch (error) {
        console.error('[Maya] Failed to load chat history:', error);
    }
}

/**
 * Initialize the application
 */
function init() {
    console.log('[Maya] Initializing...');
    
    // Get DOM elements after DOM is ready
    elements = {
        chatContainer: document.getElementById('chatContainer'),
        messagesWrapper: document.getElementById('messagesWrapper'),
        messageInput: document.getElementById('messageInput'),
        sendButton: document.getElementById('sendButton'),
        typingIndicator: document.getElementById('typingIndicator'),
        newChatButton: document.getElementById('newChatButton'),
        // Image upload elements
        imageInput: document.getElementById('imageInput'),
        imageButton: document.getElementById('imageButton'),
        imagePreview: document.getElementById('imagePreview'),
        previewImg: document.getElementById('previewImg'),
        removeImage: document.getElementById('removeImage')
    };
    
    // Load session from localStorage
    loadSessionId();
    
    setupEventListeners();
    autoResizeTextarea();
    
    // Load chat history if session or user exists
    if (sessionId || getUserId()) {
        loadChatHistory();
    }
    
    elements.messageInput.focus();
    
    console.log('[Maya] Init complete. User ID:', getUserId(), 'Session:', sessionId);
}

/**
 * Setup event listeners
 */
function setupEventListeners() {
    // Send button click
    elements.sendButton.addEventListener('click', handleSendMessage);
    
    // Enter key to send (Shift+Enter for new line)
    elements.messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    });
    
    // Auto-resize textarea
    elements.messageInput.addEventListener('input', autoResizeTextarea);
    
    // New chat button (if exists)
    if (elements.newChatButton) {
        elements.newChatButton.addEventListener('click', handleNewChat);
    }
    
    // Image upload button
    if (elements.imageButton) {
        elements.imageButton.addEventListener('click', () => {
            elements.imageInput.click();
        });
    }
    
    // Image file selection
    if (elements.imageInput) {
        elements.imageInput.addEventListener('change', handleImageSelect);
    }
    
    // Remove image button
    if (elements.removeImage) {
        elements.removeImage.addEventListener('click', clearSelectedImage);
    }
}

/**
 * Auto-resize textarea based on content
 */
function autoResizeTextarea() {
    const textarea = elements.messageInput;
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
}

/**
 * Handle image file selection
 */
function handleImageSelect(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    // Validate file type
    if (!file.type.startsWith('image/')) {
        alert('Lütfen bir görsel dosyası seçin.');
        return;
    }
    
    // Validate file size (max 10MB)
    if (file.size > 10 * 1024 * 1024) {
        alert('Görsel boyutu 10MB\'dan küçük olmalıdır.');
        return;
    }
    
    // Read file as base64
    const reader = new FileReader();
    reader.onload = (e) => {
        const base64Full = e.target.result;
        const base64Data = base64Full.split(',')[1]; // Remove data:image/xxx;base64, prefix
        
        selectedImage = {
            base64: base64Data,
            mimeType: file.type,
            file: file
        };
        
        // Show preview
        elements.previewImg.src = base64Full;
        elements.imagePreview.style.display = 'flex';
        
        // Update placeholder
        elements.messageInput.placeholder = 'Görsel hakkında soru sorun...';
    };
    reader.readAsDataURL(file);
}

/**
 * Clear selected image
 */
function clearSelectedImage() {
    selectedImage = null;
    elements.imageInput.value = '';
    elements.imagePreview.style.display = 'none';
    elements.previewImg.src = '';
    elements.messageInput.placeholder = 'Sorunuzu yazın...';
}

/**
 * Handle starting a new chat
 */
async function handleNewChat() {
    // Clear session from localStorage
    sessionId = null;
    historyLoaded = false;
    const uid = getUserId();
    const key = uid ? STORAGE_KEY + '_' + uid : STORAGE_KEY;
    localStorage.removeItem(key);
    
    // Clear UI
    elements.messagesWrapper.innerHTML = '';
    elements.messageInput.focus();
}

/**
 * Handle sending a message
 */
async function handleSendMessage() {
    const message = elements.messageInput.value.trim();
    const hasImage = selectedImage !== null;
    
    // Need either message or image
    if (!message && !hasImage) return;
    if (isLoading) return;
    
    // Store image data before clearing
    const imageToSend = selectedImage;
    const imagePreviewUrl = hasImage ? elements.previewImg.src : null;
    
    // Clear input and reset height
    elements.messageInput.value = '';
    autoResizeTextarea();
    clearSelectedImage();
    
    // Add user message to UI (with image if applicable)
    addMessageToUI(message || '', 'user', false, imagePreviewUrl);
    
    // Show typing indicator
    showTypingIndicator();
    
    // Send to API
    try {
        const response = await sendMessageToAPI(message, imageToSend);
        
        hideTypingIndicator();
        
        // Save session ID from response
        if (response.session_id) {
            saveSessionId(response.session_id);
        }
        
        addMessageToUI(response.reply, 'maya');
        
    } catch (error) {
        console.error('[Maya] API Error:', error);
        hideTypingIndicator();
        addMessageToUI(
            'Bir hata oluştu. Lütfen tekrar deneyin.',
            'maya',
            true
        );
    }
    
    // Refocus input
    elements.messageInput.focus();
}

/**
 * Send message to API
 */
async function sendMessageToAPI(message, imageData = null) {
    isLoading = true;
    elements.sendButton.disabled = true;
    
    try {
        const requestBody = { message };
        
        if (sessionId) {
            requestBody.session_id = sessionId;
        }
        
        // Add user identity from URL params
        const userId = getUserId();
        const userName = getUserName();
        const userEmail = getUserEmail();
        if (userId) requestBody.user_id = userId;
        if (userName) requestBody.user_name = userName;
        if (userEmail) requestBody.user_email = userEmail;
        
        // Add image data if present
        if (imageData) {
            requestBody.image = imageData.base64;
            requestBody.mime_type = imageData.mimeType;
        }
        
        const response = await fetch(`${CONFIG.API_BASE_URL}${CONFIG.ENDPOINTS.CHAT}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        return data;
    } finally {
        isLoading = false;
        elements.sendButton.disabled = false;
    }
}

/**
 * Add a message to the UI
 */
function addMessageToUI(content, sender, isError = false, imageUrl = null, timestamp = null) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;
    
    // Create avatar (only for Maya)
    if (sender === 'maya') {
        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'message-avatar';
        
        const avatarImg = document.createElement('img');
        avatarImg.src = 'assets/maya-robot.png';
        avatarImg.alt = 'Maya';
        
        avatarDiv.appendChild(avatarImg);
        messageDiv.appendChild(avatarDiv);
    }
    
    // Create message content
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    const bubbleDiv = document.createElement('div');
    bubbleDiv.className = `message-bubble${isError ? ' error-message' : ''}`;
    
    // Add image if present (for user messages)
    if (imageUrl && sender === 'user') {
        const imgContainer = document.createElement('div');
        imgContainer.className = 'message-image';
        
        const img = document.createElement('img');
        img.src = imageUrl;
        img.alt = 'Gönderilen görsel';
        img.onclick = (e) => {
            e.stopPropagation();
            openImageModal(imageUrl);
        };
        
        imgContainer.appendChild(img);
        bubbleDiv.appendChild(imgContainer);
    }
    
    // Parse and format the text content
    if (content) {
        const textDiv = document.createElement('div');
        textDiv.className = 'message-text';
        const formattedContent = formatMessageContent(content);
        textDiv.innerHTML = formattedContent;
        bubbleDiv.appendChild(textDiv);
    }
    
    contentDiv.appendChild(bubbleDiv);

    const timeSpan = document.createElement('span');
    timeSpan.className = 'message-time';
    const msgTime = timestamp ? new Date(timestamp) : new Date();
    timeSpan.textContent = msgTime.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
    bubbleDiv.appendChild(timeSpan);

    messageDiv.appendChild(contentDiv);
    
    // Add to messages wrapper
    elements.messagesWrapper.appendChild(messageDiv);
    
    // Scroll to bottom
    scrollToBottom();
}

/**
 * Format message content safely
 */
function formatMessageContent(content) {
    const escaped = escapeHtml(content);
    
    const withBreaks = escaped
        .split('\n\n')
        .map(para => `<p>${para.replace(/\n/g, '<br>')}</p>`)
        .join('');
    
    const withBold = withBreaks.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    
    const withLists = withBold
        .replace(/<p>(\d+\.\s)/g, '<p class="list-item">$1')
        .replace(/<p>(-\s)/g, '<p class="list-item">$1');
    
    return withLists;
}

/**
 * Escape HTML special characters
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Show typing indicator
 */
function showTypingIndicator() {
    elements.messagesWrapper.appendChild(elements.typingIndicator);
    elements.typingIndicator.style.display = 'block';
    scrollToBottom();
}

/**
 * Hide typing indicator
 */
function hideTypingIndicator() {
    elements.typingIndicator.style.display = 'none';
}

/**
 * Scroll chat container to bottom
 */
function scrollToBottom() {
    elements.chatContainer.scrollTop = elements.chatContainer.scrollHeight;
}

/**
 * Open image in modal
 */
function openImageModal(imageSrc) {
    const modal = document.getElementById('imageModal');
    const modalImg = document.getElementById('modalImage');
    modal.style.display = 'flex';
    modalImg.src = imageSrc;
    document.body.style.overflow = 'hidden'; // Prevent scrolling
}

/**
 * Close image modal
 */
function closeImageModal() {
    const modal = document.getElementById('imageModal');
    modal.style.display = 'none';
    document.body.style.overflow = ''; // Restore scrolling
}

// Close modal with Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeImageModal();
    }
});

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', init);
