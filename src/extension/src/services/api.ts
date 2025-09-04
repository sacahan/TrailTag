/**
 * TrailTag Chrome Extension API 服務模組
 *
 * 這是 Chrome 擴充功能的核心 API 通訊層，負責與 TrailTag 後端服務進行所有 HTTP 通訊。
 * 提供完整的 RESTful API 封裝、錯誤處理、重試機制和 Server-Sent Events 支援。
 *
 * 主要功能:
 *   - HTTP API 通訊: 封裝所有後端 API 呼叫
 *   - 重試機制: 智慧的指數退避重試策略
 *   - 即時通訊: Server-Sent Events (SSE) 支援
 *   - GeoJSON 處理: 地理資料格式轉換與下載
 *   - 設定管理: 多環境配置支援
 *
 * 技術特色:
 *   - TypeScript 類型安全: 完整的類型定義
 *   - 錯誤復原: 健全的網路錯誤處理
 *   - 效能優化: 適當的快取與批次處理
 *   - 跨環境支援: 開發、測試、正式環境適配
 *
 * 使用場景:
 *   - YouTube 影片分析請求
 *   - 任務狀態查詢與監控
 *   - 地理資料獲取與可視化
 *   - 即時進度追蹤
 *
 * 相依組件:
 *   - 後端 API: TrailTag FastAPI 服務
 *   - 瀏覽器 API: Fetch、EventSource、Blob
 *   - Chrome 擴充功能環境
 */

/* eslint-disable @typescript-eslint/no-explicit-any */

/**
 * 全域配置物件類型聲明
 *
 * 可由打包工具、測試環境或運行時動態注入的配置物件。
 * 支援 API 端點、重試參數等可配置項目。
 *
 * 配置項目:
 *   - API_BASE_URL: 後端 API 基礎 URL
 *   - FETCH_RETRIES: HTTP 請求重試次數
 *   - FETCH_BACKOFF_MS: 重試退避時間 (毫秒)
 */
declare const TRAILTAG_CONFIG: any;

/**
 * 嘗試從多種環境取得同步設定物件（先檢查全域常數，接著檢查 window/self）
 * @returns 設定物件或 null
 */
function getConfigSync(): any | null {
  // 如果在編譯/執行環境中有注入 TRAILTAG_CONFIG，直接回傳
  if (typeof TRAILTAG_CONFIG !== "undefined") return TRAILTAG_CONFIG;
  // 瀏覽器環境：window 可能含有設定
  if (typeof window !== "undefined" && (window as any).TRAILTAG_CONFIG)
    return (window as any).TRAILTAG_CONFIG;
  // WebWorker 或 ServiceWorker 環境：self 可能含有設定
  if (typeof self !== "undefined" && (self as any).TRAILTAG_CONFIG)
    return (self as any).TRAILTAG_CONFIG;
  // 未找到設定
  return null;
}

// 取得同步設定一次性快照
const _cfg = getConfigSync();
// API_BASE_URL 優先使用注入的設定，否則回退到本地開發預設值
export const API_BASE_URL =
  _cfg && _cfg.API_BASE_URL ? _cfg.API_BASE_URL : "http://localhost:8010";

/**
 * 具有智慧重試機制的 HTTP 請求封裝函式
 *
 * 這是所有 API 請求的底層基礎函式，提供健全的錯誤處理和重試邏輯。
 * 特別針對網路不穩定、服務暫時不可用等情況設計。
 *
 * 重試策略:
 *   - 可重試的錯誤: HTTP 5xx (伺服器錯誤) 和 429 (請求過於頻繁)
 *   - 指數退避: 每次重試間隔呈指數增長
 *   - 隨機抖動: 避免多個用戶端同時重試造成的雷鳴群問題
 *   - 最大重試限制: 防止無限重試浪費資源
 *
 * 錯誤處理:
 *   - 自動解析錯誤回應體以獲取除錯資訊
 *   - 保留 debug_id 用於問題追蹤
 *   - 不可重試的錯誤會立即拋出
 *   - 網路層錯誤會進行重試
 *
 * @param url - 完整的請求 URL
 * @param options - Fetch API 的請求選項
 * @param retries - 最大重試次數 (預設 2 次，總共最多 3 次請求)
 * @param backoffMs - 初始退避延遲時間 (毫秒，預設 500ms)
 *
 * @returns 成功的 Response 物件
 * @throws 最終失敗時拋出錯誤，包含狀態碼和錯誤訊息
 *
 * @example
 * ```typescript
 * // 基本使用
 * const response = await fetchWithRetry('https://api.example.com/data');
 *
 * // 自訂重試參數
 * const response = await fetchWithRetry(
 *   'https://api.example.com/data',
 *   { method: 'POST', body: JSON.stringify(data) },
 *   3,    // 最多重試 3 次
 *   1000  // 初始延遲 1 秒
 * );
 * ```
 */
export async function fetchWithRetry(
  url: string,
  options: RequestInit = {},
  retries = typeof TRAILTAG_CONFIG !== "undefined"
    ? TRAILTAG_CONFIG.FETCH_RETRIES
    : 2,
  backoffMs = typeof TRAILTAG_CONFIG !== "undefined"
    ? TRAILTAG_CONFIG.FETCH_BACKOFF_MS
    : 500,
): Promise<Response> {
  let attempt = 0;
  while (true) {
    try {
      // 確保 Accept header 包含 application/json，並保留呼叫者傳入的 headers
      options.headers = Object.assign(
        { Accept: "application/json" },
        options.headers || {},
      );
      const res = await fetch(url, options);
      // 若非成功回應且屬於可重試的錯誤（5xx 或 429），拋錯以觸發重試
      if (!res.ok) {
        // try to parse error body for debug id
        let bodyText = "";
        try {
          bodyText = await res.text();
        } catch (e) {}
        const err: any = new Error(
          `API error: ${res.status} ${res.statusText}`,
        );
        err.code = res.status;
        try {
          const parsed = bodyText ? JSON.parse(bodyText) : null;
          if (parsed && parsed.debug_id) err.debugId = parsed.debug_id;
          if (parsed && parsed.error) err.message = parsed.error;
        } catch (e) {
          /* ignore parse errors */
        }
        if ((res.status >= 500 && res.status < 600) || res.status === 429) {
          throw err; // retryable
        }
        throw err;
      }
      // 正常回傳 Response
      return res;
    } catch (err) {
      attempt += 1;
      // 超出重試次數就拋出最後錯誤
      if (attempt > retries) throw err;
      // 指數退避加上少量隨機抖動，避免 thundering herd
      const jitter = Math.floor(Math.random() * 200);
      const wait = backoffMs * Math.pow(2, attempt - 1) + jitter;
      // eslint-disable-next-line no-console
      console.warn(
        `Fetch attempt ${attempt} failed for ${url}, retrying in ${wait}ms`,
      );
      await new Promise((r) => setTimeout(r, wait));
    }
  }
}

/**
 * 向後端送出影片分析請求。
 *
 * 輸入：videoUrl（影片完整 URL）
 * 輸出：解析後的 JSON 回應內容或拋出錯誤
 */
export async function submitAnalysis(videoUrl: string): Promise<any> {
  try {
    const response = await fetchWithRetry(
      `${API_BASE_URL}/api/videos/analyze`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: videoUrl }),
      },
      2,
      500,
    );

    if (!response.ok) {
      // 非 2xx 直接視為錯誤
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }
    // 回傳解析過的 JSON 內容
    return await response.json();
  } catch (error) {
    // 記錄錯誤後再拋出，方便上層處理
    // eslint-disable-next-line no-console
    console.error("Submit analysis error:", error);
    throw error;
  }
}

/**
 * 查詢某 Job 的狀態
 *
 * 輸入：jobId
 * 回傳：API 的 JSON 回應
 */
export async function getJobStatus(jobId: string): Promise<any> {
  try {
    const response = await fetchWithRetry(
      `${API_BASE_URL}/api/jobs/${jobId}`,
      { method: "GET" },
      2,
      500,
    );
    if (!response.ok)
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    return await response.json();
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error("Get job status error:", error);
    throw error;
  }
}

/**
 * 以 videoId 查詢對應的 job 簡要狀態（如果沒有對應 job，API 會回傳 404）
 *
 * 輸入：videoId
 * 回傳：若存在則回傳 JSON（含 job_id / status / phase / progress / stats / error），若不存在回傳 null
 */
export async function getJobByVideo(videoId: string): Promise<any | null> {
  try {
    const response = await fetchWithRetry(
      `${API_BASE_URL}/api/videos/${videoId}/job`,
      { method: "GET" },
      2,
      500,
    );
    if (response.status === 404) return null;
    if (!response.ok)
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    return await response.json();
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error("Get job by video error:", error);
    throw error;
  }
}

/**
 * 取得影片的地點標註列表（如果不存在回傳 null）
 *
 * 輸入：videoId
 * 回傳：地點資料的 JSON 或 null（404 表示沒有資料）
 */
export async function getVideoLocations(videoId: string): Promise<any | null> {
  try {
    const response = await fetchWithRetry(
      `${API_BASE_URL}/api/videos/${videoId}/locations`,
      { method: "GET" },
      2,
      500,
    );
    // 若 API 回傳 404，代表尚無地點資料
    if (response.status === 404) return null;
    if (!response.ok)
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    return await response.json();
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error("Get video locations error:", error);
    throw error;
  }
}

/**
 * 使用 Server-Sent Events (EventSource) 連線到 job 的事件串流，並以 callbacks 回報事件
 *
 * callbacks 物件支援三個 callback：
 *  - onPhaseUpdate: 接收到階段更新時呼叫，參數為解析後的 JSON
 *  - onCompleted: 當 job 完成時呼叫，並會關閉 EventSource
 *  - onError: 發生錯誤時呼叫，參數為錯誤資訊物件
 *
 * 回傳一個物件，包含 close() 方法以手動關閉連線。
 */
export function connectToEventStream(
  jobId: string,
  callbacks: {
    onPhaseUpdate?: (d: any) => void;
    onCompleted?: (d: any) => void;
    onError?: (d: any) => void;
  },
) {
  const eventSource = new EventSource(
    `${API_BASE_URL}/api/jobs/${jobId}/stream`,
  );

  // 當收到階段更新事件時解析 JSON 並呼叫對應 callback
  eventSource.addEventListener("phase_update", (event: MessageEvent) => {
    try {
      callbacks.onPhaseUpdate?.(JSON.parse((event as any).data));
    } catch (error) {
      console.error("Parse phase_update error:", error);
    }
  });

  // job 完成後觸發 completed，解析完呼叫 callback 並關閉連線
  eventSource.addEventListener("completed", (event: MessageEvent) => {
    try {
      callbacks.onCompleted?.(JSON.parse((event as any).data));
      eventSource.close();
    } catch (error) {
      console.error("Parse completed error:", error);
    }
  });

  // 一般性的錯誤事件，嘗試解析錯誤內容並回報
  eventSource.addEventListener("error", (event: MessageEvent) => {
    try {
      const data = (event as any).data
        ? JSON.parse((event as any).data)
        : { message: "Unknown error" };
      callbacks.onError?.(data);
      eventSource.close();
    } catch (error) {
      console.error("Parse error event error:", error);
      callbacks.onError?.({ message: "Error parsing error event" });
    }
  });

  // 心跳訊號（可用於偵測連線活性）
  eventSource.addEventListener("heartbeat", () => {
    console.debug(">>> Heartbeat received");
  });

  // 當底層 EventSource 發生錯誤時的 fallback 處理
  eventSource.onerror = (error) => {
    console.error("EventSource error:", error);
    callbacks.onError?.({ message: "Connection error" });
    eventSource.close();
  };

  // 提供外部關閉連線的 API
  return { close: () => eventSource.close() };
}

// Minimal GeoJSON generation
/**
 * Route 型別描述地點項目，coordinates 以 [lat, lon] 儲存（注意：產生 GeoJSON 時會轉為 [lon, lat]）
 */
type Route = {
  coordinates?: [number, number];
  location?: string;
  description?: string;
  timecode?: string;
  tags?: string[];
  marker?: string;
};
/**
 * MapVisualization 包含多個 routes 以及可選的 video_id
 */
type MapVisualization = { routes: Route[]; video_id?: string };

/**
 * 將內部的地點資料轉換為簡易的 GeoJSON FeatureCollection
 * - 只會處理 coordinates 欄位為兩元素陣列的項目
 * - 將 coordinates 從 [lat, lon] 轉為 GeoJSON 所需的 [lon, lat]
 */
export function generateGeoJSON(mapVisualization: MapVisualization) {
  const features = (mapVisualization.routes || [])
    // 過濾出有效的 coordinates
    .filter(
      (route) =>
        Array.isArray(route.coordinates) && route.coordinates.length === 2,
    )
    .map((route) => {
      // 內部使用 [lat, lon]，但 GeoJSON 要求 [lon, lat]
      const [lat, lon] = route.coordinates as [number, number];
      return {
        type: "Feature",
        geometry: { type: "Point", coordinates: [lon, lat] },
        properties: {
          name: route.location,
          description: route.description || "",
          timecode: route.timecode || "",
          tags: route.tags || [],
          marker: route.marker || "default",
        },
      };
    });

  return {
    type: "FeatureCollection",
    features,
    // 將一些 metadata 放在 properties，包含原始 video_id 與產生時間
    properties: {
      video_id: mapVisualization.video_id,
      generated_at: new Date().toISOString(),
    },
  } as const;
}

/**
 * 將 GeoJSON 內容打包成檔案並觸發瀏覽器下載（使用 Blob 與 a 元素）
 */
export function downloadGeoJSON(geoJSON: any, videoId: string) {
  const blob = new Blob([JSON.stringify(geoJSON, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `trailtag-${videoId}.geojson`;
  a.click();
  // 釋放暫時的 URL
  URL.revokeObjectURL(url);
}
