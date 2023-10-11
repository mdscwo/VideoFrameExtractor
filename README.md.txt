# VidFrameFetcher 1.0

VidFrameFetcher is a GUI-based tool designed to extract frames from videos at specified intervals. It provides a user-friendly interface, GPU acceleration support, and real-time previews of the extracted frames.

![VidFrameFetcher Screenshot](./screenshot.png)  <!-- You can add a screenshot of your application here -->

## Features

- **Intuitive User Interface**: Easily select video files, set output directories, and configure extraction settings.
- **GPU Acceleration**: Speed up the extraction process using GPU acceleration (Beta).
- **Real-time Previews**: View the first and last frames extracted in real-time.
- **Drag and Drop**: Conveniently drag and drop video files directly into the application.
- **Dark Mode**: Switch to dark mode for a different look and feel.
- **Logging**: Detailed logs for troubleshooting and monitoring.

## Installation

1. Download the latest release from the [Releases](#) page. <!-- Update with your GitHub releases link -->
2. Extract the `.zip` file.
3. Run `VidFrameFetcher.exe`.

## Usage

1. **Select a Video**: Click on the browse button next to the "Video Path" field or drag and drop a video file into the application.
2. **Set Output Directory**: Choose where you want the extracted frames to be saved.
3. **Configure Settings**: Adjust the extraction interval, output format, resolution, and other settings as needed.
4. **Start Extraction**: Click on the "Start Extraction" button.
5. **Monitor Progress**: View the extraction progress, elapsed time, and time remaining.
6. **View Results**: Once extraction is complete, click on "Open Directory" to view the extracted frames.

## Requirements

- Windows 10 or newer.
- [K-Lite Video Codec](https://codecguide.com/download_kl.htm)
- For GPU acceleration, a compatible GPU and driver are required.

For developers, see `requirements.txt` for Python library dependencies.

## Development

To set up a development environment:

1. Clone the repository.
2. Install the required Python libraries: `pip install -r requirements.txt`
3. Run `VidFrameFetcher 1.0.py`.

## Contributing

Contributions are welcome! Please read our [Contributing Guide](#) for more information. <!-- Update with a link to your contributing guide if you have one -->

## License

This project is licensed under the MIT License. See the [LICENSE](#) file for details. <!-- Update with a link to your license file if you have one -->

