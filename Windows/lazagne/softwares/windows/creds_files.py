# -*- coding: utf-8 -*- 
from lazagne.config.module_info import ModuleInfo
from lazagne.config.dpapi_structure import *
from lazagne.config.constant import *
import os

class CredFiles(ModuleInfo):
	def __init__(self):
		ModuleInfo.__init__(self, 'creds_files', 'windows', exec_at_end=True)

	def run(self, software_name=None):
		pwdFound = []

		if constant.dpapi:
			creds_directory = os.path.join(constant.profile['APPDATA'], u'Microsoft', u'Credentials')
			if os.path.exists(creds_directory):
				for cred_file in os.listdir(creds_directory):
					# decrypting creds files will allow to retrieve more credentials such as domain password that the Credman module not allow to retrieve
					cred = constant.dpapi.decrypt_cred(os.path.join(creds_directory, cred_file))
					if cred:
						pwdFound.append(cred)

		return pwdFound