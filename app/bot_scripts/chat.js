/**
 * Bot Factory — Chat Module
 *
 * Handles chat messaging with SSE streaming, typing indicators,
 * and suggestion chips.
 *
 * Required: Set window.BOT_CONFIG before loading this script.
 *   window.BOT_CONFIG = {
 *     apiUrl: 'https://xxx.lambda-url.us-east-1.on.aws',
 *     botId: 'the-fret-detective',
 *     apiKey: 'bfk_...',
 *     botName: 'The Fret Detective',
 *     placeholder: 'Ask about guitar...'
 *   };
 *
 * Optional: Set window.BOT_CONFIG.formatMessage to a function that
 * takes (text, containerDiv) and handles custom rendering.
 * If not set, messages render as plain text.
 */

const chatMessages = document.getElementById("chatMessages");
const chatInput = document.getElementById("chatInput");
const chatSuggestions = document.getElementById("chatSuggestions");

const config = window.BOT_CONFIG || {
  apiUrl: "",
  botId: "",
  apiKey: "",
  botName: "Bot",
  placeholder: "Type a message...",
};

// Conversation history — persists for the browser session.
const conversationHistory = [];

/**
 * Default message formatter — renders text as plain text with line breaks.
 * Bot-specific formatters (e.g. guitar/formatter.js) can override this
 * by setting BOT_CONFIG.formatMessage.
 */
function defaultFormatMessage(text, container) {
  const lines = text.split("\n");
  lines.forEach((line, i) => {
    const span = document.createElement("span");
    span.textContent = line;
    container.appendChild(span);
    if (i < lines.length - 1) {
      container.appendChild(document.createElement("br"));
    }
  });
}

/**
 * Stream a welcome message into the chat on first load.
 */
function streamWelcomeMessage() {
  const welcomeText =
    `Welcome to ${config.botName}\n\n` +
    `Got a question? Just ask and I'll give you clean, step-by-step answers.`;

  const div = document.createElement("div");
  div.className = "chat-message bot";
  const label = document.createElement("div");
  label.className = "bot-label";
  label.textContent = config.botName;
  div.appendChild(label);
  chatMessages.appendChild(div);

  let index = 0;
  const chunkSize = 3;
  const interval = 15;

  function streamNext() {
    if (index >= welcomeText.length) return;

    index = Math.min(index + chunkSize, welcomeText.length);
    const partial = welcomeText.substring(0, index);

    while (div.childNodes.length > 1) {
      div.removeChild(div.lastChild);
    }

    const formatter = config.formatMessage || defaultFormatMessage;
    formatter(partial, div);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    requestAnimationFrame(() => setTimeout(streamNext, interval));
  }

  streamNext();
}

/**
 * Send a suggestion chip's text as a message
 */
function sendSuggestion(chip) {
  chatInput.value = chip.textContent;
  sendMessage();
}

/**
 * Send the current input as a message (with SSE streaming)
 */
async function sendMessage() {
  const message = chatInput.value.trim();
  if (!message) return;

  addMessage(message, "user");
  chatInput.value = "";

  if (chatSuggestions) {
    chatSuggestions.style.display = "none";
  }

  // Show bot label + typing dots together from the start
  const div = document.createElement("div");
  div.className = "chat-message bot";
  const label = document.createElement("div");
  label.className = "bot-label";
  label.textContent = config.botName;
  div.appendChild(label);
  const typing = document.createElement("div");
  typing.className = "typing-indicator";
  typing.innerHTML = "<span></span><span></span><span></span>";
  div.appendChild(typing);
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  try {
    const response = await fetch(config.apiUrl + "/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": config.apiKey,
      },
      body: JSON.stringify({
        bot_id: config.botId,
        message,
        conversation_history: conversationHistory,
      }),
    });

    if (!response.ok) {
      typing.remove();
      const formatter = config.formatMessage || defaultFormatMessage;
      formatter("Sorry, something went wrong. Try again in a moment.", div);
      return;
    }

    typing.remove();

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let sseBuffer = "";
    let fullResponse = "";
    const tokenQueue = [];
    let rendering = false;

    // Drip-render tokens at a smooth pace
    function renderNext() {
      if (tokenQueue.length === 0) {
        rendering = false;
        return;
      }
      rendering = true;
      fullResponse += tokenQueue.shift();

      while (div.childNodes.length > 1) {
        div.removeChild(div.lastChild);
      }
      const formatter = config.formatMessage || defaultFormatMessage;
      formatter(fullResponse, div);
      chatMessages.scrollTop = chatMessages.scrollHeight;

      setTimeout(renderNext, 30);
    }

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      sseBuffer += decoder.decode(value, { stream: true });
      const lines = sseBuffer.split("\n");
      sseBuffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const payload = line.slice(6).trim();
        if (payload === "[DONE]") continue;

        try {
          const data = JSON.parse(payload);
          if (data.error) {
            tokenQueue.push("Error: " + data.error);
          } else if (data.token) {
            tokenQueue.push(data.token);
          }
          if (!rendering) renderNext();
        } catch {}
      }
    }

    // Flush any remaining tokens
    while (tokenQueue.length > 0) {
      await new Promise((r) => setTimeout(r, 30));
    }

    conversationHistory.push(
      { role: "user", content: message },
      { role: "assistant", content: fullResponse },
    );

    const maxMessages = 20;
    if (conversationHistory.length > maxMessages) {
      conversationHistory.splice(0, conversationHistory.length - maxMessages);
    }
  } catch (error) {
    typing.remove();
    const formatter = config.formatMessage || defaultFormatMessage;
    formatter("Sorry, I couldn't connect. Try again in a moment.", div);
  }
}

/**
 * Add a message bubble to the chat
 */
function addMessage(text, type) {
  const div = document.createElement("div");
  div.className = `chat-message ${type}`;

  if (type === "bot") {
    const label = document.createElement("div");
    label.className = "bot-label";
    label.textContent = config.botName;
    div.appendChild(label);

    const formatter = config.formatMessage || defaultFormatMessage;
    formatter(text, div);
  } else {
    div.textContent = text;
  }

  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Show typing indicator, returns the element for removal
 */
function showTyping() {
  const div = document.createElement("div");
  div.className = "typing-indicator";
  div.innerHTML = "<span></span><span></span><span></span>";
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return div;
}

// Enter key sends message
chatInput.addEventListener("keydown", function (e) {
  if (e.key === "Enter") sendMessage();
});

// Warm up the Lambda on page load
function warmup() {
  if (config.apiUrl) {
    fetch(config.apiUrl + "/health").catch(() => {});
  }
}

// Stream the welcome message on load
streamWelcomeMessage();

// Fire warmup on page load
warmup();
