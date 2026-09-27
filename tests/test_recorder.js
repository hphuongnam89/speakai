const { createWavRecorder } = require('../static/recorder.js');

if (!global.navigator || !global.navigator.mediaDevices?.getUserMedia) {
  console.warn('MediaRecorder not available in this environment. Skipping test.');
} else {
  test('recorder creates a non-empty Blob', async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const recorder = createWavRecorder(stream);
    const blob = await recorder.stop();
    expect(blob).toBeInstanceOf(Blob);
    expect(blob.size).toBeGreaterThan(1024);
  });
}
