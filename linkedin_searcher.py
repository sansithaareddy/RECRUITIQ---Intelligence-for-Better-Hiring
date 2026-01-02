# ==================== scraper/linkedin_searcher.py ====================
"""
Handles LinkedIn search and profile URL collection
"""

# ==================== scraper/linkedin_searcher.py ====================
"""
Handles LinkedIn search and profile URL collection
"""

import time
import random
import sys
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from config import *
except ImportError:
    # Fallback values if config.py cannot be imported
    PAGES_TO_SCRAPE = 5
    DELAY_BETWEEN_PAGES = (3, 5)
    DELAY_AFTER_SEARCH = 3
    DELAY_AFTER_CLICK = 2


def random_delay(min_sec, max_sec):
    """Sleep for random duration"""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)


def search_linkedin(driver, wait, search_term):
    """
    Perform LinkedIn search and navigate to People tab
    
    Args:
        driver: Selenium WebDriver instance
        wait: WebDriverWait instance
        search_term: Search query string
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        print(f"🔍 Searching LinkedIn for: '{search_term}'")
        
        # Go to LinkedIn homepage
        driver.get("https://www.linkedin.com/feed/")
        time.sleep(3)
        
        # Find search box and enter search term
        search_box = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='Search']"))
        )
        search_box.clear()
        search_box.send_keys(search_term)
        search_box.send_keys(Keys.RETURN)
        
        time.sleep(DELAY_AFTER_SEARCH)
        
        # Click on "People" tab
        print("👥 Navigating to People tab...")
        people_button_xpaths = [
            "//button[contains(text(), 'People')]",
            "//button[contains(@aria-label, 'People')]",
            "//a[contains(text(), 'People')]",
            "//button[contains(., 'People')]"
        ]
        
        people_button = None
        for xpath in people_button_xpaths:
            try:
                people_button = driver.find_element(By.XPATH, xpath)
                break
            except:
                continue
        
        if people_button:
            driver.execute_script("arguments[0].click();", people_button)
            time.sleep(3)
            print("✅ Successfully navigated to People results")
            return True
        else:
            print("⚠️ Could not find People tab - may already be on people results")
            return True
            
    except Exception as e:
        print(f"❌ Error during search: {e}")
        return False


def collect_profile_urls_from_page(driver):
    """
    Collect all profile URLs from current search results page
    
    Args:
        driver: Selenium WebDriver instance
    
    Returns:
        list: List of profile URLs found on page
    """
    profile_urls = []
    
    try:
        # Scroll to load all results
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
        
        # Find all profile links
        # LinkedIn profile URLs typically contain '/in/'
        link_elements = driver.find_elements(By.TAG_NAME, "a")
        
        for link in link_elements:
            try:
                href = link.get_attribute("href")
                if href and "/in/" in href and "linkedin.com/in/" in href:
                    # Clean URL (remove query parameters)
                    base_url = href.split("?")[0]
                    # Remove trailing slash
                    base_url = base_url.rstrip("/")
                    
                    # Avoid duplicates and non-profile links
                    if base_url not in profile_urls and base_url.count("/in/") == 1:
                        profile_urls.append(base_url)
            except:
                continue
        
        # Remove duplicates and sort
        profile_urls = list(set(profile_urls))
        
        print(f"   📋 Found {len(profile_urls)} profile URLs on this page")
        
    except Exception as e:
        print(f"   ⚠️ Error collecting URLs: {e}")
    
    return profile_urls


def click_next_page(driver, wait):
    """
    Click the 'Next' button to go to next page of search results
    
    Args:
        driver: Selenium WebDriver instance
        wait: WebDriverWait instance
    
    Returns:
        bool: True if successful, False if no next page
    """
    try:
        # Common XPaths for 'Next' button
        next_button_xpaths = [
            "//button[contains(@aria-label, 'Next')]",
            "//button[contains(text(), 'Next')]",
            "//a[contains(@aria-label, 'Next')]",
            "//button[contains(@class, 'artdeco-pagination__button--next')]"
        ]
        
        next_button = None
        for xpath in next_button_xpaths:
            try:
                next_button = driver.find_element(By.XPATH, xpath)
                # Check if button is enabled (not disabled)
                if next_button.is_enabled():
                    break
                else:
                    next_button = None
            except:
                continue
        
        if next_button:
            driver.execute_script("arguments[0].click();", next_button)
            random_delay(*DELAY_BETWEEN_PAGES)
            print("   ➡️  Moved to next page")
            return True
        else:
            print("   ℹ️ No more pages available")
            return False
            
    except Exception as e:
        print(f"   ⚠️ Could not navigate to next page: {e}")
        return False


def collect_all_profile_urls(driver, wait, search_term, pages=PAGES_TO_SCRAPE):
    """
    Collect profile URLs from multiple pages of search results
    
    Args:
        driver: Selenium WebDriver instance
        wait: WebDriverWait instance
        search_term: Search query
        pages: Number of pages to scrape
    
    Returns:
        list: All collected profile URLs
    """
    all_urls = []
    
    # Perform search
    if not search_linkedin(driver, wait, search_term):
        print("❌ Failed to perform search")
        return all_urls
    
    print(f"\n📊 Collecting profile URLs from {pages} pages...")
    
    for page_num in range(1, pages + 1):
        print(f"\n📄 Page {page_num}/{pages}")
        
        # Collect URLs from current page
        urls = collect_profile_urls_from_page(driver)
        all_urls.extend(urls)
        
        # Go to next page (if not last page)
        if page_num < pages:
            if not click_next_page(driver, wait):
                print("⚠️ Reached end of search results early")
                break
    
    # Remove duplicates
    all_urls = list(set(all_urls))
    
    print(f"\n✅ Total unique profile URLs collected: {len(all_urls)}")
    
    return all_urls