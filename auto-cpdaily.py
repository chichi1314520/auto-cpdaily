import re
import sys
import math
import json
import time
import base64
import random
import smtplib
import requests
from lxml import etree
from datetime import datetime
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication


class Report:
    def __init__(self):
        #----------------------------------------------------------#
        #注意：脚本能否运行取决于下面两个网址能否被正常ping通
        #（只要一个成功即可).
        #html1: id.学校的英文缩写.edu.cn/authserver/login?
        #html2: https://ids.学校的英文缩写.edu.cn/authserver/login?
        #如果全部失败，尝试通过知网https://fsso.cnki.net查找对应学校
        #网址然后在下方的修改loginUrl即可（只需要改根URL）  
        #-------------------------手动输入区-----------------------#       
        # 表单构造
        self.xh1 = ['输入你学号']
        self.pwd1 = ['输入你密码',]
        self.address1 = ['输入你的地址']
        self.schoolSignal = 'hrbust'
        self.content = ""
        #----------------------------------------------------------# 

    def Get_cookies(self):
        loginUrl = 'http://authserver.hrbust.edu.cn/authserver/login?service=https%3A%2F%2Fhrbust.campusphere.net%2Fportal%2Flogin'
        aes_chars = 'ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678'
        aes_chars_len = len(aes_chars)
        def randomString(len):
            retStr = ''
            i=0
            while i < len:
                retStr += aes_chars[(math.floor(random.random() * aes_chars_len))]
                i=i+1
            return retStr

        def add_to_16(s):
            while len(s) % 16 != 0:
                s += '\0'
            return str.encode(s,'utf-8')

        def getAesString(data,key,iv):
            key = re.sub('/(^\s+)|(\s+$)/g', '', key)
            aes = AES.new(str.encode(key),AES.MODE_CBC,str.encode(iv))
            pad_pkcs7 = pad(data.encode('utf-8'), AES.block_size, style='pkcs7')
            encrypted =aes.encrypt(pad_pkcs7)
            return str(base64.b64encode(encrypted),'utf-8')

        def encryptAES(data,aesKey):
            encrypted =getAesString(randomString(64)+data,aesKey,randomString(16))
            return encrypted

        server = requests.session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.16 Safari/537.36 Edg/79.0.309.12'
        }
        try:
            login_html = server.get(loginUrl, headers=headers).text
        except:
            loginUrl = 'http://authserver.hrbust.edu.cn/authserver/login?service=https%3A%2F%2Fhrbust.campusphere.net%2Fportal%2Flogin'
            login_html = server.get(loginUrl, headers=headers).text
            
        html = etree.HTML(login_html)
        element = html.xpath('/html/script')[1].text

        # 获取表单项
        pwdDefaultEncryptSalt = element.split('\"')[3].strip()
        lt = html.xpath("//input[@type='hidden' and @name='lt']")[0].attrib['value']
        dllt = html.xpath("//input[@type='hidden' and @name='dllt']")[0].attrib['value']
        execution = html.xpath("//input[@type='hidden' and @name='execution']")[0].attrib['value']
        rmShown = html.xpath("//input[@type='hidden' and @name='rmShown']")[0].attrib['value']

        password = encryptAES(self.pwd, pwdDefaultEncryptSalt)

        params = {
            "username": self.xh,
            "password": password,
            "lt": lt,
            "dllt": dllt,
            "execution": execution,
            "_eventId": "submit",
            "rmShown": rmShown
        }

        res = server.post(loginUrl, data=params, headers=headers)
        self.cookies = server.cookies

    def Get(self):
        queryCollectWidUrl = 'https://hrbust.campusphere.net/wec-counselor-collector-apps/stu/collector/queryCollectorProcessingList'
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 4.4.4; OPPO R11 Plus Build/KTU84P) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/33.0.0.0 Safari/537.36 yiban/8.1.11 cpdaily/8.1.11 wisedu/8.1.11',
            'content-type': 'application/json',
            'Accept-Encoding': 'gzip,deflate',
            'Accept-Language': 'zh-CN,en-US;q=0.8',
            'Content-Type': 'application/json;charset=UTF-8'
        }

        params = {
            'pageSize': 6,
            'pageNumber': 1
        }

        server = requests.session()
        res = server.post(queryCollectWidUrl, headers=headers, cookies=self.cookies, data=json.dumps(params))
        
        if res.json()['datas']['rows'][0]['isHandled'] == 1:
            self.content = "当前暂无问卷提交任务,今日任务已提交" + "\n" + res.text
            return None
        self.collectWid = res.json()['datas']['rows'][0]['wid']
        self.formWid = res.json()['datas']['rows'][0]['formWid']

        detailCollector_url = "https://hrbust.campusphere.net/wec-counselor-collector-apps/stu/collector/detailCollector"
        data = {
            "collectorWid":self.collectWid
        }

        res = server.post(url=detailCollector_url, headers=headers, cookies=self.cookies, data=json.dumps(data))
        self.schoolTaskWid = res.json()['datas']['collector']['schoolTaskWid']

        res = server.post(url='https://'+ self.schoolSignal +'.campusphere.net/wec-counselor-collector-apps/stu/collector/getFormFields',
                            headers=headers, cookies=self.cookies, data=json.dumps(
                {"pageSize": 30, "pageNumber": 1, "formWid": self.formWid, "collectorWid": self.collectWid})) # 当前我们需要问卷选项有21个，pageSize可适当调整

        form = res.json()['datas']['rows']
        row = res.json()['datas']['rows'][0]

        for i in range(len(form) - 1, -1, -1):
            if form[i]['fieldItems']:
                Items = form[i]['fieldItems']
                for item in Items[:]:
                    if item['isSelected']:
                        continue
                    else:
                        Items.remove(item)
            else:
                continue

        params = {
            "formWid": self.formWid, 
            "address": self.address,
            "collectWid": self.collectWid, "schoolTaskWid": self.schoolTaskWid,
            "form": form
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 4.4.4; OPPO R11 Plus Build/KTU84P) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/33.0.0.0 Safari/537.36 okhttp/3.12.4',
            'CpdailyStandAlone': '0',
            'extension': '1',
            'Cpdaily-Extension': '7vGWlfMTok9XC2Sz+EGOWdIzrLu9t82o6JZIBNMmvdF8BryaXycAggrfdVS1 osAYMwJ0RR5GSkMKyjqumYvvI7JHcC1rSHQ4olTVG1rkP5sYaDOyq+He2xUh tdgR9Ydcdmqf/zHivo3pdgqtDCpx9CAO9meEZDptptwteeuwL553IJWPH5Hr g3n1rX7j2jSlbrpkhwDCcnXrNxkbLIeYN0fOxHZT6SS4V2k4IS/cwgTUR0Xt lXD6Yti/Wbkt+bY9gacP3Oue9ZQ=',
            'Content-Type': 'application/json; charset=utf-8',
            'Host': 'hrbust.campusphere.net',
            'Connection': 'Keep-Alive',
            'Accept-Encoding': 'gzip'
        }
        r = server.post("http://"+self.schoolSignal+".campusphere.net/wec-counselor-collector-apps/stu/collector/submitForm",
                        headers=headers, cookies=self.cookies, data=json.dumps(params))
        self.content = "成功提交！" + '\n' + res.text

    def mail(self):
        msg_from = '********'  # 发送方邮箱
        passwd = '********'  # 填入发送方邮箱的授权码
        msg_to = '********'  # 收件人邮箱
        msg = MIMEMultipart()

        subject = "今日校园"  # 主题
        content = MIMEText(self.content)  # 正文
        msg.attach(content)

        msg['Subject'] = subject
        msg['From'] = msg_from
        msg['To'] = msg_to

        try:
            s = smtplib.SMTP_SSL("smtp.qq.com", 465)# 邮件服务器及端口号
            s.login(msg_from, passwd)  # 登录SMTP服务器
            s.sendmail(msg_from, msg_to, msg.as_string())  # 发邮件 as_string()把MIMEText对象变成str
        except:
            return 0
        finally:
            s.close()

    def Main(self):
        for name in range(len(self.xh1)):
            self.xh = self.xh1[name]
            self.pwd = self.pwd1[name]
            self.address = self.address1[name]
            self.Get_cookies()
            self.Get()
            self.mail()

if __name__ == '__main__':
    Report().Main()
