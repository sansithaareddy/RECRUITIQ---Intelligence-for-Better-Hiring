# ==================== config.py ====================
"""
Configuration settings for LinkedIn scraper
"""

# Scraping settings
PAGES_TO_SCRAPE = 10  # Maximum pages to search (will stop early if user limit reached)
PROFILES_PER_PAGE = 10  # LinkedIn typically shows ~10 profiles per page

# Matching settings
MATCH_THRESHOLD = 7  # Minimum score (out of 10) to be considered a match
MIN_EXPERIENCE_YEARS = 0  # Will be set by user input (0 = no filter)

# Delay settings (in seconds)
DELAY_BETWEEN_PROFILES = (5, 10)  # Random delay between (min, max)
DELAY_BETWEEN_PAGES = (3, 5)      # Random delay between pages
DELAY_AFTER_SEARCH = 3            # Delay after performing search
DELAY_AFTER_CLICK = 2             # Delay after clicking elements

# File paths
OUTPUT_DIR = "output"
ALL_PROFILES_JSON = "output/all_profiles.json"
MATCHED_PROFILES_JSON = "output/matched_profiles.json"
MATCH_DETAILS_JSON = "output/match_details.json"
FILTERED_PROFILES_JSON = "output/filtered_by_experience.json"
PROGRESS_JSON = "output/progress.json"
FAILED_URLS_LOG = "output/failed_urls.txt"

# Chrome settings
CHROME_PROFILE_PATH = r"C:\selenium_chrome_profile"

# AI settings
AI_MODEL = "groq/llama-3.1-8b-instant"
AI_TEMPERATURE = 0

# Scraping behavior
SKIP_FAILED_PROFILES = True       # Continue if a profile fails
SAVE_AFTER_EACH_PROFILE = True    # Save progress after each profile
MAX_RETRIES_PER_PROFILE = 1       # Retry failed profiles once

# HTML truncation (to fit token limits)
MAX_HTML_LENGTH = 15000  # Characters of HTML to send to AI