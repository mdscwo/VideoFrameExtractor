''' Notes
Downloaded K-Lite Video Codec to get the video player to work
'''




import logging
import os
import subprocess
import sys
from time import time
import webbrowser

from PyQt5.QtCore import QThread, QUrl, pyqtSignal, Qt
from PyQt5.QtGui import QIcon, QPixmap, QIntValidator
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QTextEdit, QProgressBar, QFileDialog, QLabel, 
                             QLineEdit, QComboBox, QWidget, QCheckBox, QSlider, 
                             QGroupBox, QLayout, QMessageBox)

import qdarktheme

# Start Logging
if not os.path.exists('./Logs'):
    os.makedirs('./Logs')
    
logging.basicConfig(filename='./Logs/log.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


logging.info("Application started.")

class StreamToLogger:
    def __init__(self, original_stream, logger, log_level):
        self.original_stream = original_stream
        self.logger = logger
        self.log_level = log_level

    def write(self, message):
        if message.rstrip() != "":
            self.logger.log(self.log_level, message.rstrip())
        self.original_stream.write(message)

    def flush(self):
        self.original_stream.flush()

# Redirect standard output and standard error
sys.stdout = StreamToLogger(sys.stdout, logging.getLogger(), logging.INFO)
sys.stderr = StreamToLogger(sys.stderr, logging.getLogger(), logging.ERROR)



def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
    logging.error("Uncaught exception",
                  exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_uncaught_exception


def get_video_duration(video_path):
    cmd = ["ffmpeg", "-i", video_path]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    for line in result.stderr.split("\n"):
        if "Duration" in line:
            time_parts = line.split(",")[0].split("Duration:")[1].strip().split(":")
            hours, minutes, seconds = time_parts
            total_seconds = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            return total_seconds
    return None

class FrameExtractorWorker(QThread):
    # Signals
    update_progress_signal = pyqtSignal(int)
    update_status_signal = pyqtSignal(str)
    update_frames_signal = pyqtSignal(str)
    first_frame_signal = pyqtSignal(str)
    last_frame_signal = pyqtSignal(str)
    extraction_completed_signal = pyqtSignal(int, str) 
    



    def __init__(self, video_path, output_dir, interval, frame_name, output_format, resolution, use_gpu=False, gpu_method=""):
        super().__init__()
        self.video_path = video_path
        self.output_dir = output_dir
        self.interval = interval
        self.frame_name = frame_name
        self.output_format = output_format
        self.resolution = resolution
        self.cancel_extraction = False
        self.use_gpu = use_gpu
        self.gpu_method = gpu_method
        

    def run(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        video_duration = get_video_duration(self.video_path)
        if video_duration is None:
            error_msg = "Couldn't determine video duration. Exiting."
            print(error_msg)
            logging.error(error_msg)
            return

        num_screenshots = int(video_duration) // self.interval
        start_time = time()

        for i in range(num_screenshots):
            if self.cancel_extraction:
                self.update_status_signal.emit("Extraction Cancelled!")
                break

            timestamp = i * self.interval
            base_name = self.frame_name if self.frame_name else "frame"
            output_file = os.path.join(self.output_dir, f"{base_name}_{i:03d}.{self.output_format}")

            # Determine the codec based on the selected format
            codec = self.output_format
            if codec == "jpg":
                codec = "mjpeg"
            elif codec == "png":
                codec = "png"
            elif codec == "bmp":
                codec = "bmp"
            elif codec == "tiff":
                codec = "tiff"

            width, height = self.resolution.split("x")
            cmd = ["ffmpeg", "-ss", str(timestamp), "-i", self.video_path, "-vf", f"scale={width}:{height}", "-vframes", "1", "-c:v", codec, "-an", output_file]



            if self.use_gpu:
                if self.gpu_method == "cuda":
                    cmd.insert(1, "-hwaccel")
                    cmd.insert(2, "cuda")
                elif self.gpu_method == "dxva2":
                    cmd.insert(1, "-hwaccel")
                    cmd.insert(2, "dxva2")
                elif self.gpu_method == "qsv":
                    cmd.insert(1, "-hwaccel")
                    cmd.insert(2, "qsv")
                elif self.gpu_method == "d3d11va":
                    cmd.insert(1, "-hwaccel")
                    cmd.insert(2, "d3d11va")
                elif self.gpu_method == "opencl":
                    cmd.insert(1, "-hwaccel")
                    cmd.insert(2, "opencl")
                elif self.gpu_method == "vulkan":
                    cmd.insert(1, "-hwaccel")
                    cmd.insert(2, "vulkan")

                    
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode != 0:
                error_msg = f"Error on extracting frame {i}: {result.stderr}"
                print(error_msg)
                logging.error(error_msg)

            # Emit signals for UI updates
            elapsed_time = time() - start_time
            remaining_time = ((video_duration - (i * self.interval)) / self.interval) * (elapsed_time / (i+1))
            self.update_progress_signal.emit(int((i + 1) / num_screenshots * 100))
            self.update_status_signal.emit(f"Elapsed Time: {int(elapsed_time)}s | Time Remaining: {int(remaining_time)}s")
            self.update_frames_signal.emit(f"Frames Created: {i+1}/{num_screenshots}")

            # Emit signal for the first frame only once
            if i == 0:
                self.first_frame_signal.emit(output_file)

            # Emit signal for the last frame after every extraction
            self.last_frame_signal.emit(output_file)
            
        if not self.cancel_extraction:
            self.extraction_completed_signal.emit(num_screenshots, self.output_dir)



    def stop(self):
        self.cancel_extraction = True

class FFmpegFrameExtractorApp(QMainWindow):


    def __init__(self):
        super().__init__()
        self.initUI()
        
        # Connect to the mediaStatusChanged signal
        self.video_player.mediaStatusChanged.connect(self.handle_media_status_change)

    def initUI(self):
        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)

        main_layout = QHBoxLayout()  # Changed to QHBoxLayout for main layout
        

        # Left side layout
        left_layout = QVBoxLayout()

        # New vertical layout for the settings and progress bar
        settings_layout = QVBoxLayout()
        
        # Dark theme toggle checkbox
        self.dark_mode_checkbox = QCheckBox("Dark Mode", self)
        self.dark_mode_checkbox.stateChanged.connect(self.toggle_dark_mode)
        settings_layout.addWidget(self.dark_mode_checkbox)
        
        # Toggle Video Player
        self.toggle_video_player_checkbox = QCheckBox("Show Video Player", self)
        self.toggle_video_player_checkbox.setChecked(False)  # Default to not showing the video player
        self.toggle_video_player_checkbox.stateChanged.connect(self.toggle_video_player)
        settings_layout.addWidget(self.toggle_video_player_checkbox)

        # Toggle Frame Previews
        self.toggle_frame_previews_checkbox = QCheckBox("Show Frame Previews", self)
        self.toggle_frame_previews_checkbox.setChecked(False)  # Default to not showing the frame previews
        self.toggle_frame_previews_checkbox.stateChanged.connect(self.toggle_frame_previews)
        settings_layout.addWidget(self.toggle_frame_previews_checkbox)


        # File Frame
        
        # Video Path
        self.video_path_entry = QLineEdit(self)
        settings_layout.addWidget(QLabel("Video Path:"))
        self.browse_video_btn = QPushButton(QIcon('./images/browse.png'), "", self)
        self.browse_video_btn.clicked.connect(self.select_video_file)
        video_path_layout = QHBoxLayout()
        video_path_layout.addWidget(self.video_path_entry)
        video_path_layout.addWidget(self.browse_video_btn)
        settings_layout.addLayout(video_path_layout)

        # Output Directory
        self.output_dir_entry = QLineEdit(self)
        settings_layout.addWidget(QLabel("Output Directory:"))
        self.browse_output_dir_btn = QPushButton(QIcon('./images/browse.png'), "", self)
        self.browse_output_dir_btn.clicked.connect(self.select_output_directory)
        output_dir_layout = QHBoxLayout()
        output_dir_layout.addWidget(self.output_dir_entry)
        output_dir_layout.addWidget(self.browse_output_dir_btn)
        settings_layout.addLayout(output_dir_layout)

                
        # More Settings
        
        # #Interval Slider
        self.interval_slider = QSlider(Qt.Horizontal, self)
        self.interval_slider.setRange(1, 600)  # 1 to 600 seconds range
        self.interval_slider.setValue(10)  # Default value
        self.interval_slider.valueChanged.connect(self.update_interval_entry)

        self.interval_entry = QLineEdit("10", self)  # Default value
        self.interval_entry.setValidator(QIntValidator(1, 600))  # Only allow integers between 1 and 600
        self.interval_entry.textChanged.connect(self.update_interval_slider_from_entry)
        self.interval_entry.setFixedWidth(50)  # Adjust width as needed

        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Interval (in seconds):"))
        interval_layout.addWidget(self.interval_slider)
        interval_layout.addWidget(self.interval_entry)

        settings_layout.addLayout(interval_layout)
        
        # Output Format
        self.output_format = QComboBox(self)
        self.output_format.addItems(["png", "jpg", "bmp", "tiff"])

        # Resolution
        self.resolution_dropdown = QComboBox(self)
        self.resolution_dropdown.addItems(["4K (3840x2160)", "2K (2560x1440)", "1080p (1920x1080)", "720p (1280x720)", "640p (640x480)", "480p (854x480)"])
        
        # Output and Resolution Drop Downs
        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Output Format (lossless):"))
        format_layout.addWidget(self.output_format)
        format_layout.addWidget(QLabel("Resolution:"))
        format_layout.addWidget(self.resolution_dropdown)
        settings_layout.addLayout(format_layout)



        
        # File Name
        self.frame_name_entry = QLineEdit(self)
        settings_layout.addWidget(QLabel("Frame Name:"))
        settings_layout.addWidget(self.frame_name_entry)
        
        # GPU Acceleration Frame
        gpu_acceleration_group = QGroupBox("GPU Acceleration (Beta)", self)
        gpu_acceleration_layout = QVBoxLayout()

        self.gpu_accel_checkbox = QCheckBox("Enable GPU Acceleration", self)
        gpu_acceleration_layout.addWidget(self.gpu_accel_checkbox)

        self.gpu_accel_method = QComboBox(self)
        self.gpu_accel_method.addItems(["cuda", "dxva2", "qsv", "d3d11va", "opencl", "vulkan"])
        gpu_acceleration_layout.addWidget(QLabel("Acceleration Method:"))
        gpu_acceleration_layout.addWidget(self.gpu_accel_method)

        gpu_acceleration_group.setLayout(gpu_acceleration_layout)
        settings_layout.addWidget(gpu_acceleration_group)
        
        # Spacer before progress bar
        settings_layout.addStretch(1)
        
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setMinimumWidth(200)
        settings_layout.addWidget(self.progress_bar)

        # Spacer after progress bar
        settings_layout.addStretch(1)
        
        # Add the settings_layout to the left_layout
        left_layout.addLayout(settings_layout)
        
        self.status_label = QLabel(self)
        left_layout.addWidget(self.status_label)
        self.frames_label = QLabel(self)
        left_layout.addWidget(self.frames_label)

        button_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start Extraction", self)
        self.start_btn.setStyleSheet("background-color: green; color: white;")
        self.start_btn.clicked.connect(self.start_extraction)
        button_layout.addWidget(self.start_btn)

        self.open_dir_btn = QPushButton("Open Directory", self)
        self.open_dir_btn.clicked.connect(self.open_directory)
        button_layout.addWidget(self.open_dir_btn)

        self.cancel_btn = QPushButton("Cancel Extraction", self)
        self.cancel_btn.setStyleSheet("background-color: red; color: white;")
        self.cancel_btn.clicked.connect(self.handle_cancel)
        button_layout.addWidget(self.cancel_btn)

        left_layout.addLayout(button_layout)
        
        # Video Preview
        video_layout = QVBoxLayout()
        self.video_player = QMediaPlayer(self)
        self.video_widget = QVideoWidget(self)
        self.video_widget.setFixedSize(400, 300)
        self.video_title_label = QLabel("Video Preview:")
        video_layout.addWidget(self.video_title_label)
        video_layout.addWidget(self.video_widget)
        self.video_player.setVideoOutput(self.video_widget)
        
        
        # Video Slider and Timestamp Entry Layout
        slider_timestamp_layout = QHBoxLayout()

        # Video Slider
        self.video_slider = QSlider(Qt.Horizontal, self)
        self.video_slider.setRange(0, 0)
        self.video_slider.sliderMoved.connect(self.set_position)
        slider_timestamp_layout.addWidget(self.video_slider)
        
        self.video_player.positionChanged.connect(self.position_changed)
        self.video_player.durationChanged.connect(self.duration_changed)
        self.video_slider.sliderMoved.connect(self.set_position)
        self.video_slider.setTracking(False)
        
        # Timestamp Entry
        self.timestamp_entry = QLineEdit(self)
        self.timestamp_entry.setPlaceholderText("HH:MM:SS")
        self.timestamp_entry.setMaximumWidth(80)  # Adjust width as needed
        self.timestamp_entry.returnPressed.connect(self.seek_to_timestamp)
        slider_timestamp_layout.addWidget(self.timestamp_entry)

        video_layout.addLayout(slider_timestamp_layout)

        # Playback Controls
        controls_layout = QHBoxLayout()
        self.play_btn = QPushButton("Play", self)
        self.play_btn.clicked.connect(self.video_player.play)
        controls_layout.addWidget(self.play_btn)

        self.pause_btn = QPushButton("Pause", self)
        self.pause_btn.clicked.connect(self.video_player.pause)
        controls_layout.addWidget(self.pause_btn)

        self.stop_btn = QPushButton("Stop", self)
        self.stop_btn.clicked.connect(self.video_player.stop)
        controls_layout.addWidget(self.stop_btn)

        video_layout.addLayout(controls_layout)
        left_layout.addLayout(video_layout)
        
        # Quick Extract
        self.quick_extract_btn = QPushButton("Quick Extract", self)
        self.quick_extract_btn.clicked.connect(self.quick_extract)
        left_layout.addWidget(self.quick_extract_btn)
        
        # Right side layout for previews
        right_layout = QVBoxLayout()
        
        # First Frame
        self.first_frame_label = QLabel(self)
        self.first_frame_label.setFixedSize(400, 300)
        self.first_frame_title_label = QLabel("First Frame:")
        right_layout.addWidget(self.first_frame_title_label)
        right_layout.addWidget(self.first_frame_label)
        
        # Last Frame
        self.last_frame_label = QLabel(self)
        self.last_frame_label.setFixedSize(400, 300)
        self.last_frame_title_label = QLabel("Last Frame:")
        right_layout.addWidget(self.last_frame_title_label)
        right_layout.addWidget(self.last_frame_label)
        
        # Add left and right layouts to main layout
        main_layout.addLayout(left_layout)
        main_layout.addLayout(right_layout)
        
        main_widget.setLayout(main_layout)

        # Set window properties
        self.setWindowTitle('VidFrameFetcher')
        self.setWindowIcon(QIcon('./images/icon.png'))  # Update path as needed
        self.resize(0, 0)  # Adjust size if needed
        
        # Accept Drops
        self.setAcceptDrops(True)
        
        # Hide the corresponding widgets by default
        self.toggle_video_player(Qt.Unchecked)
        self.toggle_frame_previews(Qt.Unchecked)

        # Adjust the window size
        self.adjustSize()
        
        # Ensure the window cannot be resized larger than the size hint of its layout
        self.layout().setSizeConstraint(QLayout.SetFixedSize)
        
        
        '''# Tool Tips
        
        #QLineEdit
        self.video_path_entry.setToolTip("Path to the video file you want to extract frames from.")
        self.output_dir_entry.setToolTip("Directory where the extracted frames will be saved.")
        self.frame_name_entry.setToolTip("Base name for the extracted frames.")
        self.timestamp_entry.setToolTip("Enter a timestamp (HH:MM:SS) to seek to that position in the video.")
        
        #QComboBox
        self.output_format.setToolTip("Select the format for the extracted frames.")
        self.resolution_dropdown.setToolTip("Select the resolution for the extracted frames.")
        self.gpu_accel_method.setToolTip("Select the GPU acceleration method (if GPU acceleration is enabled).")
        
        #QCheckBox
        self.dark_mode_checkbox.setToolTip("Toggle dark mode for the application.")
        self.toggle_video_player_checkbox.setToolTip("Show or hide the video player.")
        self.toggle_frame_previews_checkbox.setToolTip("Show or hide the frame previews.")
        self.gpu_accel_checkbox.setToolTip("Enable or disable GPU acceleration for frame extraction.")
        
        #QSlider
        self.interval_slider.setToolTip("Set the interval (in seconds) between extracted frames.")
        self.video_slider.setToolTip("Seek to a specific position in the video.")
        
        #QPushButton
        self.browse_video_btn.setToolTip("Browse and select a video file.")
        self.browse_output_dir_btn.setToolTip("Browse and select an output directory.")
        self.start_btn.setToolTip("Start the frame extraction process.")
        self.open_dir_btn.setToolTip("Open the selected output directory.")
        self.cancel_btn.setToolTip("Cancel the ongoing frame extraction process.")
        self.play_btn.setToolTip("Play the video.")
        self.pause_btn.setToolTip("Pause the video.")
        self.stop_btn.setToolTip("Stop the video.")
        self.quick_extract_btn.setToolTip("Quickly extract a frame from the current video position.")
        
        #QGroupBox
        gpu_acceleration_group.setToolTip("Settings related to GPU acceleration for frame extraction.")

        #QProgressBar
        self.progress_bar.setToolTip("Shows the progress of the frame extraction process.")
        
        #QLabel
        self.first_frame_label.setToolTip("Preview of the first extracted frame.")
        self.last_frame_label.setToolTip("Preview of the last extracted frame.")'''






       
    def update_first_frame_preview(self, frame_path):
        pixmap = QPixmap(frame_path).scaled(400, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.first_frame_label.setPixmap(pixmap)

    def update_last_frame_preview(self, frame_path):
        pixmap = QPixmap(frame_path).scaled(400, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.last_frame_label.setPixmap(pixmap)

    def toggle_dark_mode(self, state):
        if state == Qt.Checked:
            qdarktheme.setup_theme()
        else:
            qdarktheme.setup_theme("light")  # or perhaps the default theme of your app
        
    def select_video_file(self):
        options = QFileDialog.Options()
        filepath, _ = QFileDialog.getOpenFileName(self, "Select a Video File", "", "Video Files (*.mp4; *.mkv; *.avi; *.mov);;All Files (*)", options=options)
        if filepath:
            self.video_path_entry.setText(filepath)
            self.video_player.setMedia(QMediaContent(QUrl.fromLocalFile(filepath)))

    def handle_media_status_change(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            # Media is loaded and ready to play
            pass
        elif status in [QMediaPlayer.MediaStatus.InvalidMedia, QMediaPlayer.MediaStatus.NoMedia, QMediaPlayer.MediaStatus.UnknownMediaStatus]:
            error_msg = f"Unable to play the provided video file: {self.video_path_entry.text()}"
            QMessageBox.critical(self, "Error", error_msg)
            logging.error(error_msg)

    def select_output_directory(self):
        options = QFileDialog.Options()
        directory = QFileDialog.getExistingDirectory(self, "Select an Output Directory", "", options=options)
        if directory:
            self.output_dir_entry.setText(directory)
            
    def update_interval_entry(self, value):
        self.interval_entry.setText(str(value))

    def update_interval_slider_from_entry(self, text):
        if text:  # Check if the text is not empty
            value = int(text)
        self.interval_slider.setValue(value)
            
    def position_changed(self, position):
        self.video_slider.setValue(position)
        h, m, s = position // 3600000, (position % 3600000) // 60000, (position % 60000) // 1000
        self.timestamp_entry.setText(f"{h:02d}:{m:02d}:{s:02d}")


    def duration_changed(self, duration):
        self.video_slider.setRange(0, duration)

    def set_position(self, position):
        self.video_player.setPosition(position)
        
    def seek_to_timestamp(self):
        timestamp_str = self.timestamp_entry.text()
        try:
            h, m, s = map(int, timestamp_str.split(':'))
            milliseconds = (h * 3600 + m * 60 + s) * 1000
            self.video_player.setPosition(milliseconds)
        except ValueError:
            # Handle invalid input format
            pass

    # Quick Extract    
    def quick_extract(self):
        video_path = self.video_path_entry.text()
        output_dir = self.output_dir_entry.text()

        # Check if video path is valid
        if not video_path or not os.path.exists(video_path):
            error_msg = "Please select a valid video file."
            QMessageBox.critical(self, "Error", error_msg)
            logging.error(error_msg)
            return

        # Check if output directory is specified
        if not output_dir:
            error_msg = "Please specify an output directory."
            QMessageBox.critical(self, "Error", error_msg)
            logging.error(error_msg)
            return

        # Check if output directory exists, if not, create it
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        timestamp = self.video_player.position() / 1000  # Convert from ms to seconds
        base_name = "snapshot"
        output_file = os.path.join(output_dir, f"{base_name}_{int(timestamp)}.png")

        cmd = ["ffmpeg", "-ss", str(timestamp), "-i", video_path, "-vf", f"scale=-1:1080", "-vframes", "1", "-c:v", "png", "-an", output_file]
        
        if self.gpu_accel_checkbox.isChecked():
            method = self.gpu_accel_method.currentText()
            cmd.insert(1, "-hwaccel")
            cmd.insert(2, method)

        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode != 0:
            error_msg = f"Error on extracting snapshot at {timestamp}s:\n{result.stderr}"
            QMessageBox.critical(self, "Error", error_msg)
            logging.error(error_msg)
        else:
            print(f"Snapshot saved to {output_file}")
    
    # Hide/Show Video Player / Frame Preview methods
    def toggle_video_player(self, state):
        if state == Qt.Checked:
            self.video_title_label.show()
            self.video_widget.show()
            self.play_btn.show()
            self.pause_btn.show()
            self.stop_btn.show()
            self.video_slider.show()
            self.timestamp_entry.show()  # Add this line
            self.quick_extract_btn.show()
        else:
            self.video_title_label.hide()
            self.video_widget.hide()
            self.play_btn.hide()
            self.pause_btn.hide()
            self.stop_btn.hide()
            self.video_slider.hide()
            self.timestamp_entry.hide()  # Add this line
            self.quick_extract_btn.hide()
        self.adjustSize()


    def toggle_frame_previews(self, state):
        if state == Qt.Checked:
            self.first_frame_title_label.show()
            self.first_frame_label.show()
            self.last_frame_title_label.show()
            self.last_frame_label.show()
        else:
            self.first_frame_title_label.hide()
            self.first_frame_label.hide()
            self.last_frame_title_label.hide()
            self.last_frame_label.hide()
        self.adjustSize()
    

    # Start Extraction   
    def start_extraction(self):
        video_path = self.video_path_entry.text()
        output_dir = self.output_dir_entry.text()

        if not video_path or not os.path.exists(video_path):
            error_msg = "Please select a valid video file."
            QMessageBox.critical(self, "Error", error_msg)
            logging.error(error_msg)
            return

        if not os.path.exists(output_dir):
            error_msg = f"Output directory {output_dir} does not exist."
            QMessageBox.critical(self, "Error", error_msg)
            logging.error(error_msg)
            return

        video_duration = get_video_duration(video_path)
        if video_duration is None:
            error_msg = "Couldn't determine video duration. Exiting."
            QMessageBox.critical(self, "Error", error_msg)
            logging.error(error_msg)
            return

        num_screenshots = int(video_duration) // int(self.interval_entry.text())
        logging.info(f"Extraction started for {num_screenshots} frames.")
            
        resolution = self.resolution_dropdown.currentText().split(" ")[1].replace("(", "").replace(")", "")
        self.worker = FrameExtractorWorker(
            self.video_path_entry.text(),
            self.output_dir_entry.text(),
            int(self.interval_entry.text()),
            self.frame_name_entry.text(),
            self.output_format.currentText(),
            resolution,
            self.gpu_accel_checkbox.isChecked(),
            self.gpu_accel_method.currentText()
        )

        # Signals
        self.worker.extraction_completed_signal.connect(self.log_extraction_completion)
        self.worker.update_progress_signal.connect(self.update_progress)
        self.worker.update_status_signal.connect(self.update_status)
        self.worker.update_frames_signal.connect(self.update_frames)
        self.worker.first_frame_signal.connect(self.update_first_frame_preview)
        self.worker.last_frame_signal.connect(self.update_last_frame_preview)
        self.worker.start()
        
    #Drag and Drop
    def dragEnterEvent(self, event):
        mime_data = event.mimeData()
        if mime_data.hasUrls() and len(mime_data.urls()) == 1:
            file_path = mime_data.urls()[0].toLocalFile()
            if file_path.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')):
                event.acceptProposedAction()

    def dropEvent(self, event):
        file_path = event.mimeData().urls()[0].toLocalFile()
        self.video_path_entry.setText(file_path)
        self.video_player.setMedia(QMediaContent(QUrl.fromLocalFile(file_path)))
    
    # Log Completed Extraction
    def log_extraction_completion(self, num_frames, output_dir):
        logging.info(f"Extraction completed. {num_frames} frames extracted to {output_dir}.")

    #Cancel
    def handle_cancel(self):
        if hasattr(self, 'worker'):
            self.worker.stop()
            logging.info("Extraction cancelled by the user.")

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_status(self, text):
        self.status_label.setText(text)

    def update_frames(self, text):
        self.frames_label.setText(text)
    
    def open_directory(self):
        output_dir = self.output_dir_entry.text()
        if not output_dir:
            QMessageBox.critical(self, "Error", "No directory selected.")
            return

        if os.path.exists(output_dir):
            webbrowser.open(output_dir)
        else:
            QMessageBox.critical(self, "Error", f"Directory {output_dir} does not exist.")

            
    def closeEvent(self, event):
        logging.info("Application closed.")
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Set the application style to Fusion
    ex = FFmpegFrameExtractorApp()
    ex.show()
    sys.exit(app.exec_())