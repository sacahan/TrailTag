const fs = require('fs');
const path = require('path');
// Provide minimal Leaflet mock
global.L = {
    map: (id) => ({ setView: () => ({}) }),
    tileLayer: () => ({ addTo: () => { } }),
    featureGroup: () => ({ addTo: () => { }, clearLayers: () => { }, getLayers: () => [], getBounds: () => null }),
    layerGroup: () => ({ addTo: () => { }, clearLayers: () => { }, getLayers: () => [], getBounds: () => null }),
    divIcon: (opts) => ({ ...opts }),
    marker: (coords, opts) => ({ bindPopup: () => { }, addTo: () => { }, on: () => { }, getLatLng: () => ({ lat: coords[0], lng: coords[1] }) })
};
// require compiled map.js from dist_ts (try multiple candidate locations)
function findCompiled(...parts) {
    const candidates = [path.resolve(__dirname, '..', 'dist_ts', ...parts), path.resolve(__dirname, '..', '..', 'dist_ts', ...parts), path.resolve(__dirname, '..', ...parts)];
    for (const c of candidates) {
        if (fs.existsSync(c))
            return c;
    }
    throw new Error('compiled file not found: ' + parts.join('/'));
}
const srcMap = findCompiled('map.js');
const mod = require(srcMap);
// expose named export to global for tests
global.addMarkersFromMapVisualization = mod.addMarkersFromMapVisualization || (mod.default && mod.default.addMarkersFromMapVisualization);
describe('map.addMarkersFromMapVisualization edge cases', () => {
    test('ignores invalid routes and returns 0 markers', () => {
        const result = addMarkersFromMapVisualization({ routes: [null, { coordinates: [999, 200] }, { coordinates: ['a', 'b'] }] }, null);
        expect(result).toBe(0);
    });
});
export {};
