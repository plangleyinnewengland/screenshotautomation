"""Test script for debugging Selenium click tracking with localStorage"""
from selenium_automater import SeleniumAutomater
import time

a = SeleniumAutomater(output_dir='test_selenium')
print('Starting recording...')
a.start_recording('https://example.com')
print('Recording started')

# Use Selenium to click the link - this will trigger navigation
print('Clicking link with Selenium...')
time.sleep(1)
link = a.driver.find_element('tag name', 'a')
link.click()

# Wait for navigation and give time for localStorage to be read on new page
print('Waiting for navigation...')
time.sleep(2)

# The tracker should re-inject and reload from localStorage
print(f'Workflow has {len(a.workflow)} actions')

# Get any clicks stored in localStorage on new page  
clicks = a._get_recorded_clicks()
print(f'Clicks from localStorage/tracker: {len(clicks)}')
for c in clicks:
    print(f'  - {c.get("tagName")}: {c.get("selector")}')

a.stop_recording()
saved = a.save_workflow()
print(f'Workflow saved: {saved}')
print(f'Total actions: {len(a.workflow)}')
a.close_browser()
