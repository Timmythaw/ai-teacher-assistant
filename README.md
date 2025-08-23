# AI Teacher Assistant

A comprehensive AI-powered teaching assistant that helps educators with various tasks including PDF assessment generation and Google Forms data extraction.

## Features

### PDF Assessment Generation
- Upload PDF documents and generate various types of assessments
- Support for MCQ, essay questions, and rubrics
- Configurable difficulty levels and question counts

### Google Forms Integration
- Fetch Google Forms and extract all responses
- Export responses in CSV format
- Support for both form links and form IDs
- Optional UTF-8 BOM for Excel compatibility

## Setup

### Prerequisites
- Python 3.12+
- Google Cloud Platform account with Forms API enabled
- Google OAuth credentials

### Installation
1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set up Google credentials (see Google Setup section)

### Google Setup
1. Enable Google Forms API in Google Cloud Console
2. Create OAuth 2.0 credentials
3. Download `credentials.json` and place in project root
4. Run the application once to authenticate and generate `token.pickle`

## Usage

### Web Interface
- Start the Flask app: `python app.py`
- Access PDF upload: `http://localhost:5000/`
- Access Forms fetcher: `http://localhost:5000/forms`

### API Endpoints

#### PDF Assessment
- `POST /upload` - Upload PDF and generate assessment

#### Google Forms
- `GET /forms` - Forms fetcher web interface
- `POST /forms/fetch` - Fetch form data and return CSV
- `GET /forms/fetch?form_link=<url>` - Fetch form via GET request

### Command Line Testing
Run the test script to verify functionality:
```bash
python test_forms.py
```

## Project Structure
```
ai-teacher-assistant/
├── app.py                 # Main Flask application
├── core/                  # Core functionality
│   ├── google_client.py   # Google API authentication
│   ├── logger.py          # Logging configuration
│   └── config.py          # Configuration settings
├── integrations/          # External service integrations
│   ├── form_response.py   # Google Forms main logic
│   ├── forms_fetch.py     # Forms API calls
│   ├── form_render.py     # CSV generation
│   └── form_utils.py      # Utility functions
├── agents/                # AI agent implementations
├── templates/             # HTML templates
│   ├── upload.html        # PDF upload interface
│   └── forms.html         # Forms fetcher interface
└── test_forms.py          # Testing script
```

## API Response Format

### Google Forms Response
```json
{
  "ok": true,
  "form_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptLL74jvcn0V3dK4",
  "form_title": "Sample Form",
  "num_questions": 5,
  "num_responses": 25,
  "csv_content": "Timestamp,Question 1,Question 2...",
  "csv_size": 1024
}
```

## Contributing
Please read the contributing guidelines before submitting pull requests.

## License
This project is licensed under the MIT License.
