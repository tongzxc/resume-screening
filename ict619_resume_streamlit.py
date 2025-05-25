import streamlit as st
from streamlit_tags import st_tags
import time
from ict619_resume_functions import extract_text_from_pdf, get_section_indices, extract_skills, get_highest_education, extract_year, calculate_experience, extract_experience_for_skills, evaluate_candidate, extract_info, extract_resume_sections


# Streamlit UI
st.title("Resume Screening System")

#############################
#-------- UI inputs --------#
#############################
# User to input what is the min number of working years required
work_years_required = st.number_input(
    "Enter the minimum years of experience required:", 
    min_value = 0, 
    step = 1,
    format = "%d"
)

# User to select what is the min education required
education_required = st.selectbox(
    "Select the minimum education level required:", 
    ["Diploma", "Bachelor", "Master", "PhD"]
)

# User to input skills required for the role
skills_required = st_tags(
    label = "Enter skill(s):",
    text = "Press 'Enter' to add",
    value = [],  # Start with an empty list
)


# User to select specific skills from the entered skills
specific_skills_required = st.multiselect(
    "Select mandatory skill(s) required for the role:",
    options = skills_required,  # Populate dropdown with the entered skills
)


# Dictionary to store skill and years of experience
skills_experience = {}

# Allow user to enter years of experience for each selected skill
for skill in specific_skills_required:
    years = st.number_input(
        f"Years of experience required for {skill} (leave blank if not required):",
        min_value = 0, step = 1, value = None, format = "%d"
    )

    if years is None:
        years = 0
    
    skills_experience[skill] = years  # Store skill and experience

# Store the required info in a dictionary
required_info = {
    "experience": work_years_required,
    "education": education_required,
    "skills": skills_required,
    "mandatory_skills": skills_experience
}

# File uploader
uploaded_files = st.file_uploader("Upload your resume (PDF)", type=["pdf"], accept_multiple_files=True)


#############################
#-------- Evaluation --------#
#############################
# Force user to input at least 1 skill and 1 resume, otherwise do not show "Evaluate Resume(s)" button
if len(skills_required) == 0 or len(uploaded_files) == 0:
    if len(skills_required) == 0:
        st.warning("Please enter at least one skill before evaluating the resume.")
    if len(uploaded_files) == 0:
        st.warning("Please upload at least one resume.")
else:
    if st.button("Evaluate Resume(s)"):
        if uploaded_files:
            candidates_data = []
            progress_placeholder = st.empty()

            # Process each uploaded file
            for uploaded_file in uploaded_files:
                progress_placeholder.subheader(f"Evaluating {uploaded_file.name}")

                start_time = time.time()
                
                # Extract text from the current PDF
                initial_resume = extract_text_from_pdf(uploaded_file) # Using pdf plumber first
                resume_text = extract_resume_sections(initial_resume) # Pass text extracted to Gemini

                # Extract name, email and phone number
                candidate_info = extract_info(resume_text)

                # Extract education, work and skills section
                section_index = get_section_indices(resume_text)
                education_section = next((item for item in section_index if item[0] == "Education"), None)
                work_section = next((item for item in section_index if item[0] == "Work Experience"), None)
                skills_section = next((item for item in section_index if item[0] == "Skills"), None) # Find the tuple corresponding to "Skills"
                
                # Extract skills, highest education and working years from respective sections
                extracted_skills = extract_skills(skills_section, resume_text, skills_required)
                highest_education = get_highest_education(education_section, resume_text)
                work_years = extract_year(work_section, resume_text)
                working_experience = calculate_experience(work_years)

                # Extract experience for required skills using Gemini
                if skills_experience != {}:
                    skills_experience_from_resume = extract_experience_for_skills(resume_text, skills_experience)
                else: #  Handle if no mandatory skills entered
                    skills_experience_from_resume = "no_mandatory_skills"

                # Store extracted information
                extracted_info = {
                    "experience": working_experience,
                    "education": highest_education,
                    "skills": extracted_skills,
                    "skills_met": skills_experience_from_resume
                }


                # Evaluate candidate based on extracted info vs required info
                result = evaluate_candidate(             
                    extracted_info,
                    required_info
                )

                end_time = time.time()
                # Calculate processing time in seconds
                processing_time = end_time - start_time
                print("processing time for", candidate_info['name'], ":", processing_time, "s")
                print("----------")
                print("working experience:", working_experience, "years")
                print("education level:", highest_education)
                print("skills:", extracted_skills)
                print("mandatory skills met:", skills_experience_from_resume)
                print("===========================")
                
                # Ensure candidate meets mandatory criteria
                if result[:3] == [1, 1, 1.0]:  
                    candidates_data.append({
                        "info": candidate_info,
                        "skill_ratio": result[3], 
                        "no_of_skills": result[4],
                        "filename": uploaded_file.name
                    })

            # Results output
            progress_placeholder = progress_placeholder.subheader("The top 3 candidates that meet the following criteria:")
            if skills_experience_from_resume != "no_mandatory_skills":
                st.markdown(f"""
                    - **{work_years_required}** years of working experience  
                    - At least a **{education_required}** degree
                    - All mandatory skills **({', '.join(specific_skills_required)})** with the required experience level  
                    - Possess the highest number of additional relevant skills (out of **{len(required_info['skills'])}** skills)
                """)
            else:
                st.markdown(f"""
                    - **{work_years_required}** years of working experience  
                    - At least a **{education_required}** degree
                    - Possess the highest number of additional relevant skills (out of **{len(required_info['skills'])}** skills)
                """)
            st.markdown("___")
            # Sort candidates by skill_ratio in descending order
            top_candidates = sorted(candidates_data, key=lambda c: c["skill_ratio"], reverse=True)

            # Select the top 3 candidates
            selected_candidates = top_candidates[:3]

            # Display final selected candidates (only once)
            if selected_candidates:
                for candidate in selected_candidates:
                    st.write(f"✅ {candidate['filename']} | {candidate['info']['name']} | {candidate['info']['email']} | {candidate['info']['phone']} | Number of skills: {candidate['no_of_skills']}/{len(required_info['skills'])}")
            else:
                st.write("❌ No candidates meet the criteria.")

