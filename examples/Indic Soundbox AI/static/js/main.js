// — HTML ELEMENTS —
const recordBtn    = document.getElementById('recordBtn');
// const stopBtn      = document.getElementById('stopBtn'); // No longer used
const playBtn      = document.getElementById('playBtn');
const transcriptEl = document.getElementById('transcript');
const langEl       = document.getElementById('lang');
const botReplyEl   = document.getElementById('botReply');
const statusMsgEl  = document.getElementById('statusMessage');

// — New HTML ELEMENTS —
const micBtn = document.getElementById('micBtn');
const soundBarContainer = document.getElementById('soundBarContainer');
const responseAudioPlayer = document.getElementById('responseAudioPlayer');
const micIconSpan = micBtn.querySelector('.mic-icon'); // For changing icon

let mediaRecorder, audioChunks;
let currentAudioUrl = null;
let audioContext, analyser, microphone, javascriptNode, dataArray, bufferLength;
let silenceTimeout = null;
let hasDetectedSpeech = false; // To ensure we only trigger silence stop after speech
let isRecording = false;
let animationFrameId = null; // For controlling sound bar animation loop

const SPEAKING_THRESHOLD = 0.02; // Amplitude threshold (0 to 1), adjust as needed. Lower is more sensitive.
const SILENCE_DURATION = 1500;   // ms (1.5 seconds of silence to stop). Was 2000ms.
const NUM_SOUND_BARS = 20;       // Increased number of bars for a cooler look

// --- Sound Bar Initialization ---
function createSoundBars() {
    soundBarContainer.innerHTML = ''; // Clear existing bars
    for (let i = 0; i < NUM_SOUND_BARS; i++) {
        const bar = document.createElement('div');
        bar.classList.add('sound-bar');
        // bar.style.height = '5px'; // Initial height - now handled by CSS min-height
        soundBarContainer.appendChild(bar);
    }
}
createSoundBars(); // Initialize on load

function updateSoundBars() {
    if (!isRecording || !analyser) {
        // Reset bars to minimal height (as defined in CSS) if not recording or analyser not ready
        const bars = soundBarContainer.children;
        for (let i = 0; i < bars.length; i++) {
            bars[i].style.height = ''; // Reset to CSS defined min-height
        }
        if (animationFrameId) cancelAnimationFrame(animationFrameId);
        return;
    }

    analyser.getByteFrequencyData(dataArray); // Get frequency data

    const bars = soundBarContainer.children;
    const barCount = bars.length;
    // Ensure bufferLength is available. If not, it might be too early / VAD not fully init.
    if (!bufferLength) {
        if (animationFrameId) cancelAnimationFrame(animationFrameId);
        animationFrameId = requestAnimationFrame(updateSoundBars); 
        return;
    }
    const step = Math.floor(bufferLength / barCount);
    const maxBarHeight = 55; // Max height relative to container (60px height - 5px padding)
    const minBarHeight = 2;  // Min height (from CSS)

    for (let i = 0; i < barCount; i++) {
        const value = dataArray[i * step] || 0; // Get a sample from frequency data, default to 0 if undefined
        const percent = value / 255;
        // Ensure height is at least minBarHeight and respects maxBarHeight
        let height = Math.max(minBarHeight, percent * maxBarHeight);
        height = Math.min(height, maxBarHeight); 
        bars[i].style.height = `${height}px`;
    }
    animationFrameId = requestAnimationFrame(updateSoundBars);
}

function setStatus(message, isError = false) {
    console.log("[Status]:", message);
    statusMsgEl.textContent = message;
    statusMsgEl.style.color = isError ? '#ffdddd' : '#f0f0f0';
}

// Voice Activity Detection (VAD) related functions
function startVad(stream) {
    console.log("startVad: Initializing VAD");
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 256; // Smaller FFT size for faster response for visualization
    bufferLength = analyser.frequencyBinCount;
    dataArray = new Uint8Array(bufferLength);

    microphone = audioContext.createMediaStreamSource(stream);
    microphone.connect(analyser);

    const scriptProcessorBufferSize = 2048; // Can be 2048 or 4096
    javascriptNode = audioContext.createScriptProcessor(scriptProcessorBufferSize, 1, 1);
    analyser.connect(javascriptNode); // Connect analyser to script processor
    // javascriptNode.connect(audioContext.destination); // We don't need to play mic input back

    hasDetectedSpeech = false;
    clearTimeout(silenceTimeout);
    silenceTimeout = null;

    javascriptNode.onaudioprocess = function() {
        if (!isRecording) return;

        // For VAD: Use TimeDomainData for RMS (quieter calculation)
        const vadDataArray = new Uint8Array(analyser.fftSize); // Use fftSize for time domain
        analyser.getByteTimeDomainData(vadDataArray);
        let sumOfSquares = 0;
        for (let i = 0; i < vadDataArray.length; i++) {
            const normSample = (vadDataArray[i] / 128.0) - 1.0;
            sumOfSquares += normSample * normSample;
        }
        const rms = Math.sqrt(sumOfSquares / vadDataArray.length);

        if (rms > SPEAKING_THRESHOLD) {
            hasDetectedSpeech = true;
            clearTimeout(silenceTimeout);
            silenceTimeout = null;
        } else {
            if (hasDetectedSpeech && !silenceTimeout) {
                silenceTimeout = setTimeout(stopRecordingDueToSilence, SILENCE_DURATION);
            }
        }
    };
    // Start sound bar animation
    if (animationFrameId) cancelAnimationFrame(animationFrameId);
    animationFrameId = requestAnimationFrame(updateSoundBars);
}

function stopVad() {
    console.log("stopVad: Stopping VAD components");
    if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
    }
    createSoundBars(); // Reset sound bars visually

    if (javascriptNode) {
        javascriptNode.onaudioprocess = null;
        javascriptNode.disconnect();
        javascriptNode = null;
    }
    if (analyser) {
        analyser.disconnect();
        analyser = null;
    }
    if (microphone) {
        microphone.disconnect();
        microphone = null;
    }
    if (audioContext && audioContext.state !== 'closed') {
        audioContext.close().catch(e => console.warn("Error closing AudioContext:", e));
        audioContext = null;
    }
    clearTimeout(silenceTimeout);
    silenceTimeout = null;
    hasDetectedSpeech = false;
}

function stopRecordingDueToSilence() {
    console.log("stopRecordingDueToSilence: Silence threshold met");
    if (isRecording && mediaRecorder && mediaRecorder.state === "recording") {
        setStatus('Silence detected, processing...');
        mediaRecorder.stop(); // This will trigger the 'stop' event listener
        isRecording = false;
        stopVad(); // Clean up VAD components
        // recordBtn.disabled = true; // Already handled by mediaRecorder.onstop
    }
}

// Start recording
micBtn.onclick = async () => {
    console.log("micBtn.onclick: Button clicked. isRecording:", isRecording);

    // --- Interrupt ongoing TTS playback --- 
    if (responseAudioPlayer && !responseAudioPlayer.paused && responseAudioPlayer.duration > 0) {
        console.log("micBtn.onclick: Interrupting TTS playback.");
        responseAudioPlayer.pause();
        responseAudioPlayer.currentTime = 0; // Reset audio position
        responseAudioPlayer.src = ""; // Detach src to ensure it stops loading/playing
        
        // Manually trigger what onended would do, as we are interrupting
        setStatus("Interrupted. Click mic to start.");
        if (micBtn) micBtn.disabled = false; // Ensure mic button is re-enabled
        
        // If we were interrupting, and the next action is to start recording, 
        // we might want a brief pause or reset of VAD if it was active from previous stop
        if (isRecording) { // This case should ideally not happen if logic is clean
            console.warn("micBtn.onclick: Was already recording while trying to interrupt TTS. Resetting state.")
            if (mediaRecorder && mediaRecorder.state === "recording") {
                mediaRecorder.stop(); // This will trigger its own onstop, which calls stopVad
            } else {
                stopVad(); // Ensure VAD is stopped if mediaRecorder wasn't active
            }
            isRecording = false; // Force reset recording state
        } else {
            // If not currently recording (i.e. we clicked to stop TTS and start new recording)
            // ensure VAD is reset from any prior state before starting new recording.            
            stopVad(); // Clean up any VAD remnants from a previous session
        }
    }
    // --- End of interruption logic ---

    if (!isRecording) { // Start recording
        try {
            setStatus('Initializing...');
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];
            mediaRecorder.addEventListener('dataavailable', e => audioChunks.push(e.data));
            
            mediaRecorder.onstart = () => {
                console.log("mediaRecorder.onstart: Recording started");
                isRecording = true;
                micBtn.classList.add('listening');
                // micIconSpan.textContent = '◼'; // Or use CSS ::before content change
                setStatus('Listening...');
                startVad(stream);
            };

            mediaRecorder.onstop = async () => {
                console.log("mediaRecorder.onstop: Recording stopped. Processing...");
                isRecording = false;
                micBtn.classList.remove('listening');
                // micIconSpan.textContent = '🎤';
                micBtn.disabled = true; // Disable while processing
                stopVad();
                setStatus('Processing audio...');
                await processAudioPipeline();
            };

            mediaRecorder.onerror = (event) => {
                console.error('mediaRecorder.onerror:', event.error);
                setStatus(`Mic error: ${event.error.name}`, true);
                isRecording = false;
                stopVad();
                micBtn.classList.remove('listening');
                // micIconSpan.textContent = '🎤';
                micBtn.disabled = false;
            };
            
            mediaRecorder.start();

        } catch (err) {
            console.error('Error starting recording:', err);
            setStatus(`Mic access denied: ${err.message}`, true);
            alert(`Could not start recording: ${err.message}. Please ensure microphone access is allowed.`);
        }
    } else { // Stop recording (manual click)
        setStatus('Stopping recording...');
        if (mediaRecorder && mediaRecorder.state === "recording") {
            mediaRecorder.stop();
        }
        // VAD and button state will be reset by onstop handler
    }
};

// --- Audio Processing Pipeline (No Redirect) ---
async function processAudioPipeline() {
    let asrText = "";
    let langInfo = "hi-IN / Deva"; // Default
    let botText = "";
    let audioIdToPlay = null;

    try {
        console.log("processAudioPipeline: Starting. audioChunks length:", audioChunks.length);
        if (audioChunks.length === 0) {
            setStatus('No audio recorded. Try again.', true);
            micBtn.disabled = false;
            return;
        }

        const blob = new Blob(audioChunks, { type: 'audio/wav' });
        audioChunks = [];
        
        setStatus('Transcribing (ASR)...');
        asrText = await sendASR(blob);
        console.log("Pipeline: ASR text:", asrText);
        
        setStatus('Detecting language (LID)...');
        const lidResult = await sendLID(asrText || ""); 
        if (lidResult && lidResult.language_code) {
            langInfo = `${lidResult.language_code} / ${lidResult.script_code}`;
        } else {
            console.warn("LID failed or no lang_code, using default");
        }
        console.log("Pipeline: Lang info:", langInfo);
        const langCodeForTTS = lidResult && lidResult.language_code ? lidResult.language_code : 'hi';

        setStatus('Thinking (LLM)...');
        botText = await sendChat(asrText || "(No speech detected)"); 
        console.log("Pipeline: Bot text:", botText);

        setStatus('Synthesizing speech (TTS)...');
        const textForTTS = botText || "I didn't catch that, please try again.";
        const ttsResponse = await sendTTS(textForTTS, langCodeForTTS);
        
        if (ttsResponse && ttsResponse.audio_id) {
            audioIdToPlay = ttsResponse.audio_id;
            console.log("Pipeline: TTS successful, audio_id:", audioIdToPlay);
            setStatus('Playing response...');
            playResponseAudio(audioIdToPlay);
        } else {
            throw new Error("TTS did not return a valid audio ID.");
        }

    } catch (err) {
        console.error('Audio Pipeline Error:', err);
        setStatus(`Error: ${err.message}`, true);
    } finally {
        // Re-enable button unless audio is currently playing
        if (!responseAudioPlayer.duration || responseAudioPlayer.paused) {
             micBtn.disabled = false;
        }
        // If audioIdToPlay is null, it means we didn't even try to play, so ensure button is enabled.
        if (!audioIdToPlay) {
            micBtn.disabled = false;
            setStatus("Ready. Click mic to start."); // Reset status if an early error
        }
    }
}

function playResponseAudio(audioId) {
    responseAudioPlayer.src = `/get_audio/${audioId}`;
    responseAudioPlayer.play()
        .then(() => {
            console.log("Response audio playing.");
            setStatus("Speaking..."); // Indicate bot is speaking
        })
        .catch(error => {
            console.error("Error playing response audio:", error);
            setStatus("Error playing audio.", true);
            micBtn.disabled = false;
        });
}

// Event listener for when audio finishes playing
responseAudioPlayer.onended = () => {
    console.log("Response audio finished.");
    setStatus("Ready. Click mic to start.");
    micBtn.disabled = false;
};
responseAudioPlayer.onerror = () => {
    console.error("Audio player error event.");
    setStatus("Could not play audio response.", true);
    micBtn.disabled = false;
};

// —— API CALLS to Flask Backend (largely unchanged) ——

async function sendASR(wavBlob) {
    console.log("sendASR: Called with blob size:", wavBlob ? wavBlob.size : 'null blob');
    const form = new FormData();
    form.append('file', wavBlob, 'input.wav');
    try {
        const res = await fetch('/asr', { method: 'POST', body: form });
        const data = await res.json(); 
        if (!res.ok) throw new Error(`ASR failed (${res.status}): ${data.error || res.statusText}`);
        console.log("sendASR: Success, transcript:", data.transcript);
        return data.transcript;
    } catch (error) {
        console.error("sendASR Error:", error);
        throw error; 
    }
}

async function sendLID(text) {
    console.log("sendLID: Called with text length:", text ? text.length : 0);
    try {
        const res = await fetch('/lid', { 
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(`LID failed (${res.status}): ${data.error || res.statusText}`);
        console.log("sendLID: Success, data:", data);
        return data; 
    } catch (error) {
        console.error("sendLID Error:", error);
        // Return a default or null to allow pipeline to continue if LID is not critical
        return { language_code: 'hi', script_code: 'Deva' }; 
    }
}

async function sendChat(userText) {
    console.log("sendChat: Called with userText length:", userText ? userText.length : 0);
    try {
        const res = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: userText })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(`Chat failed (${res.status}): ${data.error || res.statusText}`);
        console.log("sendChat: Success, reply:", data.reply);
        return data.reply;
    } catch (error) {
        console.error("sendChat Error:", error);
        throw error;
    }
}

async function sendTTS(text, langCode) {
    console.log("sendTTS: Called with text length:", text ? text.length : 0, " langCode:", langCode);
    try {
        const res = await fetch('/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text, lang_code: langCode })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(`TTS failed (${res.status}): ${data.error || res.statusText}`);
        if (!data.audio_id) throw new Error("TTS response OK, but no audio_id.");
        console.log("sendTTS: Success, audio_id:", data.audio_id);
        return data; 
    } catch (error) {
        console.error("sendTTS Error:", error);
        throw error;
    }
}

// Initial status
setStatus("Click the microphone to start"); 