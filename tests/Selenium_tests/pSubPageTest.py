# -*- coding: utf-8 -*-
'''This is a Python 2.7 script for testing the performance of generating subpages to the Collab wiki. Modules needed for usage: Selenium webdriver and geckodriver. If the test is succesful the script outputs the arithmetic mean of the time it took to generate a page. The time is measured from how long it took to save the page to the wiki. Change variables site, password and user to match your setup. Variable n can be changed to modify how many pages the test creates.

Step-by-step install guide:

1. Use pip to install selenium: pip install selenium 
2. Fetch geckodriver from Mozilla Github: wget https://github.com/mozilla/geckodriver/releases/download/v0.20.1/geckodriver-v0.20.1-linux64.tar.gz
3. Unpack: tar -xvzf geckodriver-v0.20.1-linux64.tar.gz
4. Add geckodriver to PATH or copy it to /usr/local/bin: cp geckodriver /usr/local/bin
5. Modify variables site, password and user in this file to match your setup.
6. The test can now be executed by command: python pSubPageTest.py
'''

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import NoAlertPresentException
import unittest, time, re, random

from timeit import default_timer as timer

class newPageGenerationCase(unittest.TestCase):
    def setUp(self):
        self.driver = webdriver.Firefox()
        self.driver.implicitly_wait(30)
        self.verificationErrors = []
        self.accept_next_alert = True
    
    def test_newPageGeneration_test_case(self):

	site = "https://172.17.0.2/collab" #FIXME: Insert the collab site root e.g. https://172.17.0.2/collab
	user = "collab" #FIXME: Insert a valid username that is used for the tests.
	password = "hunter2" #FIXME: Insert the users password.
	n = 10 #How many subpages are generated.

        driver = self.driver
        driver.get(site)
	driver.switch_to_alert().send_keys(user + Keys.TAB + password)
	driver.switch_to_alert().accept()
	total_times = [] 

	r = random.randint(1,100000)
	driver.get(site + "/pNewPageTest")
	driver.find_element_by_link_text("Edit").click()
	driver.find_element_by_id("editor-textarea").click()
	driver.find_element_by_id("editor-textarea").clear()
	driver.find_element_by_id("editor-textarea").send_keys('This is the main page. Generating %s subpages. #' %n, r)
	driver.find_element_by_name("button_save").click()

	for i in range(1,n+1):

		r = random.randint(1,100000)
		driver.get(site + "/pNewPageTest/pSubPage" + '%s' %i)
		driver.find_element_by_link_text("Edit").click()
		driver.find_element_by_id("editor-textarea").click()
		driver.find_element_by_id("editor-textarea").clear()
		driver.find_element_by_id("editor-textarea").send_keys('This is a subpage. #', r)
		t0 = timer()
		driver.find_element_by_name("button_save").click()
        	driver.find_element_by_id("main-nav").click()
		t1 = timer()
		t = t1 - t0
		total_times.append(t)
	
	driver.get(site + '/pNewPageTest?action=DeletePage')
	driver.find_element_by_name("delete_subpages").click()
        driver.find_element_by_name("delete").click()
	avg_time= sum(total_times) / len(total_times)
	print "Average time for generating the page: ", avg_time 

    def is_element_present(self, how, what):
        try: self.driver.find_element(by=how, value=what)
        except NoSuchElementException as e: return False
        return True
    
    def is_alert_present(self):
        try: self.driver.switch_to_alert()
        except NoAlertPresentException as e: return False
        return True
    
    def close_alert_and_get_its_text(self):
        try:
            alert = self.driver.switch_to_alert()
            alert_text = alert.text
            if self.accept_next_alert:
                alert.accept()
            else:
                alert.dismiss()
            return alert_text
        finally: self.accept_next_alert = True
    
    def tearDown(self):
        self.driver.quit()
        self.assertEqual([], self.verificationErrors)

if __name__ == "__main__":
    unittest.main()




