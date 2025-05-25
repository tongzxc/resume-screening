# AI-Powered Resume Screening System

A web-based tool designed to help recruiters automate resume screening using a combination of rule-based logic and Google Gemini LLM. The system extracts and evaluates candidate information such as work experience, education, and skill set from uploaded PDF resumes, and ranks top candidates based on match accuracy.


## 🔧 Features

✉️ Extracts candidate name, email, and phone number

💼 Computes total years of working experience

✅ Matches required and mandatory skills with optional year thresholds

⚖️ Evaluates education level based on highest degree

⬆️ Ranks top 3 candidates by match strength and skill coverage

⚙ Handles structured and unstructured (multi-column) resumes using Gemini LLM

⏳ Displays processing time for each resume

## 🚀 Getting Started
### Prerequisites
1. Python 3.9+
2. A browser to run Streamlit
3. Google Gemini API key (get it here)

## Installation
```# Clone the repo
git clone https://github.com/yourusername/resume-screening.git
cd resume-screening

# Create and activate a virtual environment
python3 -m venv myenv
source myenv/bin/activate     # On Windows: myenv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Add your Gemini API key
cp .env.example .env
# Edit .env to include:
# GEMINI_API_KEY=your_api_key_here

# Run the Streamlit app
streamlit run ict619_resume_streamlit.py
```

## 📂 Repository Structure
```
resume-screening/
├── ict619_resume_streamlit.py         # Streamlit UI logic
├── ict619_resume_functions.py         # Core logic and Gemini API calls
├── .env.example                       # Template for environment variables
├── requirements.txt                   # Python dependencies
└── README.md
```
## 📊 Sample Use

1. Enter minimum working experience and education level
2. Add required and mandatory skills (with optional years)
3. Upload one or more PDF resumes
4. Click "Evaluate Resume(s)"
5. View top 3 matched candidates and their breakdowns

## ⚠️ Notes on API Limits

This project uses Gemini LLM (free tier). If you process many resumes or large documents, you may hit API quota limits.

Retry logic is implemented with exponential backoff

For heavier usage, consider upgrading to a paid API plan

