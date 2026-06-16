"""
Selenium Screenshot Automater - Browser automation with reliable element-based targeting
"""

import os
import sys
import json
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Callable

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.firefox.service import Service as FirefoxService
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.edge.service import Service as EdgeService
    from selenium.webdriver.edge.options import Options as EdgeOptions
    from selenium.common.exceptions import (
        TimeoutException, NoSuchElementException, 
        ElementClickInterceptedException, StaleElementReferenceException
    )
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Please install Selenium: pip install selenium")
    sys.exit(1)


class SeleniumAutomater:
    """
    Browser automation class using Selenium for reliable web app automation.
    
    Unlike coordinate-based automation (pyautogui), this uses element selectors
    which are resolution-independent and much more reliable.
    """
    
    SUPPORTED_BROWSERS = ["chrome", "firefox", "edge"]
    
    def __init__(
        self,
        output_dir: str = "screenshots",
        naming_pattern: str = "{count}_{action}",
        image_format: str = "png",
        browser: str = "chrome",
        headless: bool = False,
        wait_timeout: float = 10.0
    ):
        """
        Initialize the Selenium Automater.
        
        Args:
            output_dir: Directory to save screenshots
            naming_pattern: Pattern for naming files. Supports:
                - {timestamp}: Current timestamp (YYYYMMDD_HHMMSS)
                - {count}: Sequential action counter
                - {action}: Action type (click, input, etc.)
                - {date}: Date (YYYY-MM-DD)
                - {time}: Time (HH-MM-SS)
            image_format: Image format (png, jpg)
            browser: Browser to use (chrome, firefox, edge)
            headless: Run browser in headless mode
            wait_timeout: Default timeout for element waits in seconds
        """
        self.output_dir = Path(output_dir)
        self.naming_pattern = naming_pattern
        self.image_format = image_format.lower()
        self.browser_name = browser.lower()
        self.headless = headless
        self.wait_timeout = wait_timeout
        
        self.driver: Optional[webdriver.Remote] = None
        self.action_count = 0
        self.workflow: List[Dict] = []
        self.is_recording = False
        self.session_start_time = None
        self.workflow_file = "selenium_workflow.json"
        self.status_callback: Optional[Callable[[str], None]] = None
        self._stop_recording_flag = False
        self._recording_thread = None
        
        # JavaScript for element detection and highlighting
        self._highlight_script = self._get_highlight_script()
        self._get_element_script = self._get_element_at_point_script()
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_highlight_script(self) -> str:
        """JavaScript to highlight an element."""
        return """
        (function(selector, selectorType) {
            // Remove any existing highlight
            var existing = document.getElementById('__selenium_highlight__');
            if (existing) existing.remove();
            
            var element = null;
            try {
                if (selectorType === 'id') {
                    element = document.getElementById(selector);
                } else if (selectorType === 'css') {
                    element = document.querySelector(selector);
                } else if (selectorType === 'xpath') {
                    element = document.evaluate(selector, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                }
            } catch(e) {}
            
            if (element) {
                var rect = element.getBoundingClientRect();
                var highlight = document.createElement('div');
                highlight.id = '__selenium_highlight__';
                highlight.style.cssText = 'position:fixed;border:3px solid red;background:rgba(255,0,0,0.1);pointer-events:none;z-index:999999;';
                highlight.style.left = rect.left + 'px';
                highlight.style.top = rect.top + 'px';
                highlight.style.width = rect.width + 'px';
                highlight.style.height = rect.height + 'px';
                document.body.appendChild(highlight);
                return true;
            }
            return false;
        })(arguments[0], arguments[1]);
        """
    
    def _get_element_at_point_script(self) -> str:
        """JavaScript to get element info at a given point or the active element."""
        return """
        (function() {
            // Get the element that was most recently clicked or is focused
            var element = document.activeElement;
            
            // If it's just body/html, try to get from recent click
            if (!element || element === document.body || element === document.documentElement) {
                return null;
            }
            
            function getSelector(el) {
                // Try ID first
                if (el.id) {
                    return {type: 'id', value: el.id};
                }
                
                // Try name attribute
                if (el.name) {
                    return {type: 'name', value: el.name};
                }
                
                // Try data-testid
                if (el.dataset && el.dataset.testid) {
                    return {type: 'css', value: '[data-testid="' + el.dataset.testid + '"]'};
                }
                
                // Try aria-label
                if (el.getAttribute('aria-label')) {
                    return {type: 'css', value: '[aria-label="' + el.getAttribute('aria-label') + '"]'};
                }
                
                // Try unique class combination
                if (el.className && typeof el.className === 'string' && el.className.trim()) {
                    var classes = el.className.trim().split(/\\s+/).filter(c => c && !c.includes(':'));
                    if (classes.length > 0) {
                        var selector = el.tagName.toLowerCase() + '.' + classes.join('.');
                        try {
                            if (document.querySelectorAll(selector).length === 1) {
                                return {type: 'css', value: selector};
                            }
                        } catch(e) {}
                    }
                }
                
                // XPath fallback
                function getXPath(node) {
                    if (node.id) return '//*[@id="' + node.id + '"]';
                    if (node === document.body) return '/html/body';
                    var ix = 0;
                    var siblings = node.parentNode ? node.parentNode.childNodes : [];
                    for (var i = 0; i < siblings.length; i++) {
                        var sibling = siblings[i];
                        if (sibling === node) {
                            var parentPath = node.parentNode && node.parentNode !== document ? getXPath(node.parentNode) : '';
                            return parentPath + '/' + node.tagName.toLowerCase() + '[' + (ix + 1) + ']';
                        }
                        if (sibling.nodeType === 1 && sibling.tagName === node.tagName) {
                            ix++;
                        }
                    }
                    return '';
                }
                return {type: 'xpath', value: getXPath(el)};
            }
            
            return {
                selector: getSelector(element),
                tagName: element.tagName.toLowerCase(),
                text: (element.innerText || element.value || '').substring(0, 100),
                value: element.value || '',
                type: element.type || '',
                url: window.location.href
            };
        })();
        """
    
    def _setup_click_listener(self) -> str:
        """JavaScript to track clicks and store in localStorage to persist across navigation."""
        return """
        (function() {
            if (window.__seleniumClickTracker) return;
            
            // Load any existing clicks from localStorage
            var storedClicks = [];
            try {
                var stored = localStorage.getItem('__selenium_clicks__');
                if (stored) storedClicks = JSON.parse(stored);
            } catch(e) {}
            
            window.__seleniumClickTracker = {
                lastClick: null,
                clicks: storedClicks
            };
            
            function saveToStorage() {
                try {
                    localStorage.setItem('__selenium_clicks__', JSON.stringify(window.__seleniumClickTracker.clicks));
                } catch(e) {}
            }
            
            function getSelector(el) {
                if (el.id) return {type: 'id', value: el.id};
                if (el.name) return {type: 'name', value: el.name};
                if (el.dataset && el.dataset.testid) return {type: 'css', value: '[data-testid="' + el.dataset.testid + '"]'};
                if (el.getAttribute && el.getAttribute('aria-label')) return {type: 'css', value: '[aria-label="' + el.getAttribute('aria-label') + '"]'};
                
                if (el.className && typeof el.className === 'string' && el.className.trim()) {
                    var classes = el.className.trim().split(/\\s+/).filter(function(c) { return c && c.indexOf(':') === -1; });
                    if (classes.length > 0) {
                        var selector = el.tagName.toLowerCase() + '.' + classes.join('.');
                        try {
                            if (document.querySelectorAll(selector).length === 1) {
                                return {type: 'css', value: selector};
                            }
                        } catch(e) {}
                    }
                }
                
                function getXPath(node) {
                    if (node.id) return '//*[@id="' + node.id + '"]';
                    if (node === document.body) return '/html/body';
                    var ix = 0;
                    var siblings = node.parentNode ? node.parentNode.childNodes : [];
                    for (var i = 0; i < siblings.length; i++) {
                        var sibling = siblings[i];
                        if (sibling === node) {
                            var parentPath = node.parentNode && node.parentNode !== document ? getXPath(node.parentNode) : '';
                            return parentPath + '/' + node.tagName.toLowerCase() + '[' + (ix + 1) + ']';
                        }
                        if (sibling.nodeType === 1 && sibling.tagName === node.tagName) ix++;
                    }
                    return '';
                }
                return {type: 'xpath', value: getXPath(el)};
            }
            
            document.addEventListener('click', function(e) {
                var el = e.target;
                var clickData = {
                    selector: getSelector(el),
                    tagName: el.tagName.toLowerCase(),
                    text: (el.innerText || el.value || '').substring(0, 100),
                    value: el.value || '',
                    inputType: el.type || '',
                    url: window.location.href,
                    timestamp: Date.now()
                };
                window.__seleniumClickTracker.lastClick = clickData;
                window.__seleniumClickTracker.clicks.push(clickData);
                saveToStorage();
            }, true);
            
            document.addEventListener('input', function(e) {
                var el = e.target;
                if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                    var inputData = {
                        selector: getSelector(el),
                        tagName: el.tagName.toLowerCase(),
                        text: '',
                        value: el.value || '',
                        inputType: el.type || 'text',
                        actionType: 'input',
                        url: window.location.href,
                        timestamp: Date.now()
                    };
                    window.__seleniumClickTracker.lastClick = inputData;
                    window.__seleniumClickTracker.clicks.push(inputData);
                    saveToStorage();
                }
            }, true);
            
            document.addEventListener('change', function(e) {
                var el = e.target;
                if (el.tagName === 'SELECT') {
                    var selectData = {
                        selector: getSelector(el),
                        tagName: el.tagName.toLowerCase(),
                        text: el.options[el.selectedIndex] ? el.options[el.selectedIndex].text : '',
                        value: el.value || '',
                        actionType: 'select',
                        url: window.location.href,
                        timestamp: Date.now()
                    };
                    window.__seleniumClickTracker.lastClick = selectData;
                    window.__seleniumClickTracker.clicks.push(selectData);
                    saveToStorage();
                }
            }, true);
            
            console.log('Click tracker initialized with', storedClicks.length, 'existing clicks');
        })();
        """
    
    def _log(self, message: str):
        """Log a message, using callback if available."""
        print(message)
        if self.status_callback:
            self.status_callback(message)
    
    def _create_driver(self) -> webdriver.Remote:
        """Create and configure the WebDriver instance."""
        if self.browser_name == "chrome":
            options = ChromeOptions()
            if self.headless:
                options.add_argument("--headless=new")
            options.add_argument("--start-maximized")
            options.add_argument("--disable-infobars")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            driver = webdriver.Chrome(options=options)
            
            # Enable CDP for click tracking (Chrome only)
            try:
                driver.execute_cdp_cmd('Input.enable', {})
            except:
                pass
            
            return driver
            
        elif self.browser_name == "firefox":
            options = FirefoxOptions()
            if self.headless:
                options.add_argument("--headless")
            return webdriver.Firefox(options=options)
            
        elif self.browser_name == "edge":
            options = EdgeOptions()
            if self.headless:
                options.add_argument("--headless=new")
            options.add_argument("--start-maximized")
            return webdriver.Edge(options=options)
            
        else:
            raise ValueError(f"Unsupported browser: {self.browser_name}")
    
    def _generate_filename(self, action_type: str = "action") -> str:
        """Generate filename based on the naming pattern."""
        now = datetime.now()
        
        replacements = {
            "{timestamp}": now.strftime("%Y%m%d_%H%M%S"),
            "{count}": str(self.action_count).zfill(4),
            "{action}": action_type,
            "{date}": now.strftime("%Y-%m-%d"),
            "{time}": now.strftime("%H-%M-%S"),
        }
        
        filename = self.naming_pattern
        for pattern, value in replacements.items():
            filename = filename.replace(pattern, value)
            
        return f"{filename}.{self.image_format}"
    
    def _capture_screenshot(self, action_type: str = "action") -> Optional[str]:
        """Capture a screenshot of the current browser state."""
        if not self.driver:
            return None
            
        try:
            self.action_count += 1
            filename = self._generate_filename(action_type)
            filepath = self.output_dir / filename
            
            # Small delay to ensure page has updated
            time.sleep(0.2)
            
            self.driver.save_screenshot(str(filepath))
            self._log(f"  Screenshot saved: {filepath}")
            return str(filepath)
            
        except Exception as e:
            self._log(f"  Error capturing screenshot: {e}")
            return None
    
    def _find_element(self, selector: Dict, timeout: float = None) -> Optional[any]:
        """
        Find an element using the selector dictionary.
        
        Args:
            selector: Dict with 'type' and 'value' keys
            timeout: Wait timeout (uses default if None)
            
        Returns:
            WebElement if found, None otherwise
        """
        if not self.driver:
            return None
            
        timeout = timeout or self.wait_timeout
        selector_type = selector.get("type", "css")
        selector_value = selector.get("value", "")
        
        by_mapping = {
            "id": By.ID,
            "name": By.NAME,
            "css": By.CSS_SELECTOR,
            "xpath": By.XPATH,
            "class": By.CLASS_NAME,
            "tag": By.TAG_NAME,
            "link_text": By.LINK_TEXT,
            "partial_link_text": By.PARTIAL_LINK_TEXT
        }
        
        by = by_mapping.get(selector_type, By.CSS_SELECTOR)
        
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, selector_value))
            )
            return element
        except TimeoutException:
            self._log(f"  Element not found: {selector_type}={selector_value}")
            return None
    
    def _click_element(self, selector: Dict, capture: bool = True) -> bool:
        """
        Click an element identified by the selector.
        
        Args:
            selector: Dict with 'type' and 'value' keys
            capture: Whether to capture screenshot after click
            
        Returns:
            True if successful, False otherwise
        """
        element = self._find_element(selector)
        if not element:
            return False
            
        try:
            # Wait for element to be clickable
            WebDriverWait(self.driver, self.wait_timeout).until(
                EC.element_to_be_clickable((
                    {"id": By.ID, "name": By.NAME, "css": By.CSS_SELECTOR, 
                     "xpath": By.XPATH}.get(selector.get("type"), By.CSS_SELECTOR),
                    selector.get("value")
                ))
            )
            
            # Try regular click first
            try:
                element.click()
            except ElementClickInterceptedException:
                # If regular click fails, try JavaScript click
                self.driver.execute_script("arguments[0].click();", element)
            
            if capture:
                self._capture_screenshot("click")
            return True
            
        except Exception as e:
            self._log(f"  Click failed: {e}")
            return False
    
    def _input_text(self, selector: Dict, text: str, clear: bool = True, capture: bool = True) -> bool:
        """
        Input text into an element.
        
        Args:
            selector: Dict with 'type' and 'value' keys
            text: Text to input
            clear: Whether to clear existing text first
            capture: Whether to capture screenshot after input
            
        Returns:
            True if successful, False otherwise
        """
        element = self._find_element(selector)
        if not element:
            return False
            
        try:
            if clear:
                element.clear()
            element.send_keys(text)
            
            if capture:
                self._capture_screenshot("input")
            return True
            
        except Exception as e:
            self._log(f"  Input failed: {e}")
            return False
    
    def _select_option(self, selector: Dict, value: str, capture: bool = True) -> bool:
        """
        Select an option from a dropdown.
        
        Args:
            selector: Dict with 'type' and 'value' keys
            value: Value to select
            capture: Whether to capture screenshot after selection
            
        Returns:
            True if successful, False otherwise
        """
        from selenium.webdriver.support.ui import Select
        
        element = self._find_element(selector)
        if not element:
            return False
            
        try:
            select = Select(element)
            try:
                select.select_by_value(value)
            except:
                select.select_by_visible_text(value)
            
            if capture:
                self._capture_screenshot("select")
            return True
            
        except Exception as e:
            self._log(f"  Select failed: {e}")
            return False
    
    def launch_browser(self, url: str = None) -> bool:
        """
        Launch the browser and optionally navigate to a URL.
        
        Args:
            url: URL to navigate to (optional)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self._log(f"Launching {self.browser_name} browser...")
            self.driver = self._create_driver()
            
            if url:
                self._log(f"Navigating to: {url}")
                self.driver.get(url)
                time.sleep(1)  # Wait for page load
            
            self._log("Browser ready")
            return True
            
        except Exception as e:
            self._log(f"Failed to launch browser: {e}")
            return False
    
    def close_browser(self):
        """Close the browser."""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
            self._log("Browser closed")
    
    def _inject_click_tracker(self):
        """Inject the click tracking script into the current page."""
        try:
            self.driver.execute_script(self._setup_click_listener())
        except Exception as e:
            self._log(f"  Failed to inject tracker: {e}")
    
    def _get_recorded_clicks(self) -> List[Dict]:
        """Get all recorded clicks, checking both memory and localStorage."""
        try:
            # Try to get from tracker first, it also loads from localStorage
            result = self.driver.execute_script("""
                if (window.__seleniumClickTracker) {
                    return window.__seleniumClickTracker.clicks;
                }
                // Fallback to localStorage directly
                try {
                    var stored = localStorage.getItem('__selenium_clicks__');
                    if (stored) return JSON.parse(stored);
                } catch(e) {}
                return [];
            """)
            return result or []
        except:
            return []
    
    def _clear_recorded_clicks(self):
        """Clear the recorded clicks from both memory and localStorage."""
        try:
            self.driver.execute_script("""
                if (window.__seleniumClickTracker) window.__seleniumClickTracker.clicks = [];
                try { localStorage.removeItem('__selenium_clicks__'); } catch(e) {}
            """)
        except:
            pass
    
    def _recording_loop(self):
        """Background loop that polls for new clicks and handles page navigation."""
        last_url = None
        last_click_count = 0
        
        while self.is_recording and not self._stop_recording_flag:
            try:
                if not self.driver:
                    break
                
                # FIRST: Always try to get clicks from current page BEFORE checking URL
                # This captures clicks that might cause navigation
                try:
                    clicks = self._get_recorded_clicks()
                    if clicks and len(clicks) > last_click_count:
                        new_clicks = clicks[last_click_count:]
                        for click in new_clicks:
                            action_type = click.get("actionType", "click")
                            selector = click.get("selector", {})
                            
                            processed = {
                                "step": len(self.workflow) + 1,
                                "type": action_type,
                                "selector": selector,
                                "tag": click.get("tagName", ""),
                                "text_preview": click.get("text", "")[:50],
                                "url": click.get("url", ""),
                                "timestamp": click.get("timestamp", 0)
                            }
                            
                            if action_type in ("input", "select"):
                                processed["value"] = click.get("value", "")
                            
                            self.workflow.append(processed)
                            self._log(f"  Recorded: {action_type} on {selector.get('type', '?')}={selector.get('value', '?')[:40]}")
                        
                        last_click_count = len(clicks)
                except:
                    pass  # Page might be in navigation transition
                
                # Check for page navigation
                try:
                    current_url = self.driver.current_url
                except:
                    time.sleep(0.3)
                    continue
                
                # Re-inject tracker if URL changed (page navigated)
                if current_url != last_url:
                    if last_url is not None:  # Don't log on first iteration
                        self._log(f"  Page changed: {current_url[:50]}...")
                    time.sleep(0.3)  # Wait for page to settle
                    self._inject_click_tracker()
                    last_url = current_url
                    last_click_count = 0  # Reset count for new page
                
                time.sleep(0.2)  # Poll interval
                
            except Exception as e:
                # Browser might have been closed or page is loading
                time.sleep(0.5)
    
    def start_recording(self, url: str = None):
        """
        Start recording user interactions in the browser.
        
        Args:
            url: URL to navigate to before recording
        """
        if not self.driver:
            if not self.launch_browser(url):
                return
        elif url:
            self.driver.get(url)
            time.sleep(1)
        
        self.workflow = []
        self.action_count = 0
        self.is_recording = True
        self._stop_recording_flag = False
        self.session_start_time = datetime.now()
        
        # Clear any previous clicks from localStorage and inject the tracker
        self._clear_recorded_clicks()
        self._inject_click_tracker()
        
        self._log("\n" + "="*50)
        self._log("RECORDING STARTED")
        self._log("="*50)
        self._log("Interact with the browser - clicks are recorded to localStorage")
        self._log("Click 'Stop Recording' when done")
        self._log("="*50 + "\n")
        
        # Start background recording loop
        self._recording_thread = threading.Thread(target=self._recording_loop, daemon=True)
        self._recording_thread.start()
    
    def stop_recording(self) -> List[Dict]:
        """
        Stop recording and retrieve the recorded actions.
        
        Returns:
            List of recorded actions
        """
        if not self.is_recording:
            return self.workflow
        
        self.is_recording = False
        self._stop_recording_flag = True
        
        # Wait for recording thread to finish
        if self._recording_thread and self._recording_thread.is_alive():
            self._recording_thread.join(timeout=2.0)
        
        # Get any final clicks
        final_clicks = self._get_recorded_clicks()
        existing_timestamps = {a.get("timestamp") for a in self.workflow}
        
        for click in final_clicks:
            if click.get("timestamp") not in existing_timestamps:
                action_type = click.get("actionType", "click")
                processed = {
                    "step": len(self.workflow) + 1,
                    "type": action_type,
                    "selector": click.get("selector", {}),
                    "tag": click.get("tagName", ""),
                    "text_preview": click.get("text", "")[:50],
                    "url": click.get("url", ""),
                    "timestamp": click.get("timestamp", 0)
                }
                if action_type in ("input", "select"):
                    processed["value"] = click.get("value", "")
                self.workflow.append(processed)
        
        self._log("\n" + "="*50)
        self._log("RECORDING STOPPED")
        self._log(f"Total actions recorded: {len(self.workflow)}")
        self._log("="*50 + "\n")
        
        return self.workflow
    
    def save_workflow(self, filepath: str = None) -> bool:
        """
        Save the recorded workflow to a JSON file.
        
        Args:
            filepath: Path to save the workflow (uses default if None)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.workflow:
            self._log("No workflow to save")
            return False
        
        filepath = filepath or str(self.output_dir / self.workflow_file)
        
        workflow_data = {
            "session_info": {
                "start_time": self.session_start_time.isoformat() if self.session_start_time else None,
                "total_actions": len(self.workflow),
                "browser": self.browser_name,
                "output_dir": str(self.output_dir),
                "naming_pattern": self.naming_pattern,
                "image_format": self.image_format,
                "recorded_with": "selenium_automater"
            },
            "actions": self.workflow
        }
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(workflow_data, f, indent=2)
            self._log(f"Workflow saved to: {filepath}")
            return True
        except Exception as e:
            self._log(f"Failed to save workflow: {e}")
            return False
    
    def load_workflow(self, filepath: str) -> bool:
        """
        Load a workflow from a JSON file.
        
        Args:
            filepath: Path to the workflow file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.workflow = data.get("actions", [])
            session_info = data.get("session_info", {})
            
            self._log(f"Loaded workflow with {len(self.workflow)} actions")
            self._log(f"  Recorded with: {session_info.get('recorded_with', 'unknown')}")
            
            return True
            
        except Exception as e:
            self._log(f"Failed to load workflow: {e}")
            return False
    
    def replay_workflow(
        self,
        workflow_path: str = None,
        output_dir: str = None,
        url: str = None,
        delay_between_actions: float = 1.0,
        capture_screenshots: bool = True,
        stop_on_error: bool = False
    ) -> Dict:
        """
        Replay a recorded workflow.
        
        Args:
            workflow_path: Path to workflow JSON file
            output_dir: Directory for screenshots (uses default if None)
            url: Starting URL (overrides workflow URL if provided)
            delay_between_actions: Delay between actions in seconds
            capture_screenshots: Whether to capture screenshots
            stop_on_error: Whether to stop on first error
            
        Returns:
            Dict with replay statistics
        """
        # Load workflow if path provided
        if workflow_path:
            if not self.load_workflow(workflow_path):
                return {"success": False, "error": "Failed to load workflow"}
        
        if not self.workflow:
            return {"success": False, "error": "No workflow to replay"}
        
        # Set up output directory
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path(f"replay_selenium_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.action_count = 0
        stats = {
            "total": len(self.workflow),
            "successful": 0,
            "failed": 0,
            "screenshots": 0,
            "errors": []
        }
        
        # Determine starting URL
        start_url = url or (self.workflow[0].get("url") if self.workflow else None)
        
        self._log("\n" + "="*50)
        self._log("SELENIUM WORKFLOW REPLAY")
        self._log("="*50)
        self._log(f"Actions to replay: {len(self.workflow)}")
        self._log(f"Output directory: {self.output_dir.absolute()}")
        self._log(f"Delay between actions: {delay_between_actions}s")
        self._log("-"*50)
        
        # Launch browser
        if not self.driver:
            if not self.launch_browser(start_url):
                return {"success": False, "error": "Failed to launch browser"}
        elif start_url:
            self.driver.get(start_url)
            time.sleep(1)
        
        # Capture initial screenshot
        if capture_screenshots:
            self._capture_screenshot("start")
            stats["screenshots"] += 1
        
        # Replay each action
        for i, action in enumerate(self.workflow):
            action_type = action.get("type", "click")
            selector = action.get("selector", {})
            
            self._log(f"\n[{i+1}/{len(self.workflow)}] {action_type.upper()}: {selector.get('type')}={selector.get('value', '')[:50]}")
            
            # Check if we need to navigate to a different URL
            action_url = action.get("url")
            if action_url and action_url != self.driver.current_url:
                self._log(f"  Navigating to: {action_url}")
                self.driver.get(action_url)
                time.sleep(1)
            
            success = False
            
            try:
                if action_type == "click":
                    success = self._click_element(selector, capture=capture_screenshots)
                    
                elif action_type == "input":
                    value = action.get("value", "")
                    success = self._input_text(selector, value, capture=capture_screenshots)
                    
                elif action_type == "select":
                    value = action.get("value", "")
                    success = self._select_option(selector, value, capture=capture_screenshots)
                    
                else:
                    self._log(f"  Unknown action type: {action_type}")
                
                if success:
                    stats["successful"] += 1
                    if capture_screenshots:
                        stats["screenshots"] += 1
                else:
                    stats["failed"] += 1
                    error_msg = f"Step {i+1}: {action_type} failed for {selector}"
                    stats["errors"].append(error_msg)
                    
                    if stop_on_error:
                        self._log("  Stopping replay due to error")
                        break
                        
            except Exception as e:
                stats["failed"] += 1
                error_msg = f"Step {i+1}: {str(e)}"
                stats["errors"].append(error_msg)
                self._log(f"  Error: {e}")
                
                if stop_on_error:
                    break
            
            # Delay between actions
            if i < len(self.workflow) - 1:
                time.sleep(delay_between_actions)
        
        self._log("\n" + "="*50)
        self._log("REPLAY COMPLETED")
        self._log(f"Successful: {stats['successful']}/{stats['total']}")
        self._log(f"Failed: {stats['failed']}")
        self._log(f"Screenshots: {stats['screenshots']}")
        self._log(f"Saved to: {self.output_dir.absolute()}")
        self._log("="*50 + "\n")
        
        stats["success"] = stats["failed"] == 0
        return stats
    
    def add_manual_action(
        self,
        action_type: str,
        selector_type: str,
        selector_value: str,
        value: str = None
    ):
        """
        Manually add an action to the workflow.
        
        Args:
            action_type: Type of action (click, input, select)
            selector_type: Type of selector (id, css, xpath, name)
            selector_value: Selector value
            value: Input/select value (for input and select actions)
        """
        action = {
            "step": len(self.workflow) + 1,
            "type": action_type,
            "selector": {
                "type": selector_type,
                "value": selector_value
            },
            "url": self.driver.current_url if self.driver else ""
        }
        
        if action_type in ("input", "select") and value:
            action["value"] = value
        
        self.workflow.append(action)
        self._log(f"Added action: {action_type} on {selector_type}={selector_value}")
    
    def capture_focused_element(self, action_type: str = "click") -> Optional[Dict]:
        """
        Capture the currently focused/active element in the browser.
        
        Call this after the user clicks an element to record it.
        
        Args:
            action_type: Type of action to record (click, input, select)
            
        Returns:
            The captured action dict, or None if no element found
        """
        if not self.driver:
            return None
        
        try:
            element_info = self.driver.execute_script("""
                var el = document.activeElement;
                if (!el || el === document.body || el === document.documentElement) {
                    return null;
                }
                
                function getSelector(element) {
                    if (element.id) return {type: 'id', value: element.id};
                    if (element.name) return {type: 'name', value: element.name};
                    if (element.dataset && element.dataset.testid) 
                        return {type: 'css', value: '[data-testid="' + element.dataset.testid + '"]'};
                    if (element.getAttribute && element.getAttribute('aria-label'))
                        return {type: 'css', value: '[aria-label="' + element.getAttribute('aria-label') + '"]'};
                    
                    // Try class-based unique selector
                    if (element.className && typeof element.className === 'string' && element.className.trim()) {
                        var classes = element.className.trim().split(/\\s+/).filter(function(c) { 
                            return c && c.indexOf(':') === -1; 
                        });
                        if (classes.length > 0) {
                            var selector = element.tagName.toLowerCase() + '.' + classes.join('.');
                            try {
                                if (document.querySelectorAll(selector).length === 1) {
                                    return {type: 'css', value: selector};
                                }
                            } catch(e) {}
                        }
                    }
                    
                    // XPath fallback
                    function getXPath(node) {
                        if (node.id) return '//*[@id="' + node.id + '"]';
                        if (node === document.body) return '/html/body';
                        var ix = 0;
                        var siblings = node.parentNode ? node.parentNode.childNodes : [];
                        for (var i = 0; i < siblings.length; i++) {
                            var sibling = siblings[i];
                            if (sibling === node) {
                                var parentPath = node.parentNode && node.parentNode !== document 
                                    ? getXPath(node.parentNode) : '';
                                return parentPath + '/' + node.tagName.toLowerCase() + '[' + (ix + 1) + ']';
                            }
                            if (sibling.nodeType === 1 && sibling.tagName === node.tagName) ix++;
                        }
                        return '';
                    }
                    return {type: 'xpath', value: getXPath(element)};
                }
                
                return {
                    selector: getSelector(el),
                    tagName: el.tagName.toLowerCase(),
                    text: (el.innerText || el.value || '').substring(0, 100),
                    value: el.value || '',
                    inputType: el.type || ''
                };
            """)
            
            if not element_info:
                self._log("  No focused element found")
                return None
            
            action = {
                "step": len(self.workflow) + 1,
                "type": action_type,
                "selector": element_info.get("selector", {}),
                "tag": element_info.get("tagName", ""),
                "text_preview": element_info.get("text", "")[:50],
                "url": self.driver.current_url,
                "timestamp": int(time.time() * 1000)
            }
            
            if action_type == "input":
                action["value"] = element_info.get("value", "")
            
            self.workflow.append(action)
            selector = element_info.get("selector", {})
            self._log(f"  Captured: {action_type} on {selector.get('type', '?')}={selector.get('value', '?')[:40]}")
            return action
            
        except Exception as e:
            self._log(f"  Error capturing element: {e}")
            return None
    
    def capture_element_at_coords(self, x: int, y: int, action_type: str = "click") -> Optional[Dict]:
        """
        Capture the element at specific coordinates (relative to viewport).
        
        Args:
            x: X coordinate in viewport
            y: Y coordinate in viewport
            action_type: Type of action to record
            
        Returns:
            The captured action dict, or None if no element found
        """
        if not self.driver:
            return None
        
        try:
            element_info = self.driver.execute_script(f"""
                var el = document.elementFromPoint({x}, {y});
                if (!el) return null;
                
                function getSelector(element) {{
                    if (element.id) return {{type: 'id', value: element.id}};
                    if (element.name) return {{type: 'name', value: element.name}};
                    if (element.dataset && element.dataset.testid) 
                        return {{type: 'css', value: '[data-testid="' + element.dataset.testid + '"]'}};
                    
                    // XPath fallback
                    function getXPath(node) {{
                        if (node.id) return '//*[@id="' + node.id + '"]';
                        if (node === document.body) return '/html/body';
                        var ix = 0;
                        var siblings = node.parentNode ? node.parentNode.childNodes : [];
                        for (var i = 0; i < siblings.length; i++) {{
                            var sibling = siblings[i];
                            if (sibling === node) {{
                                var parentPath = node.parentNode && node.parentNode !== document 
                                    ? getXPath(node.parentNode) : '';
                                return parentPath + '/' + node.tagName.toLowerCase() + '[' + (ix + 1) + ']';
                            }}
                            if (sibling.nodeType === 1 && sibling.tagName === node.tagName) ix++;
                        }}
                        return '';
                    }}
                    return {{type: 'xpath', value: getXPath(element)}};
                }}
                
                return {{
                    selector: getSelector(el),
                    tagName: el.tagName.toLowerCase(),
                    text: (el.innerText || el.value || '').substring(0, 100)
                }};
            """)
            
            if not element_info:
                return None
            
            action = {
                "step": len(self.workflow) + 1,
                "type": action_type,
                "selector": element_info.get("selector", {}),
                "tag": element_info.get("tagName", ""),
                "url": self.driver.current_url,
                "timestamp": int(time.time() * 1000)
            }
            
            self.workflow.append(action)
            return action
            
        except Exception as e:
            self._log(f"  Error capturing element at coords: {e}")
            return None
    
    def execute_action(
        self,
        action_type: str,
        selector_type: str,
        selector_value: str,
        value: str = None,
        capture: bool = True
    ) -> bool:
        """
        Execute a single action immediately.
        
        Args:
            action_type: Type of action (click, input, select)
            selector_type: Type of selector (id, css, xpath, name)
            selector_value: Selector value
            value: Input/select value (for input and select actions)
            capture: Whether to capture screenshot
            
        Returns:
            True if successful, False otherwise
        """
        selector = {"type": selector_type, "value": selector_value}
        
        if action_type == "click":
            return self._click_element(selector, capture=capture)
        elif action_type == "input":
            return self._input_text(selector, value or "", capture=capture)
        elif action_type == "select":
            return self._select_option(selector, value or "", capture=capture)
        else:
            self._log(f"Unknown action type: {action_type}")
            return False
    
    def navigate(self, url: str, capture: bool = True) -> bool:
        """
        Navigate to a URL.
        
        Args:
            url: URL to navigate to
            capture: Whether to capture screenshot after navigation
            
        Returns:
            True if successful, False otherwise
        """
        if not self.driver:
            return False
        
        try:
            self.driver.get(url)
            time.sleep(1)
            
            if capture:
                self._capture_screenshot("navigate")
            
            return True
            
        except Exception as e:
            self._log(f"Navigation failed: {e}")
            return False
    
    def wait_for_element(self, selector_type: str, selector_value: str, timeout: float = None) -> bool:
        """
        Wait for an element to be present.
        
        Args:
            selector_type: Type of selector (id, css, xpath, name)
            selector_value: Selector value
            timeout: Wait timeout (uses default if None)
            
        Returns:
            True if element found, False if timeout
        """
        selector = {"type": selector_type, "value": selector_value}
        element = self._find_element(selector, timeout)
        return element is not None
    
    def get_page_info(self) -> Dict:
        """
        Get information about the current page.
        
        Returns:
            Dict with page information
        """
        if not self.driver:
            return {}
        
        return {
            "url": self.driver.current_url,
            "title": self.driver.title,
            "window_size": self.driver.get_window_size()
        }


def main():
    """Main entry point with CLI interface."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Selenium Screenshot Automater - Browser automation with element-based targeting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Record a workflow:
    python selenium_automater.py record --url https://example.com --output my_workflow

  Replay a workflow:
    python selenium_automater.py replay --workflow my_workflow/selenium_workflow.json

  Replay with custom settings:
    python selenium_automater.py replay --workflow workflow.json --delay 2.0 --browser firefox
"""
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Record command
    record_parser = subparsers.add_parser("record", help="Record a new workflow")
    record_parser.add_argument("--url", "-u", required=True, help="Starting URL")
    record_parser.add_argument("--output", "-o", default="screenshots", help="Output directory")
    record_parser.add_argument("--browser", "-b", default="chrome", 
                              choices=["chrome", "firefox", "edge"], help="Browser to use")
    record_parser.add_argument("--pattern", "-p", default="{count}_{action}", 
                              help="Screenshot naming pattern")
    
    # Replay command
    replay_parser = subparsers.add_parser("replay", help="Replay a recorded workflow")
    replay_parser.add_argument("--workflow", "-w", required=True, help="Workflow JSON file")
    replay_parser.add_argument("--output", "-o", help="Output directory for screenshots")
    replay_parser.add_argument("--url", "-u", help="Override starting URL")
    replay_parser.add_argument("--delay", "-d", type=float, default=1.0, 
                              help="Delay between actions (seconds)")
    replay_parser.add_argument("--browser", "-b", default="chrome",
                              choices=["chrome", "firefox", "edge"], help="Browser to use")
    replay_parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    replay_parser.add_argument("--no-screenshots", action="store_true", 
                              help="Don't capture screenshots")
    replay_parser.add_argument("--stop-on-error", action="store_true",
                              help="Stop replay on first error")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == "record":
        automater = SeleniumAutomater(
            output_dir=args.output,
            naming_pattern=args.pattern,
            browser=args.browser
        )
        
        automater.start_recording(args.url)
        
        print("\n" + "-"*50)
        print("Recording in progress...")
        print("When finished, press Enter in this terminal to stop recording")
        print("-"*50 + "\n")
        
        input()
        
        automater.stop_recording()
        automater.save_workflow()
        automater.close_browser()
        
    elif args.command == "replay":
        automater = SeleniumAutomater(
            output_dir=args.output or "replay_output",
            browser=args.browser,
            headless=args.headless
        )
        
        stats = automater.replay_workflow(
            workflow_path=args.workflow,
            output_dir=args.output,
            url=args.url,
            delay_between_actions=args.delay,
            capture_screenshots=not args.no_screenshots,
            stop_on_error=args.stop_on_error
        )
        
        automater.close_browser()
        
        # Exit with error code if replay had failures
        if not stats.get("success"):
            sys.exit(1)


if __name__ == "__main__":
    main()
