// Load utils into the jsdom environment
const fs = require('fs');
const path = require('path');

// load utils into window context
const code = fs.readFileSync(path.resolve(__dirname, '..', 'utils.js'), 'utf8');
window.eval(code + '\n//# sourceURL=utils.js');

describe('utils helpers', () => {
  test('extractVideoId from watch url', () => {
    expect(extractVideoId('https://www.youtube.com/watch?v=abcdEFGhijk')).toBe('abcdEFGhijk');
  });

  test('extractVideoId from short url', () => {
    expect(extractVideoId('https://youtu.be/abcdEFGhijk')).toBe('abcdEFGhijk');
  });

  test('isValidVideoId', () => {
    expect(isValidVideoId('abcdEFGhijk')).toBe(true);
    expect(isValidVideoId('invalid-id')).toBe(false);
  });

  test('formatTimecode hh:mm:ss', () => {
    expect(formatTimecode('01:02:03')).toBe('1:02:03');
  });

  test('formatTimecode mm:ss', () => {
    expect(formatTimecode('02:03')).toBe('2:03');
  });

  test('createTimecodeUrl converts to seconds', () => {
    expect(createTimecodeUrl('abcdEFGhijk', '01:02:03')).toContain('t=3723');
    expect(createTimecodeUrl('abcdEFGhijk', '02:03')).toContain('t=123');
  });
});
