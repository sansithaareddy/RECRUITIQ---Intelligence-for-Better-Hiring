# ==================== scraper/scraper.py ====================
"""
Scrapes individual LinkedIn profile HTML
"""

import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def slow_scroll(driver, rounds=5):
    """Scroll page slowly to load dynamic content"""
    for _ in range(rounds):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)


def click_show_all_sections(driver):
    """
    Attempt to click all 'Show all' buttons to expand sections
    """
    show_all_patterns = [
        "//a[contains(@href,'details/experience')]",
        "//a[contains(@href,'details/education')]",
        "//a[contains(@href,'details/skills')]",
        "//button[contains(text(),'Show all')]",
        "//a[contains(text(),'Show all')]",
    ]
    
    expanded_count = 0
    for pattern in show_all_patterns:
        try:
            elements = driver.find_elements(By.XPATH, pattern)
            for element in elements:
                try:
                    driver.execute_script("arguments[0].click();", element)
                    time.sleep(2)
                    expanded_count += 1
                except:
                    pass
        except:
            pass
    
    if expanded_count > 0:
        time.sleep(2)
        slow_scroll(driver, rounds=2)
    
    return expanded_count


def scrape_single_profile(driver, profile_url, wait):
    """
    Scrape a single LinkedIn profile and return HTML content
    
    Args:
        driver: Selenium WebDriver instance (reused)
        profile_url: LinkedIn profile URL
        wait: WebDriverWait instance
    
    Returns:
        dict: Profile data with HTML content
    """
    data = {
        "url": profile_url,
        "html_content": "",
        "page_text": "",
        "success": False,
        "error": None
    }

    try:
        # Load profile
        driver.get(profile_url)
        time.sleep(4)
        
        # Scroll to load content
        slow_scroll(driver, rounds=4)
        
        # Try to expand sections
        expanded = click_show_all_sections(driver)
        
        # Extra time for content
        time.sleep(2)
        
        # Capture HTML
        data["html_content"] = driver.page_source
        data["page_text"] = driver.find_element(By.TAG_NAME, "body").text
        data["success"] = True
        
        # Get name for logging
        try:
            name = driver.find_element(By.TAG_NAME, "h1").text.strip()
            data["name"] = name
        except:
            data["name"] = "Unknown"
        
        return data

    except Exception as e:
        data["success"] = False
        data["error"] = str(e)
        return data