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
let trainingPollTimer = null;
let currentTrainingRunId = "";
let availableModels = [];

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
      option.textContent = `${model.run_id} / ${datasetName} / ${labels}`;
      modelSelect.appendChild(option);
    }
    if ([...modelSelect.options].some((option) => option.value === currentValue)) {
      modelSelect.value = currentValue;
    }
  } catch (error) {
    showStatus(`Failed to load models: ${error.message}`, "error");
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
renderTrainingCharts([]);
