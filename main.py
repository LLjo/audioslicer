import os
import time
from flask import Flask, request, render_template_string, jsonify
from flask_socketio import SocketIO, emit
import whisper
from slicer import slice_audio
from transcribe import get_audio_files, transcribe_audio, save_transcriptions_to_csv
    
# Global Variables
INPUT_FOLDER = os.path.join(os.getcwd(), 'temp_audio')
OUTPUT_FOLDER_NAME = 'output'
AUDIO_MIN_LENGTH = 3  # in seconds (default value)
AUDIO_MAX_LENGTH = 11  # in seconds (default value)

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

progress = {
    "current": 0,
    "total": 100,
    "message": "Starting..."
}

HEADER_ROW = "audio_file|text|speaker_name"
METADATA_FORMAT = "{audio_file}|{text}|{speaker_name}"
SPEAKER_NAME = "coqui"


def ensure_output_folder(output_folder):
    if os.path.exists(output_folder):
        for file in os.listdir(output_folder):
            file_path = os.path.join(output_folder, file)
            if os.path.isfile(file_path):
                os.remove(file_path)
    else:
        os.makedirs(output_folder)

def main(input_folder, output_folder_name, audio_min_length, audio_max_length):
    output_folder = f'temp_audio/{output_folder_name}/sliced'
    progress['current'] = 1
    socketio.emit("progress", {"message": f"Create folder {output_folder}", "current": progress['current'], "total": 100})
    ensure_output_folder(output_folder)
    
    sliced_files = slice_audio(input_folder, output_folder, audio_min_length, audio_max_length)
    total_files = 0
    for idx, file_name in enumerate(sliced_files):
        progress['current'] = progress['current'] + 1
        socketio.emit("progress", {"message": f"Slicing {file_name}", "current": progress['current'], "total": 100})
        total_files = total_files + 1

    if total_files == 0:
        socketio.emit("progress", {
            "message": "Error: No files found in the input folder",
            "current": 100,
            "total": 100,
            "isError": True
        })
        return

    socketio.emit("progress", {
        "message": "Processing complete!",
        "current": total_files,
        "total": total_files,
        "isError": False
    })

# Flask routes

@app.route('/')
def index():
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Audio Processing Tool</title>
    <script src="https://cdn.socket.io/4.0.1/socket.io.min.js"></script>
    <style>
        body { 
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        .container {
            background: #fff;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h2 {
            color: #333;
            margin-bottom: 20px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
            color: #555;
        }
        input[type="text"], input[type="file"], select {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }
        .range-group {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .buttons {
            display: flex;
            gap: 10px;
            margin-top: 30px;
        }
        button {
            padding: 12px 24px;
            border: none;
            border-radius: 4px;
            background: #007bff;
            color: white;
            cursor: pointer;
            transition: background 0.3s;
        }
        button:hover {
            background: #0056b3;
        }
        #progress-bar {
            margin-top: 30px;
            background: #f3f3f3;
            border-radius: 8px;
            overflow: hidden;
        }
        #progress {
            height: 20px;
            background: #4caf50;
            width: 0%;
            transition: width 0.3s;
        }
        #progress-text {
            margin-top: 10px;
            font-size: 14px;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="container">
        <h2>Audio Processing Tool</h2>
        <form id="process-form">
            <div class="form-group">
                <label for="input_folder">Audio Folder Path:</label>
                <div style="display: flex; gap: 10px; align-items: center;">
                <input type="text" id="input_folder" name="input_folder" 
                    placeholder="Enter folder path"
                    style="flex: 1;"
                    oninput="(async () => {
                        const errorElement = document.getElementById('path-error');
                        const isValid = await validatePath(this.value);
                        errorElement.style.display = isValid ? 'none' : 'block';
                        errorElement.textContent = isValid ? '' : 'Invalid folder path';
                    })()">
                </div>
                <small id="path-error" style="color: red; display: none;">Invalid folder path</small>
            </div>

            <div class="form-group">
                <label for="output_folder_name">Output Folder Name:</label>
                <input type="text" id="output_folder_name" name="output_folder_name" placeholder="Name for output folder" value="{{ OUTPUT_FOLDER_NAME }}">
            </div>

            <div class="form-group">
                <label for="speaker_name">Speaker Name:</label>
                <input type="text" id="speaker_name" name="speaker_name" placeholder="Enter speaker name" value="{{ SPEAKER_NAME }}">
            </div>

            <div class="form-group">
                <label for="metadata_format">Metadata Format:</label>
                <input type="text" id="metadata_format" name="metadata_format" placeholder="{{ METADATA_FORMAT }}" value="{{ METADATA_FORMAT }}">
                <small>Use {audio_file}, {text}, and {speaker_name} as placeholders such as: <b>{audio_file}|{text}|{speaker_name}</b></small>
            </div>

            <div class="form-group">
                <label for="header_row">CSV Header Row:</label>
                <input type="text" id="header_row" name="header_row" placeholder="Enter CSV header row" value="{{ HEADER_ROW }}">
                <small>Example: <b>audio_file|text|speaker_name</b></small>
            </div>

            <div class="form-group">
                <label>Audio Length Settings:</label>
                <div class="range-group">
                    <div>
                        <label for="min_length">Min (seconds):</label>
                        <input type="range" id="min_length" name="audio_min_length" min="1" max="60" value="{{ AUDIO_MIN_LENGTH }}" oninput="document.getElementById('min_length_value').innerHTML = this.value;">
                        <span id="min_length_value">{{ AUDIO_MIN_LENGTH }}</span>
                    </div>
                    <div>
                        <label for="max_length">Max (seconds):</label>
                        <input type="range" id="max_length" name="audio_max_length" min="1" max="60" value="{{ AUDIO_MAX_LENGTH }}" oninput="document.getElementById('max_length_value').innerHTML = this.value;">
                        <span id="max_length_value">{{ AUDIO_MAX_LENGTH }}</span>
                    </div>
                </div>
            </div>

            <div class="buttons">
                <button type="button" onclick="startProcessing()">Process Audio</button>
                <button type="button" onclick="startTranscription()" id="transcribe-btn">Start Transcription</button>
            </div>
        </form>

        <div id="progress-bar">
            <div id="progress"></div>
        </div>
        <div id="progress-text">Waiting for progress...</div>
    </div>

            <script>
                const socket = io();
                const inputFolder = document.getElementById('input_folder');

                // Load saved settings from localStorage
                const savedSettings = {
                    input_folder: localStorage.getItem('input_folder'),
                    output_folder_name: localStorage.getItem('output_folder_name'),
                    speaker_name: localStorage.getItem('speaker_name'),
                    metadata_format: localStorage.getItem('metadata_format'),
                    header_row: localStorage.getItem('header_row'),
                    audio_min_length: localStorage.getItem('audio_min_length'),
                    audio_max_length: localStorage.getItem('audio_max_length')
                };

                // Apply saved settings to form
                if (savedSettings.input_folder) {
                    inputFolder.value = savedSettings.input_folder;
                }
                if (savedSettings.output_folder_name) {
                    document.getElementById('output_folder_name').value = savedSettings.output_folder_name;
                }
                if (savedSettings.speaker_name) {
                    document.getElementById('speaker_name').value = savedSettings.speaker_name;
                }
                if (savedSettings.metadata_format) {
                    document.getElementById('metadata_format').value = savedSettings.metadata_format;
                }
                if (savedSettings.header_row) {
                    document.getElementById('header_row').value = savedSettings.header_row;
                }
                if (savedSettings.audio_min_length) {
                    document.getElementById('min_length').value = savedSettings.audio_min_length;
                    document.getElementById('min_length_value').textContent = savedSettings.audio_min_length;
                }
                if (savedSettings.audio_max_length) {
                    document.getElementById('max_length').value = savedSettings.audio_max_length;
                    document.getElementById('max_length_value').textContent = savedSettings.audio_max_length;
                }

                async function validatePath(path) {
                    try {
                        const response = await fetch('/validate-path', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({ path: path })
                        });
                        const data = await response.json();
                        return data.valid;
                    } catch (error) {
                        console.error('Validation error:', error);
                        return false;
                    }
                }

                function handleFolderSelection() {
                    openFolderPicker();
                }
                
                function saveSettings() {
                    const form = document.getElementById('process-form');
                    
                    localStorage.setItem('input_folder', form.input_folder.value);
                    localStorage.setItem('output_folder_name', form.output_folder_name.value);
                    localStorage.setItem('speaker_name', form.speaker_name.value);
                    localStorage.setItem('metadata_format', form.metadata_format.value);
                    localStorage.setItem('header_row', form.header_row.value);
                    localStorage.setItem('audio_min_length', form.audio_min_length.value);
                    localStorage.setItem('audio_max_length', form.audio_max_length.value);
                }

                function startProcessing() {
                    const formData = new FormData(document.getElementById('process-form'));
                    const inputFolder = document.getElementById('input_folder');
                    
                    saveSettings()
                    
                    fetch('/process', {
                        method: 'POST',
                        body: formData
                    }).then(response => response.text())
                    .then(data => {
                        console.log(data);
                    }).catch(error => {
                        console.error('Error:', error);
                    });
                }

                function startTranscription() {
                    const transcribeBtn = document.getElementById('transcribe-btn');
                    transcribeBtn.disabled = true;
                    transcribeBtn.textContent = 'Loading Model...';
                    
                    const formData = new FormData(document.getElementById('process-form'));
                    saveSettings()
                    fetch('/transcribe', {
                        method: 'POST',
                        body: formData
                    }).then(response => response.text())
                    .then(data => {
                        console.log(data);
                        transcribeBtn.disabled = false;
                        transcribeBtn.textContent = 'Start Transcription';
                    }).catch(error => {
                        console.error('Error:', error);
                        transcribeBtn.disabled = false;
                        transcribeBtn.textContent = 'Start Transcription';
                    });
                }

                // Handle progress updates
                socket.on('progress', data => {
                    const progressBar = document.getElementById('progress');
                    const progressText = document.getElementById('progress-text');
                    
                    // Update progress bar
                    progressBar.style.width = (data.current / data.total * 100) + '%';
                    
                    // Update progress text with error styling if needed
                    progressText.textContent = data.message;
                    if (data.isError === true || data.isError === 'True') {
                        progressText.style.color = 'red';
                        progressBar.style.backgroundColor = '#ff4444';
                    } else {
                        progressText.style.color = '#666';
                        progressBar.style.backgroundColor = '#4caf50';
                    }
                });

                // Handle connection errors
                socket.on('connect_error', (error) => {
                    console.error('Connection error:', error);
                    const progressText = document.getElementById('progress-text');
                    if (progressText) {
                        progressText.textContent = 'Connection error - please refresh the page';
                        progressText.style.color = 'red';
                    }
                });

                // Handle successful connection
                socket.on('connect', () => {
                    const progressText = document.getElementById('progress-text');
                    if (progressText) {
                        progressText.textContent = 'Connected - ready to process';
                        progressText.style.color = '#666';
                    }
                });
   
            </script>
</body>
</html>
''', INPUT_FOLDER=INPUT_FOLDER, OUTPUT_FOLDER_NAME=OUTPUT_FOLDER_NAME, AUDIO_MIN_LENGTH=AUDIO_MIN_LENGTH, AUDIO_MAX_LENGTH=AUDIO_MAX_LENGTH)

@app.route('/process', methods=['POST'])
def process():
    input_folder = request.form.get('input_folder') or INPUT_FOLDER
    output_folder_name = request.form.get('output_folder_name') or OUTPUT_FOLDER_NAME
    audio_min_length = int(request.form.get('audio_min_length')) if request.form.get('audio_min_length') else AUDIO_MIN_LENGTH
    audio_max_length = int(request.form.get('audio_max_length')) if request.form.get('audio_max_length') else AUDIO_MAX_LENGTH
    audio_min_length = audio_min_length * 1000
    audio_max_length = audio_max_length * 1000

    socketio.start_background_task(main, input_folder, output_folder_name, audio_min_length, audio_max_length)

    return 'Processing started. Monitor progress in the progress bar.'

@app.route('/validate-path', methods=['POST'])
def validate_path():
    data = request.get_json()
    path = data.get('path')
    if not path:
        return jsonify({'valid': False})
    
    try:
        if os.path.exists(path) and os.path.isdir(path):
            return jsonify({'valid': True})
        return jsonify({'valid': False})
    except Exception:
        return jsonify({'valid': False})

@app.route('/transcribe', methods=['POST'])
def transcribe():
    # Get form data before creating background task
    speaker_name = request.form.get('speaker_name') or SPEAKER_NAME
    metadata_format = request.form.get('metadata_format') or METADATA_FORMAT
    header_row = request.form.get('header_row') or HEADER_ROW
    
    def transcribe_task(speaker_name, metadata_format, header_row):
        try:
            # Update progress
            progress['current'] = 0
            progress['total'] = 100
            socketio.emit("progress", {"message": "Loading Whisper model...", "current": 0, "total": 100})
            
            # Get audio files
            output_folder = f'temp_audio/{OUTPUT_FOLDER_NAME}/sliced'
            audio_files = get_audio_files(output_folder)
            
            if not audio_files:
                socketio.emit("progress", {
                    "message": "Error: No audio files found in output folder",
                    "current": 100,
                    "total": 100,
                    "isError": True
                })
                return
            
            model = whisper.load_model("turbo")
            transcriptions = []
            
            for idx, file_path in enumerate(audio_files):
                progress['current'] = progress['current'] + 1
                progress_message = f"Processing {os.path.basename(file_path)} ({idx + 1}/{len(audio_files)})"
                socketio.emit("progress", {"message": progress_message, "current": idx + 1, "total": len(audio_files)})
                
                full_path = os.path.abspath(file_path)
                text = transcribe_audio(model, file_path).strip()
                output_line = metadata_format.format(
                    audio_file=full_path,
                    text=text,
                    speaker_name=speaker_name
                )
                transcriptions.append(output_line)

            save_transcriptions_to_csv(transcriptions, output_folder, header_row)    
            
            socketio.emit("progress", {"message": "Transcription complete!", "current": len(audio_files), "total": len(audio_files)})
        except Exception as e:
            socketio.emit("progress", {"message": f"Error: {str(e)}", "current": 100, "total": 100})

    socketio.start_background_task(transcribe_task, speaker_name, metadata_format, header_row)
    return 'Transcription started'

if __name__ == "__main__":
    socketio.run(app, debug=True)
