Python 2.7 scripts for testing Collab wiki functionality and performance. Modules needed for usage: Selenium webdriver and geckodriver. 
Change variables site, password and user from test_config.ini to match your setup on each test. Variable site should be set as the address to collab wiki frontpage (e.g. site='https://172.17.0.2/collab'). Variables user and password should be set as any account you want the tests to be ran as.
Tests that start with 'p' measure performance.
Different settings for each test can be modified from test_config.ini.

Step-by-step install guide:
1. Use pip to install Selenium: pip install selenium 
2. Fetch geckodriver from Mozilla Github: wget https://github.com/mozilla/geckodriver/releases/download/v0.20.1/geckodriver-v0.20.1-linux64.tar.gz
3. Unpack: tar -xvzf geckodriver-v0.20.1-linux64.tar.gz
4. Add geckodriver to PATH or copy it to /usr/local/bin: cp geckodriver /usr/local/bin
5. Modify variables site, password and user from test_config.ini to match your setup.
6. The test can now be executed by command e.g. : python basicFunctionsTest.py
