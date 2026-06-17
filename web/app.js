let images = [];
let selectedIndex = -1;
let availableLabels = [
  { name: "target", count: 0 },
  { name: "other", count: 0 },
  { name: "unknown", count: 0 },
];
const selectedIds = new Set();
const DEBUG = true;

const imageGrid = document.querySelector("#imageGrid");
const selectedImage = document.querySelector("#selectedImage");
const selectedMeta = document.querySelector("#selectedMeta");
const statusFilter = document.querySelector("#statusFilter");
const labelFilter = document.querySelector("#labelFilter");
const labelPalette = document.querySelector("#labelPalette");
const bulkLabelButtons = document.querySelector("#bulkLabelButtons");
const newLabelInput = document.querySelector("#newLabelInput");
const deleteLabelSelect = document.querySelector("#deleteLabelSelect");
const deleteLabelButton = document.querySelector("#deleteLabelButton");
const selectedCount = document.querySelector("#selectedCount");
const statusMessage = document.querySelector("#statusMessage");
const datasetSelect = document.querySelector("#datasetSelect");
const modelSelect = document.querySelector("#modelSelect");
const logBox = document.querySelector("#logBox");
const trainingProgress = document.querySelector("#trainingProgress");
const testResults = document.querySelector("#testResults");
const lossChart = document.querySelector("#lossChart");
const accuracyChart = document.querySelector("#accuracyChart");
const artifactStatus = document.querySelector("#artifactStatus");
const flashProgress = document.querySelector("#flashProgress");
const serialPortSelect = document.querySelector("#serialPortSelect");
const devicePortSelect = document.querySelector("#devicePortSelect");
const wifiFlashProgress = document.querySelector("#wifiFlashProgress");
const wifiSsidInput = document.querySelector("#wifiSsidInput");
const wifiSsidOptions = document.querySelector("#wifiSsidOptions");
const wifiPasswordInput = document.querySelector("#wifiPasswordInput");
const toggleWifiPasswordButton = document.querySelector("#toggleWifiPasswordButton");
const serverUploadUrlInput = document.querySelector("#serverUploadUrlInput");
const deviceIdInput = document.querySelector("#deviceIdInput");
const esp32BaseUrlInput = document.querySelector("#esp32BaseUrlInput");
const discoverCameraButton = document.querySelector("#discoverCameraButton");
const openAiCameraButton = document.querySelector("#openAiCameraButton");
const remoteCameraDialog = document.querySelector("#remoteCameraDialog");
const remoteCameraStream = document.querySelector("#remoteCameraStream");
const remoteCameraStatus = document.querySelector("#remoteCameraStatus");
const remoteCaptureButton = document.querySelector("#remoteCaptureButton");
const remoteShutterFlash = document.querySelector("#remoteShutterFlash");
const remoteLabelOverlay = document.querySelector("#remoteLabelOverlay");
let trainingPollTimer = null;
let currentTrainingRunId = "";
let availableModels = [];
let firmwareArtifacts = [];
let flashTargets = [];
let aiCameraTimer = null;
let aiCameraRunning = false;

function debugLog(message, value) {
  if (!DEBUG) return;
  if (value === undefined) {
    console.log(`[vision-ui] ${message}`);
  } else {
    console.log(`[vision-ui] ${message}`, value);
  }
}

function showStatus(message, type = "info") {
  statusMessage.textContent = message;
  statusMessage.className = `statusMessage ${type}`;
}

function formatApiError(data) {
  const detail = data?.detail ?? data;
  if (!detail || typeof detail === "string") {
    return detail || "Request failed.";
  }
  const lines = [];
  if (detail.message) lines.push(detail.message);
  if (detail.hint) lines.push(`hint: ${detail.hint}`);
  if (detail.command) lines.push(`command: ${detail.command}`);
  if (detail.returncode !== undefined) lines.push(`returncode: ${detail.returncode}`);
  if (detail.stdout) lines.push("", "stdout:", detail.stdout);
  if (detail.stderr) lines.push("", "stderr:", detail.stderr);
  return lines.length ? lines.join("\n") : JSON.stringify(data, null, 2);
}

function drawChart(canvas, history, series, options = {}) {
  const context = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  const padding = { left: 36, right: 12, top: 12, bottom: 28 };
  context.clearRect(0, 0, width, height);
  context.fillStyle = "#ffffff";
  context.fillRect(0, 0, width, height);

  const values = [];
  for (const point of history) {
    for (const item of series) {
      if (typeof point[item.key] === "number") values.push(point[item.key]);
    }
  }
  if (!history.length || !values.length) {
    context.fillStyle = "#667085";
    context.font = "12px system-ui";
    context.fillText("No history yet", padding.left, height / 2);
    return;
  }

  const minValue = options.min ?? Math.min(...values);
  const maxValue = options.max ?? Math.max(...values);
  const range = Math.max(maxValue - minValue, 0.001);
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;

  context.strokeStyle = "#d9dee7";
  context.lineWidth = 1;
  context.beginPath();
  context.moveTo(padding.left, padding.top);
  context.lineTo(padding.left, padding.top + plotHeight);
  context.lineTo(padding.left + plotWidth, padding.top + plotHeight);
  context.stroke();

  context.fillStyle = "#667085";
  context.font = "11px system-ui";
  context.fillText(maxValue.toFixed(2), 4, padding.top + 4);
  context.fillText(minValue.toFixed(2), 4, padding.top + plotHeight);
  context.fillText(`epoch ${history[history.length - 1].epoch}`, padding.left + plotWidth - 54, height - 8);

  for (const item of series) {
    const points = history
      .filter((point) => typeof point[item.key] === "number")
      .map((point, index, filtered) => {
        const x = padding.left + (filtered.length === 1 ? 0 : (index / (filtered.length - 1)) * plotWidth);
        const y = padding.top + plotHeight - ((point[item.key] - minValue) / range) * plotHeight;
        return { x, y };
      });
    if (!points.length) continue;
    context.strokeStyle = item.color;
    context.lineWidth = 2;
    context.beginPath();
    points.forEach((point, index) => {
      if (index === 0) context.moveTo(point.x, point.y);
      else context.lineTo(point.x, point.y);
    });
    context.stroke();
  }

  let legendX = padding.left;
  for (const item of series) {
    context.fillStyle = item.color;
    context.fillRect(legendX, height - 18, 9, 9);
    context.fillStyle = "#1c2430";
    context.fillText(item.label, legendX + 13, height - 10);
    legendX += item.label.length * 7 + 34;
  }
}

function renderTrainingCharts(history) {
  drawChart(lossChart, history, [
    { key: "loss", label: "loss", color: "#b42318" },
    { key: "val_loss", label: "val_loss", color: "#146c94" },
  ]);
  drawChart(
    accuracyChart,
    history,
    [
      { key: "accuracy", label: "accuracy", color: "#2f7d32" },
      { key: "val_accuracy", label: "val_accuracy", color: "#7a4cc2" },
    ],
    { min: 0, max: 1 }
  );
}

async function loadTrainingHistory(runId) {
  if (!runId) {
    renderTrainingCharts([]);
    return;
  }
  try {
    const response = await fetch(`/api/training/${encodeURIComponent(runId)}/history`);
    const data = await response.json();
    if (response.ok && data.ok) {
      renderTrainingCharts(data.history || []);
    }
  } catch (error) {
    debugLog("load training history failed", error);
  }
}

async function loadLabels() {
  try {
    const response = await fetch("/api/labels");
    if (!response.ok) {
      showStatus(`Failed to load labels: ${response.status}`, "error");
      return;
    }
    const data = await response.json();
    if (Array.isArray(data.labels)) {
      availableLabels = data.labels;
    } else if (Array.isArray(data.classes)) {
      availableLabels = data.classes.map((name) => ({ name, count: 0 }));
    }
  } catch (error) {
    showStatus(`Failed to load labels: ${error.message}`, "error");
    debugLog("load labels failed", error);
    return;
  }
  renderLabelFilter();
  renderDeleteLabelSelect();
  renderLabelPalette();
}

function renderLabelFilter() {
  const currentValue = labelFilter.value;
  labelFilter.innerHTML = `<option value="">All labels</option>`;
  for (const label of availableLabels) {
    const name = labelName(label);
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    labelFilter.appendChild(option);
  }
  labelFilter.value = currentValue;
}

function renderDeleteLabelSelect() {
  const currentValue = deleteLabelSelect.value;
  deleteLabelSelect.innerHTML = `<option value="">Select label to delete</option>`;
  for (const label of availableLabels) {
    const name = labelName(label);
    if (name === "unknown" || name === "test") continue;
    const option = document.createElement("option");
    option.value = name;
    option.textContent = `${name} (${Number(label.count || 0)})`;
    deleteLabelSelect.appendChild(option);
  }
  deleteLabelSelect.value = [...deleteLabelSelect.options].some((option) => option.value === currentValue)
    ? currentValue
    : "";
}

function renderLabelPalette() {
  labelPalette.innerHTML = "";
  bulkLabelButtons.innerHTML = "";
  for (const label of availableLabels) {
    const name = labelName(label);
    const count = Number(label.count || 0);
    const selected = labelIsActiveForCurrentContext(name);

    const paletteButton = document.createElement("button");
    paletteButton.className = "label-chip-button" + (selected ? " active" : "");
    paletteButton.textContent = `${name} ${count}`;
    paletteButton.title = `Toggle ${name}`;
    paletteButton.addEventListener("click", () => togglePaletteLabel(name, false));
    labelPalette.appendChild(paletteButton);

    const bulkButton = document.createElement("button");
    bulkButton.className = "label-chip-button";
    bulkButton.textContent = `${name} ${count}`;
    bulkButton.addEventListener("click", () => togglePaletteLabel(name, true));
    bulkLabelButtons.appendChild(bulkButton);
  }
}

function labelName(label) {
  return typeof label === "string" ? label : label?.name || "";
}

async function loadImages() {
  const params = new URLSearchParams();
  if (statusFilter.value) params.set("status", statusFilter.value);
  if (labelFilter.value) params.set("label", labelFilter.value);
  params.set("limit", "80");
  const response = await fetch(`/api/images?${params.toString()}`);
  const data = await response.json();
  images = data.images;
  debugLog("loaded images", images.length);
  for (const id of [...selectedIds]) {
    if (!images.some((image) => image.id === id)) selectedIds.delete(id);
  }
  selectedIndex = images.length ? 0 : -1;
  renderImages();
  renderSelected();
}

function renderImages() {
  imageGrid.innerHTML = "";
  for (const [index, image] of images.entries()) {
    const card = document.createElement("article");
    const checked = selectedIds.has(image.id);
    card.className =
      "imageCard" +
      (index === selectedIndex ? " active" : "") +
      (checked ? " selected" : "") +
      (image.reserved_for_test ? " testReserved" : "");
    card.dataset.imageId = String(image.id);
    card.addEventListener("click", () => {
      selectedIndex = index;
      renderImages();
      renderSelected();
    });
    const labels = labelsForImage(image);
    const labelChips = labels.length
      ? renderLabelChips(labels, image.id)
      : `<span class="label-chip muted">unknown</span>`;
    card.innerHTML = `
      <label class="checkboxWrap" title="Select for bulk label" data-select-label>
        <input class="image-select-checkbox" type="checkbox" ${checked ? "checked" : ""} data-image-id="${image.id}" aria-label="Select ${escapeHtml(image.filename)}">
      </label>
      <img src="${image.url}" alt="${image.filename}" loading="lazy">
      <div class="caption">
        <div class="filename">${escapeHtml(image.filename)}</div>
        <div class="image-labels">${labelChips}</div>
      </div>
    `;
    const selectBox = card.querySelector("[data-select-label]");
    const checkbox = card.querySelector("input[type='checkbox']");
    selectBox.addEventListener("click", (event) => {
      event.stopPropagation();
    });
    checkbox.addEventListener("click", (event) => {
      event.stopPropagation();
    });
    checkbox.addEventListener("change", (event) => {
      event.stopPropagation();
      toggleImageSelection(image.id, event.target.checked);
    });
    card.querySelectorAll(".label-remove").forEach((button) => {
      button.addEventListener("click", async (event) => {
        event.stopPropagation();
        await removeLabelsFromImages([Number(button.dataset.imageId)], [button.dataset.label]);
      });
    });
    imageGrid.appendChild(card);
  }
  renderSelectionCount();
}

function labelsForImage(image) {
  const rawLabel = Array.isArray(image.labels) ? image.labels : image.label;
  if (Array.isArray(rawLabel)) {
    const labels = rawLabel
      .map((label) => (typeof label === "string" ? label : label?.name))
      .filter((label) => typeof label === "string" && label.trim() && !label.startsWith("#"))
      .map((label) => label.trim());
    if (image.reserved_for_test && !labels.includes("test")) labels.push("test");
    return labels;
  }
  if (typeof rawLabel === "string") {
    const labels = rawLabel
      .split(",")
      .map((label) => label.trim())
      .filter((label) => label && !label.startsWith("#"));
    if (image.reserved_for_test && !labels.includes("test")) labels.push("test");
    return labels;
  }
  return image.reserved_for_test ? ["test"] : [];
}

function renderLabelChips(labels, imageId) {
  return labels
    .map(
      (label) => `
        <span class="label-chip">
          ${escapeHtml(label)}
          <button class="label-remove" type="button" data-image-id="${imageId}" data-label="${escapeHtml(label)}" title="Remove ${escapeHtml(label)}">x</button>
        </span>
      `
    )
    .join("");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderSelected() {
  const image = images[selectedIndex];
  if (!image) {
    selectedImage.removeAttribute("src");
    selectedMeta.textContent = "No image selected";
    return;
  }
  selectedImage.src = image.url;
  selectedMeta.innerHTML = `
    <div>#${image.id} ${escapeHtml(image.filename)} / ${escapeHtml(image.status)}</div>
    <div>${image.reserved_for_test ? "Reserved for test review" : "Training candidate"}</div>
    <div class="image-labels">${renderLabelChips(labelsForImage(image), image.id)}</div>
  `;
  selectedMeta.querySelectorAll(".label-remove").forEach((button) => {
    button.addEventListener("click", async (event) => {
      event.stopPropagation();
      await removeLabelsFromImages([Number(button.dataset.imageId)], [button.dataset.label]);
    });
  });
  renderLabelPalette();
}

function renderSelectionCount() {
  selectedCount.textContent = `Selected: ${selectedIds.size} images`;
}

function toggleImageSelection(imageId, checked) {
  debugLog("checkbox changed", { imageId, checked });
  if (checked) {
    selectedIds.add(imageId);
  } else {
    selectedIds.delete(imageId);
  }
  debugLog("selected image ids", [...selectedIds]);
  renderImages();
  renderLabelPalette();
  showStatus(`Selected ${selectedIds.size} images`, "info");
}

function selectAllVisible() {
  for (const image of images) selectedIds.add(image.id);
  renderImages();
  renderLabelPalette();
  showStatus(`Selected ${selectedIds.size} images`, "info");
}

function clearSelection() {
  selectedIds.clear();
  renderImages();
  renderLabelPalette();
  showStatus("Selection cleared", "info");
}

async function setLabel(label) {
  const image = images[selectedIndex];
  if (!image) return;
  const response = await fetch(`/api/images/${image.id}/label`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label }),
  });
  const data = await response.json();
  if (data.ok) {
    image.label = label;
    image.status = label === "unknown" ? "unlabeled" : "labeled";
    nextImage();
  }
}

function currentTargetImageIds(requireCheckedSelection) {
  if (selectedIds.size) return [...selectedIds];
  if (requireCheckedSelection) return [];
  const image = images[selectedIndex];
  return image ? [image.id] : [];
}

function labelIsActiveForCurrentContext(label) {
  const targetIds = currentTargetImageIds(false);
  if (!targetIds.length) return false;
  return targetIds.every((id) => {
    const image = images.find((item) => item.id === id);
    return image ? labelsForImage(image).includes(label) : false;
  });
}

async function togglePaletteLabel(label, requireCheckedSelection) {
  const imageIds = currentTargetImageIds(requireCheckedSelection);
  if (!imageIds.length) {
    showStatus("Please select at least one image", "error");
    return;
  }
  if (label === "test") {
    await updateTestReserveForImages(imageIds, !labelIsActiveForCurrentContext("test"));
    return;
  }
  if (labelIsActiveForCurrentContext(label)) {
    await removeLabelsFromImages(imageIds, [label]);
  } else {
    await addLabelsToImages(imageIds, [label]);
  }
}

async function addLabelsToImages(imageIds, labelNames) {
  if (labelNames.includes("test")) {
    await updateTestReserveForImages(imageIds, true);
    return;
  }
  if (!imageIds.length) {
    showStatus("Please select at least one image", "error");
    logBox.textContent = "Please select at least one image.";
    return;
  }
  const requestBody = { image_ids: imageIds, label_names: labelNames };
  debugLog("bulk label request", requestBody);
  try {
    const response = await fetch("/api/images/batch/labels", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });
    const data = await response.json();
    debugLog("bulk label response", data);
    logBox.textContent = JSON.stringify(data, null, 2);
    if (!response.ok || !data.ok) {
      showStatus(`Failed to apply label: ${response.status}`, "error");
      return;
    }
    showStatus(`Applied ${labelNames.join(", ")} to ${data.updated_count} images`, "success");
    await loadLabels();
    await loadImages();
  } catch (error) {
    debugLog("bulk label failed", error);
    showStatus(`Failed to apply label: ${error.message}`, "error");
    logBox.textContent = String(error);
  }
}

async function createLabel() {
  const name = newLabelInput.value.trim();
  if (!name) {
    showStatus("Please enter a label name", "error");
    return;
  }
  try {
    const response = await fetch("/api/labels", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      showStatus(`Failed to add label: ${response.status}`, "error");
      return;
    }
    newLabelInput.value = "";
    showStatus(`Added label ${data.label.name}`, "success");
    await loadLabels();
    deleteLabelSelect.value = data.label.name;
  } catch (error) {
    showStatus(`Failed to add label: ${error.message}`, "error");
  }
}

async function postLabel(name) {
  const response = await fetch("/api/labels", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(`Failed to add label ${name}: ${response.status}`);
  }
  return data;
}

async function createTestLabel() {
  const baseName = newLabelInput.value.trim();
  if (!baseName) {
    showStatus("Please enter a base label name", "error");
    return;
  }
  const normalName = baseName.startsWith("test_") ? baseName.slice(5) : baseName;
  const testName = baseName.startsWith("test_") ? baseName : `test_${baseName}`;
  if (!normalName) {
    showStatus("Please enter a base label name after test_", "error");
    return;
  }
  try {
    await postLabel(normalName);
    await postLabel(testName);
    newLabelInput.value = "";
    showStatus(`Added ${normalName} and ${testName}`, "success");
    await loadLabels();
    deleteLabelSelect.value = testName;
  } catch (error) {
    showStatus(error.message, "error");
    logBox.textContent = String(error);
  }
}

async function deleteSelectedLabel() {
  const labelName = deleteLabelSelect.value;
  if (!labelName) {
    showStatus("Please select a label to delete", "error");
    return;
  }

  try {
    const response = await fetch(`/api/labels/${encodeURIComponent(labelName)}`, {
      method: "DELETE",
    });
    const data = await response.json();
    logBox.textContent = JSON.stringify(data, null, 2);
    if (!response.ok || !data.ok) {
      showStatus(`Failed to delete label: ${response.status}`, "error");
      return;
    }
    if (labelFilter.value === labelName) {
      labelFilter.value = "";
    }
    deleteLabelSelect.value = "";
    selectedIds.clear();
    showStatus(`Deleted label ${labelName} from all images`, "success");
    await loadLabels();
    await loadImages();
  } catch (error) {
    debugLog("delete label failed", error);
    showStatus(`Failed to delete label: ${error.message}`, "error");
    logBox.textContent = String(error);
  }
}

async function removeLabelsFromImages(imageIds, labelNames) {
  if (labelNames.includes("test")) {
    await updateTestReserveForImages(imageIds, false);
    return;
  }
  const requestBody = { image_ids: imageIds, label_names: labelNames };
  debugLog("remove labels request", requestBody);
  try {
    const response = await fetch("/api/images/batch/labels", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });
    const data = await response.json();
    debugLog("remove labels response", data);
    logBox.textContent = JSON.stringify(data, null, 2);
    if (!response.ok || !data.ok) {
      showStatus(`Failed to remove label: ${response.status}`, "error");
      return;
    }
    showStatus(`Removed ${labelNames.join(", ")} from ${data.updated_count} images`, "success");
    await loadLabels();
    await loadImages();
  } catch (error) {
    debugLog("remove labels failed", error);
    showStatus(`Failed to remove label: ${error.message}`, "error");
    logBox.textContent = String(error);
  }
}

async function updateTestReserveForImages(imageIds, reservedForTest) {
  if (!imageIds.length) {
    showStatus("Please select at least one image", "error");
    return;
  }
  try {
    const response = await fetch("/api/images/batch/test-reserve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image_ids: imageIds, reserved_for_test: reservedForTest }),
    });
    const data = await response.json();
    logBox.textContent = JSON.stringify(data, null, 2);
    if (!response.ok || !data.ok) {
      showStatus(`Failed to update test reserve: ${response.status}`, "error");
      return;
    }
    showStatus(
      `${reservedForTest ? "Marked" : "Unmarked"} ${data.updated_count} images for test review`,
      "success"
    );
    await loadImages();
  } catch (error) {
    showStatus(`Failed to update test reserve: ${error.message}`, "error");
    logBox.textContent = String(error);
  }
}

async function deleteUnknownImages() {
  const confirmed = window.confirm("Delete all unknown/unlabeled images from the database and data/raw?");
  if (!confirmed) return;
  try {
    let response = await fetch("/api/images/delete-unknown", { method: "POST" });
    if (response.status === 405) {
      response = await fetch("/api/images/unknown", { method: "DELETE" });
    }
    const data = await response.json();
    logBox.textContent = JSON.stringify(data, null, 2);
    if (!response.ok || !data.ok) {
      showStatus(`Failed to delete unknown images: ${response.status}`, "error");
      return;
    }
    selectedIds.clear();
    showStatus(`Deleted ${data.deleted_images} unknown images`, "success");
    await loadLabels();
    await loadImages();
  } catch (error) {
    showStatus(`Failed to delete unknown images: ${error.message}`, "error");
    logBox.textContent = String(error);
  }
}

function nextImage() {
  if (!images.length) return;
  selectedIndex = Math.min(selectedIndex + 1, images.length - 1);
  renderImages();
  renderSelected();
}

async function downloadMultilabelCsv() {
  try {
    const response = await fetch("/api/images/export/multilabel.csv");
    debugLog("CSV download status", response.status);
    if (!response.ok) {
      showStatus(`Failed to download CSV: ${response.status}`, "error");
      return;
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "label_dataset.csv";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    debugLog("CSV download complete");
    showStatus("Downloaded label CSV", "success");
  } catch (error) {
    debugLog("CSV download failed", error);
    showStatus(`Failed to download CSV: ${error.message}`, "error");
  }
}

async function loadDatasets() {
  try {
    const response = await fetch("/api/datasets");
    if (!response.ok) {
      showStatus(`Failed to load datasets: ${response.status}`, "error");
      return;
    }
    const data = await response.json();
    const currentValue = datasetSelect.value || document.querySelector("#datasetPath").value;
    datasetSelect.innerHTML = `<option value="">Select exported dataset</option>`;
    for (const dataset of data.datasets || []) {
      const option = document.createElement("option");
      option.value = dataset.path;
      option.textContent = `${dataset.name} (${dataset.train_count}/${dataset.val_count}/${dataset.test_count})`;
      datasetSelect.appendChild(option);
    }
    if ([...datasetSelect.options].some((option) => option.value === currentValue)) {
      datasetSelect.value = currentValue;
    }
  } catch (error) {
    showStatus(`Failed to load datasets: ${error.message}`, "error");
  }
}

async function loadModels() {
  try {
    const response = await fetch("/api/training/models");
    if (!response.ok) {
      showStatus(`Failed to load models: ${response.status}`, "error");
      return;
    }
    const data = await response.json();
    availableModels = data.models || [];
    const currentValue = modelSelect.value || currentTrainingRunId;
    modelSelect.innerHTML = `<option value="">Select trained model</option>`;
    for (const model of availableModels) {
      const option = document.createElement("option");
      option.value = model.run_id;
      const datasetName = model.dataset_path_relative ? model.dataset_path_relative.split(/[\\\\/]/).pop() : "unknown dataset";
      const labels = Array.isArray(model.labels) ? model.labels.join(",") : "";
      const exportState = [
        model.has_int8_tflite ? "int8" : "no-int8",
        model.has_ai_model_package ? "ai-model" : "no-ai-model",
      ].join(" ");
      option.textContent = `${model.run_id} / ${datasetName} / ${labels} / ${exportState}`;
      modelSelect.appendChild(option);
    }
    if ([...modelSelect.options].some((option) => option.value === currentValue)) {
      modelSelect.value = currentValue;
    }
  } catch (error) {
    showStatus(`Failed to load models: ${error.message}`, "error");
  }
}

function selectedModelRunId() {
  const runId = modelSelect.value || currentTrainingRunId;
  if (!runId) {
    showStatus("Select a trained model first", "error");
    return "";
  }
  return runId;
}

async function exportSelectedTflite() {
  const runId = selectedModelRunId();
  if (!runId) return;
  const datasetPath = document.querySelector("#datasetPath").value;
  showStatus(`Exporting TFLite for ${runId}...`, "info");
  logBox.textContent = "Exporting TFLite. This can take a while...";
  try {
    const response = await fetch(`/api/training/${encodeURIComponent(runId)}/export-tflite`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dataset_path: datasetPath || null }),
    });
    const data = await response.json();
    logBox.textContent = JSON.stringify(data, null, 2);
    if (!response.ok || !data.ok) {
      showStatus(`TFLite export failed: ${response.status}`, "error");
      return;
    }
    showStatus(`Generated model_int8.tflite (${data.model_int8_size} bytes)`, "success");
    await loadModels();
    modelSelect.value = runId;
  } catch (error) {
    showStatus(`TFLite export failed: ${error.message}`, "error");
    logBox.textContent = String(error);
  }
}

async function exportSelectedCArray() {
  const runId = selectedModelRunId();
  if (!runId) return;
  showStatus(`Exporting C array for ${runId}...`, "info");
  logBox.textContent = "Exporting C array and copying it to firmware...";
  try {
    const response = await fetch(`/api/training/${encodeURIComponent(runId)}/export-c-array`, {
      method: "POST",
    });
    const data = await response.json();
    logBox.textContent = JSON.stringify(data, null, 2);
    if (!response.ok || !data.ok) {
      showStatus(`C array export failed: ${response.status}`, "error");
      return;
    }
    showStatus("Generated model_data.cc/h and copied them to inference firmware", "success");
    await loadModels();
    modelSelect.value = runId;
  } catch (error) {
    showStatus(`C array export failed: ${error.message}`, "error");
    logBox.textContent = String(error);
  }
}

async function buildInferenceFirmware() {
  showStatus("Building inference firmware...", "info");
  logBox.textContent = "Building inference firmware. Start the server from ESP-IDF PowerShell if this fails.";
  try {
    const response = await fetch("/api/training/build-inference-firmware", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ clean: false }),
    });
    const data = await response.json();
    logBox.textContent = JSON.stringify(data, null, 2);
    if (!response.ok || !data.ok) {
      showStatus(`Firmware build failed: ${response.status}`, "error");
      return;
    }
    showStatus("Inference firmware build passed", "success");
    await loadInferenceArtifacts();
  } catch (error) {
    showStatus(`Firmware build failed: ${error.message}`, "error");
    logBox.textContent = String(error);
  }
}

async function prepareInferenceFirmware() {
  const runId = selectedModelRunId();
  if (!runId) return;
  const datasetPath = document.querySelector("#datasetPath").value;
  showStatus(`Preparing model package for ${runId}...`, "info");
  logBox.textContent = [
    "Preparing model package...",
    "1. Export TFLite",
    "2. Build ai_model.bin",
  ].join("\n");
  try {
    const response = await fetch(`/api/training/${encodeURIComponent(runId)}/prepare-inference-firmware`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dataset_path: datasetPath || null }),
    });
    const data = await response.json();
    logBox.textContent = [
      "Prepare model package completed.",
      `run_id: ${data.run_id}`,
      `model_int8.tflite: ${data.steps?.export_tflite?.model_int8_size || "-"} bytes`,
      `ai_model.bin: ${data.steps?.export_ai_model_package?.ai_model_size || "-"} bytes`,
      `model partition offset: ${data.steps?.export_ai_model_package?.partition_offset || "0x310000"}`,
      "",
      "Next: select COM port and click Write model only.",
    ].join("\n");
    if (!response.ok || !data.ok) {
      showStatus(`Prepare firmware failed: ${response.status}`, "error");
      return;
    }
    showStatus("Model package is ready to write", "success");
    renderFlashSteps("prepared");
    await loadModels();
    modelSelect.value = runId;
  } catch (error) {
    showStatus(`Prepare model package failed: ${error.message}`, "error");
    logBox.textContent = String(error);
  }
}

function renderFlashSteps(state = "idle") {
  const steps = [
    ["select", "Model selected"],
    ["tflite", "Export TFLite"],
    ["package", "Build model package"],
    ["port", "COM port selected"],
    ["flash", "Write model only"],
  ];
  const completedByState = {
    idle: [],
    prepared: ["select", "tflite", "package"],
    flashing: ["select", "tflite", "package", "port"],
    done: ["select", "tflite", "package", "port", "flash"],
  };
  const activeByState = {
    idle: "",
    prepared: "",
    flashing: "flash",
    done: "",
  };
  const completed = new Set(completedByState[state] || []);
  const active = activeByState[state] || "";
  flashProgress.innerHTML = steps
    .map(([key, label]) => {
      const className = completed.has(key) ? "done" : active === key ? "active" : "";
      const marker = completed.has(key) ? "OK" : active === key ? "..." : "--";
      return `<div class="flashStep ${className}"><span>${escapeHtml(label)}</span><strong>${marker}</strong></div>`;
    })
    .join("");
}

function renderWifiFirmwareProgress(state = "idle", message = "") {
  if (!wifiFlashProgress) return;
  const steps = [
    ["save", "Save Wi-Fi settings"],
    ["write", "Write firmware"],
    ["verify", "Restart and find camera"],
  ];
  const stateMap = {
    idle: { percent: 0, done: [], active: "", tone: "", label: "" },
    saving: { percent: 22, done: [], active: "save", tone: "active", label: "Saving settings..." },
    writing: { percent: 68, done: ["save"], active: "write", tone: "active indeterminate", label: "Writing firmware..." },
    verifying: { percent: 88, done: ["save", "write"], active: "verify", tone: "active indeterminate", label: "Restarting and checking camera..." },
    done: { percent: 100, done: ["save", "write", "verify"], active: "", tone: "done", label: "Write completed" },
    error: { percent: 100, done: [], active: "", tone: "error", label: "Write failed" },
  };
  const current = stateMap[state] || stateMap.idle;
  const done = new Set(current.done);
  const rows = steps
    .map(([key, label]) => {
      const className = done.has(key) ? "done" : current.active === key ? "active" : state === "error" ? "error" : "";
      const marker = done.has(key) ? "OK" : current.active === key ? "..." : "--";
      return `<div class="wifiFlashStep ${className}"><span>${escapeHtml(label)}</span><strong>${marker}</strong></div>`;
    })
    .join("");
  wifiFlashProgress.innerHTML = `
    <div class="wifiFlashBar ${current.tone}">
      <span style="width: ${current.percent}%"></span>
    </div>
    <div class="wifiFlashMessage">${escapeHtml(message || current.label)}</div>
    <div class="wifiFlashSteps">${rows}</div>
  `;
}

function formatBytes(value) {
  if (typeof value !== "number") return "-";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

async function loadInferenceArtifacts() {
  if (!artifactStatus) return;
  try {
    const response = await fetch("/api/firmware/artifacts");
    const data = await response.json();
    if (!response.ok || !data.ok) {
      artifactStatus.innerHTML = `<div class="artifactRow missing">Failed to load firmware artifacts</div>`;
      return;
    }
    firmwareArtifacts = data.firmwares || [];
    flashTargets = data.flash_targets || [];
    const selectedTarget = flashTargets.find((item) => item.id === "capture_full") || flashTargets[0];
    const selected = firmwareArtifacts.find((item) => item.name === selectedTarget?.firmware) || firmwareArtifacts[0];
    if (!selected) {
      artifactStatus.innerHTML = `<div class="artifactRow missing">No firmware artifacts found</div>`;
      return;
    }
    const rows = (selectedTarget?.files || [])
      .map((item) => {
        const status = item?.exists ? "OK" : "NG";
        const className = item?.exists ? "ready" : "missing";
        const label = `${item.address} ${item.relative_file}`;
        return `
          <div class="artifactRow ${className}">
            <span>${label}</span>
            <strong>${status}</strong>
            <small>${formatBytes(item?.size)}</small>
          </div>
        `;
      })
      .join("");
    artifactStatus.innerHTML = `
      <div class="artifactSummary ${selectedTarget?.ready_to_flash ? "ready" : "missing"}">
        ${escapeHtml(selectedTarget?.label || selected.label)}: ${selectedTarget?.ready_to_flash ? "Ready to flash" : "Not ready"}
      </div>
      ${rows}
    `;
  } catch (error) {
    artifactStatus.innerHTML = `<div class="artifactRow missing">${escapeHtml(error.message)}</div>`;
  }
}

async function loadSerialPorts() {
  try {
    const currentInferenceValue = serialPortSelect.value;
    const currentDeviceValue = devicePortSelect.value;
    const response = await fetch("/api/firmware/serial-ports");
    const data = await response.json();
    const selects = [serialPortSelect, devicePortSelect];
    for (const select of selects) {
      select.innerHTML = `<option value="">Select COM port</option>`;
      for (const item of data.ports || []) {
        const option = document.createElement("option");
        option.value = item.port;
        option.textContent = `${item.port} / ${item.name}`;
        select.appendChild(option);
      }
    }
    if ([...serialPortSelect.options].some((option) => option.value === currentInferenceValue)) {
      serialPortSelect.value = currentInferenceValue;
    }
    if ([...devicePortSelect.options].some((option) => option.value === currentDeviceValue)) {
      devicePortSelect.value = currentDeviceValue;
    } else if (serialPortSelect.value) {
      devicePortSelect.value = serialPortSelect.value;
    }
    showStatus(`Found ${(data.ports || []).length} serial ports`, "info");
  } catch (error) {
    showStatus(`Failed to load serial ports: ${error.message}`, "error");
  }
}

async function loadWifiNetworks() {
  try {
    const response = await fetch("/api/firmware/wifi-networks");
    const data = await response.json();
    wifiSsidOptions.innerHTML = "";
    for (const ssid of data.ssids || []) {
      const option = document.createElement("option");
      option.value = ssid;
      wifiSsidOptions.appendChild(option);
    }
  } catch (error) {
    debugLog("failed to load Wi-Fi networks", error);
  }
}

async function loadWifiConfig() {
  try {
    const response = await fetch("/api/firmware/wifi-config");
    const data = await response.json();
    if (!response.ok || !data.ok) {
      showStatus(`Failed to load Wi-Fi settings: ${response.status}`, "error");
      return;
    }
    wifiSsidInput.value = data.ssid || "";
    wifiPasswordInput.value = data.password || "";
    wifiPasswordInput.placeholder = "Enter Wi-Fi password";
    serverUploadUrlInput.value = data.server_upload_url || "";
    deviceIdInput.value = data.device_id || "";
  } catch (error) {
    showStatus(`Failed to load Wi-Fi settings: ${error.message}`, "error");
  }
}

async function saveWifiConfig() {
  const requestBody = {
    ssid: wifiSsidInput.value.trim(),
    password: wifiPasswordInput.value,
    server_upload_url: serverUploadUrlInput.value.trim(),
    device_id: deviceIdInput.value.trim(),
  };
  if (!requestBody.ssid || !requestBody.server_upload_url || !requestBody.device_id) {
    showStatus("SSID, Server URL, and Device ID are required", "error");
    return false;
  }
  try {
    const response = await fetch("/api/firmware/wifi-config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      logBox.textContent = formatApiError(data);
      showStatus(`Failed to save Wi-Fi settings: ${response.status}`, "error");
      return false;
    }
    wifiPasswordInput.value = data.password || requestBody.password || "";
    wifiPasswordInput.placeholder = "Enter Wi-Fi password";
    logBox.textContent = [
      "Wi-Fi settings saved.",
      `SSID: ${data.ssid}`,
      `Server URL: ${data.server_upload_url}`,
      `Device ID: ${data.device_id}`,
      `Password: ${data.password_set ? data.password || requestBody.password : "not set"}`,
      "",
      data.message,
    ].join("\n");
    showStatus("Wi-Fi settings saved", "success");
    return true;
  } catch (error) {
    showStatus(`Failed to save Wi-Fi settings: ${error.message}`, "error");
    logBox.textContent = String(error);
    return false;
  }
}

async function writeWifiFirmware() {
  const port = devicePortSelect.value || serialPortSelect.value;
  if (!port) {
    showStatus("Select an ESP32-S3 COM port first", "error");
    renderWifiFirmwareProgress("error", "Select an ESP32-S3 COM port first.");
    return;
  }
  const confirmed = window.confirm(
    `Save Wi-Fi settings and write capture firmware to ${port}?\n\nThis writes capture_upload firmware, not inference firmware.`
  );
  if (!confirmed) return;

  const writeButton = document.querySelector("#writeWifiFirmwareButton");
  writeButton.disabled = true;
  renderWifiFirmwareProgress("saving", "Saving Wi-Fi settings before writing.");
  const saved = await saveWifiConfig();
  if (!saved) {
    renderWifiFirmwareProgress("error", "Wi-Fi settings could not be saved.");
    writeButton.disabled = false;
    return;
  }
  showStatus(`Writing Wi-Fi capture firmware to ${port}...`, "info");
  renderWifiFirmwareProgress("writing", `Writing unified firmware to ${port}. Keep the ESP32-S3 connected.`);
  logBox.textContent = [
    "Writing capture_upload firmware.",
    "1. Save Wi-Fi settings",
    "2. Build capture_upload if needed",
    "3. Write bootloader, partition table, and capture_upload app",
    "",
    "Keep the ESP32-S3 connected.",
  ].join("\n");
  let verifyTimer = null;
  try {
    verifyTimer = setTimeout(() => {
      renderWifiFirmwareProgress("verifying", "Write is taking a while. Waiting for reset and camera URL detection.");
    }, 18000);
    const response = await fetch("/api/firmware/flash-selected", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ port, target: "capture_full", force_build: true }),
    });
    clearTimeout(verifyTimer);
    verifyTimer = null;
    const data = await response.json();
    if (!response.ok || !data.ok) {
      logBox.textContent = formatApiError(data);
      showStatus(`Wi-Fi firmware write failed: ${response.status}`, "error");
      renderWifiFirmwareProgress("error", `Write failed: HTTP ${response.status}`);
      return;
    }
    renderWifiFirmwareProgress("verifying", "Firmware written. Checking camera URL after reset.");
    const writtenFiles = (data.target?.files || [])
      .map((item) => `${item.address} ${item.relative_file}`)
      .join("\n");
    logBox.textContent = [
      "Wi-Fi firmware write completed.",
      `port: ${data.port || port}`,
      `target: ${data.target?.label || "Capture upload firmware full image"}`,
      `build: ${data.force_build ? "rebuilt before flash" : "used existing build"}`,
      data.camera?.found ? `camera: ${data.camera.url}` : "camera: IP not found in monitor output yet",
      "",
      "written files:",
      writtenFiles || "-",
      "",
      "After reset, ESP32-S3 will connect to the saved Wi-Fi and upload images to the saved server URL.",
    ].join("\n");
    showStatus(`Wrote Wi-Fi capture firmware to ${port}`, "success");
    renderWifiFirmwareProgress(
      "done",
      data.camera?.found ? `Write completed. Camera found: ${data.camera.url}` : "Write completed. Camera IP is still being detected."
    );
    await loadInferenceArtifacts();
    if (data.camera?.found && data.camera.url) {
      esp32BaseUrlInput.value = data.camera.url;
      localStorage.setItem("esp32BaseUrl", data.camera.url);
      openRemoteCamera(data.camera.url);
    } else {
      setTimeout(() => discoverRemoteCamera({ openAfterFound: true }), 3500);
    }
  } catch (error) {
    showStatus(`Wi-Fi firmware write failed: ${error.message}`, "error");
    logBox.textContent = String(error);
    renderWifiFirmwareProgress("error", `Write failed: ${error.message}`);
  } finally {
    if (verifyTimer) {
      clearTimeout(verifyTimer);
    }
    writeButton.disabled = false;
  }
}

function normalizedEsp32BaseUrl() {
  let value = esp32BaseUrlInput.value.trim();
  if (value.includes("[object PointerEvent]")) {
    esp32BaseUrlInput.value = "";
    value = "";
  }
  if (!value) {
    showStatus("Enter the ESP32-S3 URL first", "error");
    return "";
  }
  if (!/^https?:\/\//i.test(value)) {
    value = `http://${value}`;
  }
  return value.replace(/\/+$/, "");
}

async function discoverRemoteCamera(options = {}) {
  if (esp32BaseUrlInput.value.includes("[object PointerEvent]")) {
    esp32BaseUrlInput.value = "";
    localStorage.removeItem("esp32BaseUrl");
  }
  const { openAfterFound = false } = options;
  showStatus("Searching for ESP32-S3 camera URL...", "info");
  if (remoteCameraDialog.open) remoteCameraStatus.textContent = "Searching for camera...";
  const previousDisabled = discoverCameraButton.disabled;
  discoverCameraButton.disabled = true;
  try {
    const port = devicePortSelect.value || serialPortSelect.value;
    const cameraUrlEndpoint = port
      ? `/api/firmware/camera-url?port=${encodeURIComponent(port)}`
      : "/api/firmware/camera-url";
    const response = await fetch(cameraUrlEndpoint);
    const data = await response.json();
    if (!response.ok || !data.ok) {
      logBox.textContent = formatApiError(data);
      showStatus(`Camera discovery failed: ${response.status}`, "error");
      return "";
    }
    if (!data.found || !data.camera?.url) {
      const networks = (data.discovery?.networks || []).join(", ");
      const monitorSummary = (data.monitor_results || [])
        .map((item) => `${item.port}: ${item.result?.found ? item.result.url : "not found"}`)
        .join("\n");
      logBox.textContent = [
        data.message || "ESP32-S3 camera was not found.",
        `tried ports: ${(data.tried_ports || []).join(", ") || "-"}`,
        `scanned: ${networks || "-"}`,
        `checked hosts: ${data.discovery?.checked ?? 0}`,
        "",
        monitorSummary,
        "",
        "Make sure capture_upload is running and the ESP32-S3 is on the same Wi-Fi as this PC.",
      ].join("\n");
      showStatus("ESP32-S3 camera not found", "error");
      return "";
    }
    const baseUrl = data.camera.url;
    esp32BaseUrlInput.value = baseUrl;
    localStorage.setItem("esp32BaseUrl", baseUrl);
    logBox.textContent = [
      "ESP32-S3 camera URL found.",
      `URL: ${baseUrl}`,
      `source: ${data.source || "-"}`,
      `COM: ${data.port || "-"}`,
      `response: ${data.camera.response || "-"}`,
    ].join("\n");
    showStatus(`Found ESP32-S3 camera at ${baseUrl}`, "success");
    if (openAfterFound) openRemoteCamera(baseUrl);
    return baseUrl;
  } catch (error) {
    showStatus(`Camera discovery failed: ${error.message}`, "error");
    logBox.textContent = String(error);
    return "";
  } finally {
    discoverCameraButton.disabled = previousDisabled;
  }
}

function stopAiCameraLoop() {
  aiCameraRunning = false;
  if (aiCameraTimer) {
    clearTimeout(aiCameraTimer);
    aiCameraTimer = null;
  }
}

function updateInferenceDisplay(data, { overlay = false } = {}) {
  const scoreLines = Array.isArray(data.scores)
    ? data.scores.map((item) => `${item.label}: ${(Number(item.score) * 100).toFixed(1)}%`)
    : [];
  remoteCameraStatus.textContent = `Inference: ${data.label}`;
  if (overlay && remoteLabelOverlay) {
    const bestScore = Array.isArray(data.scores)
      ? data.scores.find((item) => item.label === data.label)?.score
      : null;
    const suffix = Number.isFinite(Number(bestScore)) ? ` ${(Number(bestScore) * 100).toFixed(1)}%` : "";
    remoteLabelOverlay.textContent = `${data.label}${suffix}`;
    remoteLabelOverlay.classList.add("active");
  }
}

async function requestRemoteInference(baseUrl, { pauseStream = true, overlay = false } = {}) {
  const streamUrl = `${baseUrl}/stream?t=${Date.now()}`;
  if (pauseStream) {
    remoteCameraStream.removeAttribute("src");
  }
  try {
    const response = await fetch(`${baseUrl}/infer?t=${Date.now()}`, { method: "GET", cache: "no-store" });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data?.error || data?.detail?.message || `HTTP ${response.status}`);
    }
    updateInferenceDisplay(data, { overlay });
    return data;
  } finally {
    if (pauseStream && remoteCameraDialog.open) {
      remoteCameraStream.src = streamUrl;
    }
  }
}

function scheduleAiCameraInference(baseUrl) {
  stopAiCameraLoop();
  aiCameraRunning = true;
  const run = async () => {
    if (!aiCameraRunning || !remoteCameraDialog.open) return;
    try {
      remoteLabelOverlay.textContent = "Infer...";
      await requestRemoteInference(baseUrl, { pauseStream: false, overlay: true });
    } catch (error) {
      remoteCameraStatus.textContent = `AI label failed: ${error.message}`;
      remoteLabelOverlay.textContent = "No inference";
      remoteLabelOverlay.classList.remove("active");
    } finally {
      if (aiCameraRunning && remoteCameraDialog.open) {
        aiCameraTimer = setTimeout(run, 2500);
      }
    }
  };
  run();
}

async function openRemoteCamera(baseUrlOverride = "", options = {}) {
  if (typeof baseUrlOverride !== "string") {
    baseUrlOverride = "";
  }
  let baseUrl = baseUrlOverride;
  if (!baseUrl && !esp32BaseUrlInput.value.trim()) {
    baseUrl = await discoverRemoteCamera({ openAfterFound: false });
  } else if (!baseUrl) {
    baseUrl = normalizedEsp32BaseUrl();
  }
  if (!baseUrl) return;
  localStorage.setItem("esp32BaseUrl", baseUrl);
  esp32BaseUrlInput.value = baseUrl;
  const aiMode = Boolean(options.aiMode);
  stopAiCameraLoop();
  remoteCameraStatus.textContent = aiMode ? "Opening AI camera..." : "Opening stream...";
  remoteLabelOverlay.textContent = aiMode ? "Infer..." : "";
  remoteLabelOverlay.classList.toggle("visible", aiMode);
  remoteLabelOverlay.classList.remove("active");
  remoteCameraStream.src = `${baseUrl}/stream?t=${Date.now()}`;
  remoteCameraDialog.showModal();
  if (aiMode) {
    scheduleAiCameraInference(baseUrl);
  }
}

function closeRemoteCamera() {
  stopAiCameraLoop();
  remoteCameraStream.removeAttribute("src");
  remoteCameraStatus.textContent = "Idle";
  remoteLabelOverlay.textContent = "";
  remoteLabelOverlay.classList.remove("visible", "active");
  remoteCameraDialog.close();
}

function triggerShutterFlash() {
  remoteShutterFlash.classList.remove("flash");
  void remoteShutterFlash.offsetWidth;
  remoteShutterFlash.classList.add("flash");
}

async function remoteCapture() {
  const baseUrl = normalizedEsp32BaseUrl();
  if (!baseUrl) return;
  const streamUrl = `${baseUrl}/stream?t=${Date.now()}`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 15000);
  remoteCaptureButton.disabled = true;
  remoteCameraStatus.textContent = "Capturing...";
  logBox.textContent = [
    "Remote capture requested.",
    `URL: ${baseUrl}/capture`,
    "Pausing stream while the ESP32-S3 captures and uploads.",
  ].join("\n");
  remoteCameraStream.removeAttribute("src");
  try {
    const response = await fetch("/api/firmware/remote-capture", {
      method: "POST",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ base_url: baseUrl }),
      signal: controller.signal,
    });
    const data = await response.json();
    if (!response.ok) {
      remoteCameraStatus.textContent = `Capture failed: ${response.status}`;
      logBox.textContent = formatApiError(data);
      return;
    }
    triggerShutterFlash();
    remoteCameraStatus.textContent = "Captured and uploaded. Refreshing images...";
    logBox.textContent = [
      "Remote capture completed.",
      `URL: ${data.url}`,
      `status: ${data.status}`,
      "",
      data.body || "",
    ].join("\n");
    setTimeout(loadImages, 1200);
  } catch (error) {
    const message = error.name === "AbortError" ? "request timed out" : error.message;
    remoteCameraStatus.textContent = `Capture failed: ${message}`;
    logBox.textContent = [
      "Remote capture failed.",
      "Check that capture_upload firmware is running, ESP32-S3 URL is correct, and the PC can reach the ESP32-S3 port.",
      "",
      String(error),
    ].join("\n");
  } finally {
    clearTimeout(timeoutId);
    remoteCaptureButton.disabled = false;
    if (remoteCameraDialog.open) {
      remoteCameraStream.src = streamUrl;
    }
  }
}

async function flashAiModelOnly() {
  const runId = selectedModelRunId();
  const port = serialPortSelect.value;
  if (!runId) return;
  if (!port) {
    showStatus("Select a COM port first", "error");
    return;
  }
  const confirmed = window.confirm(
    `Write only ai_model partition to ESP32-S3 on ${port}?\n\nrun_id: ${runId}\noffset: 0x310000\napp firmware will not be rewritten.`
  );
  if (!confirmed) return;
  showStatus(`Writing ai_model partition to ${port}...`, "info");
  renderFlashSteps("flashing");
  logBox.textContent = [
    "Model-only write started.",
    "The app firmware is not rewritten.",
    "Keep the ESP32-S3 connected.",
  ].join("\n");
  try {
    const response = await fetch(`/api/training/${encodeURIComponent(runId)}/flash-ai-model`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ port }),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      logBox.textContent = formatApiError(data);
      showStatus(`Model write failed: ${response.status}`, "error");
      return;
    }
    logBox.textContent = [
      "Model-only write completed.",
      `run_id: ${data.run_id}`,
      `port: ${data.port || port}`,
      `partition: ${data.partition}`,
      `offset: ${data.offset}`,
      `ai_model.bin: ${data.ai_model_size} bytes`,
      "",
      data.message || "AI model partition write completed.",
    ].join("\n");
    renderFlashSteps("done");
    showStatus(`Wrote ai_model partition to ${port}`, "success");
    await loadModels();
    modelSelect.value = runId;
  } catch (error) {
    showStatus(`Model write failed: ${error.message}`, "error");
    logBox.textContent = String(error);
  }
}

async function exportDataset() {
  const datasetName = document.querySelector("#datasetName").value;
  const imageSize = Number(document.querySelector("#imageSize").value);
  const response = await fetch("/api/datasets/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dataset_name: datasetName,
      train_ratio: 0.7,
      val_ratio: 0.2,
      test_ratio: 0.1,
      image_size: imageSize,
    }),
  });
  const data = await response.json();
  logBox.textContent = JSON.stringify(data, null, 2);
  if (data.ok) {
    document.querySelector("#datasetPath").value = data.dataset_path;
    await loadDatasets();
    datasetSelect.value = data.dataset_path;
  }
}

function stopTrainingPolling() {
  if (trainingPollTimer) {
    clearInterval(trainingPollTimer);
    trainingPollTimer = null;
  }
}

async function pollTrainingStatus(runId) {
  const response = await fetch(`/api/training/${runId}/status`);
  const data = await response.json();
  if (data.log_tail) {
    logBox.textContent = JSON.stringify(
      {
        run_id: runId,
        status: data.status,
        returncode: data.returncode,
        epoch: data.current_epoch && data.total_epochs ? `${data.current_epoch}/${data.total_epochs}` : null,
      },
      null,
      2
    ) + "\n\n" + data.log_tail;
  }
  if (data.current_epoch && data.total_epochs) {
    trainingProgress.textContent = `Training progress: epoch ${data.current_epoch}/${data.total_epochs}`;
    await loadTrainingHistory(runId);
  } else {
    trainingProgress.textContent = `Training progress: ${data.status}`;
  }
  if (data.status === "completed") {
    showStatus(`Training completed: ${runId}`, "success");
    trainingProgress.textContent = data.total_epochs
      ? `Training completed: epoch ${data.total_epochs}/${data.total_epochs}`
      : "Training completed";
    stopTrainingPolling();
    document.querySelector("#startTrainingButton").disabled = false;
    await loadModels();
    modelSelect.value = runId;
    await loadTrainingHistory(runId);
  } else if (data.status === "failed") {
    showStatus(`Training failed: ${runId}`, "error");
    stopTrainingPolling();
    document.querySelector("#startTrainingButton").disabled = false;
  }
}

async function startTraining() {
  const button = document.querySelector("#startTrainingButton");
  button.disabled = true;
  showStatus("Training started. This can take a while.", "info");
  logBox.textContent = "Starting training...";
  try {
    const response = await fetch("/api/training/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dataset_path: document.querySelector("#datasetPath").value,
        epochs: Number(document.querySelector("#epochs").value),
        batch_size: Number(document.querySelector("#batchSize").value),
        model_type: "tiny_cnn",
      }),
    });
    const data = await response.json();
    logBox.textContent = JSON.stringify(data, null, 2);
    if (!response.ok || !data.ok) {
      showStatus(`Training failed: ${data.detail || data.log_path || response.status}`, "error");
      button.disabled = false;
    } else {
      currentTrainingRunId = data.run_id;
      modelSelect.value = currentTrainingRunId;
      showStatus(`Training running: ${data.run_id}`, "info");
    }
    if (data.run_id) {
      stopTrainingPolling();
      await pollTrainingStatus(data.run_id);
      trainingPollTimer = setInterval(() => pollTrainingStatus(data.run_id), 2000);
    }
  } catch (error) {
    showStatus(`Training failed: ${error.message}`, "error");
    logBox.textContent = String(error);
    button.disabled = false;
  }
}

async function testReservedImages() {
  if (!currentTrainingRunId) {
    showStatus("Select a trained model first", "error");
    return;
  }
  showStatus("Testing dataset images...", "info");
  logBox.textContent = "Testing dataset images...";
  try {
    const datasetPath = document.querySelector("#datasetPath").value;
    const params = new URLSearchParams();
    if (datasetPath) params.set("dataset_path", datasetPath);
    const response = await fetch(`/api/training/${encodeURIComponent(currentTrainingRunId)}/test-dataset?${params.toString()}`, {
      method: "POST",
    });
    const data = await response.json();
    logBox.textContent = JSON.stringify(data, null, 2);
    if (!response.ok || !data.ok) {
      showStatus(`Dataset image test failed: ${response.status}`, "error");
      return;
    }
    renderTestResults(data);
    showStatus(`Dataset image test complete: ${data.checked_count} images predicted. Review the log.`, "success");
  } catch (error) {
    showStatus(`Dataset image test failed: ${error.message}`, "error");
    logBox.textContent = String(error);
  }
}

function renderTestResults(data) {
  const results = Array.isArray(data.results) ? data.results : [];
  if (!results.length) {
    testResults.innerHTML = `<div class="metaText">No test images found in review_test.</div>`;
    return;
  }
  testResults.innerHTML = results
    .map((result) => {
      const topPredictions = Array.isArray(result.predictions) ? result.predictions.slice(0, 4) : [];
      const predictionRows = topPredictions
        .map(
          (prediction) => `
            <div class="predictionRow">
              <span>${escapeHtml(prediction.label)}</span>
              <strong>${Math.round(Number(prediction.probability || 0) * 100)}%</strong>
            </div>
          `
        )
        .join("");
      return `
        <article class="testResultCard">
          <img src="/data/raw/${encodeURIComponent(result.filename)}" alt="${escapeHtml(result.filename)}">
          <div class="testResultBody">
            <div class="filename">${escapeHtml(result.filename)}</div>
            <div class="predictedLabel">${escapeHtml(result.predicted_label || "unknown")}</div>
            <div class="predictionList">${predictionRows}</div>
          </div>
        </article>
      `;
    })
    .join("");
}

document.querySelector("#refreshButton").addEventListener("click", loadImages);
document.querySelector("#nextButton").addEventListener("click", nextImage);
document.querySelector("#selectAllButton").addEventListener("click", selectAllVisible);
document.querySelector("#clearSelectionButton").addEventListener("click", clearSelection);
document.querySelector("#deleteUnknownButton").addEventListener("click", deleteUnknownImages);
document.querySelector("#downloadCsvButton").addEventListener("click", downloadMultilabelCsv);
document.querySelector("#exportDatasetButton").addEventListener("click", exportDataset);
document.querySelector("#startTrainingButton").addEventListener("click", startTraining);
document.querySelector("#testModelButton").addEventListener("click", testReservedImages);
document.querySelector("#prepareInferenceButton").addEventListener("click", prepareInferenceFirmware);
document.querySelector("#refreshPortsButton").addEventListener("click", loadSerialPorts);
document.querySelector("#flashAiModelButton").addEventListener("click", flashAiModelOnly);
document.querySelector("#saveWifiConfigButton").addEventListener("click", saveWifiConfig);
document.querySelector("#refreshDevicePortsButton").addEventListener("click", loadSerialPorts);
document.querySelector("#writeWifiFirmwareButton").addEventListener("click", writeWifiFirmware);
toggleWifiPasswordButton.addEventListener("click", () => {
  const isHidden = wifiPasswordInput.type === "password";
  wifiPasswordInput.type = isHidden ? "text" : "password";
  toggleWifiPasswordButton.textContent = isHidden ? "Hide password" : "Show password";
});
discoverCameraButton.addEventListener("click", () => discoverRemoteCamera({ openAfterFound: false }));
document.querySelector("#openRemoteCameraButton").addEventListener("click", () => openRemoteCamera());
openAiCameraButton.addEventListener("click", () => openRemoteCamera("", { aiMode: true }));
document.querySelector("#closeRemoteCameraButton").addEventListener("click", closeRemoteCamera);
remoteCaptureButton.addEventListener("click", remoteCapture);
remoteCameraDialog.addEventListener("close", () => {
  stopAiCameraLoop();
  remoteCameraStream.removeAttribute("src");
  remoteCameraStatus.textContent = "Idle";
  remoteLabelOverlay.textContent = "";
  remoteLabelOverlay.classList.remove("visible", "active");
});
devicePortSelect.addEventListener("change", () => {
  serialPortSelect.value = devicePortSelect.value;
});
serialPortSelect.addEventListener("change", () => {
  devicePortSelect.value = serialPortSelect.value;
});
datasetSelect.addEventListener("change", () => {
  if (datasetSelect.value) {
    document.querySelector("#datasetPath").value = datasetSelect.value;
  }
});
modelSelect.addEventListener("change", () => {
  currentTrainingRunId = modelSelect.value;
  const model = availableModels.find((item) => item.run_id === currentTrainingRunId);
  if (model?.dataset_path_relative) {
    document.querySelector("#datasetPath").value = model.dataset_path_relative;
    if ([...datasetSelect.options].some((option) => option.value === model.dataset_path_relative)) {
      datasetSelect.value = model.dataset_path_relative;
    }
  }
  loadTrainingHistory(currentTrainingRunId);
});
document.querySelector("#addLabelButton").addEventListener("click", createLabel);
deleteLabelButton.addEventListener("click", deleteSelectedLabel);
newLabelInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") createLabel();
});
statusFilter.addEventListener("change", loadImages);
labelFilter.addEventListener("change", loadImages);

document.addEventListener("keydown", (event) => {
  if (event.target.matches("input, select, textarea")) return;
  if (event.key === "1") setLabel("target");
  if (event.key === "2") setLabel("other");
  if (event.key === "u") setLabel("unknown");
  if (event.key === "n") nextImage();
});

loadLabels().then(loadImages);
loadDatasets();
loadModels();
loadSerialPorts();
loadWifiConfig();
loadWifiNetworks();
{
  const savedEsp32BaseUrl = localStorage.getItem("esp32BaseUrl") || "";
  if (savedEsp32BaseUrl.includes("[object PointerEvent]")) {
    localStorage.removeItem("esp32BaseUrl");
    esp32BaseUrlInput.value = "";
  } else {
    esp32BaseUrlInput.value = savedEsp32BaseUrl;
  }
}
renderFlashSteps("idle");
renderTrainingCharts([]);
