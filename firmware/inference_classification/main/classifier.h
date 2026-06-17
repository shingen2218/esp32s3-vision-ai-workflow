#pragma once

#include <stdint.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

#define MAX_CLASS_COUNT 32

typedef struct {
    float scores[MAX_CLASS_COUNT];
    int best_index;
    int score_count;
} classification_result_t;

esp_err_t classifier_init(void);
esp_err_t classifier_run(const int8_t *input, classification_result_t *result);
float classifier_input_scale(void);
int classifier_input_zero_point(void);
int classifier_label_count(void);
const char *classifier_label(int index);

#ifdef __cplusplus
}
#endif
