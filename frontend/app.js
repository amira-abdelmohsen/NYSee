const API_BASE = "http://127.0.0.1:8000/api";

const photoInput = document.getElementById("photoInput");
const preview = document.getElementById("preview");
const analyzeImageBtn = document.getElementById("analyzeImageBtn");
const findApsBtn = document.getElementById("findApsBtn");
const replayBtn = document.getElementById("replayBtn");
const stopBtn = document.getElementById("stopBtn");
const statusEl = document.getElementById("status");
const resultEl = document.getElementById("result");

let latestSpeechText = "";
let previewUrl = null;

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

photoInput.addEventListener("change", () => {
  const file = photoInput.files?.[0];
  if (!file) {
    preview.hidden = true;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
    return;
  }

  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = URL.createObjectURL(file);
  preview.src = previewUrl;
  preview.hidden = false;
});

analyzeImageBtn.addEventListener("click", async () => {
  const file = photoInput.files?.[0];
  if (!file) {
    setResult("Please choose an image first.", "error");
    rememberAndSpeak("Please choose an image first.");
    return;
  }

  const formData = new FormData();
  formData.append("image", file);

  setStatus("Analyzing image...");
  analyzeImageBtn.disabled = true;

  try {
    const response = await fetch(`${API_BASE}/analyze-image`, {
      method: "POST",
      body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Image analysis failed.");
    }

    setResult(data.summary_text, "success");
    rememberAndSpeak(data.summary_text);
    setStatus("Image analysis complete.");
  } catch (error) {
    const message = error instanceof Error ? error.message : "Image analysis failed.";
    setResult(message, "error");
    rememberAndSpeak(message);
    setStatus("Image analysis failed.");
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

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "APS lookup failed.");
    }

    setResult(data.summary_text, "success");
    rememberAndSpeak(data.summary_text);
    setStatus("APS lookup complete.");
  } catch (error) {
    const message = error instanceof Error ? error.message : "APS lookup failed.";
    setResult(message, "error");
    rememberAndSpeak(message);
    setStatus("APS lookup failed.");
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
