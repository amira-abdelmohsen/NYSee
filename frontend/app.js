const API_BASE = "http://127.0.0.1:8000/api";

const photoInput = document.getElementById("photoInput");
const preview = document.getElementById("preview");
const previewEmpty = document.getElementById("previewEmpty");

const openCameraBtn = document.getElementById("openCameraBtn");
const captureBtn = document.getElementById("captureBtn");
const closeCameraBtn = document.getElementById("closeCameraBtn");
const cameraShell = document.getElementById("cameraShell");
const cameraPreview = document.getElementById("cameraPreview");
const captureCanvas = document.getElementById("captureCanvas");

const analyzeImageBtn = document.getElementById("analyzeImageBtn");
const clearImageBtn = document.getElementById("clearImageBtn");
const findApsBtn = document.getElementById("findApsBtn");
const replayBtn = document.getElementById("replayBtn");
const stopBtn = document.getElementById("stopBtn");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");

const detailsPanel = document.getElementById("detailsPanel");
const textLinesList = document.getElementById("textLinesList");
const metaList = document.getElementById("metaList");

let latestSpeechText = "";
let previewUrl = null;
let selectedFile = null;
let cameraStream = null;
let capturedBlob = null;

function setStatus(message) {
  statusEl.textContent = message;
}

function setResult(message, type = "success") {
  resultEl.textContent = message;
  resultEl.classList.remove("success", "error");
  resultEl.classList.add(type);
}

function speakText(text) {
  if (!("speechSynthesis" in window)) {
    return;
  }

  window.speechSynthesis.cancel();

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-US";
  utterance.rate = 1;
  utterance.pitch = 1;

  window.speechSynthesis.speak(utterance);
}

function rememberAndSpeak(text) {
  latestSpeechText = text;
  replayBtn.disabled = !text;
  if (text) {
    speakText(text);
  }
}

function clearList(el) {
  el.innerHTML = "";
}

function addListItems(el, items) {
  clearList(el);
  if (!items || items.length === 0) {
    const li = document.createElement("li");
    li.textContent = "None";
    el.appendChild(li);
    return;
  }

  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    el.appendChild(li);
  });
}

function showPreviewFromBlob(blob) {
  if (previewUrl) {
    URL.revokeObjectURL(previewUrl);
  }

  previewUrl = URL.createObjectURL(blob);
  preview.src = previewUrl;
  preview.hidden = false;
  previewEmpty.hidden = true;
}

function clearPreview() {
  if (previewUrl) {
    URL.revokeObjectURL(previewUrl);
    previewUrl = null;
  }

  preview.removeAttribute("src");
  preview.hidden = true;
  previewEmpty.hidden = false;
}

function resetImageSelection() {
  selectedFile = null;
  capturedBlob = null;
  photoInput.value = "";
  clearPreview();
}

function extractErrorMessage(data, fallbackMessage) {
  if (!data) return fallbackMessage;
  if (typeof data.detail === "string") return data.detail;
  if (typeof data.message === "string") return data.message;
  return fallbackMessage;
}

function buildExtraImageSpeech(data) {
  const parts = [];

  if (Array.isArray(data.objects) && data.objects.length > 0) {
    const objectNames = data.objects
      .slice(0, 3)
      .map((obj) => obj.name)
      .filter(Boolean);

    if (objectNames.length === 1) {
      parts.push(`Possible object detected: ${objectNames[0]}.`);
    } else if (objectNames.length > 1) {
      parts.push(`Possible objects detected: ${objectNames.join(", ")}.`);
    }
  }

  if (Array.isArray(data.selected_text_lines) && data.selected_text_lines.length > 0) {
    const spokenLines = data.selected_text_lines
      .slice(0, 3)
      .map((line) => String(line).trim())
      .filter(Boolean);

    if (spokenLines.length > 0) {
      parts.push(`Important visible text includes ${spokenLines.join(", ")}.`);
    }
  }

  return parts.join(" ");
}

function renderImageDetails(data) {
  const textLines = Array.isArray(data.selected_text_lines)
    ? data.selected_text_lines
    : [];

  const metaItems = [];

  if (Array.isArray(data.objects) && data.objects.length > 0) {
    const objectNames = data.objects.slice(0, 3).map((obj) => obj.name);
    metaItems.push(`Objects: ${objectNames.join(", ")}`);
  }

  if (Array.isArray(data.labels) && data.labels.length > 0) {
    const labelNames = data.labels.slice(0, 3).map((label) => label.description);
    metaItems.push(`Scene labels: ${labelNames.join(", ")}`);
  }

  addListItems(textLinesList, textLines);
  addListItems(metaList, metaItems);
  detailsPanel.hidden = false;
}

function renderLocationDetails(data) {
  const textItems = [];
  const metaItems = [];

  if (data?.nearest_aps?.intersection_name) {
    textItems.push(`Intersection: ${data.nearest_aps.intersection_name}`);
  }

  if (typeof data?.nearest_aps?.distance_meters === "number") {
    textItems.push(`Distance: ${data.nearest_aps.distance_meters} meters`);
  }

  if (data?.nearest_aps?.direction) {
    textItems.push(`Direction: ${data.nearest_aps.direction}`);
  }

  if (typeof data?.nearest_aps?.bearing_degrees === "number") {
    metaItems.push(`Bearing: ${data.nearest_aps.bearing_degrees} degrees`);
  }

  addListItems(textLinesList, textItems);
  addListItems(metaList, metaItems);
  detailsPanel.hidden = false;
}

function clearDetailsPanel() {
  clearList(textLinesList);
  clearList(metaList);
  detailsPanel.hidden = true;
}

async function stopCamera() {
  if (cameraStream) {
    cameraStream.getTracks().forEach((track) => track.stop());
    cameraStream = null;
  }

  cameraPreview.srcObject = null;
  cameraShell.hidden = true;
  captureBtn.disabled = true;
  closeCameraBtn.disabled = true;
}

async function startCamera() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    throw new Error("Camera access is not supported in this browser.");
  }

  await stopCamera();

  cameraStream = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: { ideal: "environment" } },
    audio: false,
  });

  cameraPreview.srcObject = cameraStream;
  cameraShell.hidden = false;
  captureBtn.disabled = false;
  closeCameraBtn.disabled = false;
}

openCameraBtn.addEventListener("click", async () => {
  setStatus("Opening camera...");
  try {
    await startCamera();
    setStatus("Camera ready.");
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Could not open the camera.";
    setResult(message, "error");
    rememberAndSpeak(message);
    setStatus("Camera unavailable.");
  }
});

closeCameraBtn.addEventListener("click", async () => {
  await stopCamera();
  setStatus("Camera closed.");
});

captureBtn.addEventListener("click", async () => {
  if (!cameraStream) {
    setResult("Camera is not open.", "error");
    rememberAndSpeak("Camera is not open.");
    return;
  }

  const width = cameraPreview.videoWidth;
  const height = cameraPreview.videoHeight;

  if (!width || !height) {
    setResult("Camera preview is not ready yet.", "error");
    rememberAndSpeak("Camera preview is not ready yet.");
    return;
  }

  captureCanvas.width = width;
  captureCanvas.height = height;

  const context = captureCanvas.getContext("2d");
  context.drawImage(cameraPreview, 0, 0, width, height);

  captureCanvas.toBlob(
    async (blob) => {
      if (!blob) {
        setResult("Could not capture the photo.", "error");
        rememberAndSpeak("Could not capture the photo.");
        return;
      }

      capturedBlob = blob;
      selectedFile = new File([blob], "camera-capture.jpg", { type: "image/jpeg" });
      showPreviewFromBlob(blob);
      setStatus("Photo captured and ready to analyze.");
      await stopCamera();
    },
    "image/jpeg",
    0.92
  );
});

photoInput.addEventListener("change", () => {
  const file = photoInput.files?.[0];

  if (!file) {
    resetImageSelection();
    return;
  }

  selectedFile = file;
  capturedBlob = null;
  showPreviewFromBlob(file);
  setStatus("Image selected and ready to analyze.");
});

clearImageBtn.addEventListener("click", async () => {
  resetImageSelection();
  await stopCamera();
  setStatus("Image cleared.");
  clearDetailsPanel();
});

analyzeImageBtn.addEventListener("click", async () => {
  if (!selectedFile) {
    const message = "Please take a photo or upload an image first.";
    setResult(message, "error");
    rememberAndSpeak(message);
    return;
  }

  const formData = new FormData();
  formData.append("image", selectedFile);

  setStatus("Analyzing image...");
  analyzeImageBtn.disabled = true;
  clearDetailsPanel();

  try {
    const response = await fetch(`${API_BASE}/analyze-image`, {
      method: "POST",
      body: formData,
    });

    const data = await response.json().catch(() => null);

    if (!response.ok) {
      throw new Error(extractErrorMessage(data, "Image analysis failed."));
    }

    const displayText = data.summary_text || "Image analyzed successfully.";
    const baseSpokenText = data.spoken_text || displayText;
    const extraSpokenText = buildExtraImageSpeech(data);
    const spokenText = [baseSpokenText, extraSpokenText].filter(Boolean).join(" ");

    setResult(displayText, "success");
    rememberAndSpeak(spokenText);
    renderImageDetails(data);
    setStatus("Image analysis complete.");
    resultEl.focus();
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "Image analysis failed.";
    setResult(message, "error");
    rememberAndSpeak(message);
    clearDetailsPanel();
    setStatus("Image analysis failed.");
    resultEl.focus();
  } finally {
    analyzeImageBtn.disabled = false;
  }
});

function getCurrentLocation() {
  return new Promise((resolve, reject) => {
    if (!("geolocation" in navigator)) {
      reject(new Error("Geolocation is not supported in this browser."));
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        resolve({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        });
      },
      (error) => {
        let message = "Could not access your location.";
        if (error.code === error.PERMISSION_DENIED) {
          message = "Location permission was denied.";
        } else if (error.code === error.TIMEOUT) {
          message = "Location request timed out.";
        }
        reject(new Error(message));
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0,
      }
    );
  });
}

findApsBtn.addEventListener("click", async () => {
  setStatus("Getting your location...");
  findApsBtn.disabled = true;
  clearDetailsPanel();

  try {
    const location = await getCurrentLocation();
    setStatus("Looking up the nearest APS...");

    const response = await fetch(`${API_BASE}/find-nearest-aps`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(location),
    });

    const data = await response.json().catch(() => null);

    if (!response.ok) {
      throw new Error(extractErrorMessage(data, "APS lookup failed."));
    }

    const displayText = data.summary_text || "APS lookup complete.";
    const spokenText = data.spoken_text || displayText;

    setResult(displayText, "success");
    rememberAndSpeak(spokenText);
    renderLocationDetails(data);
    setStatus("APS lookup complete.");
    resultEl.focus();
  } catch (error) {
    const message =
      error instanceof Error ? error.message : "APS lookup failed.";
    setResult(message, "error");
    rememberAndSpeak(message);
    clearDetailsPanel();
    setStatus("APS lookup failed.");
    resultEl.focus();
  } finally {
    findApsBtn.disabled = false;
  }
});

replayBtn.addEventListener("click", () => {
  if (!latestSpeechText) return;
  speakText(latestSpeechText);
});

stopBtn.addEventListener("click", () => {
  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
});

window.addEventListener("beforeunload", () => {
  if (previewUrl) {
    URL.revokeObjectURL(previewUrl);
  }
  if (cameraStream) {
    cameraStream.getTracks().forEach((track) => track.stop());
  }
});