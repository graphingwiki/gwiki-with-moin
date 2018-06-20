# -*- coding: utf-8 -*-
'''This is a Python 2.7 script for testing Collab wiki graph generation function graphingwiki. Modules needed for usage: Selenium webdriver and geckodriver. Change variables site, password and user to match your setup. The script creates a test page to the wiki with a graph of the Collab wiki front page. If the test is succesful the script outputs the arithmetic mean of the time it took to generate the graph five times. The time is measured from when the page is saved to when the graph is first displayed. Change variables site, password and user from test_config.ini to match your setup. 

Step-by-step install guide:

1. Use pip to install selenium: pip install selenium 
2. Fetch geckodriver from Mozilla Github: wget https://github.com/mozilla/geckodriver/releases/download/v0.20.1/geckodriver-v0.20.1-linux64.tar.gz
3. Unpack: tar -xvzf geckodriver-v0.20.1-linux64.tar.gz
4. Add geckodriver to PATH or copy it to /usr/local/bin: cp geckodriver /usr/local/bin
5. Modify variables site, password and user from test_config.ini to match your setup.
6. The test can now be executed by command: python pGraphTest.py

'''

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import NoAlertPresentException
import unittest, time, re, random, ConfigParser
from timeit import default_timer as timer

config = ConfigParser.ConfigParser()
config.read('test_config.ini')
site = config.get('Site_variables','site').strip("'")
user = config.get('Site_variables','user').strip("'")
password = config.get('Site_variables','password').strip("'")

class GeneratingTestCase(unittest.TestCase):
    def setUp(self):
        self.driver = webdriver.Firefox()
        self.driver.implicitly_wait(30)
        self.verificationErrors = []
        self.accept_next_alert = True
    
    def test_untitled_test_case(self):
	'''Generates a test page five times with a graph and then deletes it. Outputs the mean of the time it took to generate a graph if the test did not generate any errors.'''

	n=int(config.get('pGraphTest_settings','number_of_tests'))

        driver = self.driver
        driver.get(site)
	driver.switch_to_alert().send_keys(user + Keys.TAB + password)
	driver.switch_to_alert().accept()
	total_times = []
	for i in range(0,n+1):
		r = random.randint(1,100000)
		driver.get(site + "/graphtestpage")
		driver.find_element_by_link_text("Edit").click()
		driver.find_element_by_id("editor-textarea").click()
		driver.find_element_by_id("editor-textarea").clear()
		driver.find_element_by_id("editor-textarea").send_keys("Creating a test page with a graph and then deleting it. <<InlineGraph(FrontPage?orderby=&colorby=&ordershape=&format=png&shapeby=&neighbours=&height=1024.0&otherpages=FrontPage&width=1024.0&depth=1&limit=&invisnodes=&action=ShowGraph&legend=bottom&overview_threshold=150)>>", r)
		t0 = timer()
		driver.find_element_by_name("button_save").click()
		driver.find_element_by_id("main-nav").click()
		t1 = timer()
		t = t1 - t0
		total_times.append(t)
		driver.get(site + '/graphtestpage?action=DeletePage')
        	driver.find_element_by_name("delete").click()

	avg_time= sum(total_times) / len(total_times)
	print "Average time for generating a graph: ", avg_time 

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

