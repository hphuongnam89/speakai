const createWavRecorder = (stream) => {
  const mimeType = MediaRecorder.isTypeSupported('audio/wav')
    ? 'audio/wav'
    : MediaRecorder.isTypeSupported('audio/webm')
    ? 'audio/webm'
    : 'audio/ogg';

  const mediaRecorder = new MediaRecorder(stream, { mimeType });
  const chunks = [];
  mediaRecorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunks.push(e.data);
  };
  mediaRecorder.start(10); // start recording immediately

  return {
    async stop() {
      return new Promise((resolve) => {
        const handleStop = () => {
          mediaRecorder.removeEventListener('stop', handleStop);
          resolve(new Blob(chunks, { type: mimeType }));
        };
        mediaRecorder.addEventListener('stop', handleStop);
        mediaRecorder.stop();
      });
    },
  };
};

window.createWavRecorder = createWavRecorder;
