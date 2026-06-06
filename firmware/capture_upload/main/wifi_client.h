#pragma once

#include "esp_err.h"

esp_err_t wifi_connect_sta(const char *ssid, const char *password);
