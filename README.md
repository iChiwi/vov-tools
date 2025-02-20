# Voice of Valrise

Voice of Valrise is a web application that allows users to interact with Spotify to manage a song queue and process song requests. Built using Flask, this application provides a user-friendly interface for logging in with Spotify credentials and viewing the current song queue and console logs.

## Features

- User authentication with Spotify
- Real-time song queue management
- Console logging for tracking song requests and application status
- Responsive design with a clean user interface

## Project Structure

```
voice-of-valrise
├── production
│   ├── app.py               # Main application file
│   ├── static
│   │   └── styles.css       # CSS styles for the web application
│   └── templates
│       └── index.html       # Main HTML template
├── requirements.txt          # Python dependencies
├── .gitignore                # Files and directories to ignore in Git
└── README.md                 # Project documentation
```

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/iChiwi/vov-tools.git
   cd voice-of-valrise
   ```

2. Create a virtual environment (optional but recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up your Spotify Developer account and create an application to obtain your Client ID and Client Secret. Update the `app.py` file with your credentials.

## Usage

1. Run the application:
   ```
   python app.py
   ```

2. Open your web browser and navigate to `http://localhost:5000`.

3. Log in using your Spotify credentials and start managing your song queue!

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.
