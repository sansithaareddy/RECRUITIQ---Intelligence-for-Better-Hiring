# ==================== main.py ====================
"""
Advanced LinkedIn Multi-Profile Scraper with JD Matching and Experience Filter
"""

import os
import json
import random
import time
from pathlib import Path
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from crewai import Agent, Task, Crew, LLM

# Import config and scrapers
from config import *
from scraper.linkedin_searcher import collect_all_profile_urls
from scraper.scraper import scrape_single_profile

# Silence LiteLLM noise
os.environ["LITELLM_LOG"] = "ERROR"

load_dotenv()


# ==================== HELPER FUNCTIONS ====================

def ensure_output_dir():
    """Create output directory if it doesn't exist"""
    Path(OUTPUT_DIR).mkdir(exist_ok=True)


def load_progress():
    """Load progress from previous run"""
    if os.path.exists(PROGRESS_JSON):
        with open(PROGRESS_JSON, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def save_progress(search_term, job_description, profile_limit, min_experience, all_urls, completed_urls):
    """Save current progress"""
    progress = {
        "search_term": search_term,
        "job_description": job_description,
        "profile_limit": profile_limit,
        "min_experience": min_experience,
        "total_urls": len(all_urls),
        "completed_urls": completed_urls,
        "remaining_urls": [url for url in all_urls if url not in completed_urls]
    }
    with open(PROGRESS_JSON, 'w', encoding='utf-8') as f:
        json.dump(progress, f, indent=2)


def load_json_file(filepath):
    """Load existing JSON file"""
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_to_json(filepath, data):
    """Save data to JSON file"""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def append_to_json(filepath, new_data):
    """Append new data to JSON file"""
    existing_data = load_json_file(filepath)
    existing_data.append(new_data)
    save_to_json(filepath, existing_data)


def log_failed_url(url, error):
    """Log failed profile URL"""
    with open(FAILED_URLS_LOG, 'a', encoding='utf-8') as f:
        f.write(f"{url} | Error: {error}\n")


def get_multiline_input(prompt):
    """Get multi-line input from user"""
    print(prompt)
    print("(Press Enter twice when done)")
    lines = []
    empty_count = 0
    
    while True:
        line = input()
        if line == "":
            empty_count += 1
            if empty_count >= 2:
                break
        else:
            empty_count = 0
            lines.append(line)
    
    return "\n".join(lines)


def setup_driver():
    """Initialize Chrome WebDriver"""
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument(f"--user-data-dir={CHROME_PROFILE_PATH}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 30)
    
    return driver, wait


def login_to_linkedin(driver, wait):
    """Log in to LinkedIn"""
    EMAIL = os.getenv("EMAIL")
    PASSWORD = os.getenv("PASSWORD")

    if not EMAIL or not PASSWORD:
        raise Exception("EMAIL or PASSWORD missing in .env")

    print("🔐 Logging in to LinkedIn...")
    driver.get("https://www.linkedin.com/login")

    try:
        username_field = wait.until(EC.presence_of_element_located((By.ID, "username")))
        username_field.send_keys(EMAIL)
        driver.find_element(By.ID, "password").send_keys(PASSWORD + Keys.RETURN)
        time.sleep(5)
        print("✅ Login successful\n")
    except:
        print("ℹ️ Already logged in\n")


def setup_ai_agents():
    """Initialize AI agents"""
    llm = LLM(
        model=AI_MODEL,
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=AI_TEMPERATURE
    )

    # Agent 1: Profile Extractor
    profile_extractor = Agent(
        role="LinkedIn Profile Data Extractor",
        goal="Extract structured information from LinkedIn profile HTML including years of experience",
        backstory="""You are an expert at parsing LinkedIn profiles and extracting 
        key information like name, headline, experience, education, skills, and 
        calculating total years of professional experience.""",
        llm=llm,
        verbose=False
    )

    # Agent 2: Profile Structurer
    profile_structurer = Agent(
        role="Profile Data Structurer",
        goal="Convert extracted data into clean JSON format with experience calculation",
        backstory="""You organize profile information into structured JSON format 
        and calculate total years of experience based on all job roles.""",
        llm=llm,
        verbose=False
    )

    # Agent 3: JD Matcher
    jd_matcher = Agent(
        role="Job Description Matching Specialist",
        goal="Analyze how well a profile matches a job description",
        backstory="""You are an expert recruiter who evaluates candidate profiles 
        against job descriptions. You assess skills match, experience relevance, 
        and overall fit, providing detailed scoring and reasoning.""",
        llm=llm,
        verbose=False
    )

    return profile_extractor, profile_structurer, jd_matcher


def extract_profile_data(page_text, profile_extractor, profile_structurer):
    """Extract and structure profile data using AI"""
    
    truncated_text = page_text[:MAX_HTML_LENGTH]
    
    # Task 1: Extract data
    extraction_task = Task(
        description=f"""
Extract the following from this LinkedIn profile:
- Name
- Headline
- Location
- Open to Work (true/false)
- Experience (all roles with company, duration, description)
- Education (all entries with degree, institution, duration)
- Skills (all skills listed)
- **Total Years of Experience** (calculate by adding up all job durations)

For experience calculation:
- Look at all job roles and their durations
- Add them up to get total years
- If dates overlap (multiple jobs at once), count once
- If "Present" or "Current", calculate to today
- Return as a number (e.g., 5.5 for 5 years 6 months)

Profile text:
{truncated_text}

Return extracted data in structured format.
""",
        expected_output="Structured extracted data with total years of experience",
        agent=profile_extractor
    )

    # Task 2: Structure as JSON
    structuring_task = Task(
        description="""
Convert the extracted data into this JSON structure:
{{
  "name": "Full Name",
  "headline": "Professional headline",
  "location": "City, Country",
  "open_to_work": true/false,
  "total_years_experience": 5.5,
  "experience": [
    {{"role": "Title", "company": "Company", "duration": "Dates", "description": "What they did"}}
  ],
  "education": [
    {{"degree": "Degree", "institution": "School", "duration": "Dates"}}
  ],
  "skills": ["skill1", "skill2", "skill3"]
}}

IMPORTANT: 
- total_years_experience must be a NUMBER (not a string)
- Calculate it by adding up all job durations
- If you cannot calculate, set it to 0

Return ONLY valid JSON, no extra text.
""",
        expected_output="Clean JSON profile data with years of experience",
        agent=profile_structurer,
        context=[extraction_task]
    )

    crew = Crew(
        agents=[profile_extractor, profile_structurer],
        tasks=[extraction_task, structuring_task],
        verbose=False
    )

    result = crew.kickoff()
    
    # Parse JSON
    try:
        result_str = str(result)
        start = result_str.find('{')
        end = result_str.rfind('}') + 1
        json_str = result_str[start:end]
        profile_json = json.loads(json_str)
        
        # Ensure total_years_experience exists and is a number
        if "total_years_experience" not in profile_json:
            profile_json["total_years_experience"] = 0
        else:
            try:
                profile_json["total_years_experience"] = float(profile_json["total_years_experience"])
            except:
                profile_json["total_years_experience"] = 0
        
        return profile_json
    except:
        return {
            "raw_output": str(result),
            "total_years_experience": 0
        }


def match_profile_to_jd(profile_data, job_description, jd_matcher):
    """Match profile against job description and generate score"""
    
    profile_summary = f"""
Name: {profile_data.get('name', 'Unknown')}
Headline: {profile_data.get('headline', 'N/A')}
Total Years of Experience: {profile_data.get('total_years_experience', 0)} years
Skills: {', '.join(profile_data.get('skills', []))}
Experience: {json.dumps(profile_data.get('experience', []), indent=2)}
Education: {json.dumps(profile_data.get('education', []), indent=2)}
"""
    
    matching_task = Task(
        description=f"""
Analyze how well this candidate profile matches the job description.

JOB DESCRIPTION:
{job_description}

CANDIDATE PROFILE:
{profile_summary}

Provide your analysis in this EXACT JSON format:
{{
  "match_score": <number from 0-10>,
  "matching_skills": ["skill1", "skill2"],
  "missing_skills": ["skill3", "skill4"],
  "experience_relevance": "<brief assessment of experience fit>",
  "overall_assessment": "<2-3 sentence summary of why this score>"
}}

Scoring guide:
- 9-10: Exceptional match, has most key skills and highly relevant experience
- 7-8: Strong match, has many required skills with relevant experience
- 5-6: Moderate match, has some skills but missing key requirements
- 3-4: Weak match, limited relevant skills or experience
- 0-2: Poor match, does not meet basic requirements

Return ONLY the JSON, no extra text.
""",
        expected_output="JSON with match analysis",
        agent=jd_matcher
    )

    crew = Crew(
        agents=[jd_matcher],
        tasks=[matching_task],
        verbose=False
    )

    result = crew.kickoff()
    
    # Parse JSON
    try:
        result_str = str(result)
        start = result_str.find('{')
        end = result_str.rfind('}') + 1
        json_str = result_str[start:end]
        match_json = json.loads(json_str)
        return match_json
    except:
        return {
            "match_score": 0,
            "matching_skills": [],
            "missing_skills": [],
            "experience_relevance": "Error parsing match result",
            "overall_assessment": str(result)
        }


# ==================== MAIN WORKFLOW ====================

def main():
    print("="*70)
    print("🚀 ADVANCED LINKEDIN SCRAPER WITH JD MATCHING")
    print("="*70 + "\n")
    
    ensure_output_dir()
    
    # Check for existing progress
    progress = load_progress()
    
    if progress:
        print(f"📂 Found previous run:")
        print(f"   Search term: '{progress['search_term']}'")
        print(f"   Profile limit: {progress['profile_limit']}")
        print(f"   Min experience: {progress['min_experience']} years")
        print(f"   Completed: {len(progress['completed_urls'])}/{progress['total_urls']}")
        print(f"   Remaining: {len(progress['remaining_urls'])}")
        
        resume = input("\n❓ Resume from previous run? (y/n): ").strip().lower()
        
        if resume == 'y':
            search_term = progress['search_term']
            job_description = progress['job_description']
            profile_limit = progress['profile_limit']
            min_experience = progress['min_experience']
            all_urls = progress['completed_urls'] + progress['remaining_urls']
            completed_urls = progress['completed_urls']
            print(f"✅ Resuming scrape...\n")
        else:
            search_term = None
            job_description = None
            profile_limit = None
            min_experience = None
            all_urls = []
            completed_urls = []
    else:
        search_term = None
        job_description = None
        profile_limit = None
        min_experience = None
        all_urls = []
        completed_urls = []
    
    # Get user inputs (if starting fresh)
    if not search_term:
        search_term = input("🔍 Enter LinkedIn search term: ").strip()
        if not search_term:
            print("❌ Search term cannot be empty!")
            return
        
        profile_limit = input("📊 How many profiles to scrape?: ").strip()
        try:
            profile_limit = int(profile_limit)
            if profile_limit <= 0:
                print("❌ Number must be positive!")
                return
        except:
            print("❌ Invalid number!")
            return
        
        min_experience_input = input("⏱️  Minimum years of experience (0 for no filter): ").strip()
        try:
            min_experience = float(min_experience_input)
            if min_experience < 0:
                print("❌ Experience cannot be negative!")
                return
        except:
            print("❌ Invalid number!")
            return
        
        print("\n📝 Enter Job Description:")
        job_description = get_multiline_input("")
        
        if not job_description.strip():
            print("❌ Job description cannot be empty!")
            return
        
        print(f"\n✅ Configuration saved:")
        print(f"   Search: '{search_term}'")
        print(f"   Profiles: {profile_limit}")
        print(f"   Min Experience: {min_experience} years")
        print(f"   JD length: {len(job_description)} characters\n")
    
    # Setup
    driver, wait = setup_driver()
    profile_extractor, profile_structurer, jd_matcher = setup_ai_agents()
    
    # Counters for experience filter
    filtered_by_experience_count = 0
    
    try:
        # Login
        login_to_linkedin(driver, wait)
        
        # Collect URLs (if not resuming)
        if not all_urls:
            # Calculate how many pages we need
            pages_needed = min(PAGES_TO_SCRAPE, (profile_limit // PROFILES_PER_PAGE) + 1)
            all_urls = collect_all_profile_urls(driver, wait, search_term, pages_needed)
            
            if not all_urls:
                print("❌ No profile URLs collected!")
                return
            
            # Limit to user's requested number
            all_urls = all_urls[:profile_limit]
        
        # Calculate remaining URLs
        remaining_urls = [url for url in all_urls if url not in completed_urls]
        
        print(f"\n{'='*70}")
        print(f"📊 SCRAPING SUMMARY")
        print(f"{'='*70}")
        print(f"Total profiles to scrape: {len(remaining_urls)}")
        print(f"Already completed: {len(completed_urls)}")
        print(f"Experience filter: ≥{min_experience} years")
        print(f"{'='*70}\n")
        
        # Scrape each profile
        for idx, url in enumerate(remaining_urls, start=len(completed_urls) + 1):
            print(f"\n{'='*70}")
            print(f"📄 Profile {idx}/{len(all_urls)}")
            print(f"{'='*70}")
            print(f"🔗 URL: {url}")
            
            # Scrape HTML
            print("🌐 Scraping profile HTML...")
            profile_raw = scrape_single_profile(driver, url, wait)
            
            if not profile_raw["success"]:
                print(f"❌ Failed to scrape: {profile_raw['error']}")
                log_failed_url(url, profile_raw['error'])
                completed_urls.append(url)
                save_progress(search_term, job_description, profile_limit, min_experience, all_urls, completed_urls)
                continue
            
            print(f"✅ HTML scraped for: {profile_raw.get('name', 'Unknown')}")
            
            # Extract profile data
            print("🤖 Extracting profile data with AI...")
            try:
                profile_data = extract_profile_data(
                    profile_raw["page_text"],
                    profile_extractor,
                    profile_structurer
                )
                
                profile_data["url"] = url
                profile_data["scraped_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                
                # Check experience filter
                years_exp = profile_data.get("total_years_experience", 0)
                print(f"📊 Total Experience: {years_exp} years")
                
                # Save to all_profiles.json
                append_to_json(ALL_PROFILES_JSON, profile_data)
                print(f"💾 Saved to {ALL_PROFILES_JSON}")
                
                # Apply experience filter
                if years_exp < min_experience:
                    print(f"⚠️ FILTERED: Experience ({years_exp} yrs) below minimum ({min_experience} yrs)")
                    filtered_by_experience_count += 1
                    completed_urls.append(url)
                    save_progress(search_term, job_description, profile_limit, min_experience, all_urls, completed_urls)
                    continue
                
                print(f"✅ Passed experience filter ({years_exp} ≥ {min_experience} years)")
                
                # Save to filtered profiles
                append_to_json(FILTERED_PROFILES_JSON, profile_data)
                
            except Exception as e:
                print(f"❌ Profile extraction failed: {e}")
                log_failed_url(url, f"Extraction error: {e}")
                completed_urls.append(url)
                save_progress(search_term, job_description, profile_limit, min_experience, all_urls, completed_urls)
                continue
            
            # Match against JD (only if passed experience filter)
            print("🎯 Matching against job description...")
            try:
                match_result = match_profile_to_jd(profile_data, job_description, jd_matcher)
                
                match_score = match_result.get("match_score", 0)
                print(f"📊 Match Score: {match_score}/10")
                
                # Create detailed match record
                match_detail = {
                    "url": url,
                    "name": profile_data.get("name", "Unknown"),
                    "total_years_experience": years_exp,
                    "match_score": match_score,
                    "matching_skills": match_result.get("matching_skills", []),
                    "missing_skills": match_result.get("missing_skills", []),
                    "experience_relevance": match_result.get("experience_relevance", ""),
                    "overall_assessment": match_result.get("overall_assessment", ""),
                    "evaluated_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                
                # Save to match_details.json
                append_to_json(MATCH_DETAILS_JSON, match_detail)
                
                # If match score >= threshold, save to matched_profiles.json
                if match_score >= MATCH_THRESHOLD:
                    matched_profile = profile_data.copy()
                    matched_profile["match_score"] = match_score
                    matched_profile["match_details"] = match_result
                    append_to_json(MATCHED_PROFILES_JSON, matched_profile)
                    print(f"✅ STRONG MATCH! Saved to {MATCHED_PROFILES_JSON}")
                else:
                    print(f"ℹ️ Score below threshold ({MATCH_THRESHOLD}), not added to matches")
                
            except Exception as e:
                print(f"❌ Matching failed: {e}")
                log_failed_url(url, f"Matching error: {e}")
            
            # Mark as completed
            completed_urls.append(url)
            save_progress(search_term, job_description, profile_limit, min_experience, all_urls, completed_urls)
            
            # Random delay
            if idx < len(all_urls):
                delay = random.uniform(*DELAY_BETWEEN_PROFILES)
                print(f"⏳ Waiting {delay:.1f} seconds...")
                time.sleep(delay)
        
        # Final summary
        print(f"\n{'='*70}")
        print(f"✅ SCRAPING COMPLETE!")
        print(f"{'='*70}")
        
        all_profiles = load_json_file(ALL_PROFILES_JSON)
        filtered_profiles = load_json_file(FILTERED_PROFILES_JSON)
        matched_profiles = load_json_file(MATCHED_PROFILES_JSON)
        match_details = load_json_file(MATCH_DETAILS_JSON)
        
        print(f"Total profiles scraped: {len(all_profiles)}")
        print(f"Filtered by experience (<{min_experience} yrs): {filtered_by_experience_count}")
        print(f"Passed experience filter: {len(filtered_profiles)}")
        print(f"Matched JD requirements (≥{MATCH_THRESHOLD}/10): {len(matched_profiles)}")
        print(f"\n📁 Output files:")
        print(f"   • All profiles: {ALL_PROFILES_JSON}")
        print(f"   • Filtered by experience: {FILTERED_PROFILES_JSON}")
        print(f"   • Matched profiles: {MATCHED_PROFILES_JSON}")
        print(f"   • Match details: {MATCH_DETAILS_JSON}")
        print(f"   • Failed URLs: {FAILED_URLS_LOG}")
        print(f"{'='*70}\n")
        
        # Clean up progress file
        if os.path.exists(PROGRESS_JSON):
            os.remove(PROGRESS_JSON)
            print("🧹 Progress file cleaned up\n")
    
    except KeyboardInterrupt:
        print("\n\n⚠️ Scraping interrupted by user!")
        print(f"📊 Progress saved. Run again to resume.")
        save_progress(search_term, job_description, profile_limit, min_experience, all_urls, completed_urls)
    
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        save_progress(search_term, job_description, profile_limit, min_experience, all_urls, completed_urls)
    
    finally:
        driver.quit()
        print("🔚 Browser closed")


if __name__ == "__main__":
    main()