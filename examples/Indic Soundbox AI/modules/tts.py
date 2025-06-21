import os
import base64
import wave
import io
import requests
import re # Added for regex cleaning
from dotenv import load_dotenv

load_dotenv()

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
TTS_CHARACTER_LIMIT = 1500 # As per Sarvam API documentation
MIN_TEXT_LENGTH_FOR_FORCED_TWO_WAY_SPLIT = 20 # Chars, don't split very short texts forcibly

def _clean_text_for_tts(text_input):
    """Cleans text by removing common markdown, multiple spaces, and emojis."""
    if not text_input:
        return ""

    # Remove common markdown (asterisks for bold/italics, hashes for headers)
    # Remove *bold*, **italic**, ***bolditalic***
    cleaned_text = re.sub(r'\*\*\*(.*?)\*\*\*', r'\1', text_input) # Must be first for ***
    cleaned_text = re.sub(r'\*\*(.*?)\*\*', r'\1', cleaned_text)   # Then **
    cleaned_text = re.sub(r'\*(.*?)\*', r'\1', cleaned_text)       # Then *
    # Remove #, ##, ### headers
    cleaned_text = re.sub(r'^#+\s*', '', cleaned_text, flags=re.MULTILINE) 

    # Remove emojis (this is a basic range, more comprehensive regex is possible but larger)
    # Basic BMP emoji pattern
    emoji_pattern = re.compile("["
                               u"\U0001F600-\U0001F64F"  # emoticons
                               u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                               u"\U0001F680-\U0001F6FF"  # transport & map symbols
                               u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                               u"\u2600-\u26FF"          # miscellaneous symbols
                               u"\u2700-\u27BF"          # dingbats
                               u"\uFE0F"                # variation selector
                               u"\U0001F900-\U0001F9FF"  # supplemental symbols and pictographs
                               "]+", flags=re.UNICODE)
    cleaned_text = emoji_pattern.sub(r'', cleaned_text)

    # Replace multiple spaces with a single space
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()

    # Specific known artifacts like "```" for code blocks (optional, can be expanded)
    cleaned_text = cleaned_text.replace('```', '')

    print(f"[modules/tts.py] _clean_text_for_tts: Original (len {len(text_input)}): '{text_input[:100]}...', Cleaned (len {len(cleaned_text)}): '{cleaned_text[:100]}...'")
    return cleaned_text

def _call_sarvam_tts(text_chunk, lang_code, speaker='meera', model='bulbul:v1'):
    """Helper function to call Sarvam TTS API for a single text chunk."""
    print(f"[modules/tts.py] _call_sarvam_tts: Calling API for chunk (length: {len(text_chunk)}): '{text_chunk[:100]}...'")
    if not SARVAM_API_KEY:
        print("[modules/tts.py] _call_sarvam_tts: Error - SARVAM_API_KEY not found.")
        raise ValueError("SARVAM_API_KEY not found for TTS call.")

    headers = {
        'api-subscription-key': SARVAM_API_KEY,
        'Content-Type': 'application/json'
    }
    payload = {
        'text': text_chunk,
        'target_language_code': lang_code,
        'speaker': speaker,
        'model': model
    }

    response = requests.post('https://api.sarvam.ai/text-to-speech', json=payload, headers=headers)

    if not response.ok:
        error_msg = f"Sarvam TTS API request failed for chunk with status {response.status_code}: {response.text}"
        print(f"[modules/tts.py] _call_sarvam_tts: {error_msg}")
        raise Exception(error_msg)
    
    json_response = response.json()
    if not json_response.get('audios') or not json_response['audios'][0]:
        error_msg = "Sarvam TTS API response OK, but no audio data found in 'audios' list."
        print(f"[modules/tts.py] _call_sarvam_tts: {error_msg}")
        raise Exception(error_msg)

    base64_audio_for_chunk = json_response['audios'][0]
    
    if not base64_audio_for_chunk or len(base64_audio_for_chunk) < 100: # Arbitrary short length check
        error_msg = f"Sarvam TTS API returned what seems to be invalid or too short base64 audio data: {base64_audio_for_chunk[:100]}..."
        print(f"[modules/tts.py] _call_sarvam_tts: {error_msg}")
        raise Exception(error_msg)
        
    print(f"[modules/tts.py] _call_sarvam_tts: Successfully received audio for chunk. Base64 length: {len(base64_audio_for_chunk)}")
    return base64_audio_for_chunk

def _chunk_text_boundary_aware(text, max_length):
    """Chunks text, trying to respect sentence/word boundaries."""
    chunks = []
    current_pos = 0
    text_len = len(text)

    while current_pos < text_len:
        # If remaining text is within limit, it's the last chunk
        if text_len - current_pos <= max_length:
            chunks.append(text[current_pos:])
            break
        
        # Determine potential split point at max_length
        split_at = current_pos + max_length
        best_split_point = split_at # Default to hard split if no boundary found

        # Try to find sentence boundaries (e.g., . ! ? followed by a space or end of string)
        # Search backwards from split_at
        sentence_delimiters = ['. ', '! ', '? ', '\n'] # Added newline as a potential break
        found_sentence_split = -1
        for delim in sentence_delimiters:
            # Search for the delimiter within the current segment to be chunked
            # Adjust search range to be from current_pos up to split_at
            last_occurrence = text.rfind(delim, current_pos, split_at)
            if last_occurrence != -1:
                # Point to split *after* the delimiter
                potential_split = last_occurrence + len(delim)
                if potential_split > found_sentence_split: # Take the latest occurring delimiter
                    found_sentence_split = potential_split
        
        if found_sentence_split > current_pos: # Ensure we are making progress
            best_split_point = found_sentence_split
        else:
            # If no sentence boundary, try word boundary (space) backwards from split_at
            last_space = text.rfind(' ', current_pos, split_at)
            if last_space > current_pos: # Ensure we are making progress
                best_split_point = last_space + 1 # Split after the space
            # else: stick with hard split at max_length (best_split_point remains split_at)

        chunk = text[current_pos:best_split_point]
        chunks.append(chunk)
        current_pos = best_split_point

    # Filter out any potential empty strings that might result from splitting logic, though less likely with this approach
    final_chunks = [c.strip() for c in chunks if c.strip()]
    print(f"[modules/tts.py] _chunk_text_boundary_aware: Text (len {text_len}) chunked into {len(final_chunks)} pieces.")
    return final_chunks

def _concatenate_wav_from_base64_list(base64_audio_list):
    """Decodes list of base64 WAV audio, concatenates them, and re-encodes to base64."""
    if not base64_audio_list:
        print("[modules/tts.py] _concatenate_wav_from_base64_list: No audio list provided.")
        return None
    if len(base64_audio_list) == 1:
        print("[modules/tts.py] _concatenate_wav_from_base64_list: Only one chunk, no concatenation needed.")
        return base64_audio_list[0]

    print(f"[modules/tts.py] _concatenate_wav_from_base64_list: Concatenating {len(base64_audio_list)} audio chunks.")
    
    all_frames_data = []
    wav_params = None

    for i, b64_string in enumerate(base64_audio_list):
        try:
            wav_bytes = base64.b64decode(b64_string)
            with io.BytesIO(wav_bytes) as wav_file_in_memory:
                with wave.open(wav_file_in_memory, 'rb') as wf:
                    if i == 0:
                        wav_params = wf.getparams()
                        print(f"[modules/tts.py] _concatenate_wav_from_base64_list: Audio params from first chunk: {wav_params}")
                    # Basic check: Sarvam should be consistent, but good to be aware
                    elif wav_params[:3] != wf.getparams()[:3]: # nchannels, sampwidth, framerate
                        error_msg = "Mismatch in critical audio parameters (channels, sampwidth, framerate) between chunks."
                        print(f"[modules/tts.py] _concatenate_wav_from_base64_list: {error_msg}")
                        raise ValueError(error_msg)
                    
                    frames = wf.readframes(wf.getnframes())
                    all_frames_data.append(frames)
        except Exception as e:
            print(f"[modules/tts.py] _concatenate_wav_from_base64_list: Error processing base64 chunk {i}: {e}")
            raise # Re-raise, as partial concatenation is problematic

    if not all_frames_data or not wav_params:
        print("[modules/tts.py] _concatenate_wav_from_base64_list: No valid audio frames to concatenate.")
        return None

    # Write the concatenated audio to an in-memory WAV file
    with io.BytesIO() as wav_output_in_memory:
        with wave.open(wav_output_in_memory, 'wb') as wf_out:
            wf_out.setparams(wav_params) # Use params from the first file
            for frame_data_chunk in all_frames_data:
                wf_out.writeframes(frame_data_chunk)
        concatenated_wav_bytes = wav_output_in_memory.getvalue()
    
    final_concatenated_base64 = base64.b64encode(concatenated_wav_bytes).decode('utf-8')
    print(f"[modules/tts.py] _concatenate_wav_from_base64_list: Concatenation successful. Final base64 length: {len(final_concatenated_base64)}")
    return final_concatenated_base64

def text_to_speech(text, lang_code, speaker='anushka', model='bulbul:v2'):
    """
    Converts text to speech. Handles chunking for texts longer than TTS_CHARACTER_LIMIT.
    For texts <= TTS_CHARACTER_LIMIT but >= MIN_TEXT_LENGTH_FOR_FORCED_TWO_WAY_SPLIT, it will be split into two.
    Returns a single base64 encoded string of the full audio.
    """
    print(f"[modules/tts.py] text_to_speech function called with raw text (length: {len(text)}): '{text[:100]}...', lang_code: {lang_code}, speaker: {speaker}, model: {model}")
    
    # Clean the input text first
    cleaned_text = _clean_text_for_tts(text)
    
    text_chunks = []

    if not cleaned_text or not cleaned_text.strip(): # Check cleaned_text now
        print("[modules/tts.py] text_to_speech: Empty or whitespace-only text after cleaning.")
        silent_wav_base64 = "UklGRkoAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQYAAAAAAQ=="
        print("[modules/tts.py] text_to_speech: Returning placeholder for silent audio due to empty input post-cleaning.")
        return silent_wav_base64

    if len(cleaned_text) > TTS_CHARACTER_LIMIT:
        print(f"[modules/tts.py] text_to_speech: Cleaned text exceeds limit ({len(cleaned_text)} > {TTS_CHARACTER_LIMIT}). Using boundary-aware chunking.")
        text_chunks = _chunk_text_boundary_aware(cleaned_text, TTS_CHARACTER_LIMIT)
    elif len(cleaned_text) < MIN_TEXT_LENGTH_FOR_FORCED_TWO_WAY_SPLIT:
        print(f"[modules/tts.py] text_to_speech: Cleaned text is very short (len {len(cleaned_text)} < {MIN_TEXT_LENGTH_FOR_FORCED_TWO_WAY_SPLIT}). Treating as a single chunk.")
        text_chunks = [cleaned_text.strip()] 
    else: 
        print(f"[modules/tts.py] text_to_speech: Cleaned text (len {len(cleaned_text)}) will be forcibly split into two chunks.")
        stripped_text = cleaned_text.strip()
        mid_point = len(stripped_text) // 2
        
        # Try to find a space near the midpoint for a cleaner split
        # Search backwards from midpoint then forwards
        split_pos_backward = stripped_text.rfind(' ', 0, mid_point + 1) # Include midpoint in search
        split_pos_forward = stripped_text.find(' ', mid_point)

        actual_split = -1

        if split_pos_backward != -1 and split_pos_forward != -1:
            # Both found, choose the one closer to the actual midpoint
            if (mid_point - split_pos_backward) <= (split_pos_forward - mid_point):
                actual_split = split_pos_backward + 1 # Split after the space
            else:
                actual_split = split_pos_forward + 1 # Split after the space
        elif split_pos_backward != -1:
            actual_split = split_pos_backward + 1
        elif split_pos_forward != -1:
            actual_split = split_pos_forward + 1
        else: # No space found (e.g., one very long word, or text without spaces)
            actual_split = mid_point # Fallback to hard split at midpoint
        
        chunk1 = stripped_text[:actual_split].strip()
        chunk2 = stripped_text[actual_split:].strip()
        
        text_chunks = []
        if chunk1: text_chunks.append(chunk1)
        if chunk2: text_chunks.append(chunk2)

        if not text_chunks: # Should not happen if original text was not empty and stripped
             text_chunks = [stripped_text] # Fallback to single chunk

        # Corrected logging for chunks:
        chunk_previews = [ (c[:50]+"...") if len(c)>50 else c for c in text_chunks ]
        print(f"[modules/tts.py] text_to_speech: Forced split resulted in {len(text_chunks)} chunks: {chunk_previews}")

    # Common processing for all chunks
    if not text_chunks: 
        print("[modules/tts.py] text_to_speech: No text chunks to process after splitting logic (this indicates an issue).")
        # This should ideally be caught by the empty text check earlier
        raise ValueError("Text resulted in no processable chunks unexpectedly.")

    base64_audio_parts = []
    for i, chunk in enumerate(text_chunks):
        if not chunk: 
            print(f"[modules/tts.py] text_to_speech: Skipping empty chunk {i+1} in processing loop.")
            continue
        print(f"[modules/tts.py] text_to_speech: Processing chunk {i+1}/{len(text_chunks)}.")
        try:
            base64_audio_chunk = _call_sarvam_tts(chunk, lang_code, speaker, model)
            base64_audio_parts.append(base64_audio_chunk)
        except Exception as e:
            print(f"[modules/tts.py] text_to_speech: CRITICAL - Error synthesizing audio for chunk {i+1} ('{chunk[:50]}...'). Error: {e}")
            raise Exception(f"Failed to synthesize complete audio due to error in chunk {i+1}. {e}")

    if not base64_audio_parts:
        print("[modules/tts.py] text_to_speech: No audio parts were successfully synthesized after chunking.")
        raise Exception("No audio parts were generated from text chunks.")

    print(f"[modules/tts.py] text_to_speech: All {len(base64_audio_parts)} chunks processed. Concatenating audio.")
    final_audio_base64 = _concatenate_wav_from_base64_list(base64_audio_parts)
    if not final_audio_base64:
         print("[modules/tts.py] text_to_speech: CRITICAL - Concatenation of audio chunks failed.")
         raise Exception("Audio chunk concatenation resulted in no data.")
    return final_audio_base64 