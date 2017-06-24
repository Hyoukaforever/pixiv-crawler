#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests,re,os,time,datetime,threading,copy,pickle,sys,paramiko
from lxml import html

def login():
	if os.path.exists("./cookies") :
		with open("./cookies","rb") as f:
			session_requests.cookies=pickle.load(f)
	r=session_requests.get('http://www.pixiv.net')
	if r.status_code==200 and re.search('not-logged-in',r.text)==None:
		print("loaded cookies")
		return
	
	login_url='http://accounts.pixiv.net/login'
	r=session_requests.get(login_url)

	tree=html.fromstring(r.text)
	authenticity_token=list(set(tree.xpath("//input[@name='post_key']/@value")))[0]
	with open("account","r") as f:	#account文件放在同目录下，包含一行:用户名(空格)密码
		account=f.read().split()
	payload={
		'pixiv_id':account[0],
		'password':account[1],
		'post_key':authenticity_token
	}
	r=session_requests.post(
		login_url,
		data=payload,
		headers=dict(referer=login_url)
	)
	
	r=session_requests.get('http://www.pixiv.net')
	if re.search('not-logged-in',r.text)!=None:raise IOError('login failed')	
	else:
		print("log in")
		with open("./cookies","wb") as f:	#第一次登录后将存档cookies用来登录
			pickle.dump(session_requests.cookies,f)

def downloadImage(imgurl,filename,*,header=None,imgid=None,imgidext=None):
	print("%s is downloading %s"%(threading.current_thread().name,filename))
	try:
		if header : r=session_requests.get(imgurl,headers=header,timeout=30)
		else : r=session_requests.get(imgurl,timeout=30)
		if r.status_code==200:
			try:
				write_rlock.acquire()
				with open(filename,'wb') as f:
					f.write(r.content)
			finally:write_rlock.release()
		else:raise IOError('requestFailed')
	except Exception as e:
		print('FAIL %s failed to download %s'%(threading.current_thread().name,filename))
		if os.path.exists(filename) : os.remove(filename)
		faillog.append(filename)
		return 0
	else:
		print('SUCCESS %s has sucessfully downloaded %s'%(threading.current_thread().name,filename))
		try:
			garage_rlock.acquire()
			if imgidext:garage.add(imgidext)
			elif imgid:garage.add(imgid)
		finally:garage_rlock.release()
		return 1

def listener():
	while(listen_active):
		x=input()
		if x=="q":
			try:
				garage_rlock.acquire()
				if os.path.exists("./garage") :
					with open("./garage","r") as f:
						garage.update(f.read().split())
				with open("./garage","w") as f:
					f.write(" ".join(garage))
				print("local garage update complete")
				synchronize_garage()
				break
			finally:garage_rlock.release()
		elif x=="e":
			break

def synchronize_garage():	#当你使用多台计算机下载图片时，你可能需要将你的garage文件同步到你的服务器上以免重复
	try:
		private_key = paramiko.RSAKey.from_private_key_file("C:/Users/HanYue/.ssh/id_rsa")
		transport = paramiko.Transport(("akaisora.tech",22))
		transport.connect(username="root",pkey=private_key)
		sftp = paramiko.SFTPClient.from_transport(transport)
		
		remotedir="/home/upload/pixiv_scrapy/"
		if "garage" not in sftp.listdir(remotedir):
			sftp.put("garage",remotedir+"garage")

		sftp.get(remotedir+"garage","tmp_garage")
		
		with open("tmp_garage","r") as f:
			garage.update(f.read().split())
		os.remove("tmp_garage")
		
		with open("garage","w") as f:
			f.write(" ".join(garage))
		
		sftp.put("garage",remotedir+"garage")
		
		print("synchronize garage successed")
	except Exception as e:
		print("synchronize garage failed")
		print(e)
	finally:
		try:
			transport.close()
		except Exception as e:
			pass

def testrecommen():	#未完成功能
	r=session_requests.get(pixiv_root+"recommended.php")
	tree=html.fromstring(r.text)
	token=tree.xpath("/pixiv.context.token")
	print(token)
	# "//input[@name='post_key']/@value"
	
	
#----------ARGS
pixiv_root="http://www.pixiv.net/"
referpfx=r'http://www.pixiv.net/member_illust.php?mode=medium&illust_id='
local_save_root="D:\Image\图站\pixiv\\"+datetime.datetime.now().strftime("%y.%m.%d")+"\\"

classification=[
	("normalRank",[
		pixiv_root+"ranking_area.php?type=detail&no=6",
		pixiv_root+"ranking.php?mode=daily&p=1",
		pixiv_root+"ranking.php?mode=daily&p=2",
		pixiv_root+"ranking.php?mode=original"]),
	# ("r18Rank",[
		# pixiv_root+"ranking.php?mode=daily_r18&p=1",
		# pixiv_root+"ranking.php?mode=male_r18&p=1",
		# pixiv_root+"ranking.php?mode=weekly_r18&p=1",
		# pixiv_root+"ranking.php?mode=weekly_r18&p=2"]),
	("bookmark",[
		pixiv_root+"/bookmark_new_illust.php?p=%d"%i for i in range(1,10)]),
	# ("tag-栗山未来",[
		# pixiv_root+"search.php?word=栗山未来&order=date_d&p=%d"%i for i in range(1,10)]),
	# ("画师-Re-しましま",[
		# pixiv_root+"member_illust.php?id=9935837&type=all&p=%d"%i for i in range(1,4)]),
	# ("画师-TMLV",[
		# pixiv_root+"member_illust.php?id=8191442&type=all&p=%d"%i for i in range(1,2)]),
]

#----------PREDO
session_requests=requests.session()
try: login()
except Exception as e:
	print('Connect failed')
	exit()

#testrecommen()

if not os.path.exists(local_save_root) : os.makedirs(local_save_root)

garage=set()
if os.path.exists("./garage") : #garage文档存放车库清单，避免文件重复
	with open("./garage","r") as f:
		garage.update(f.read().split())
		
synchronize_garage()
	

faillog=[]
threads=[]
write_rlock=threading.RLock()
garage_rlock=threading.RLock()
#----------MAINPROC
listen_active=True
t=threading.Thread(target=listener)
t.start()
for classi,urlList in classification:
	local_save=local_save_root+classi+"\\"
	if not os.path.exists(local_save) : os.makedirs(local_save)
	for pageUrl in urlList:	
		try:
			rankPage=session_requests.get(pageUrl)
			regex=r'(?<=img-master/img)(.*?)(?=_master)'
			imagelist=re.findall(regex,rankPage.text)
		except Exception as e:
			faillog.append(pageUrl+"Pagefail")
			continue	
		for img in imagelist:
			try:
				imgid=re.search('\d+(?=\_)',img).group(0)
			except Exception as e:
				print('fail : '+img)
				faillog.append(img)
				continue
			refer=referpfx+imgid
			try:
				toDownlist=[]
				r=session_requests.get(refer,timeout=25)
				match=re.search('(?<=data-src=").*?img-original.*?\.(jpg|png)',r.text)
				if match : toDownlist.append((match.group(0),local_save+os.path.split(match.group(0))[1]))
				else:
					for i in range(0,100 if "画师" in classi else 1):
						r=session_requests.get("http://www.pixiv.net/member_illust.php?mode=manga_big&illust_id="+imgid+"&page=%d"%i)
						if r.status_code!=200:break
						match=re.search('(?<=src=").*?img-original.*?\.(jpg|png)',r.text)
						if match : toDownlist.append((match.group(0),local_save+os.path.split(match.group(0))[1]))
			except Exception as e:
				faillog.append(imgid)
				print(e)
			for orgurl,filename in toDownlist:
				imgidext=os.path.splitext(os.path.basename(filename))[0]
				if imgidext in garage:continue
				if os.path.exists(filename): 
					garage.add(imgidext)
					continue
				print("<"+orgurl+">")			
				t=threading.Thread(target=downloadImage,args=(orgurl,filename),kwargs={"header":{"referer":refer},"imgid":imgid,"imgidext":imgidext})
				threads.append(t)
				while sum(map(lambda x:1 if x.is_alive() else 0,threads))>=8 : time.sleep(1)
				t.start()

	for t in threads :
		if t.is_alive():t.join()

#_______________AFTER
print('-------------------------faillog-------------------------')
for log in faillog:print(log)

with open("./garage","w") as f:
	f.write(" ".join(garage))
	
synchronize_garage()


listen_active=False

"""
--------------------backup----------------------
header={
	"cookies":'p_ab_id=0; p_ab_id_2=8; _ga=GA1.2.244081158.1482900312; device_token=2fa311bb23ce900bd65eca1037ab7610; PHPSESSID=4187518_555624b44264e95b2419bb0f73611586; module_orders_mypage=%5B%7B%22name%22%3A%22recommended_illusts%22%2C%22visible%22%3Atrue%7D%2C%7B%22name%22%3A%22everyone_new_illusts%22%2C%22visible%22%3Atrue%7D%2C%7B%22name%22%3A%22following_new_illusts%22%2C%22visible%22%3Atrue%7D%2C%7B%22name%22%3A%22mypixiv_new_illusts%22%2C%22visible%22%3Atrue%7D%2C%7B%22name%22%3A%22fanbox%22%2C%22visible%22%3Atrue%7D%2C%7B%22name%22%3A%22featured_tags%22%2C%22visible%22%3Atrue%7D%2C%7B%22name%22%3A%22contests%22%2C%22visible%22%3Atrue%7D%2C%7B%22name%22%3A%22sensei_courses%22%2C%22visible%22%3Atrue%7D%2C%7B%22name%22%3A%22spotlight%22%2C%22visible%22%3Atrue%7D%2C%7B%22name%22%3A%22booth_follow_items%22%2C%22visible%22%3Atrue%7D%5D; __utmt=1; __utma=235335808.244081158.1482900312.1488263964.1488271923.8; __utmb=235335808.3.10.1488271923; __utmc=235335808; __utmz=235335808.1483276352.5.4.utmcsr=galacg.me|utmccn=(referral)|utmcmd=referral|utmcct=/archives/60193.html; __utmv=235335808.|2=login%20ever=yes=1^3=plan=normal=1^4=p_ab_id_2=8=1^5=gender=male=1^6=user_id=4187518=1^9=illust_tag_placeholder=no=1^12=fanbox_subscribe_button=orange=1',
	'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36',
	'Host':'i2.pixiv.net',
	'Referer':'http://www.pixiv.net/member_illust.php?mode=medium&illust_id=61577957'
}
"""