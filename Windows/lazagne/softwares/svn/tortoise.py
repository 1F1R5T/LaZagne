# -*- coding: utf-8 -*- 
from lazagne.config.module_info import ModuleInfo
from lazagne.config.winstructure import *
from lazagne.config.constant import *
import base64
import os 

class Tortoise(ModuleInfo):
	def __init__(self):
		ModuleInfo.__init__(self, 'tortoise', 'svn', dpapi_used=True)

	# main function
	def run(self, software_name=None):	
		pwdFound = []
		
		path = os.path.join(constant.profile["APPDATA"], u'Subversion\\auth\\svn.simple')
		if os.path.exists(path):
			for root, dirs, files in os.walk(path + os.sep):
				for filename in files:
					f = open(os.path.join(path, filename), 'r')
					
					url = ''
					username = ''
					result = ''
					
					i = 0
					# password
					for line in f:
						if i == -1:
							result = line.replace('\n', '')
							break
						if line.startswith('password'):
							i = -3
						i+=1
					
					i = 0
					# url
					for line in f:
						if i == -1:
							url = line.replace('\n', '')
							break
						if line.startswith('svn:realmstring'):
							i = -3
						i+=1

					i = 0
					
					# username
					for line in f:
						if i == -1:
							username = line.replace('\n', '')
							break
						if line.startswith('username'):
							i = -3
						i+=1
					
					# encrypted the password
					if result:
						try:
							password = Win32CryptUnprotectData(base64.b64decode(result))
							pwdFound.append(
								{
									'URL'		: 	url, 
									'Login'		: 	username, 
									'Password'	: 	str(password)
								}
							)
						except:
							pass
			return pwdFound

