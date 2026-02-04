#!/usr/bin/env python3
"""
Parallel Google Maps Review Scraper for Brussels Food Map
Scrapes reviews from restaurants using multiple browser instances.

Usage:
    python src/scrape_gmaps_reviews_parallel.py [options]

Options:
    --workers N          Number of browser instances (default: 2)
    --resume             Resume from previous state
    --max-restaurants N  Limit number of restaurants to scrape
    --retry-failed       Retry previously failed restaurants

Output:
    data/scraped_reviews_parallel.json - Review data per restaurant
    data/scrape_state.json - State tracking for resume capability
"""

import json
import time
import random
import re
import signal
import argparse
import threading
import queue
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    InvalidSessionIdException,
    WebDriverException
)
from webdriver_manager.chrome import ChromeDriverManager

# === CONFIGURATION ===

INPUT_FILE = Path("data/brussels_restaurants.json")
OUTPUT_FILE = Path("data/scraped_reviews_parallel.json")
STATE_FILE = Path("data/scrape_state.json")

# Worker settings
NUM_WORKERS = 2
REVIEWS_PER_RESTAURANT = 50

# Rate limiting (slightly higher for parallel to avoid detection)
REQUEST_DELAY_MIN = 3
REQUEST_DELAY_MAX = 7
SCROLL_PAUSE = 1.5

# Retry settings
MAX_RETRIES = 2
RETRY_DELAY_BASE = 5

# Browser restart threshold (restart after N restaurants to avoid memory leaks)
BROWSER_RESTART_THRESHOLD = 50

# Global stop event for graceful shutdown
stop_event = threading.Event()


# === STATE MANAGEMENT ===

def load_restaurants_from_json(filepath: Path) -> List[Dict]:
    """
    Load restaurant list from brussels_restaurants.json.

    Returns:
        List of restaurant dicts with keys: name, address, google_maps_url, rating, review_count
    """
    with open(filepath, "r", encoding="utf-8") as f:
        restaurants = json.load(f)

    # Extract only required fields and generate search query fallback
    result = []
    for r in restaurants:
        restaurant = {
            "name": r.get("name"),
            "address": r.get("address"),
            "google_maps_url": r.get("google_maps_url"),
            "rating": r.get("rating"),
            "review_count": r.get("review_count"),
        }
        # Generate search query as fallback
        name = r.get("name", "")
        address = r.get("address", "")
        commune = r.get("commune", "Brussels")
        restaurant["search_query"] = f"{name} {commune} {address.split(',')[0] if address else ''}"
        result.append(restaurant)

    return result


def load_scrape_state(state_file: Path) -> Dict:
    """
    Load scraping state for resume capability.

    Returns:
        Dict with keys: completed (set), in_progress (dict), failed (dict)
    """
    if not state_file.exists():
        return {
            "completed": set(),
            "in_progress": {},
            "failed": {},
            "started_at": datetime.now().isoformat(),
        }

    with open(state_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Convert lists back to sets
    data["completed"] = set(data.get("completed", []))
    return data


def save_scrape_state(state: Dict, state_file: Path, lock: threading.Lock) -> None:
    """Atomically save scrape state to file."""
    with lock:
        # Convert set to list for JSON serialization
        state_copy = state.copy()
        state_copy["completed"] = list(state["completed"])
        state_copy["last_updated"] = datetime.now().isoformat()

        # Atomic write: temp file then rename
        temp_path = state_file.with_suffix('.tmp')
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(state_copy, f, indent=2, ensure_ascii=False)
        temp_path.rename(state_file)


def mark_in_progress(state: Dict, restaurant_name: str, worker_id: int,
                     state_file: Path, lock: threading.Lock) -> None:
    """Mark a restaurant as currently being scraped."""
    state["in_progress"][restaurant_name] = {
        "worker_id": worker_id,
        "started_at": datetime.now().isoformat()
    }
    save_scrape_state(state, state_file, lock)


def mark_completed(state: Dict, restaurant_name: str,
                   state_file: Path, lock: threading.Lock) -> None:
    """Mark a restaurant as successfully completed."""
    if restaurant_name in state["in_progress"]:
        del state["in_progress"][restaurant_name]
    if restaurant_name in state["failed"]:
        del state["failed"][restaurant_name]
    state["completed"].add(restaurant_name)
    save_scrape_state(state, state_file, lock)


def mark_failed(state: Dict, restaurant_name: str, error: str,
                state_file: Path, lock: threading.Lock) -> None:
    """Mark a restaurant as failed."""
    if restaurant_name in state["in_progress"]:
        del state["in_progress"][restaurant_name]

    # Track failure with attempt count
    if restaurant_name in state["failed"]:
        state["failed"][restaurant_name]["attempts"] += 1
        state["failed"][restaurant_name]["last_error"] = error
        state["failed"][restaurant_name]["last_failed_at"] = datetime.now().isoformat()
    else:
        state["failed"][restaurant_name] = {
            "error": error,
            "attempts": 1,
            "first_failed_at": datetime.now().isoformat(),
            "last_failed_at": datetime.now().isoformat()
        }
    save_scrape_state(state, state_file, lock)


# === THREAD-SAFE FILE I/O ===

def atomic_json_write(data: List, filepath: Path) -> None:
    """Write JSON atomically using temp file + rename."""
    temp_path = filepath.with_suffix('.tmp')
    with open(temp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    temp_path.rename(filepath)


def load_existing_results(output_file: Path) -> Tuple[List[Dict], Set[str]]:
    """
    Load existing results and extract completed names.

    Returns:
        Tuple of (results_list, completed_names_set)
    """
    if not output_file.exists():
        return [], set()

    with open(output_file, "r", encoding="utf-8") as f:
        results = json.load(f)

    # Only consider entries with reviews and no error as 'completed'
    completed = {
        r["name"] for r in results
        if r.get("reviews") and len(r["reviews"]) > 0 and not r.get("error")
    }

    return results, completed


def thread_safe_save_result(result: Dict, output_file: Path,
                            lock: threading.Lock, results_cache: List[Dict]) -> None:
    """
    Append a single result to the output JSON file in a thread-safe manner.
    Uses an in-memory cache to avoid reading file on every write.
    """
    with lock:
        # Check for duplicates
        existing_names = {r["name"] for r in results_cache}
        if result["name"] in existing_names:
            # Update existing entry
            for i, r in enumerate(results_cache):
                if r["name"] == result["name"]:
                    results_cache[i] = result
                    break
        else:
            results_cache.append(result)

        # Write atomically
        atomic_json_write(results_cache, output_file)


# === WORK DISTRIBUTION ===

def create_work_queue(restaurants: List[Dict], completed: Set[str],
                      failed: Dict, retry_failed: bool = False) -> queue.Queue:
    """
    Create a thread-safe queue of restaurants to scrape.

    Args:
        restaurants: Full list of restaurants
        completed: Set of already completed restaurant names
        failed: Dict of failed restaurants
        retry_failed: Whether to include failed restaurants for retry
    """
    work_queue = queue.Queue()

    # Filter and optionally shuffle
    to_scrape = []
    for r in restaurants:
        name = r["name"]
        if name in completed:
            continue
        if name in failed and not retry_failed:
            continue
        to_scrape.append(r)

    # Shuffle to spread load across different areas
    random.shuffle(to_scrape)

    for r in to_scrape:
        work_queue.put(r)

    return work_queue


# === BROWSER MANAGEMENT ===

def setup_driver_for_worker(worker_id: int) -> webdriver.Chrome:
    """Setup Chrome driver with unique profile for a worker."""
    options = Options()

    # NOT headless - Google blocks headless browsers
    # options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--lang=en-US")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Unique user data directory per worker to avoid conflicts
    user_data_dir = Path(f"/tmp/chrome_scraper_worker_{worker_id}")
    user_data_dir.mkdir(parents=True, exist_ok=True)
    options.add_argument(f"--user-data-dir={user_data_dir}")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # Hide webdriver flag
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    return driver


def restart_driver(driver: Optional[webdriver.Chrome], worker_id: int) -> webdriver.Chrome:
    """Safely restart a crashed driver."""
    if driver:
        try:
            driver.quit()
        except Exception:
            pass

    time.sleep(2)
    return setup_driver_for_worker(worker_id)


# === SCRAPING FUNCTIONS (reused from original) ===

def accept_cookies(driver) -> None:
    """Accept cookie consent if present."""
    try:
        accept_btn = driver.find_element(By.CSS_SELECTOR, "button[aria-label*='Accept']")
        accept_btn.click()
        time.sleep(1)
    except NoSuchElementException:
        pass
    try:
        accept_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Accept all')]")
        accept_btn.click()
        time.sleep(1)
    except NoSuchElementException:
        pass


def get_restaurant_metadata(driver) -> Dict:
    """Extract metadata: price, rating, review count, address."""
    metadata = {
        "price": None,
        "rating": None,
        "review_count": None,
        "address": None,
    }

    try:
        rating_elem = driver.find_element(By.CSS_SELECTOR, "div.F7nice span[aria-hidden='true']")
        metadata["rating"] = rating_elem.text
    except NoSuchElementException:
        pass

    try:
        review_elem = driver.find_element(By.CSS_SELECTOR, "div.F7nice span[aria-label*='reviews']")
        count_text = review_elem.get_attribute("aria-label")
        match = re.search(r"([\d,]+)\s*reviews", count_text)
        if match:
            metadata["review_count"] = int(match.group(1).replace(",", ""))
    except NoSuchElementException:
        pass

    try:
        price_elem = driver.find_element(By.CSS_SELECTOR, "span[aria-label*='Price']")
        metadata["price"] = price_elem.text
    except NoSuchElementException:
        pass

    try:
        address_elem = driver.find_element(By.CSS_SELECTOR, "button[data-item-id='address'] div.fontBodyMedium")
        metadata["address"] = address_elem.text
    except NoSuchElementException:
        pass

    return metadata


def open_reviews_panel(driver) -> bool:
    """Open the reviews panel using URL parameter approach."""
    accept_cookies(driver)

    try:
        time.sleep(2)

        # Try URL-based approach: append reviews parameter to current URL
        current_url = driver.current_url

        # Add reviews parameter if not present
        if "!9m1!1b1" not in current_url:
            if "?" in current_url:
                new_url = current_url.replace("?", "!9m1!1b1?")
            else:
                new_url = current_url + "!9m1!1b1"
            driver.get(new_url)
            time.sleep(3)
            accept_cookies(driver)

        # Verify reviews are visible by checking for review elements
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.jftiEf"))
            )
            return True
        except TimeoutException:
            pass

        # Fallback: try clicking the Reviews tab
        selectors = [
            "button[aria-label*='Reviews']",
            "button[role='tab'][aria-label*='Reviews']",
            "//button[contains(text(), 'Reviews')]",
        ]

        for selector in selectors:
            try:
                if selector.startswith("//"):
                    reviews_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                else:
                    reviews_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                reviews_button.click()
                time.sleep(3)
                return True
            except TimeoutException:
                continue

        return False
    except (TimeoutException, Exception):
        return False


def extract_single_review(elem) -> Optional[Dict]:
    """Extract data from a single review element."""
    review = {
        "text": None,
        "rating": None,
        "date": None,
        "reviewer_name": None,
        "is_local_guide": False,
        "reviewer_review_count": None,
    }

    try:
        # Get reviewer name first (used as part of unique key)
        try:
            name_elem = elem.find_element(By.CSS_SELECTOR, "div.d4r55")
            review["reviewer_name"] = name_elem.text
        except NoSuchElementException:
            pass

        # Get review text
        text_elem = None
        for selector in ["span.wiI7pd", ".MyEned span", ".wiI7pd"]:
            try:
                text_elem = elem.find_element(By.CSS_SELECTOR, selector)
                if text_elem and text_elem.text:
                    break
            except NoSuchElementException:
                continue

        if text_elem:
            review["text"] = text_elem.text
        else:
            return None

        # Get rating
        try:
            stars_elem = elem.find_element(By.CSS_SELECTOR, "span.kvMYJc")
            aria_label = stars_elem.get_attribute("aria-label")
            match = re.search(r"(\d)", aria_label)
            if match:
                review["rating"] = int(match.group(1))
        except NoSuchElementException:
            pass

        # Get date
        try:
            date_elem = elem.find_element(By.CSS_SELECTOR, "span.rsqaWe")
            review["date"] = date_elem.text
        except NoSuchElementException:
            pass

        # Get Local Guide status
        try:
            badge_elem = elem.find_element(By.CSS_SELECTOR, "span.RfnDt")
            if "Local Guide" in badge_elem.text:
                review["is_local_guide"] = True
                match = re.search(r"(\d+)\s*reviews", badge_elem.text)
                if match:
                    review["reviewer_review_count"] = int(match.group(1))
        except NoSuchElementException:
            pass

        return review if review["text"] else None

    except Exception:
        return None


def get_review_key(review: Dict) -> str:
    """Generate a unique key for deduplication."""
    # Use reviewer name + first 50 chars of text as unique identifier
    name = review.get("reviewer_name", "") or ""
    text = (review.get("text", "") or "")[:50]
    return f"{name}::{text}"


def click_more_buttons(driver) -> None:
    """Click 'More' buttons to expand truncated review text."""
    try:
        more_buttons = driver.find_elements(By.CSS_SELECTOR, "button.w8nwRe.kyuRq")
        for btn in more_buttons:
            try:
                btn.click()
                time.sleep(0.05)
            except Exception:
                pass
    except Exception:
        pass


def scroll_and_extract_reviews(driver, target_count: int = 50) -> List[Dict]:
    """
    Scroll through reviews and extract incrementally to avoid losing reviews
    to DOM virtualization. Returns deduplicated list of reviews.
    """
    collected_reviews = {}  # Key -> review dict for deduplication
    scrollable_div = None

    # Find scrollable container
    try:
        scrollable_div = driver.find_element(By.CSS_SELECTOR, "div.m6QErb.DxyBCb.kA9KIf.dS8AEf")
    except NoSuchElementException:
        try:
            scrollable_div = driver.find_element(By.CSS_SELECTOR, "div.m6QErb.DxyBCb")
        except NoSuchElementException:
            return []

    # Wait for initial reviews to load
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.jftiEf.fontBodyMedium"))
        )
    except TimeoutException:
        return []

    last_collected_count = 0
    no_change_count = 0
    scroll_count = 0
    max_scrolls = 100  # Safety limit

    while no_change_count < 5 and scroll_count < max_scrolls:
        # Click "More" buttons on visible reviews first
        click_more_buttons(driver)
        time.sleep(0.3)

        # Extract all currently visible reviews
        review_elements = driver.find_elements(By.CSS_SELECTOR, "div.jftiEf.fontBodyMedium")

        for elem in review_elements:
            try:
                review = extract_single_review(elem)
                if review:
                    key = get_review_key(review)
                    if key not in collected_reviews:
                        collected_reviews[key] = review
            except Exception:
                continue

        current_count = len(collected_reviews)

        # Check if we've reached target
        if current_count >= target_count:
            break

        # Check for progress
        if current_count == last_collected_count:
            no_change_count += 1
        else:
            no_change_count = 0

        last_collected_count = current_count
        scroll_count += 1

        # Scroll down to load more reviews
        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_div)
        time.sleep(SCROLL_PAUSE)

    # Final extraction pass after scrolling completes
    click_more_buttons(driver)
    time.sleep(0.3)

    review_elements = driver.find_elements(By.CSS_SELECTOR, "div.jftiEf.fontBodyMedium")
    for elem in review_elements:
        try:
            review = extract_single_review(elem)
            if review:
                key = get_review_key(review)
                if key not in collected_reviews:
                    collected_reviews[key] = review
        except Exception:
            continue

    # Return as list, limited to target count
    return list(collected_reviews.values())[:target_count]


def extract_reviews(driver, max_reviews: int = 50) -> List[Dict]:
    """
    Legacy function - now calls scroll_and_extract_reviews for incremental extraction.
    Kept for API compatibility.
    """
    return scroll_and_extract_reviews(driver, max_reviews)


def estimate_years_open(reviews: List[Dict]) -> str:
    """Estimate how long restaurant has been open based on oldest review."""
    if not reviews:
        return "unknown"

    oldest_date = None
    for r in reviews:
        date_str = r.get("date", "")
        if "year" in date_str:
            match = re.search(r"(\d+)\s*year", date_str)
            if match:
                years = int(match.group(1))
                if oldest_date is None or years > oldest_date:
                    oldest_date = years

    if oldest_date is None:
        return "<2y"
    elif oldest_date < 2:
        return "<2y"
    elif oldest_date < 5:
        return "2-5y"
    elif oldest_date < 10:
        return "5-10y"
    else:
        return "10y+"


def calculate_reviewer_quality(reviews: List[Dict]) -> Dict:
    """Calculate reviewer quality metrics."""
    if not reviews:
        return {"quality": "unknown", "local_guides_pct": 0, "avg_reviews": 0}

    local_guides = sum(1 for r in reviews if r.get("is_local_guide"))
    review_counts = [r.get("reviewer_review_count", 0) for r in reviews if r.get("reviewer_review_count")]

    local_guides_pct = round(local_guides / len(reviews) * 100) if reviews else 0
    avg_reviews = round(sum(review_counts) / len(review_counts)) if review_counts else 0

    if local_guides_pct >= 60 and avg_reviews >= 30:
        quality = "High"
    elif local_guides_pct >= 40 or avg_reviews >= 20:
        quality = "Medium"
    elif local_guides_pct < 20 and avg_reviews < 10:
        quality = "Low"
    else:
        quality = "Mixed"

    return {
        "quality": quality,
        "local_guides_pct": local_guides_pct,
        "avg_reviews": avg_reviews,
    }


# === NAVIGATION ===

def navigate_to_restaurant(driver, restaurant: Dict) -> bool:
    """
    Navigate to restaurant page, preferring direct URL.

    Returns:
        True if navigation successful, False otherwise
    """
    # Try direct URL first
    google_maps_url = restaurant.get("google_maps_url")
    if google_maps_url:
        try:
            driver.get(google_maps_url)
            time.sleep(3)
            accept_cookies(driver)
            time.sleep(1)

            # Check if we landed on a valid place page
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.F7nice"))
                )
                return True
            except TimeoutException:
                pass
        except Exception:
            pass

    # Fall back to search
    search_query = restaurant.get("search_query", restaurant.get("name", ""))
    if search_query:
        try:
            search_url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"
            driver.get(search_url)
            time.sleep(3)
            accept_cookies(driver)
            time.sleep(1)

            # Click first result if there are multiple
            try:
                first_result = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "a.hfpxzc"))
                )
                first_result.click()
                time.sleep(2)
            except TimeoutException:
                pass

            # Verify we're on a place page
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.F7nice"))
                )
                return True
            except TimeoutException:
                pass
        except Exception:
            pass

    return False


def scrape_restaurant_direct(driver, restaurant: Dict) -> Dict:
    """
    Scrape a restaurant using direct navigation.

    Returns:
        Result dict matching existing output format
    """
    result = {
        "name": restaurant["name"],
        "search_query": restaurant.get("search_query", ""),
        "scraped_at": datetime.now().isoformat(),
        "metadata": {},
        "reviews": [],
        "years_open": "unknown",
        "reviewer_quality": {},
        "error": None,
    }

    try:
        # Navigate to restaurant
        if not navigate_to_restaurant(driver, restaurant):
            result["error"] = "Could not navigate to restaurant"
            return result

        # Get metadata
        result["metadata"] = get_restaurant_metadata(driver)

        # Open reviews panel
        if not open_reviews_panel(driver):
            result["error"] = "Could not open reviews panel"
            return result

        # Scroll and extract reviews incrementally (captures reviews before virtualization)
        result["reviews"] = scroll_and_extract_reviews(driver, REVIEWS_PER_RESTAURANT)

        # Calculate derived data
        result["years_open"] = estimate_years_open(result["reviews"])
        result["reviewer_quality"] = calculate_reviewer_quality(result["reviews"])

    except Exception as e:
        result["error"] = str(e)

    return result


# === WORKER FUNCTION ===

def worker_scrape(worker_id: int, work_queue: queue.Queue,
                  state: Dict, state_lock: threading.Lock,
                  results_lock: threading.Lock, results_cache: List[Dict],
                  output_file: Path, state_file: Path,
                  progress_counter: List[int], total_count: int) -> None:
    """
    Worker function that runs in each thread.
    """
    print(f"[Worker {worker_id}] Starting...")
    driver = None
    restaurants_scraped = 0

    try:
        driver = setup_driver_for_worker(worker_id)

        while not stop_event.is_set():
            try:
                # Get next restaurant from queue (non-blocking with timeout)
                try:
                    restaurant = work_queue.get(timeout=1)
                except queue.Empty:
                    break  # Queue is empty, we're done

                name = restaurant["name"]
                print(f"[Worker {worker_id}] Scraping: {name}")

                # Mark as in progress
                mark_in_progress(state, name, worker_id, state_file, state_lock)

                # Scrape with retry logic
                result = None
                for attempt in range(MAX_RETRIES + 1):
                    try:
                        result = scrape_restaurant_direct(driver, restaurant)
                        break
                    except (InvalidSessionIdException, WebDriverException) as e:
                        print(f"[Worker {worker_id}] Browser error: {e}")
                        driver = restart_driver(driver, worker_id)
                        if attempt < MAX_RETRIES:
                            time.sleep(RETRY_DELAY_BASE * (2 ** attempt))
                        else:
                            result = {
                                "name": name,
                                "search_query": restaurant.get("search_query", ""),
                                "scraped_at": datetime.now().isoformat(),
                                "metadata": {},
                                "reviews": [],
                                "years_open": "unknown",
                                "reviewer_quality": {},
                                "error": f"Browser error after {MAX_RETRIES} retries: {str(e)}"
                            }

                # Save result
                thread_safe_save_result(result, output_file, results_lock, results_cache)

                # Update state
                if result.get("reviews") and len(result["reviews"]) > 0 and not result.get("error"):
                    mark_completed(state, name, state_file, state_lock)
                    print(f"[Worker {worker_id}] Completed: {name} ({len(result['reviews'])} reviews)")
                else:
                    mark_failed(state, name, result.get("error", "No reviews"), state_file, state_lock)
                    print(f"[Worker {worker_id}] Failed: {name} - {result.get('error', 'No reviews')}")

                # Update progress
                with state_lock:
                    progress_counter[0] += 1
                    current = progress_counter[0]
                print(f"[Progress] {current}/{total_count} ({current*100//total_count}%)")

                restaurants_scraped += 1
                work_queue.task_done()

                # Restart browser periodically to avoid memory leaks
                if restaurants_scraped >= BROWSER_RESTART_THRESHOLD:
                    print(f"[Worker {worker_id}] Restarting browser (memory management)...")
                    driver = restart_driver(driver, worker_id)
                    restaurants_scraped = 0

                # Random delay between requests
                if not stop_event.is_set():
                    delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
                    time.sleep(delay)

            except Exception as e:
                print(f"[Worker {worker_id}] Error: {e}")
                continue

    except Exception as e:
        print(f"[Worker {worker_id}] Fatal error: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass
        print(f"[Worker {worker_id}] Stopped")


# === MAIN ===

def signal_handler(signum, frame):
    """Handle Ctrl+C for graceful shutdown."""
    print("\n[INTERRUPT] Graceful shutdown initiated... (waiting for current tasks)")
    stop_event.set()


def main():
    """Main function with parallel scraping support."""
    parser = argparse.ArgumentParser(description='Parallel Google Maps review scraper')
    parser.add_argument('--workers', type=int, default=NUM_WORKERS,
                        help=f'Number of browser instances (default: {NUM_WORKERS})')
    parser.add_argument('--resume', action='store_true',
                        help='Resume from previous state')
    parser.add_argument('--max-restaurants', type=int,
                        help='Limit number of restaurants to scrape')
    parser.add_argument('--retry-failed', action='store_true',
                        help='Retry previously failed restaurants')
    args = parser.parse_args()

    # Setup signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)

    print("=" * 60)
    print("Parallel Google Maps Review Scraper - Brussels Food Map")
    print("=" * 60)

    # Load restaurants
    print(f"\nLoading restaurants from {INPUT_FILE}...")
    restaurants = load_restaurants_from_json(INPUT_FILE)
    print(f"Loaded {len(restaurants)} restaurants")

    if args.max_restaurants:
        restaurants = restaurants[:args.max_restaurants]
        print(f"Limited to {args.max_restaurants} restaurants")

    # Load existing results
    print(f"\nLoading existing results from {OUTPUT_FILE}...")
    results_cache, results_completed = load_existing_results(OUTPUT_FILE)
    print(f"Found {len(results_completed)} previously completed restaurants")

    # Load state
    if args.resume:
        print(f"\nLoading state from {STATE_FILE}...")
        state = load_scrape_state(STATE_FILE)
        # Reconcile state with actual results
        state["completed"] = state["completed"].union(results_completed)
        # Clear stale in_progress entries
        state["in_progress"] = {}
        print(f"State: {len(state['completed'])} completed, {len(state.get('failed', {}))} failed")
    else:
        state = {
            "completed": results_completed,
            "in_progress": {},
            "failed": {},
            "started_at": datetime.now().isoformat(),
        }

    # Create work queue
    work_queue = create_work_queue(
        restaurants,
        state["completed"],
        state.get("failed", {}),
        retry_failed=args.retry_failed
    )
    total_to_scrape = work_queue.qsize()
    print(f"\nRestaurants to scrape: {total_to_scrape}")

    if total_to_scrape == 0:
        print("Nothing to scrape. All restaurants already completed.")
        return

    print(f"Workers: {args.workers}")
    print(f"Reviews per restaurant: {REVIEWS_PER_RESTAURANT}")
    print(f"Output: {OUTPUT_FILE}")
    print("\nStarting scraping...")
    print("Press Ctrl+C to stop gracefully\n")

    # Locks
    state_lock = threading.Lock()
    results_lock = threading.Lock()
    progress_counter = [0]  # Mutable container for thread-safe counting

    # Start worker threads
    threads = []
    for i in range(args.workers):
        t = threading.Thread(
            target=worker_scrape,
            args=(i, work_queue, state, state_lock, results_lock,
                  results_cache, OUTPUT_FILE, STATE_FILE,
                  progress_counter, total_to_scrape)
        )
        t.start()
        threads.append(t)
        time.sleep(2)  # Stagger browser starts

    # Wait for all threads to complete
    for t in threads:
        t.join()

    # Final statistics
    print("\n" + "=" * 60)
    print("Scraping Complete!")
    print("=" * 60)
    print(f"Total processed: {progress_counter[0]}")
    print(f"Total completed: {len(state['completed'])}")
    print(f"Total failed: {len(state.get('failed', {}))}")
    print(f"Results saved to: {OUTPUT_FILE}")
    print(f"State saved to: {STATE_FILE}")


if __name__ == "__main__":
    main()
