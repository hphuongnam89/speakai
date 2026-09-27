const preflight = document.querySelector("#device-preflight");

// createWavRecorder is defined in static/recorder.js

if (preflight) {
  const micButton = preflight.querySelector("[data-mic-test]");
  const micStatus = preflight.querySelector("[data-mic-status]");
  const preview = preflight.querySelector("[data-mic-preview]");
  const confirmWrap = preflight.querySelector("[data-mic-confirm-wrap]");
  const confirmMic = preflight.querySelector("[data-mic-confirm]");
  const networkButton = preflight.querySelector("[data-network-test]");
  const networkStatus = preflight.querySelector("[data-network-status]");
  const startButton = preflight.querySelector("[data-start-button]");
  const gateStatus = preflight.querySelector("[data-gate-status]");
  let micVerified = false;
  let networkResult = null;
  let playbackEnded = false;
  let serverVerified = false;
  let savingVerification = false;
  let previewUrl;

  const persistVerification = async () => {
    if (savingVerification || serverVerified || !(micVerified && confirmMic.checked && networkResult)) return;
    savingVerification = true;
    gateStatus.textContent = "Đang xác nhận kết quả kiểm tra…";
    const complete = new FormData();
    complete.set("csrfmiddlewaretoken", preflight.querySelector("[name=csrfmiddlewaretoken]").value);
    complete.set("nonce", preflight.dataset.nonce);
    complete.set("mic_verified", "1");
    complete.set("playback_confirmed", "1");
    complete.set("speed_bps", String(networkResult.speedBps));
    complete.set("latency_ms", String(networkResult.latencyMs));
    try {
      const response = await fetch(preflight.dataset.completeUrl, { method: "POST", body: complete, cache: "no-store" });
      if (!response.ok) throw new Error("Không lưu được kết quả kiểm tra. Tải lại trang và thử lại.");
      serverVerified = true;
      gateStatus.textContent = "Thiết bị sẵn sàng. Bạn có thể bắt đầu bài luyện.";
    } catch (error) {
      gateStatus.textContent = error.message;
    } finally {
      savingVerification = false;
      syncGate();
    }
  };

  const syncGate = () => {
    startButton.disabled = !serverVerified;
    if (micVerified && confirmMic.checked && networkResult && !serverVerified) persistVerification();
  };

  micButton.addEventListener("click", async () => {
    micButton.disabled = true;
    playbackEnded = false;
    micVerified = false;
    confirmMic.checked = false;
    confirmMic.disabled = true;
    micStatus.textContent = "Đang xin quyền micro…";
    let stream;
    try {
      if (!navigator.mediaDevices?.getUserMedia || !(window.AudioContext || window.webkitAudioContext)) {
        throw new Error("Trình duyệt này chưa hỗ trợ ghi âm. Hãy dùng Safari hoặc Chrome phiên bản mới.");
      }
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = createWavRecorder(stream);
      const finish = async () => {
        stream.getTracks().forEach((track) => track.stop());
        const recording = await recorder.stop();
        if (recording.size < 1024) {
          micStatus.textContent = "Chưa thu được âm thanh. Kiểm tra đầu vào micro rồi thử lại.";
          micButton.disabled = false;
          return;
        }
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        previewUrl = URL.createObjectURL(recording);
        preview.src = previewUrl;
        preview.load();
        preview.hidden = false;
        confirmWrap.hidden = false;
        micStatus.textContent = "Đã ghi bản thử. Phát lại toàn bộ rồi xác nhận bạn nghe rõ.";
        micButton.textContent = "Ghi lại bản thử";
        micButton.disabled = false;
      };
      micStatus.textContent = "Hãy nói thử trong 3 giây…";
      window.setTimeout(finish, 3000);
    } catch (error) {
      stream?.getTracks().forEach((track) => track.stop());
      micStatus.textContent = error.name === "NotAllowedError"
        ? "Bạn chưa cấp quyền micro. Mở cài đặt trang web, cho phép Microphone rồi thử lại."
        : error.message || "Không thể mở micro. Kiểm tra thiết bị và thử lại.";
      micButton.disabled = false;
    }
  });

  preview.addEventListener("ended", () => {
    playbackEnded = true;
    confirmMic.disabled = false;
    micStatus.textContent = "Bản thử đã phát hết. Xác nhận nếu giọng nghe rõ.";
  });
  preview.addEventListener("error", () => {
    playbackEnded = false;
    confirmWrap.hidden = true;
    micStatus.textContent = "Bản ghi không phát được trên trình duyệt này. Hãy thử Chrome hoặc Safari mới nhất.";
  });
  confirmMic.addEventListener("change", () => {
    micVerified = playbackEnded && confirmMic.checked;
    if (micVerified) micStatus.textContent = "Đạt · micro đã ghi và phát lại bản thử.";
    syncGate();
  });

  networkButton.addEventListener("click", async () => {
    networkButton.disabled = true;
    networkStatus.textContent = "Đang đo tốc độ gửi/nhận…";
    networkResult = null;
    syncGate();
    const payload = new Uint8Array(256 * 1024);
    for (let offset = 0; offset < payload.length; offset += 65_536) {
      crypto.getRandomValues(payload.subarray(offset, offset + 65_536));
    }
    const csrfToken = preflight.querySelector("[name=csrfmiddlewaretoken]").value;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 12_000);
    try {
      const pingStarted = performance.now();
      const ping = await fetch(preflight.dataset.networkUrl, {
        method: "POST", headers: { "X-CSRFToken": csrfToken }, cache: "no-store", signal: controller.signal,
      });
      const latencyMs = Math.round(performance.now() - pingStarted);
      if (!ping.ok || latencyMs > 2000) throw new Error(`Độ trễ ${latencyMs} ms, yêu cầu không quá 2 giây. Thử lại gần bộ phát Wi-Fi.`);
      const started = performance.now();
      const response = await fetch(preflight.dataset.networkUrl, {
        method: "POST",
        headers: { "Content-Type": "application/octet-stream", "X-CSRFToken": csrfToken },
        body: payload,
        cache: "no-store",
        signal: controller.signal,
      });
      const echoed = await response.arrayBuffer();
      const elapsedMs = Math.max(1, performance.now() - started);
      const speedBps = Math.floor((payload.byteLength * 2 * 1000) / elapsedMs);
      if (!response.ok || echoed.byteLength !== payload.byteLength) throw new Error("Không nhận đủ dữ liệu kiểm tra.");
      if (speedBps < 32_768 || latencyMs > 2000) {
        throw new Error(`Kết nối chưa đạt ngưỡng (${Math.round(speedBps * 8 / 1000)} kbps, ${latencyMs} ms). Hãy kiểm tra Wi-Fi và thử lại.`);
      }
      networkResult = { speedBps, latencyMs };
      networkStatus.textContent = `Đạt · khoảng ${Math.round(speedBps * 8 / 1000)} kbps · ${latencyMs} ms.`;
      syncGate();
    } catch (error) {
      networkStatus.textContent = error.name === "AbortError"
        ? "Kiểm tra quá 12 giây chưa hoàn tất. Kiểm tra mạng và thử lại."
        : error.message || "Không kết nối được. Kiểm tra mạng rồi thử lại.";
    } finally {
      window.clearTimeout(timeout);
      networkButton.disabled = false;
    }
  });

  preflight.querySelector("[data-start-form]").addEventListener("submit", (event) => {
    if (!startButton.disabled) {
      startButton.disabled = true;
      startButton.textContent = "Đang tạo bài luyện…";
    } else {
      event.preventDefault();
    }
  });
}
