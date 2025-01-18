# audioslicer
Slice audio files, generate transcriptions, used for creating a dataset for TTS training etc

setup environment:

1. python3 -m venv env
2. source env/bin/activate
3. pip3 install -r requirements.txt 

start service:

4. python3 main.py
5. Check terminal for localhost::xxxx to access the service in browser

Output folder of the files and transcription will be located in the folder /temp_audio/{output_folder_name}
