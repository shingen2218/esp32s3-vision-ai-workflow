#pragma once

#include <stdint.h>

#include "esp_err.h"

#define CLASS_COUNT 2

typedef struct {
    float scores[CLASS_COUNT];
    int best_index;
} classification_result_t;

esp_err_t classifier_init(void);
esp_err_t classifier_run(const int8_t *input, classification_result_t *result);
