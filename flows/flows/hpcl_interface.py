import requests

from bs4 import BeautifulSoup
from flows.stdlogger import root

headers = {'User-agent': 'ALPINE ENERGY LIMITED ND Distributor/9914526902/alpineenergyhpcl@gmail.com'}


class HPCLCustomerPortal():
	def get_session(self):
		if not self.session:
			self.session = requests.Session()
		return self.session

	def __init__(self, user, password, debug=False):
		self.user = user
		self.password = password
		self.session = None
		self.debug = debug

	def login(self):
		s = self.get_session()

		# r = s.get("https://sales.hpcl.co.in/bportal/index_sales.jsp")
		login_key = {
		"cust_id": self.user,
		"pwd": self.password,
		"x": "14",
		"y": "0",
		"next": "html/home.html",
		"bad": "error/badlogin_en.html",
		"entityjavascript": "true",
		"entityscreensize": "unknown"
		}

		r = s.post("https://sales.hpcl.co.in/bportal/login/cust_login.jsp", data=login_key, headers=headers)
		content = r.content

		if self.debug:
			root.debug(content)

		if 'invalid' in content:
			raise LoginError('Invalid User')

		if 'lpg_select' in content:
			root.info('Login Success')

		if 'SERVER IS BUSY' in content:
			root.debug("Server busy. Will retry")
			raise ServerBusy()

	def get_account_data(self, from_date, to_date, mode='raw'):
		s = self.get_session()
		account_data = {
		"txtfrmday": from_date.split('-')[2],
		"txtfrmmonth": from_date.split('-')[1],
		"txtfrmyear": from_date.split('-')[0],
		"txttoday": to_date.split('-')[2],
		"txttomonth": to_date.split('-')[1],
		"txttoyear": to_date.split('-')[0],
		"r2": "EXCEL"
		}
		account_data = s.post('https://sales.hpcl.co.in/bportal/lpg/accountdisp.jsp', data=account_data,
							  headers=headers, stream=True)
		content = account_data.content

		if self.debug:
			root.debug(content)

		if mode == 'raw':
			return content

		soup = BeautifulSoup(content)

		headings_list = [td.text.strip() for td in soup.body.findAll(id='Headings')[0].findAll('tr')[0].findAll('td')]
		content_rows = soup.body.findAll(id='content')[0].findAll('tr')[:-4]
		rs_list = []
		for row in content_rows:
			rs_list.append({headings_list[index]: value.text.strip() for index, value in enumerate(row.findAll('td'))})

		return rs_list

	def get_debit_credit_total(self, from_date, to_date):
		soup = BeautifulSoup(self.get_account_data(from_date, to_date, mode='raw'))
		dr_cr = soup.findAll('tr')[-4].findAll('td')[4:6]
		dr_cr = (float(dr_cr[0].text.replace(',', '')), -1 * float(dr_cr[1].text.replace(',', '')))
		return dr_cr[0], dr_cr[1]

	def get_current_balance_as_on_date(self):
		s = self.get_session()

		data = s.post(
			'https://sales.hpcl.co.in/Cust_Credit_Client/CreditCheckResponseBP_Live.jsp',
			data={'custcode': self.user},
			headers=headers
		)
		content = data.content
		soup = BeautifulSoup(content)

		return float(soup.findAll('tr')[3].findAll('td')[1].text.replace("&nbsp", ""))


class LoginError(Exception):
	def __init__(self, msg):
		self.msg = msg

class ServerBusy(Exception):
	pass