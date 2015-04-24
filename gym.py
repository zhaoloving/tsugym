# coding: UTF-8
import requests
import logging
import re
from bs4 import BeautifulSoup
import time
import thread


#####################
#  Data Structures  #
#####################

class Court(object):
  def __init__(self):
    self.id = ''
    self.session = [] # list of hours
    self.name = ''
    self.bookId = ''
    self.cost = ''
    self.status = 0  # 0 for available, 1 for booked

class Gym(object):
  def __init__(self):
    self.courts = []

#############
#  Crawler  #
#############

class GymParser(object):

  URL_PAT = ('http://50.tsinghua.edu.cn/gymsite/cacheAction.do?ms=viewBook&'
             'gymnasium_id=%(gymid)s&item_id=%(itemid)s&'
             'time_date=%(date)s&userType=')

  INFO_RE = re.compile(r'''resourceArray\.push(\{id:'(.*)',time_session:'.*',field_name:'.*',overlaySize:'.*'\});''')

  def __init__(self, gymId, itemId):
    self.gymId = gymId
    self.itemId = itemId

  def Crawl(self, date=None):
    if date is None:
      pass
    url = self.URL_PAT % {'gymid': self.gymId, 'date': date,
                          'itemid': self.itemId}
    try:
      r = requests.get(url, timeout=5)
      logging.debug(r.status_code)
      return r.text if r.status_code == 200 else None
    except requests.exceptions.RequestException, e:
      logging.error(e)
      return None

  def ExtractCourts(self, html):
    id2court = {}
    for match in re.finditer(r'''resourceArray\.push\(\{id:'(.*)',time_session:'(.*)',field_name:'(.*)',overlaySize:'(.*)'\}\);''', html):
      if (len(match.groups()) < 4):
        logging.error('xxx')
        continue
      court = Court()
      court.id = match.group(1)
      court.session = match.group(2)
      court.name = match.group(3)
      id2court[court.id] = court
    # Don't need cost for now.
    # for match in re.finditer(r'''addCost\('(.*)','(.*)'\);''', html):
      # if (len(match.groups()) < 2):
        # logging.error('yyy')
        # continue
    for match in re.finditer(r'''markResStatus\('(.*)','(.*)','(.*)'\);''', html):
      if (len(match.groups()) < 3 or match.group(2) not in id2court):
        logging.error('yyy')
        continue
      court = id2court[match.group(2)]
      court.status = match.group(3)
      court.bookId = match.group(1)

    gym = Gym()
    gym.courts = list(id2court.itervalues())
    for c in gym.courts:
      logging.debug(c.__dict__)
    return gym


class CourtBooker(object):

  BOOK_URL = 'http://50.tsinghua.edu.cn/gymbook/gymbook/gymBookAction.do?ms=saveGymBook'
  LIST_URL = 'http://50.tsinghua.edu.cn/gymbook/gymBookAction.do?ms=viewGymBook&gymnasium_id=3998000&item_id=&time_date=&viewType=m'

  def __init__(self, sessionId):
    self.sessionId = sessionId
    self.cookies = dict(JSESSIONID=sessionId)
    self._refresh_started = False

  def fetchBookedCourts(self):
    try:
      r = requests.get(self.LIST_URL, cookies=self.cookies, timeout=5)
      if r.status_code != 200:
        return None
    except requests.exceptions.RequestException, e:
      logging.error(e)
      return None

    soup = BeautifulSoup(r.text)
    try:
      records = soup.find('h4', text='已预约场地信息').parent.table.tbody("tr")
      if not records:
        return None
    except AttributeError, e:
      return None

    ans = []
    for record in records:
      tds = record("td")
      if tds is None or len(tds) < 4:
        logging.error("malformed booked record: %s", str(record))
        continue
      item = tuple([tds[i].text for i in xrange(4)])
      logging.info('Booked court: %s', ' | '.join(item))
      ans.append(item)
    return ans

  def startKeepSession(self, interval=20, background=True):
    def keepSession(cookies, interval):
      while True:
        try:
          r = requests.get(CourtBooker.LIST_URL, cookies=cookies, timeout=5)
          logging.info('Session refreshed with status_code %d', r.status_code)
          if r.status_code == 200 and u'登录' in r.text:
            logging.error('Session ended, please login again.')
        except requests.exceptions.RequestException, e:
          logging.error(e)
        time.sleep(interval)
    if not self._refresh_started:
      self._refresh_started = True
      if background:
        thread.start_new(keepSession, (self.cookies, interval))
        logging.info('Thread started to keep session.')
      else:
        keepSession(self.cookies, interval)


  def Book(self, courtId, date):
    payload = {
        'bookData.totalCost': '',
        'bookData.book_person_zjh': '',
        'bookData.book_person_name': '',
        'bookData.book_person_phone': '18612184561',  #TODO: config
        'bookData.book_mode': 'from-phone',
        'allFieldTime': courtId + '#' + date
    }
    try:
      r = requests.post(self.BOOK_URL, payload, cookies=self.cookies, timeout=5)
      if r.status_code != 200:
        return False
    except requests.exceptions.RequestException, e:
      logging.error(e)
      return False

    succeeded = r.json().get('msg', '') == u'预定成功'
    if not succeeded:
      logging.error(r.json().get('msg', ''))
    return succeeded


if __name__ == '__main__':
  logging.basicConfig(
      level=logging.DEBUG,
      format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
      datefmt='%a, %d %b %Y %H:%M:%S')

  parser = GymParser('3998000', '4045681')
  html = parser.Crawl('2015-04-03')
  if html:
    parser.ExtractCourts(html)

  booker = CourtBooker('abcF8CnWBN0ny6kdtEOXu')
  logging.info(booker.fetchBookedCourts())
  booker.startKeepSession(15, background = False)
  # logging.info(booker.Book("5307614", "2015-04-02"))
