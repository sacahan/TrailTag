const fs = require('fs');
const path = require('path');

function loadScriptWithMockL(filename) {
  // minimal mock of Leaflet L
  global.L = {
    map: (id) => {
      const m = {
        setView: function() { return this; },
        on: function() {},
        fitBounds: function() {},
        addTo: function() { return this; }
      };
      return m;
    },
    tileLayer: () => ({ addTo: () => {} }),
    layerGroup: () => {
      const group = {
        _layers: [],
        addTo: function() { return this; },
        getLayers: function() { return this._layers; },
        clearLayers: function() { this._layers = []; },
        getBounds: function() { return [[25,121],[24,120]]; }
      };
      return group;
    },
    marker: (coords) => {
      const mk = {
        _coords: coords,
        addTo: function(layer) { if (layer && Array.isArray(layer._layers)) { layer._layers.push(this); } return this; },
        bindPopup: function(c) { this._popup = c; }
      };
      return mk;
    },
  };

  const code = fs.readFileSync(path.resolve(__dirname, '..', filename), 'utf8');
  window.eval(code + '\n//# sourceURL=' + filename);
}

describe('map module', () => {
  beforeAll(() => {
  // load utils first (createTimecodeUrl used by map)
  const fs = require('fs');
  const path = require('path');
  const utilsCode = fs.readFileSync(path.resolve(__dirname, '..', 'utils.js'), 'utf8');
  window.eval(utilsCode + '\n//# sourceURL=utils.js');

  loadScriptWithMockL('map.js');
  });

  test('initMap returns a map instance', () => {
    const m = window.initMap('map');
    expect(m).not.toBeNull();
  });

  test('addMarkersFromMapVisualization adds markers and returns count', () => {
    const mapVisualization = {
      routes: [
        { coordinates: [121.5, 25.03], location: 'A' },
        { coordinates: [120.7, 24.1], location: 'B', timecode: '00:02:00' }
      ]
    };

    const count = window.addMarkersFromMapVisualization(mapVisualization, 'vid123');
    expect(count).toBe(2);
  });
});
