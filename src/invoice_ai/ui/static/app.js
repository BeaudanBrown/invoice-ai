const STORAGE_KEY = "invoice-ai-ui-state";

const state = {
  token: "",
  defaultsText: "",
  conversationContext: {},
  messages: [],
  currentArtifact: null,
  deferredPrompt: null,
  recognition: null,
  recording: false,
};

const el = {
  connectionBadge: document.querySelector("#connection-badge"),
  currentArtifact: document.querySelector("#current-artifact"),
  defaultsInput: document.querySelector("#defaults-input"),
  draftBadge: document.querySelector("#draft-badge"),
  installButton: document.querySelector("#install-button"),
  messageInput: document.querySelector("#message-input"),
  recordButton: document.querySelector("#record-button"),
  saveSettings: document.querySelector("#save-settings"),
  settingsPanel: document.querySelector("#settings-panel"),
  sendButton: document.querySelector("#send-button"),
  template: document.querySelector("#message-template"),
  testConnection: document.querySelector("#test-connection"),
  timeline: document.querySelector("#timeline"),
  tokenInput: document.querySelector("#token-input"),
  voiceCopy: document.querySelector("#voice-copy"),
  voiceIndicator: document.querySelector("#voice-indicator"),
};

boot();

function boot() {
  hydrate();
  bind();
  render();
  setupSpeech();
  setupInstall();
  setupServiceWorker();
}

function bind() {
  el.saveSettings.addEventListener("click", () => {
    state.token = el.tokenInput.value.trim();
    state.defaultsText = el.defaultsInput.value;
    persist();
    flashConnection("Saved locally");
  });

  el.testConnection.addEventListener("click", async () => {
    await testConnection();
  });

  el.sendButton.addEventListener("click", async () => {
    await sendCurrentMessage();
  });

  el.recordButton.addEventListener("click", () => {
    toggleRecording();
  });

  el.messageInput.addEventListener("keydown", async (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      await sendCurrentMessage();
    }
  });
}

async function sendCurrentMessage() {
  const message = el.messageInput.value.trim();
  if (!message) {
    return;
  }
  if (!state.token) {
    flashConnection("Add an operator token first");
    el.settingsPanel.open = true;
    return;
  }

  pushMessage({
    role: "user",
    text: message,
    timestamp: new Date().toISOString(),
  });
  el.messageInput.value = "";

  let defaults = {};
  if (el.defaultsInput.value.trim()) {
    try {
      defaults = JSON.parse(el.defaultsInput.value);
    } catch (error) {
      flashConnection("Defaults JSON is invalid");
      return;
    }
  }

  const requestId = `ui-${Date.now()}`;
  try {
    const response = await fetchJson("/api/ui/turn", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${state.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        request_id: requestId,
        message,
        defaults,
        conversation_context: state.conversationContext,
      }),
    });
    state.conversationContext = response.conversation_state || {};
    state.currentArtifact = response.current_artifact || null;
    pushMessage({
      role: "assistant",
      response,
      timestamp: new Date().toISOString(),
    });
    persist();
    render();
    flashConnection("Connected");
  } catch (error) {
    pushMessage({
      role: "assistant",
      response: {
        summary: {
          text: error.message || "Request failed",
          stage: "error",
          status: "internal_error",
        },
        warnings: [],
        errors: [],
        artifacts: [],
        reviews: [],
        erp_refs: [],
      },
      timestamp: new Date().toISOString(),
    });
    render();
    flashConnection("Request failed");
  }
}

async function testConnection() {
  if (!state.token) {
    flashConnection("Add an operator token first");
    return;
  }
  try {
    await fetchJson("/api/runtime", {
      headers: {
        Authorization: `Bearer ${state.token}`,
      },
    });
    flashConnection("Connected");
  } catch (error) {
    flashConnection(error.message || "Connection failed");
  }
}

function setupSpeech() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    el.recordButton.disabled = true;
    el.voiceCopy.textContent = "Speech input unavailable in this browser";
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.lang = "en-AU";
  recognition.interimResults = true;
  recognition.continuous = false;
  recognition.onstart = () => {
    state.recording = true;
    renderVoiceState();
  };
  recognition.onend = () => {
    state.recording = false;
    renderVoiceState();
  };
  recognition.onerror = () => {
    state.recording = false;
    renderVoiceState();
    flashConnection("Speech input failed");
  };
  recognition.onresult = (event) => {
    const transcript = Array.from(event.results)
      .map((result) => result[0]?.transcript || "")
      .join(" ")
      .trim();
    el.messageInput.value = transcript;
  };
  state.recognition = recognition;
  renderVoiceState();
}

function toggleRecording() {
  if (!state.recognition) {
    return;
  }
  if (state.recording) {
    state.recognition.stop();
  } else {
    state.recognition.start();
  }
}

function renderVoiceState() {
  if (!state.recognition) {
    el.voiceIndicator.className = "status-dot";
    return;
  }
  if (state.recording) {
    el.recordButton.textContent = "Stop recording";
    el.voiceIndicator.className = "status-dot recording";
    el.voiceCopy.textContent = "Listening now";
    return;
  }
  el.recordButton.textContent = "Start recording";
  el.voiceIndicator.className = "status-dot live";
  el.voiceCopy.textContent = "Voice input ready";
}

function render() {
  el.tokenInput.value = state.token;
  el.defaultsInput.value = state.defaultsText;
  renderTimeline();
  renderCurrentArtifact();
  renderDraftBadge();
}

function renderTimeline() {
  el.timeline.replaceChildren();
  if (!state.messages.length) {
    const empty = document.createElement("div");
    empty.className = "message-card";
    empty.innerHTML = `
      <div class="message-body">
        <div class="summary-block">
          <strong>Ready for the next draft.</strong>
          <p class="microcopy">Ask for a quote, an invoice, or a review action. The app keeps only the current session on this device.</p>
        </div>
      </div>
    `;
    el.timeline.append(empty);
    return;
  }

  for (const item of state.messages) {
    const fragment = el.template.content.cloneNode(true);
    const card = fragment.querySelector(".message-card");
    const role = fragment.querySelector(".message-role");
    const meta = fragment.querySelector(".message-meta");
    const body = fragment.querySelector(".message-body");

    card.classList.add(item.role);
    role.textContent = item.role === "user" ? "You" : "invoice-ai";
    meta.textContent = formatTimestamp(item.timestamp);

    if (item.role === "user") {
      body.textContent = item.text;
    } else {
      body.append(renderAssistantResponse(item.response));
    }
    el.timeline.append(fragment);
  }
}

function renderAssistantResponse(response) {
  const wrapper = document.createElement("div");
  wrapper.className = "assistant-response";

  const summary = document.createElement("section");
  summary.className = "summary-block";
  summary.innerHTML = `
    <strong>${escapeHtml(response.summary?.text || "Completed request")}</strong>
    <p class="microcopy">${escapeHtml(response.stage || "")} · ${escapeHtml(response.status || "")}</p>
  `;
  wrapper.append(summary);

  if (response.artifacts?.length) {
    const artifactList = document.createElement("section");
    artifactList.className = "artifact-list";
    for (const artifact of response.artifacts) {
      artifactList.append(renderArtifactItem(artifact));
    }
    wrapper.append(artifactList);
  }

  if (response.reviews?.length) {
    const reviewList = document.createElement("section");
    reviewList.className = "review-list";
    for (const review of response.reviews) {
      reviewList.append(renderReviewItem(review));
    }
    wrapper.append(reviewList);
  }

  if (response.erp_refs?.length) {
    const erpList = document.createElement("section");
    erpList.className = "erp-list";
    for (const ref of response.erp_refs) {
      const item = document.createElement("div");
      item.className = "erp-item";
      item.innerHTML = `<strong>${escapeHtml(ref.doctype || "ERP")}</strong><span>${escapeHtml(ref.name || "Draft")}</span>`;
      erpList.append(item);
    }
    wrapper.append(erpList);
  }

  if (response.warnings?.length) {
    const warnings = document.createElement("p");
    warnings.className = "microcopy";
    warnings.textContent = `Warnings: ${response.warnings.join(" | ")}`;
    wrapper.append(warnings);
  }

  return wrapper;
}

function renderArtifactItem(artifact) {
  const item = document.createElement("div");
  item.className = "artifact-item";
  item.innerHTML = `
    <strong>${escapeHtml(artifact.label || artifact.kind)}</strong>
    <span>${escapeHtml(artifact.file_name || "")}</span>
  `;

  const actions = document.createElement("div");
  actions.className = "artifact-actions";
  if (artifact.url) {
    actions.append(actionButton("Open", async () => openArtifact(artifact, false)));
  }
  if (artifact.download_url) {
    actions.append(actionButton("Download", async () => openArtifact(artifact, true), true));
  }
  item.append(actions);
  return item;
}

function renderReviewItem(review) {
  const item = document.createElement("div");
  item.className = "review-item";
  item.innerHTML = `
    <strong>${escapeHtml(review.summary)}</strong>
    <span>${escapeHtml(review.review_id)}</span>
  `;

  if (review.artifacts?.length) {
    const artifacts = document.createElement("div");
    artifacts.className = "artifact-actions";
    for (const artifact of review.artifacts) {
      if (artifact.url) {
        artifacts.append(
          actionButton(
            artifact.label || "Open",
            async () => openArtifact(artifact, false),
          ),
        );
      }
    }
    item.append(artifacts);
  }

  const actions = document.createElement("div");
  actions.className = "review-actions";
  const accept = document.createElement("button");
  accept.type = "button";
  accept.textContent = "Accept";
  accept.addEventListener("click", async () => {
    await triggerReviewAction("accept", review.review_id);
  });
  const reject = document.createElement("button");
  reject.type = "button";
  reject.className = "ghost-button";
  reject.textContent = "Reject";
  reject.addEventListener("click", async () => {
    await triggerReviewAction("reject", review.review_id);
  });
  actions.append(accept, reject);
  item.append(actions);
  return item;
}

async function triggerReviewAction(action, reviewId) {
  const note = window.prompt(`${action === "accept" ? "Accept" : "Reject"} review ${reviewId}. Optional note:`, "");
  const suffix = note ? ` because ${note}` : "";
  el.messageInput.value = `${action} review ${reviewId}${suffix}`;
  await sendCurrentMessage();
}

function renderCurrentArtifact() {
  el.currentArtifact.replaceChildren();
  if (!state.currentArtifact?.available) {
    el.currentArtifact.classList.add("empty");
    el.currentArtifact.innerHTML = "<p>No quote or invoice has been generated in this session yet.</p>";
    return;
  }

  el.currentArtifact.classList.remove("empty");
  const title = document.createElement("strong");
  title.textContent = state.currentArtifact.label;
  const file = document.createElement("span");
  file.textContent = state.currentArtifact.file_name;
  const actions = document.createElement("div");
  actions.className = "artifact-actions";
  actions.append(
    actionButton("Open", async () => openArtifact(state.currentArtifact, false)),
    actionButton(
      "Download",
      async () => openArtifact(state.currentArtifact, true),
      true,
    ),
  );
  el.currentArtifact.append(title, file, actions);
}

function renderDraftBadge() {
  const activeInvoice = state.conversationContext.active_invoice;
  const activeQuote = state.conversationContext.active_quote;
  if (activeInvoice?.sales_invoice) {
    el.draftBadge.textContent = `Invoice ${activeInvoice.sales_invoice}`;
    return;
  }
  if (activeQuote?.quotation) {
    el.draftBadge.textContent = `Quote ${activeQuote.quotation}`;
    return;
  }
  el.draftBadge.textContent = "No active draft";
}

function pushMessage(message) {
  state.messages.push(message);
  state.messages = state.messages.slice(-18);
  persist();
  render();
}

function hydrate() {
  try {
    const saved = JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "{}");
    state.token = saved.token || "";
    state.defaultsText = saved.defaultsText || "";
  } catch {
    state.token = "";
    state.defaultsText = "";
  }

  try {
    const session = JSON.parse(window.sessionStorage.getItem(STORAGE_KEY) || "{}");
    state.messages = Array.isArray(session.messages) ? session.messages : [];
    state.conversationContext = session.conversationContext || {};
    state.currentArtifact = session.currentArtifact || null;
  } catch {
    state.messages = [];
    state.conversationContext = {};
    state.currentArtifact = null;
  }
}

function persist() {
  window.localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      token: state.token,
      defaultsText: state.defaultsText,
    }),
  );
  window.sessionStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      messages: state.messages,
      conversationContext: state.conversationContext,
      currentArtifact: state.currentArtifact,
    }),
  );
}

function setupInstall() {
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    state.deferredPrompt = event;
    el.installButton.classList.remove("hidden");
  });
  el.installButton.addEventListener("click", async () => {
    if (!state.deferredPrompt) {
      return;
    }
    state.deferredPrompt.prompt();
    await state.deferredPrompt.userChoice;
    state.deferredPrompt = null;
    el.installButton.classList.add("hidden");
  });
}

function setupServiceWorker() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
}

function flashConnection(text) {
  el.connectionBadge.textContent = text;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let message = `${response.status}`;
    try {
      const payload = await response.json();
      message = payload.message || payload.error || message;
    } catch {
      message = response.statusText || message;
    }
    throw new Error(message);
  }
  return response.json();
}

function actionButton(label, onClick, ghost = false) {
  const button = document.createElement("button");
  button.type = "button";
  if (ghost) {
    button.className = "ghost-button";
  } else {
    button.className = "accent-button";
  }
  button.textContent = label;
  button.addEventListener("click", () => {
    void onClick();
  });
  return button;
}

async function openArtifact(artifact, download) {
  const target = download ? artifact.download_url : artifact.url;
  if (!target || !state.token) {
    return;
  }
  const response = await fetch(target, {
    headers: {
      Authorization: `Bearer ${state.token}`,
    },
  });
  if (!response.ok) {
    flashConnection("Artifact fetch failed");
    return;
  }
  const blob = await response.blob();
  const blobUrl = URL.createObjectURL(blob);
  if (download) {
    const anchor = document.createElement("a");
    anchor.href = blobUrl;
    anchor.download = artifact.file_name || "artifact";
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
    return;
  }
  window.open(blobUrl, "_blank", "noopener,noreferrer");
  setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
}

function formatTimestamp(timestamp) {
  try {
    return new Date(timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}
