import os
from pydub import AudioSegment
from pydub.silence import detect_nonsilent, detect_silence


def save_audio(audio_segment, output_path, sample_rate=22050, bit_depth=16):
    """
    Save an AudioSegment to a .wav file with specified sample rate and bit depth.

    Parameters:
        audio_segment (AudioSegment): The audio segment to save.
        output_path (str): Path to save the .wav file.
        sample_rate (int): The sample rate of the output file (default: 22050 Hz).
        bit_depth (int): The bit depth of the output file (default: 16-bit).
    """
    audio_segment = audio_segment.set_frame_rate(sample_rate).set_sample_width(bit_depth // 8)
    audio_segment.export(output_path, format="wav")
    

def is_silent(audio_segment, silence_thresh=-40.0):
    """
    Check if the audio segment is mostly silent.

    Parameters:
        audio_segment (AudioSegment): The audio segment to check.
        silence_thresh (float): The silence threshold in dBFS.

    Returns:
        bool: True if the audio is mostly silent, False otherwise.
    """
    return audio_segment.dBFS < silence_thresh


def slice_audio(input_folder, output_folder, min_length, max_length):
    """
    Slice audio files in the input_folder, saving sliced segments to output_folder.

    Parameters:
        input_folder (str): Path to the folder containing input .wav or .mp3 files.
        output_folder (str): Path to save the sliced .wav files.
        min_length (int): Minimum duration of a slice in milliseconds.
        max_length (int): Maximum duration of a slice in milliseconds.
    """
    sliced_audios = []
    if os.path.exists(output_folder):
        for file in os.listdir(output_folder):
            file_path = os.path.join(output_folder, file)
            if os.path.isfile(file_path):
                os.remove(file_path)
    else:
        os.makedirs(output_folder)

    for filename in os.listdir(input_folder):
        if filename.lower().endswith(('.wav', '.mp3')):
            file_path = os.path.join(input_folder, filename)
            if filename.lower().endswith('.wav'):
                audio = AudioSegment.from_wav(file_path)
            elif filename.lower().endswith('.mp3'):
                audio = AudioSegment.from_mp3(file_path)

            slice_start = 0
            slice_index = 0

            while slice_start < len(audio):
                slice_end = slice_start + max_length

                # Find the quietest point within the max_length window
                window_audio = audio[slice_start:slice_end]
                silence = detect_silence(window_audio, min_silence_len=500, silence_thresh=audio.dBFS-14)
                best_silence_point = None

                if silence:
                    # Prioritize silences closer to max_length but still valid
                    best_silence_point = max(
                        (s for s in silence if s[0] >= min_length),
                        key=lambda s: (s[1] - s[0], s[0]),
                        default=None
                    )

                if best_silence_point:
                    slice_end = slice_start + best_silence_point[0]
                else:
                    # If no good silence found, use max_length as fallback
                    slice_end = min(slice_start + max_length, len(audio))

                # Ensure slice_end does not cut through speech
                slice_audio = audio[slice_start:slice_end]
                

                silence_in_slice = detect_silence(slice_audio, min_silence_len=500, silence_thresh=slice_audio.dBFS-14)
                if silence_in_slice:
                    last_silence_start = silence_in_slice[-1][0]
                    if last_silence_start > min_length:
                        slice_audio = slice_audio[:last_silence_start]

                slice_audio = slice_audio + AudioSegment.silent(duration=500)
                # Ensure non-empty and context-aware audio slices
                if len(slice_audio) > 0 and not is_silent(slice_audio):
                    output_path = os.path.join(output_folder, f"{os.path.splitext(filename)[0]}_slice_{slice_index}.wav")
                    save_audio(slice_audio, output_path)
                    sliced_audios.append(slice_audio)

                slice_index += 1
                slice_start = slice_end + 50  # Adjust for slight overlap to avoid premature slicing
                yield filename