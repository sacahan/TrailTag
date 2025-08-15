const fs = require('fs');
const path = require('path');

function loadScript(filename) {
  const code = fs.readFileSync(path.resolve(__dirname, '..', filename), 'utf8');
  window.eval(code + '\n//# sourceURL=' + filename);
}

const testUtils = require('./test-utils');

describe('popup module', () => {
  beforeEach(() => {
    // minimal DOM required by popup.js
    document.body.innerHTML = `
      <div id="idle-view" class="view"></div>
      <div id="checking-view" class="view hidden"></div>
      <div id="analyzing-view" class="view hidden">
        <div class="progress-container"><div id="progress-bar" class="progress-bar"></div></div>
        <p id="phase-text"></p>
        <p id="progress-text"></p>
        <button id="cancel-btn"></button>
      </div>
      <div id="map-view" class="view hidden">
        <div id="map"></div>
        <div class="map-controls"><span id="locations-count"></span><button id="export-btn"></button></div>
      </div>
      <div id="error-view" class="view hidden"><p id="error-message"></p><button id="retry-btn"></button></div>
      <div id="status-badge"></div>
      <button id="analyze-btn"></button>
    `;

    // mock chrome APIs used by popup
    global.chrome = {
      id: 'test',
      runtime: {
        id: 'test',
        sendMessage: jest.fn((msg, cb) => { if (cb) cb({ success: true }); }),
        onMessage: {
          _listeners: [],
          addListener(fn) { this._listeners.push(fn); },
          // used by tests to dispatch messages to registered listeners
          dispatch(msg) { this._listeners.forEach(l => l(msg, { id: chrome.runtime.id || 'test' }, () => {})); }
  }
      },
      storage: {
        local: {
          set: jest.fn((obj, cb) => cb && cb()),
          get: jest.fn((k, cb) => cb({ trailtag_state: null }))
  },
  id: 'test'
      }
    };
    // mock tabs API used by utils.getCurrentVideoId
    global.chrome.tabs = {
      query: jest.fn((q, cb) => cb([{ url: 'https://www.youtube.com/watch?v=abcdEFGhijk' }]))
    };

    // stub external functions used in popup.js
    window.getCurrentVideoId = jest.fn(() => Promise.resolve('vid123'));
    window.getVideoLocations = jest.fn(() => Promise.resolve(null));
    window.submitAnalysis = jest.fn(() => Promise.resolve({ job_id: 'job1', cached: false, phase: null }));
    window.getJobStatus = jest.fn(() => Promise.resolve({ status: 'running', progress: 42, phase: 'metadata' }));
    window.initMap = jest.fn();
    window.addMarkersFromMapVisualization = jest.fn(() => 2);
  // stubs for export functionality
  window.generateGeoJSON = jest.fn((v) => ({ type: 'FeatureCollection', features: [] }));
  window.downloadGeoJSON = jest.fn(() => {});

    // load utils first to ensure functions exist
    const utilsCode = fs.readFileSync(path.resolve(__dirname, '..', 'utils.js'), 'utf8');
    window.eval(utilsCode + '\n//# sourceURL=utils.js');

  // make a test hook so popup.js can register its internal helpers into our test-utils
  window.__registerPopupTestingHelpers = (h) => { require('./test-utils').register(h); };

  // now load popup
  loadScript('popup.js');

    // attach spies BEFORE DOMContentLoaded so handlers registered on the event will call the spies
    try {
      if (typeof window.startAnalysis === 'function') jest.spyOn(window, 'startAnalysis');
    } catch (e) {}
    try {
      if (typeof window.stopEventListener === 'function') jest.spyOn(window, 'stopEventListener');
    } catch (e) {}
    try {
      if (typeof window.changeState === 'function') jest.spyOn(window, 'changeState');
    } catch (e) {}
    try {
      if (typeof window.exportGeoJSON === 'function') jest.spyOn(window, 'exportGeoJSON');
    } catch (e) {}
    try {
      if (typeof window.startPolling === 'function') jest.spyOn(window, 'startPolling');
    } catch (e) {}

    // simulate DOMContentLoaded so event handlers register and initializeApp runs
    document.dispatchEvent(new Event('DOMContentLoaded'));

  // popup.js will have registered its helpers via window.__registerPopupTestingHelpers
  });

  afterEach(() => {
    // clear any intervals
    if (window.pollingIntervalId) {
      clearInterval(window.pollingIntervalId);
      window.pollingIntervalId = null;
    }
    jest.restoreAllMocks();
  });

  test('changeState to ANALYZING updates progress and phase text', () => {
    // call changeState
    window.changeState('analyzing', { progress: 33.7, phase: 'metadata' });

    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const phaseText = document.getElementById('phase-text');

    expect(progressBar.style.width).toBe('33.7%');
    expect(progressText.textContent).toBe('34%');
    expect(phaseText.textContent).toBe('正在抓取影片資料...');
  });

  test('pollJobStatus handles completed status and calls handleJobCompleted', async () => {
    // spy on handleJobCompleted
    window.handleJobCompleted = jest.fn(() => Promise.resolve());
    window.getJobStatus = jest.fn(() => Promise.resolve({ status: 'completed' }));

    await window.pollJobStatus('job1');

    expect(window.handleJobCompleted).toHaveBeenCalled();
  });

  test('receiving sse_fallback starts polling', () => {
    const spy = jest.spyOn(window, 'startPolling');
    // set state to ANALYZING and matching jobId so popup handler will start polling
    testUtils.setState({ currentState: 'analyzing', jobId: 'job1' });
    // dispatch message via our mock
    chrome.runtime.onMessage.dispatch({ type: 'sse_fallback', jobId: 'job1', data: {} });
    expect(spy).toHaveBeenCalledWith('job1');
  });

  test('cancel button stops event listener and sets idle', () => {
    const stopSpy = jest.spyOn(window, 'stopEventListener');
    const changeSpy = jest.spyOn(window, 'changeState');

    const cancelBtn = document.getElementById('cancel-btn');
    cancelBtn.click();

    expect(stopSpy).toHaveBeenCalled();
    expect(changeSpy).toHaveBeenCalledWith('idle');
  });

  test('retry button triggers startAnalysis', () => {
  const startSpy = jest.spyOn(window, 'startAnalysis');
  const retryBtn = document.getElementById('retry-btn');
  // simulate click
  retryBtn.click();
  expect(startSpy).toHaveBeenCalled();
  });

  test('export button calls exportGeoJSON when map ready', () => {
    testUtils.setState({ mapVisualization: { routes: [] }, videoId: 'vid123' });
    const exportSpy = jest.spyOn(window, 'exportGeoJSON');
    const exportBtn = document.getElementById('export-btn');
    exportBtn.click();
    expect(exportSpy).toHaveBeenCalled();
  });
});
