import datetime
import pdfplumber # parse pdf
import re # regex
from google import  genai
import os
from dotenv import load_dotenv
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import time


load_dotenv()


#############################
#-------- Gemini API key initialisation --------#
#############################
my_key = os.getenv("GEMINI_API_KEY")  # Get API key from env variable
# Check if API key is loaded correctly
if not my_key:
    print("API Key is missing or not loaded correctly.")
else:
    try:
        # Initialize the client asynchronously
        async def init_client():
            client = genai.Client(api_key=my_key)
            return client
        
        # Run the initialization asynchronously
        loop = asyncio.new_event_loop()  # Create a new event loop
        asyncio.set_event_loop(loop)  # Set this loop as the current event loop
        
        # Now call the init_client function within the event loop
        client = loop.run_until_complete(init_client())  # Initialize the client
        print("Client initialized successfully!")
    except Exception as e:
        print(f"Error initializing client: {e}")


#############################
#-------- Gemini retry handling --------#
#############################
@retry(
    stop = stop_after_attempt(10),  # Retry up to 10 times
    wait = wait_exponential(multiplier = 1, min = 2, max = 10),  # Exponential "retry time" (2s, 4s, 8s...)
    retry = retry_if_exception_type(genai.errors.ClientError),
)
# To retry if exceeded usage quota
def generate_gemini_response(prompt):
    try:
        response = client.models.generate_content(
            model = 'gemini-2.0-flash',
            contents = prompt
        )
        return response.text
    except genai.errors.ClientError as e:
        error_message = str(e)
        if "RESOURCE_EXHAUSTED" in error_message:
            print("⚠️ API quota exceeded. Retrying...")
            raise e  # Explicitly re-raise the exception so that retry works
        else:
            print(f"⚠️ An unexpected client error occurred: {error_message}")
            raise e  # Don't retry if it's another error


this_year = int(datetime.date.today().year)


#############################
#-------- Functions --------#
#############################
# Function to extract text from PDF
def extract_text_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text

def extract_resume_sections(initial_resume):   
    prompt = f"""
    The following text is extracted from a resume and may be disorganized due to multi-column formatting. 
    Please identify and structure the key sections properly:

    Education
    Work Experience
    Skills
    
    If some information appears misplaced, attempt to logically reconstruct it.
    Return the sections as plain text and DO NOT use markdown formatting such as '**', '*', '-', '|', or bullet points.

    Resume Text:
    {initial_resume}

    Return the sections in an easy-to-read format.
    """
    try:
        # response = client.models.generate_content(
        #     model = 'gemini-2.0-flash',
        #     contents = prompt
        # )

        # # Ensure response is a string
        # if isinstance(response, str):
        #     response_text = response
        # elif hasattr(response, 'text'):
        #     response_text = response.text
        # else:
        #     response_text = str(response)

        response_text = generate_gemini_response(prompt)

        # Clean bullet points if necessary
        cleaned_text = re.sub(r"[-•]\s*", "", response_text)

        return cleaned_text
    
    except Exception as e:
        return f"Error processing resume: {str(e)}"


# Function to extract candidate name, email and phone
def extract_info(resume_text):
    prompt = f'''
        This is the candidate's resume:
        {resume_text}
        Extract the candidate's name, email address and phone number.
        Return the result **ONLY** as a valid Python dictionary. Do not include explanations, additional text, or markdown formatting.
        Phone numbers usually start with 65
        If the detail is not found, return None
        Example output:
        {{
            "name": "Linus Chia",
            "email": None,
            "phone": "6599990000"
        }}
        Now, return the dictionary:
    '''

    response = generate_gemini_response(prompt)
    
    # Extract dictionary-like content using regex
    match = re.search(r"\{.*\}", response, re.DOTALL) # Extract the part between { and }
    if match:
        clean_response = match.group(0)
    else:
        clean_response = response.strip()
    
    # Try to parse the cleaned response as a dictionary
    try:
        candidate_info = eval(clean_response)  # Convert string to dictionary
    except Exception as e:
        print(f"Error parsing response: {e}")
        candidate_info = {}


    return candidate_info


# Function to determine the start index of key sections
def get_section_indices(text):
    sections = {
        "Summary": None,
        "Work Experience": None,
        "Education": None,
        "Skills": None,
        "Projects": None,
        "Certifications": None
    }
    
    # Define the keywords for each section with
    section_keywords = {
        "Summary": r"(?m)^\s*(\w+\s+)?(summary|objective|profile)\s*$",
        "Work Experience": r"(?m)^\s*(work|job|professional)\s+experience(s)?\s*$",
        "Education": r"(?m)^\s*(education|academic|educational)\s*(and|&)?\s*(\w+\s+)?(background|history|qualifications|degree)?\s*$",
        "Skills": r"(?m)^\s*(\w+\s+)?skill(s)?(\s*\w+)?(\s*(and|&)\s*competencies)?\s*$",
        "Projects": r"(?m)^\s*(projects?)\s*$",
        "Certifications": r"(?m)^\s*(\w+\s+)?(certificates?|certifications?)\s*$"
        #(?m)^\s*(\w+\s+)?skill(s)?(\s*\w+)?(\s*(and|&)\s*competencies)?\s*$
    }
    
    # Loop through each section and search for the keyword
    for section, pattern in section_keywords.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            sections[section] = match.start()  # Get the start index of the match
    
    # Sort the sections by their start index in ascending order, ignoring sections with None
    sorted_sections = sorted(
        ((section, index) for section, index in sections.items() if index is not None),
        key = lambda x: x[1] #sort based on the 2nd value of the tuple, or the starting index
    )

    # Generate (section, start, end) tuples
    section_ranges = []
    for i in range(len(sorted_sections)):
        section_name, start_index = sorted_sections[i]
        end_index = sorted_sections[i + 1][1] if i + 1 < len(sorted_sections) else len(text)
        section_ranges.append((section_name, start_index, end_index))

    return section_ranges

# Function to extract year based on sections
def extract_year(section, resume_text):
    if section is None:
        return []  # Return an empty list if the section does not exist
    
    _, start_index, end_index = section  # Unpack the tuple
    years = []
    
    # Extract the relevant text portion
    section_text = resume_text[start_index:end_index]
    
    # Find all the years in the text, preserving the order
    pattern = r'''
        (\b(?:JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER|
        JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)?\s*(\d{4})\b)  # (1) Optional Month + (2) Year
        (?:\s*[-–—]?\s*|\s*to\s*)  # Tweaked Separator: Allows optional spaces before/after dash, or "to"
        (\b(?:JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER|
        JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)?\s*(\d{4})\b  # (3) Optional Month + (4) Year
        |\b(PRESENT|CURRENT)\b)  # (5) "PRESENT" or "CURRENT"
    '''

    # Apply regex with verbose mode for clarity
    matches = re.finditer(pattern, section_text, re.IGNORECASE | re.VERBOSE)
    
    for match in matches:
        start_year = int(match.group(2))  # First captured year
        end_year = match.group(4)  # Second year (may be None)
        present_keyword = match.group(5)  # 'PRESENT' or 'CURRENT' (may be None)

        if present_keyword:  
            end_year = this_year  # Convert "PRESENT" or "CURRENT" to current year
        elif end_year:
            end_year = int(end_year)  # Convert end year to integer

        years.append((start_year, end_year))

    if not years:
        standalone_pattern = r"\b(19|20)\d{2}\b"  # Corrected to capture the full year
        standalone_matches = re.finditer(standalone_pattern, section_text)
        
        # Add the standalone years to the result (we assume the latest one is the relevant year)
        for match in standalone_matches:
            year = match.group(0)  # Capture the full year
            match_start = match.start() + start_index  # Adjust for section's starting index
            match_end = match.end() + start_index  # Adjust for section's starting index

            years.append(int(year))

    return years

# Function to calculate years of experience based on sections
def calculate_experience(year_ranges):
    if not year_ranges:
        return 0  # No experience if no years available
    
    # Flatten the list to get all years (both start and end years)
    all_years = []

    for start_year, end_year in year_ranges:
        # Add both start year and end year (for range)
        all_years.append(start_year)
        if isinstance(end_year, int):
            all_years.append(end_year)

    # Calculate the minimum and maximum year
    min_year = min(all_years)
    max_year = max(all_years)
    
    # Calculate the total years of experience
    experience_years = max_year - min_year
    return experience_years

# Function to extract skills
def extract_skills(skills_section, resume_text, skills_required):

    # Extract text from skills section or full resume
    if skills_section:
        _, start_index, end_index = skills_section
        skills_text = resume_text[start_index:end_index]
    else:
        skills_text = resume_text

    # Clean up the text by removing newlines and excessive spaces
    skills_text = re.sub(r'\n', ' ', skills_text)  # Remove newline characters
    skills_text = re.sub(r'\s+', ' ', skills_text)  # Remove extra spaces
    skills_text = skills_text.lower()  # Convert to lowercase for case-insensitive search
    skills_text = skills_text.replace('-', ' ')  # Replace hyphens with spaces

    extracted_skills = []

    # Check each skill in the skills_required list
    for skill in skills_required:
        pattern = r'\b' + re.escape(skill.lower()) + r'\b' #  Use \b for word boundary to ensure it's a standalone skill
        if re.search(pattern, skills_text):
            extracted_skills.append(skill)

    return extracted_skills

# Function to extract mandatory skills and relevant years of experience
def extract_experience_for_skills(resume_text, skills_experience):   
    skills_experience_str = "\n".join([f"{skill}: {years}" for skill, years in skills_experience.items()])
    prompt = f'''
        This is the candidate's resume:
        {resume_text}
        Check if the candidate meets the required skills as specified in the format (skill: required years):
        {skills_experience_str}
        **STRICT REQUIREMENT:**  
        Return the result **ONLY** as a valid Python dictionary. Do not include explanations, additional text, or markdown formatting.
        Example output:
        {{
            "python": "meets",
            "java": "does not meet"
        }}
        Now, return the dictionary:
    '''

    response = generate_gemini_response(prompt)
    
    # Extract dictionary-like content using regex
    match = re.search(r"\{.*\}", response, re.DOTALL) # Extract the part between { and }
    if match:
        clean_response = match.group(0)
    else:
        clean_response = response.strip()
    
    # Try to parse the cleaned response as a dictionary
    try:
        skill_status = eval(clean_response)  # Convert string to dictionary
    except Exception as e:
        print(f"Error parsing response: {e}")
        skill_status = {}

    return skill_status
    
# Function to get highest education (can combine with meet_education_requirement but kept to ensure output is correct)
def get_highest_education(education_section, resume_text):
    # Extract text from education section or full resume
    if education_section:
        _, start_index, end_index = education_section
        education_text = resume_text[start_index:end_index]
    else:
        education_text = education_section

    # Define regex patterns for each degree
    degree_keywords = {
        'PhD': r'\b(?:PhD|Doctor of Philosophy)[^|]*',
        'Master': r'\b(?:Master(?:’s|s)?|MSc|MA|MEng|M\.B\.A\.|MBA)\b',
        'Bachelor': r'\b(?:Bachelor(?:’s|s)?|B\.?S\.?|BSc|BA|BEng|BBA)[^|]*',
        'Diploma': r'\b(?:Diploma|Associate)[^|]*'
    }

    # Check for degrees in order of hierarchy
    for degree, pattern in degree_keywords.items():
        if re.search(pattern, education_text, re.IGNORECASE):
            return degree

    return 'No degree found'


# Function to evaluate whether the candidate meets the requirement
def evaluate_candidate(extracted_info, required_info):
    requirement_check = []

    experience = extracted_info["experience"]
    highest_education = extracted_info["education"]
    skills = extracted_info["skills"]
    mandatory_skills_with_years = extracted_info["skills_met"]
    
    required_experience = required_info["experience"]
    required_education = required_info["education"]
    required_skills = required_info["skills"]


    # 1. Check work experience
    if experience < required_experience:
        requirement_check.append(0)
    else:
        requirement_check.append(1)


    # 2. Check education requirement
    education_order = ["Diploma", "Bachelor", "Master", "PhD"]
    if highest_education not in education_order or education_order.index(highest_education) < education_order.index(required_education):
        requirement_check.append(0)
    else:
        requirement_check.append(1)


    # 3. Check mandatory skills
    if mandatory_skills_with_years == "no_mandatory_skills":
        requirement_check.append(1)
    else: # Count the number of skills that meet the requirement
        num_met = sum(1 for status in mandatory_skills_with_years.values() if status == "meets")
        proportion_mandatory_skills_met = num_met / len(mandatory_skills_with_years) if mandatory_skills_with_years else 0
        requirement_check.append(proportion_mandatory_skills_met)

    # 4. Check proportion of skills
    proportion_skills_met = len(skills)/len(required_skills)
    requirement_check.append(proportion_skills_met)

    # 5. Number of skills met
    requirement_check.append(len(skills))

    return requirement_check 





# Prompt user to run ict619_resume_streamlit.py instead
if __name__ == "__main__":
    print("Run this as a module or use ict619_resumt_streamlit.py for UI.")