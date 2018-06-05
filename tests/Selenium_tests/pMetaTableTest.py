# -*- coding: utf-8 -*-
'''This is a Python 2.7 script for testing Collab wiki table generation performance. Modules needed for usage: Selenium webdriver and geckodriver. The script measures the performance of generating tables with function MetaTable to the wiki. Change variables site, password and user to match your setup. Variables n, n_p and n_v can be modified to change how many times the test will be run, how many pages the table will contain and how many columns the table will have.

Step-by-step install guide:

1. Use pip to install selenium: pip install selenium 
2. Fetch geckodriver from Mozilla Github: wget https://github.com/mozilla/geckodriver/releases/download/v0.20.1/geckodriver-v0.20.1-linux64.tar.gz
3. Unpack: tar -xvzf geckodriver-v0.20.1-linux64.tar.gz
4. Add geckodriver to PATH or copy it to /usr/local/bin: cp geckodriver /usr/local/bin
5. Modify variables site, password and user in this file to match your setup.
6. The test can now be executed by command: python pMetaTableTest.py

'''

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import NoAlertPresentException
import unittest, time, re, random
from timeit import default_timer as timer

class basicFunctionsTestCase(unittest.TestCase):
    def setUp(self):
        self.driver = webdriver.Firefox()
        self.driver.implicitly_wait(30)
        self.verificationErrors = []
        self.accept_next_alert = True
    
    def test_basicFuntionsTest_test_case(self):
        driver = self.driver
		
	r = random.randint(1,100000)
	site = "https://172.17.0.2/collab" #FIXME: Insert the collab site root e.g. https://172.17.0.2/collab 
	user = "collab" #FIXME: Insert a valid username that is used for the tests.
	password = "hunter2" #FIXME: Insert the users password.
	n = 5 # How many times the table will be generated.
	n_p = 5 # How many pages will be created.
	n_v = 20 # How many columns the table will have.

	driver.get(site)
	driver.switch_to_alert().send_keys(user + Keys.TAB + password)
	driver.switch_to_alert().accept()

	r = random.randint(1,100000)
	l_n = ['metatableTest']
	for i in range(1,n_p+1):
		s_n = 'metatableTest/metatableTestSub'+str(i)
		l_n.append(s_n)
	frontPage_input ="<<MetaTable(" + ','.join(l_n) + ")>>"

	for i in range(1,n_p+1):
		subPage_input = []
		for j in range(1,n_v+1):
			j = str(j)
			r = random.randint(1,100000)
			s_n = " VARIABLE"+j+" :: randomText#"+str(r)
			subPage_input.append(s_n)

		subPage_input = '\n'.join(subPage_input)
		r = random.randint(1,100000)
		driver.get(site+'/metatableTest/metatableTestSub' + str(i))
		driver.find_element_by_link_text("Edit").click()
        	driver.find_element_by_id("editor-textarea").click()
        	driver.find_element_by_id("editor-textarea").clear()
        	driver.find_element_by_id("editor-textarea").send_keys(subPage_input + "\n #"+str(r))
        	driver.find_element_by_name("button_save").click()
	test_times = []
	
	for k in range (1,n+1):
		driver.get(site + '/metatableTest')
		r = random.randint(1,100000)
		driver.find_element_by_link_text("Edit").click()
		driver.find_element_by_id("editor-textarea").click()
		driver.find_element_by_id("editor-textarea").clear()
		driver.find_element_by_id("editor-textarea").send_keys(frontPage_input + "\n #"+str(r))
		t0 = timer()
		driver.find_element_by_name("button_save").click()
		driver.find_element_by_xpath("//div[@id='content']/div/div/table/tbody/tr/td").click()
		t1 = timer()
		test_times.append(t1-t0)
		driver.get(site + '/metatableTest?action=DeletePage')
		driver.find_element_by_name("delete").click()


	driver.get(site + '/metatableTest')
	r = random.randint(1,100000)
	driver.find_element_by_link_text("Edit").click()
	driver.find_element_by_id("editor-textarea").click()
	driver.find_element_by_id("editor-textarea").clear()
	driver.find_element_by_id("editor-textarea").send_keys("Test finished, deleting subpages #" +str(r))
	driver.find_element_by_name("button_save").click()
	driver.get(site + '/metatableTest?action=DeletePage')
	driver.find_element_by_name("delete_subpages").click()
	driver.find_element_by_name("delete").click()
	avg_time = sum(test_times)/len(test_times)
	print "Average time for generating a table: ", avg_time
    
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
