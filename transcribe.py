import os
from typing import List

def get_audio_files(input_folder: str) -> List[str]:
    """Retrieve a list of audio files (mp3/wav) in the input folder."""
    supported_extensions = (".mp3", ".wav")
    return [os.path.join(input_folder, f) for f in os.listdir(input_folder) if f.endswith(supported_extensions)]

def transcribe_audio(model, audio_path: str) -> str:
    """Transcribe an audio file using Whisper."""
    result = model.transcribe(audio_path)
    return result.get("text", "")

def save_transcriptions_to_csv(transcriptions: List[str], output_path: str, header: str):
    output_csv_path = os.path.join(output_path, "transcriptions.csv")
    """Save the list of transcriptions to a CSV file."""
    with open(output_csv_path, mode="w", newline="", encoding="utf-8") as file:
        # Write the header row manually
        file.write(f"{header}\n")
        for row in transcriptions:
            # Write each row manually to avoid any automatic quoting
            file.write(row + "\n")