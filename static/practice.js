const createWavRecorder = (stream) => {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  const context = new AudioContextClass();
  const source = context.createMediaStreamSource(stream);
  const processor = context.createScriptProcessor(4096, 1, 1);
  const samples = [];
  processor.onaudioprocess = (event) => {
    samples.push(new Float32Array(event.inputBuffer.getChannelData(0)));
    event.outputBuffer.getChannelData(0).fill(0);
  };
  source.connect(processor); processor.connect(context.destination);
  return { stop: async () => {
    const sampleRate = context.sampleRate;
    processor.disconnect(); source.disconnect(); await context.close();
    const length = samples.reduce((total, sample) => total + sample.length, 0);
    const buffer = new ArrayBuffer(44 + length * 2); const view = new DataView(buffer);
    const write = (offset, value) => [...value].forEach((char, index) => view.setUint8(offset + index, char.charCodeAt(0)));
    write(0, "RIFF"); view.setUint32(4, 36 + length * 2, true); write(8, "WAVE"); write(12, "fmt ");
    view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
    view.setUint32(24, sampleRate, true); view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true); view.setUint16(34, 16, true); write(36, "data"); view.setUint32(40, length * 2, true);
    let offset = 44;
    samples.forEach((sample) => sample.forEach((value) => {
      const clamped = Math.max(-1, Math.min(1, value));
      view.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true); offset += 2;
    }));
    return new Blob([buffer], { type: "audio/wav" });
  }};
};

document.querySelectorAll(".audio-record-form").forEach((form) => {
  const toggle = form.querySelector("[data-record-toggle]");
  const timer = form.querySelector("[data-record-timer]");
  const fileInput = form.querySelector("[data-audio-file]");
  const durationInput = form.querySelector("[data-duration]");
  const preview = form.querySelector("[data-preview]");
  const upload = form.querySelector("[data-upload]");
  const status = form.querySelector("[data-record-status]");
  let recorder;
  let stream;
  let startedAt = 0;
  let remaining = Number(form.dataset.maxSeconds);
  let ticker;
  let recordingActive = false;
  let stopRecording;

  const finishRecording = () => {
    if (recordingActive) stopRecording?.();
  };

  toggle.addEventListener("click", async () => {
    if (recordingActive) {
      finishRecording();
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia || !(window.AudioContext || window.webkitAudioContext)) {
      status.textContent = "Trình duyệt không hỗ trợ ghi âm. Hãy thử Chrome hoặc Safari mới nhất.";
      return;
    }
    try {
      preview.hidden = true;
      toggle.setAttribute("aria-pressed", "true");
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      recorder = createWavRecorder(stream);
      const finish = async () => {
        recordingActive = false;
        clearInterval(ticker);
        stream.getTracks().forEach((track) => track.stop());
        const duration = Math.max(1, Math.min(Number(form.dataset.maxSeconds), Math.ceil((Date.now() - startedAt) / 1000)));
        const blob = await recorder.stop();
        const extension = "wav";
        const audioFile = new File([blob], `answer.${extension}`, { type: blob.type });
        const transfer = new DataTransfer();
        transfer.items.add(audioFile);
        fileInput.files = transfer.files;
        durationInput.value = String(duration);
        preview.src = URL.createObjectURL(blob);
        preview.hidden = false;
        upload.disabled = false;
        toggle.disabled = false;
        toggle.setAttribute("aria-pressed", "false");
        toggle.textContent = "Ghi lại";
        timer.textContent = `${duration} giây đã ghi`;
        status.textContent = "Nghe thử bản ghi, sau đó chọn lưu câu trả lời.";
      };
      stopRecording = finish;
      recordingActive = true;
      startedAt = Date.now();
      remaining = Number(form.dataset.maxSeconds);
      toggle.textContent = "Dừng ghi âm";
      status.textContent = "Đang ghi âm…";
      ticker = setInterval(() => {
        remaining -= 1;
        timer.textContent = `${Math.max(remaining, 0)} giây còn lại`;
        if (remaining <= 0) finish();
      }, 1000);
    } catch (_error) {
      toggle.setAttribute("aria-pressed", "false");
      stream?.getTracks().forEach((track) => track.stop());
      status.textContent = "Không truy cập được micro. Hãy cấp quyền Microphone cho trang localhost rồi thử lại.";
    }
  });

  form.addEventListener("submit", () => {
    if (upload.disabled) return;
    upload.disabled = true;
    upload.textContent = "Đang lưu bản ghi…";
    status.textContent = "Đang tải bản ghi lên. Không đóng trang trong lúc lưu.";
  });
});

const createForm = document.querySelector("#practice-create-form");
createForm?.addEventListener("submit", () => {
  const button = createForm.querySelector("#practice-create-button");
  button.disabled = true;
  button.textContent = "Local AI đang tạo câu hỏi…";
});
