import defaults from './config.mjs';

// bootstrap module for popup: resolve config and load legacy scripts in order
(async function bootstrap() {
  const resolved = Object.assign({}, defaults);

  try {
    // try to read from chrome.storage.local
    const storage = await new Promise((resolve) => {
      try {
        chrome.storage.local.get(['trailtag_config', 'api_base_url'], (res) => resolve(res || {}));
      } catch (e) {
        resolve({});
      }
    });

    if (storage) {
      if (storage.trailtag_config && typeof storage.trailtag_config === 'object') {
        Object.assign(resolved, storage.trailtag_config);
      }
      if (storage.api_base_url) resolved.API_BASE_URL = storage.api_base_url;
    }
  } catch (e) {
    // ignore
  }

  // expose global snapshot for legacy scripts & tests
  window.TRAILTAG_CONFIG = resolved;

  // dynamically inject legacy non-module scripts in order
  const scripts = ['utils.js','api.js','map.js','popup.js'];
  for (const s of scripts) {
    await new Promise((resolve, reject) => {
      const el = document.createElement('script');
      el.src = s;
      el.onload = () => resolve();
      el.onerror = (err) => reject(err);
      document.body.appendChild(el);
    });
  }

})();
