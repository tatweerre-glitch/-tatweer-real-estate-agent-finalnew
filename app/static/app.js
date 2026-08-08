const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("message-input");
const sendBtn = document.getElementById("send-btn");
const statusDot = document.getElementById("status-dot");
const statusText = document.getElementById("status-text");

const history = [];

function appendMessage(role, content, extraClass = "") {
  const bubble = document.createElement("div");
  bubble.className = `message ${role} ${extraClass}`.trim();
  bubble.textContent = content;
  messagesEl.appendChild(bubble);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return bubble;
}

function appendPhotos(photos) {
  if (!photos || !photos.length) return;

  const gallery = document.createElement("div");
  gallery.className = "message assistant photo-gallery";

  photos.slice(0, 5).forEach((url) => {
    const img = document.createElement("img");
    img.src = url;
    img.alt = "Property photo";
    img.loading = "lazy";
    gallery.appendChild(img);
  });

  messagesEl.appendChild(gallery);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

async function checkHealth() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) throw new Error("Health check failed");
    const data = await response.json();
    statusDot.classList.add("online");
    statusText.textContent = `${data.company} assistant online`;
  } catch {
    statusText.textContent = "Assistant offline";
  }
}

async function sendMessage(text) {
  const message = text.trim();
  if (!message) return;

  appendMessage("user", message);
  history.push({ role: "user", content: message });
  inputEl.value = "";
  sendBtn.disabled = true;

  const typingBubble = appendMessage("assistant", "Typing...", "typing");

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history: history.slice(0, -1) }),
    });

    if (!response.ok) {
      throw new Error("Chat request failed");
    }

    const data = await response.json();
    typingBubble.remove();
    appendMessage("assistant", data.reply);
    appendPhotos(data.photos);
    history.push({ role: "assistant", content: data.reply });
  } catch (error) {
    typingBubble.textContent =
      "Sorry, something went wrong. Please try again or contact Tatweer sales.";
  } finally {
    sendBtn.disabled = false;
    inputEl.focus();
  }
}

formEl.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage(inputEl.value);
});

document.querySelectorAll("[data-prompt]").forEach((button) => {
  button.addEventListener("click", () => {
    sendMessage(button.dataset.prompt);
  });
});

checkHealth();
appendMessage(
  "assistant",
  "Hello! I'm the Tatweer Real Estate assistant. Ask me about projects, payment plans, site visits, or after-sales support."
);
