# -*- coding: utf-8 -*-
'''This is a Python 2.7 script for testing Collab wiki basic functionality. Modules needed for usage: Selenium webdriver and geckodriver. The script creates three new pages to the wiki: plaintextpage, graphtestpage and macrotestpage. These pages are used to test different basic functionality of the wiki. The pages are deleted at the end of the script. Change variables site, password and user from test_config.ini to match your setup. 

Step-by-step install guide:

1. Use pip to install selenium: pip install selenium 
2. Fetch geckodriver from Mozilla Github: wget https://github.com/mozilla/geckodriver/releases/download/v0.20.1/geckodriver-v0.20.1-linux64.tar.gz
3. Unpack: tar -xvzf geckodriver-v0.20.1-linux64.tar.gz
4. Add geckodriver to PATH or copy it to /usr/local/bin: cp geckodriver /usr/local/bin
5. Modify variables site, password and user from test_config.ini to match your setup.
6. The test can now be executed by command: python basicFunctionsTest.py

'''
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import NoAlertPresentException
import unittest, time, re, random, ConfigParser

config = ConfigParser.ConfigParser()
config.read('test_config.ini')
site = config.get('Site_variables','site').strip("'")
user = config.get('Site_variables','user').strip("'")
password = config.get('Site_variables','password').strip("'")

class basicFunctionsTestCase(unittest.TestCase):
    def setUp(self):
        self.driver = webdriver.Firefox()
        self.driver.implicitly_wait(30)
        self.verificationErrors = []
        self.accept_next_alert = True
    
    def test_basicFuntionsTest_test_case(self):
        driver = self.driver
	r = random.randint(1,100000)

	driver.get(site)
	driver.switch_to_alert().send_keys(user + Keys.TAB + password)
	driver.switch_to_alert().accept()
	if (config.get('basicFunctionsTest_settings', 'test_newpage') == 'True'):
		driver.get(site + '/plaintexttestpage')
		print "Test 1: Attempting to create a new page with plaintext"
		driver.find_element_by_link_text("Edit").click()
		driver.find_element_by_id("editor-textarea").click()
		driver.find_element_by_id("editor-textarea").clear()
		driver.find_element_by_id("editor-textarea").send_keys("A test page with plaintext.", r)
		driver.find_element_by_name("button_save").click()
		print "Test 1: Successful!"	
		driver.get(site+ '/plaintexttestpage')
		print "Test 2: Attempting to edit an existing page"
		driver.find_element_by_link_text("Edit").click()
		driver.find_element_by_id("editor-textarea").click()
		driver.find_element_by_id("editor-textarea").send_keys("\nEditing test", r)
		driver.find_element_by_name("button_save").click()
		print "Test 2: Successful!"

	if (config.get('basicFunctionsTest_settings','test_graphpage') == 'True'):
		driver.get(site + '/graphtestpage')
		print "Test 3: Attempting to create a page with a graph"
		driver.find_element_by_link_text("Edit").click()
		driver.find_element_by_id("editor-textarea").click()
		driver.find_element_by_id("editor-textarea").clear()
		driver.find_element_by_id("editor-textarea").send_keys("A test page with a graph <<InlineGraph(FrontPage?orderby=&colorby=&ordershape=&format=png&shapeby=&neighbours=&height=1024.0&otherpages=FrontPage&width=1024.0&depth=1&limit=&invisnodes=&action=ShowGraph&legend=bottom&overview_threshold=150)>>", r)
		driver.find_element_by_name("button_save").click()
		print "Test 3: Successful!"
	if (config.get('basicFunctionsTest_settings','test_search') == 'True'):
		driver.get(site)
		print "Test 4: Testing frontpage search"
		driver.find_element_by_name("value").click()
		driver.find_element_by_name("value").clear()
		driver.find_element_by_name("value").send_keys("Search test")
		driver.find_element_by_name("value").send_keys(Keys.ENTER)
		time.sleep(2)
		print "Test 4: Successful!"

	if (config.get('basicFunctionsTest_settings','test_macropage') == 'True'):
		driver.get(site + '/macrotestpage')
		print "Test 5: Creating a page with several different macrofunctions"
		driver.find_element_by_link_text("Edit").click()
		driver.find_element_by_id("editor-textarea").clear()
		driver.find_element_by_id("editor-textarea").send_keys("Macro tests1\n\nAdvanced Search: <<AdvancedSearch>>\n\nTitle Search: <<TitleSearch>>\n\nFull Search: <<FullSearch>>\n\nFull Search(): <<FullSearch()>>\n\nGoTo: <<GoTo>>\n\nPageCount: <<PageCount(exists)>>\n\nChart: <<StatsChart(hitcounts)>>\n\nSystem Admins: <<SystemAdmin>>\nCreate a new page: <<NewPage(NewPage, Create a new page)>>\nMetaTable test<<MetaTable(WikiSandBox)>>\n #", r)
		driver.find_element_by_name("button_save").click()
		print "Test 5: Successful!"
		print "Test 6: Testing Advanced Search macro"
		driver.find_element_by_name("and_terms").click()
		driver.find_element_by_name("and_terms").clear()
		driver.find_element_by_name("and_terms").send_keys("test")
		driver.find_element_by_xpath("//input[@value='Go get it!']").click()
		print "Test 6: Successful!"
		driver.get(site + '/macrotestpage')
		print "Test 7: Testing Title Search macro"
		driver.find_element_by_xpath("(//input[@name='value'])[2]").click()
		driver.find_element_by_xpath("(//input[@name='value'])[2]").clear()
		driver.find_element_by_xpath("(//input[@name='value'])[2]").send_keys("test")
		driver.find_element_by_xpath("//input[@value='Search Titles']").click()
		print "Test 7: Successful!"
		driver.get(site + '/macrotestpage')
		print "Test 8: Testing Full Search macro"
		driver.find_element_by_xpath("(//input[@name='value'])[3]").click()
		driver.find_element_by_xpath("(//input[@name='value'])[3]").clear()
		driver.find_element_by_xpath("(//input[@name='value'])[3]").send_keys("test")
		driver.find_element_by_xpath("//input[@value='Search Text']").click()
		print "Test 8: Successful!"
		driver.get(site + '/macrotestpage')
		print "Test 9: Testing GoTo macro"
		driver.find_element_by_name("target").click()
		driver.find_element_by_name("target").clear()
		driver.find_element_by_name("target").send_keys("FrontPage")
		driver.find_element_by_xpath("//input[@value='Go To Page']").click()
		print "Test 9: Successful!"
		driver.get(site + '/macrotestpage')
		print "Test 10: Testing NewPage macro"
		driver.find_element_by_name("pagename").click()
		driver.find_element_by_name("pagename").clear()
		driver.find_element_by_name("pagename").send_keys("testpage1")
		driver.find_element_by_xpath("//input[@value='Create a new page']").click()
		driver.find_element_by_link_text("Edit").click()
		print "Test 10: Successful!"
	if (config.get('basicFunctionsTest_settings','test_deletePages') == 'True'):
		print "Test 11: Testing page deletion"
		if (config.get('basicFunctionsTest_settings','test_newpage') == 'True'):
			driver.get(site + '/plaintexttestpage?action=DeletePage')
			driver.find_element_by_name("delete").click()

		if (config.get('basicFunctionsTest_settings','test_graphpage') == 'True'):
			driver.get(site + '/graphtestpage?action=DeletePage')
			driver.find_element_by_name("delete").click()

		if (config.get('basicFunctionsTest_settings','test_macropage') == 'True'):
			driver.get(site + '/macrotestpage?action=DeletePage')
			driver.find_element_by_name("delete").click()
		print "Test 11: Successful!"
    
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
