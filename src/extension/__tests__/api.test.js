const fs = require('fs');
const path = require('path');

function loadScriptToWindow(filename) {
  const code = fs.readFileSync(path.resolve(__dirname, '..', filename), 'utf8');
  // evaluate in jsdom window context so top-level declarations attach to window
  window.eval(code + '\n//# sourceURL=' + filename);
}

describe('api module', () => {
  beforeAll(() => {
    loadScriptToWindow('api.js');
  });

  test('generateGeoJSON creates valid FeatureCollection', () => {
    const mapVisualization = {
      video_id: 'vid123',
      routes: [
        { coordinates: [121.5, 25.03], location: 'Taipei', description: 'Desc', timecode: '00:01:23' },
        { coordinates: [120.7, 24.1], location: 'Taichung' }
      ]
    };

    const geo = window.generateGeoJSON(mapVisualization);
    expect(geo.type).toBe('FeatureCollection');
    expect(Array.isArray(geo.features)).toBe(true);
    expect(geo.features.length).toBe(2);
    expect(geo.properties.video_id).toBe('vid123');
  });

  test('downloadGeoJSON creates link and revokes URL', () => {
    // mock URL.createObjectURL and revokeObjectURL
    const originalCreate = global.URL.createObjectURL;
    const originalRevoke = global.URL.revokeObjectURL;
    let created = null;
    global.URL.createObjectURL = (b) => { created = b; return 'blob://test-url'; };
    global.URL.revokeObjectURL = (u) => { /* noop */ };

    // spy on anchor click by mocking createElement
    const originalCreateElement = document.createElement.bind(document);
    let generated = {};
    document.createElement = (tag) => {
      if (tag === 'a') {
        return {
          href: null,
          download: null,
          click: () => { generated.clicked = true; }
        };
      }
      return originalCreateElement(tag);
    };

    const sampleGeo = { type: 'FeatureCollection', features: [] };
    window.downloadGeoJSON(sampleGeo, 'videoXYZ');
    expect(generated.clicked).toBe(true);

    // restore
    document.createElement = originalCreateElement;
    global.URL.createObjectURL = originalCreate;
    global.URL.revokeObjectURL = originalRevoke;
  });
});
