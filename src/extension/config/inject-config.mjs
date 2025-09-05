#!/usr/bin/env node

/**
 * TrailTag 環境變數配置注入腳本
 *
 * 此腳本用於在建制時將環境變數注入到 JavaScript 代碼中，
 * 生成包含運行時配置的檔案，供擴充功能在執行時使用。
 *
 * 功能:
 *   - 讀取環境變數並生成配置物件
 *   - 支援預設值回退機制
 *   - 生成 TypeScript 相容的配置檔案
 *   - 提供建制時的配置驗證
 *
 * 使用方式:
 *   node config/inject-config.mjs [output-path]
 *
 * 環境變數:
 *   - TRAILTAG_API_BASE_URL: API 服務基礎 URL
 *   - TRAILTAG_FETCH_RETRIES: HTTP 請求重試次數
 *   - TRAILTAG_FETCH_BACKOFF_MS: 重試退避時間(毫秒)
 *   - TRAILTAG_MAX_RECONNECT: SSE 最大重連次數
 *   - TRAILTAG_POLLING_INTERVAL_MS: 輪詢間隔(毫秒)
 *   - TRAILTAG_KEEPALIVE_MS: Keep-alive 時間(毫秒)
 *   - TRAILTAG_STATE_TTL_MS: 狀態 TTL 時間(毫秒)
 */

import fs from "fs";
import path from "path";

/**
 * 預設配置值
 * 當環境變數未設定時使用這些預設值
 */
const DEFAULT_CONFIG = {
  API_BASE_URL: "http://localhost:8010",
  FETCH_RETRIES: 2,
  FETCH_BACKOFF_MS: 500,
  MAX_RECONNECT: 1,
  POLLING_INTERVAL_MS: 5000,
  KEEPALIVE_MS: 30000,
  STATE_TTL_MS: 30 * 60 * 1000, // 30 分鐘
};

/**
 * 環境變數映射表
 * 將環境變數名稱映射到配置鍵名
 */
const ENV_VAR_MAPPING = {
  TRAILTAG_API_BASE_URL: "API_BASE_URL",
  TRAILTAG_FETCH_RETRIES: "FETCH_RETRIES",
  TRAILTAG_FETCH_BACKOFF_MS: "FETCH_BACKOFF_MS",
  TRAILTAG_MAX_RECONNECT: "MAX_RECONNECT",
  TRAILTAG_POLLING_INTERVAL_MS: "POLLING_INTERVAL_MS",
  TRAILTAG_KEEPALIVE_MS: "KEEPALIVE_MS",
  TRAILTAG_STATE_TTL_MS: "STATE_TTL_MS",
};

/**
 * 解析環境變數值
 * @param {string} value - 環境變數原始值
 * @param {string} key - 配置鍵名
 * @returns {string|number} 解析後的值
 */
function parseEnvValue(value, key) {
  // URL 類型保持字串
  if (key === "API_BASE_URL") {
    return value;
  }

  // 數值類型轉換為整數
  const numValue = parseInt(value, 10);
  if (!isNaN(numValue)) {
    return numValue;
  }

  // 無法解析時回傳原始值
  console.warn(`警告: 無法解析環境變數 ${key}=${value}，將使用原始字串值`);
  return value;
}

/**
 * 從環境變數構建配置物件
 * @returns {Object} 最終配置物件
 */
function buildConfig() {
  const config = { ...DEFAULT_CONFIG };

  // 遍歷所有環境變數映射
  for (const [envVar, configKey] of Object.entries(ENV_VAR_MAPPING)) {
    const envValue = process.env[envVar];
    if (envValue !== undefined && envValue !== "") {
      config[configKey] = parseEnvValue(envValue, configKey);
      console.log(
        `✓ 使用環境變數 ${envVar}=${envValue} -> ${configKey}=${config[configKey]}`,
      );
    } else {
      console.log(`ℹ 使用預設值 ${configKey}=${config[configKey]}`);
    }
  }

  return config;
}

/**
 * 生成配置 JavaScript 檔案內容
 * @param {Object} config - 配置物件
 * @returns {string} JavaScript 檔案內容
 */
function generateConfigFile(config) {
  return `/**
 * TrailTag 運行時配置
 *
 * 此檔案由 inject-config.mjs 在建制時自動生成
 * 請勿手動修改此檔案
 *
 * 生成時間: ${new Date().toISOString()}
 */

// ES module 格式的配置匯出
const TRAILTAG_CONFIG = ${JSON.stringify(config, null, 2)};

// 全域配置物件，供 api.ts 和其他模組使用
if (typeof window !== 'undefined') {
  window.TRAILTAG_CONFIG = TRAILTAG_CONFIG;
}

// 同時將配置掛載到 globalThis，支援 Worker 環境
if (typeof globalThis !== 'undefined') {
  globalThis.TRAILTAG_CONFIG = TRAILTAG_CONFIG;
}

// 如果在 ServiceWorker 環境中，將配置掛載到 self
if (typeof self !== 'undefined' && typeof window === 'undefined') {
  self.TRAILTAG_CONFIG = TRAILTAG_CONFIG;
}

export default TRAILTAG_CONFIG;
`;
}

/**
 * 主要執行函式
 */
function main() {
  const args = process.argv.slice(2);
  const outputPath =
    args[0] || path.join(process.cwd(), "dist_ts", "config.mjs");

  try {
    console.log("🔧 開始注入 TrailTag 配置...");

    // 構建配置
    const config = buildConfig();

    // 生成檔案內容
    const content = generateConfigFile(config);

    // 確保輸出目錄存在
    const outputDir = path.dirname(outputPath);
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
      console.log(`📁 創建輸出目錄: ${outputDir}`);
    }

    // 寫入檔案
    fs.writeFileSync(outputPath, content, "utf8");

    console.log(`✅ 配置已成功注入到: ${outputPath}`);
    console.log("📋 最終配置:");
    console.log(JSON.stringify(config, null, 2));
  } catch (error) {
    console.error("❌ 配置注入失敗:", error.message);
    process.exit(1);
  }
}

// 執行主函式
main();
