#include "classifier.h"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <new>

#include "esp_check.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_partition.h"
#include "image_preprocess.h"
#include "tensorflow/lite/c/common.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/schema/schema_generated.h"

static const char *TAG = "classifier";

namespace {
constexpr size_t kTensorArenaSize = 700 * 1024;
constexpr esp_partition_subtype_t kModelPartitionSubtype = static_cast<esp_partition_subtype_t>(0x40);
constexpr char kModelPartitionLabel[] = "ai_model";
constexpr char kModelMagic[] = "AIMDL001";
constexpr uint32_t kModelPackageVersion = 1;
constexpr size_t kMaxLabelsTextBytes = 4096;

const tflite::Model *model = nullptr;
TfLiteTensor *input_tensor = nullptr;
TfLiteTensor *output_tensor = nullptr;
uint8_t *tensor_arena = nullptr;
tflite::MicroInterpreter *interpreter = nullptr;
alignas(tflite::MicroInterpreter) uint8_t interpreter_storage[sizeof(tflite::MicroInterpreter)];
const esp_partition_t *model_partition = nullptr;
const void *model_map_ptr = nullptr;
esp_partition_mmap_handle_t model_map_handle = 0;
size_t model_bytes = 0;
char labels_text[kMaxLabelsTextBytes] = {};
const char *labels[MAX_CLASS_COUNT] = {};
int label_count = 0;

typedef struct {
    char magic[8];
    uint32_t version;
    uint32_t header_size;
    uint32_t model_offset;
    uint32_t model_size;
    uint32_t labels_offset;
    uint32_t labels_size;
    uint32_t crc32;
} ai_model_header_t;

uint32_t crc32_update(uint32_t crc, const uint8_t *data, size_t len)
{
    crc = ~crc;
    for (size_t i = 0; i < len; ++i) {
        crc ^= data[i];
        for (int bit = 0; bit < 8; ++bit) {
            const uint32_t mask = -(crc & 1U);
            crc = (crc >> 1) ^ (0xEDB88320U & mask);
        }
    }
    return ~crc;
}

esp_err_t read_partition_crc(uint32_t offset, uint32_t size, uint32_t *crc)
{
    constexpr size_t kChunkSize = 4096;
    uint8_t buffer[kChunkSize];
    uint32_t value = 0;
    uint32_t remaining = size;
    uint32_t cursor = offset;
    while (remaining > 0) {
        const uint32_t chunk = std::min<uint32_t>(remaining, kChunkSize);
        esp_err_t err = esp_partition_read(model_partition, cursor, buffer, chunk);
        if (err != ESP_OK) {
            return err;
        }
        value = crc32_update(value, buffer, chunk);
        cursor += chunk;
        remaining -= chunk;
    }
    *crc = value;
    return ESP_OK;
}

void parse_labels(void)
{
    label_count = 0;
    char *cursor = labels_text;
    while (*cursor && label_count < MAX_CLASS_COUNT) {
        while (*cursor == '\r' || *cursor == '\n') {
            ++cursor;
        }
        if (!*cursor) {
            break;
        }
        labels[label_count++] = cursor;
        while (*cursor && *cursor != '\r' && *cursor != '\n') {
            ++cursor;
        }
        if (*cursor) {
            *cursor++ = '\0';
        }
    }
}

esp_err_t load_model_from_partition(void)
{
    model_partition = esp_partition_find_first(ESP_PARTITION_TYPE_DATA, kModelPartitionSubtype, kModelPartitionLabel);
    if (!model_partition) {
        ESP_LOGE(TAG, "partition '%s' was not found", kModelPartitionLabel);
        return ESP_ERR_NOT_FOUND;
    }

    ai_model_header_t header = {};
    ESP_RETURN_ON_ERROR(esp_partition_read(model_partition, 0, &header, sizeof(header)), TAG, "failed to read model header");
    if (std::memcmp(header.magic, kModelMagic, sizeof(header.magic)) != 0) {
        ESP_LOGE(TAG, "model package magic mismatch. Write ai_model.bin to partition '%s'", kModelPartitionLabel);
        return ESP_FAIL;
    }
    if (header.version != kModelPackageVersion) {
        ESP_LOGE(TAG, "model package version mismatch: %u", (unsigned int)header.version);
        return ESP_FAIL;
    }
    const uint32_t data_end = std::max(header.model_offset + header.model_size, header.labels_offset + header.labels_size);
    if (header.model_size == 0 || data_end > model_partition->size || header.labels_size >= kMaxLabelsTextBytes) {
        ESP_LOGE(TAG, "invalid model package layout");
        return ESP_FAIL;
    }

    uint32_t actual_crc = 0;
    ESP_RETURN_ON_ERROR(read_partition_crc(header.model_offset, data_end - header.model_offset, &actual_crc), TAG, "failed to verify model crc");
    if (actual_crc != header.crc32) {
        ESP_LOGE(TAG, "model crc mismatch: expected=0x%08x actual=0x%08x", (unsigned int)header.crc32, (unsigned int)actual_crc);
        return ESP_FAIL;
    }

    ESP_RETURN_ON_ERROR(
        esp_partition_mmap(model_partition, header.model_offset, header.model_size, ESP_PARTITION_MMAP_DATA, &model_map_ptr, &model_map_handle),
        TAG,
        "failed to mmap model");
    model_bytes = header.model_size;

    ESP_RETURN_ON_ERROR(
        esp_partition_read(model_partition, header.labels_offset, labels_text, header.labels_size),
        TAG,
        "failed to read labels");
    labels_text[header.labels_size] = '\0';
    parse_labels();
    if (label_count <= 0) {
        ESP_LOGE(TAG, "model package has no labels");
        return ESP_FAIL;
    }

    ESP_LOGI(TAG, "loaded model package: model=%u bytes labels=%d partition=%s", (unsigned int)model_bytes, label_count, kModelPartitionLabel);
    return ESP_OK;
}

float tensor_scale(const TfLiteTensor *tensor, float fallback)
{
    if (!tensor || tensor->params.scale <= 0.0f) {
        return fallback;
    }
    return tensor->params.scale;
}

int tensor_zero_point(const TfLiteTensor *tensor, int fallback)
{
    if (!tensor) {
        return fallback;
    }
    return tensor->params.zero_point;
}

float dequantize_output_value(int index)
{
    const float scale = tensor_scale(output_tensor, 1.0f);
    const int zero_point = tensor_zero_point(output_tensor, 0);
    if (output_tensor->type == kTfLiteInt8) {
        return ((int)output_tensor->data.int8[index] - zero_point) * scale;
    }
    if (output_tensor->type == kTfLiteUInt8) {
        return ((int)output_tensor->data.uint8[index] - zero_point) * scale;
    }
    if (output_tensor->type == kTfLiteFloat32) {
        return output_tensor->data.f[index];
    }
    return 0.0f;
}

int tensor_element_count(const TfLiteTensor *tensor)
{
    if (!tensor) {
        return 0;
    }
    switch (tensor->type) {
    case kTfLiteInt8:
        return tensor->bytes / sizeof(int8_t);
    case kTfLiteUInt8:
        return tensor->bytes / sizeof(uint8_t);
    case kTfLiteFloat32:
        return tensor->bytes / sizeof(float);
    default:
        return 0;
    }
}
}

esp_err_t classifier_init(void)
{
    ESP_RETURN_ON_ERROR(load_model_from_partition(), TAG, "model partition load failed");

    model = tflite::GetModel(static_cast<const unsigned char *>(model_map_ptr));
    if (model->version() != TFLITE_SCHEMA_VERSION) {
        ESP_LOGE(TAG, "model schema mismatch: model=%d runtime=%d", (int)model->version(), (int)TFLITE_SCHEMA_VERSION);
        return ESP_FAIL;
    }

    tensor_arena = static_cast<uint8_t *>(heap_caps_malloc(kTensorArenaSize, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    if (!tensor_arena) {
        tensor_arena = static_cast<uint8_t *>(heap_caps_malloc(kTensorArenaSize, MALLOC_CAP_8BIT));
    }
    if (!tensor_arena) {
        ESP_LOGE(TAG, "failed to allocate tensor arena (%u bytes)", (unsigned int)kTensorArenaSize);
        return ESP_ERR_NO_MEM;
    }

    static tflite::MicroMutableOpResolver<8> resolver;
    if (resolver.AddConv2D() != kTfLiteOk ||
        resolver.AddMaxPool2D() != kTfLiteOk ||
        resolver.AddMean() != kTfLiteOk ||
        resolver.AddFullyConnected() != kTfLiteOk ||
        resolver.AddSoftmax() != kTfLiteOk) {
        ESP_LOGE(TAG, "failed to register TFLite Micro operators");
        return ESP_FAIL;
    }

    interpreter = new (interpreter_storage) tflite::MicroInterpreter(
        model,
        resolver,
        tensor_arena,
        kTensorArenaSize);

    if (interpreter->AllocateTensors() != kTfLiteOk) {
        ESP_LOGE(TAG, "AllocateTensors failed");
        return ESP_FAIL;
    }

    input_tensor = interpreter->input(0);
    output_tensor = interpreter->output(0);
    if (!input_tensor || !output_tensor) {
        ESP_LOGE(TAG, "model input/output tensor not found");
        return ESP_FAIL;
    }
    if (input_tensor->type != kTfLiteInt8) {
        ESP_LOGE(TAG, "expected int8 input tensor, got type=%d", input_tensor->type);
        return ESP_FAIL;
    }
    const int output_count = tensor_element_count(output_tensor);
    if (output_count <= 0 || output_count > MAX_CLASS_COUNT) {
        ESP_LOGE(TAG, "unsupported output count: %d", output_count);
        return ESP_FAIL;
    }
    if (output_count != label_count) {
        ESP_LOGW(TAG, "label count (%d) differs from output count (%d); using output count", label_count, output_count);
    }

    ESP_LOGI(
        TAG,
        "model bytes=%u input scale=%.6f zero_point=%d output scale=%.6f zero_point=%d arena_used=%u",
        (unsigned int)model_bytes,
        classifier_input_scale(),
        classifier_input_zero_point(),
        tensor_scale(output_tensor, 1.0f),
        tensor_zero_point(output_tensor, 0),
        (unsigned int)interpreter->arena_used_bytes());
    return ESP_OK;
}

esp_err_t classifier_run(const int8_t *input, classification_result_t *result)
{
    if (!interpreter || !input_tensor || !output_tensor || !input || !result) {
        return ESP_ERR_INVALID_STATE;
    }

    const size_t expected_len = MODEL_INPUT_WIDTH * MODEL_INPUT_HEIGHT * MODEL_INPUT_CHANNELS;
    std::copy(input, input + expected_len, input_tensor->data.int8);

    if (interpreter->Invoke() != kTfLiteOk) {
        ESP_LOGE(TAG, "Invoke failed");
        return ESP_FAIL;
    }

    int best_index = 0;
    float best_score = -1.0f;
    const int output_count = std::min<int>(tensor_element_count(output_tensor), MAX_CLASS_COUNT);
    result->score_count = output_count;
    for (int i = 0; i < output_count; ++i) {
        const float score = dequantize_output_value(i);
        result->scores[i] = score;
        if (score > best_score) {
            best_score = score;
            best_index = i;
        }
    }
    result->best_index = best_index;
    return ESP_OK;
}

float classifier_input_scale(void)
{
    return tensor_scale(input_tensor, 1.0f);
}

int classifier_input_zero_point(void)
{
    return tensor_zero_point(input_tensor, -128);
}

int classifier_label_count(void)
{
    return label_count;
}

const char *classifier_label(int index)
{
    if (index < 0 || index >= label_count) {
        return "?";
    }
    return labels[index];
}
