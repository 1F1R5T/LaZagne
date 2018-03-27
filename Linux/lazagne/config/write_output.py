#!/usr/bin/env python
# -*- encoding: utf-8 -*-
from lazagne.config.constant import constant
from time import gmtime, strftime
from constant import *
import logging
import getpass
import socket
import json
import sys
import os

class bcolors():
	HEADER 	= '\033[95m'
	OKBLUE 	= '\033[94m'
	OK 		= '\033[92m'
	WARNING = '\033[96m'
	FAIL 	= '\033[91m'
	TITLE 	= '\033[93m'
	ENDC 	= '\033[0m'

class StandartOutput():
	def __init__(self):
		self.banner = '''
|====================================================================|
|                                                                    |
|                        The LaZagne Project                         |
|                                                                    |
|                          ! BANG BANG !                             |
|                                                                    |
|====================================================================|
		'''

	def setColor(self, color=None, intensity=False):
		b = bcolors()
		if color == 'white':
			sys.stdout.write(b.TITLE) 
		elif color == 'red':
			sys.stdout.write(b.FAIL)
		elif color == 'green':
			sys.stdout.write(b.OK)
		elif color == 'cyan':
			sys.stdout.write(b.WARNING)
		else:
			sys.stdout.write(b.ENDC)
		
	# Print banner
	def first_title(self):
		self.do_print(message=self.banner, color='white', intensity=True)
		print

	# Info option for the logging
	def print_title(self, title):
		t = u'------------------- ' + title + ' passwords -----------------\n'
		self.do_print(message=t, color='white', intensity=True)

	# Debug option for the logging
	def title_info(self, title):
		t = u'------------------- ' + title + ' passwords -----------------\n'
		self.print_logging(function=logging.info, prefix='', message=t, color=False, intensity=True)

	def write_header(self):
		time 	= strftime("%Y-%m-%d %H:%M:%S", gmtime())
		header 	= u'{banner}\r\n- Date: {date}\r\n- Username: {username}\r\n- Hostname:{hostname}\r\n\r\n'.format(
					banner 	= self.banner.replace('\n', '\r\n'),
					date 	= str(time), 
					username= getpass.getuser(), 
					hostname= socket.gethostname()
				)
		open(os.path.join(constant.folder_name, '{filename}.txt'.format(filename=constant.file_name_results)),"a+b").write(header)

	def write_footer(self):
		footer = '\n[+] %s passwords have been found.\r\n\r\n' % str(constant.nbPasswordFound)
		open(os.path.join(constant.folder_name, '{filename}.txt'.format(filename=constant.file_name_results)),"a+b").write(footer)

	def print_footer(self, elapsed_time=None):
		footer = '\n[+] %s passwords have been found.\n' % str(constant.nbPasswordFound)
		if logging.getLogger().isEnabledFor(logging.INFO) == False:
			footer += 'For more information launch it again with the -v option\n'
		if elapsed_time:
			footer += '\nelapsed time = ' + str(elapsed_time)
		self.do_print(footer)

	def print_logging(self, function, prefix='[!]', message='', color=False, intensity=False):
		if constant.quiet_mode:
			return

		try:
			msg = u'{prefix} {msg}'.format(prefix=prefix, msg=message)
		except:
			msg = '{prefix} {msg}'.format(prefix=prefix, msg=str(message))

		if color:
			self.setColor(color, intensity)
			function(msg)
			self.setColor()
		else:
			function(msg)

	def try_unicode(self, obj, encoding='utf-8'):
		try:
			if isinstance(obj, basestring):
				if not isinstance(obj, unicode):
					obj = unicode(obj, encoding)
		except:
			pass
		return obj

	def print_without_error(self, message):
		try:
			print message
		except:
			print repr(message)

	# Centralize print function
	def do_print(self, message='', color=False, intensity=False):
		# Quiet mode => nothing is printed
		if constant.quiet_mode:
			return
		
		message = self.try_unicode(message)
		if color:
			self.setColor(color=color, intensity=intensity)
			self.print_without_error(message)
			self.setColor()
		else:
			self.print_without_error(message)

	def checks_write(self, values, category):
		if values:
			if "Passwords" not in constant.finalResults:
				constant.finalResults["Passwords"] = []
			constant.finalResults["Passwords"].append([{"Category": category}, values])

	def print_output(self, software_name, pwdFound):
		if pwdFound:
			# If the debug logging level is not apply => print the title
			if logging.getLogger().isEnabledFor(logging.INFO) == False:
				self.print_title(software_name)

			toWrite = []
			
			# Remove duplicated password
			pwdFound = [dict(t) for t in set([tuple(d.items()) for d in pwdFound])]

			for pwd in pwdFound:
				password_category = False
				# Detect which kinds of password has been found
				lower_list = [s.lower() for s in pwd.keys()]
				password = [s for s in lower_list if "password" in s]
				if password:
					password_category = password
				else:
					key = [s for s in lower_list if "key" in s] # for the wifi
					if key:
						password_category = key
					else:
						hash = [s for s in lower_list if "hash" in s]
						if hash:
							password_category = hash
						else:
							cmd = [s for s in lower_list if "cmd" in s]
							if cmd:
								password_category = cmd

				# No password found
				if not password_category:
					print_debug("FAILED", "Password not found !!!")
				else:
					print_debug("OK", '%s found !!!' % password_category[0].title())
					toWrite.append(pwd)

					# Store all passwords found on a table => for dictionary attack if master password set
					constant.nbPasswordFound += 1
					try:
						passwd = pwd[password_category[0].capitalize()]
						if passwd not in constant.passwordFound:
							constant.passwordFound.append(passwd)
					except:
						pass

				for p in pwd.keys():
					self.do_print('%s: %s' % (p, pwd[p]))
				self.do_print()

			# Write credentials into a text file
			self.checks_write(toWrite, software_name)
		else:
			logging.info("[!] No passwords found\n")


def print_debug(error_level, message): 
	# Print when password is found
	if error_level == 'OK':
		constant.st.do_print(message='[+] {message}'.format(message=message), color='green')

	# Print when password is not found
	elif error_level == 'FAILED':
		constant.st.do_print(message='[-] {message}'.format(message=message), color='red', intensity=True)

	elif error_level == 'CRITICAL' or error_level == 'ERROR':
		constant.st.print_logging(function=logging.error, prefix='[-]', message=message, color='red', intensity=True)

	elif error_level == 'WARNING':
		constant.st.print_logging(function=logging.warning, prefix='[!]', message=message, color='cyan')

	elif error_level == 'DEBUG':
		constant.st.print_logging(function=logging.debug, message=message, prefix='[!]')

	else:
		constant.st.print_logging(function=logging.info, message=message, prefix='[!]')

# --------------------------- End of output functions ---------------------------

def parseJsonResultToBuffer(jsonString, color=False):
	green = ''
	reset = ''
	title = ''
	if color:
		b = bcolors()
		green = b.OK
		title = b.TITLE
		reset = b.ENDC

	buffer = ''
	try:
		for json in jsonString:
			if json:
				if 'Passwords' not in json:
					buffer += 'No passwords found for this user !'
				else:
					for all_passwords in json['Passwords']:
						buffer += '{title_color}------------------- {password_category} -----------------{reset_color}\r\n'.format(title_color=title, password_category=all_passwords[0]['Category'], reset_color=reset)
						for password_by_category in all_passwords[1]:
							buffer += '\r\n{green_color}Password found !!!{reset_color}\r\n'.format(green_color=green, reset_color=reset)
							for dic in password_by_category.keys():
								try:
									buffer += '%s: %s\r\n' % (dic, password_by_category[dic].encode('utf-8'))
								except:
									buffer += '%s: %s\r\n' % (dic, password_by_category[dic].encode(encoding='utf-8',errors='replace'))
						buffer += '\r\n'

	except Exception as e:
		print_debug('ERROR', u'Error parsing the json results: {error}'.format(error=e))

	return buffer
