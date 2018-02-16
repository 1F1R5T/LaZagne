# -*- coding: utf-8 -*- 
from lazagne.config.write_output import print_debug
from lazagne.config.moduleInfo import ModuleInfo
from lazagne.config.WinStructure import *
from lazagne.config.constant import *
from lazagne.config.dpapi_structure import *
from ctypes.wintypes import *

class Vault(ModuleInfo):
	def __init__(self):
		ModuleInfo.__init__(self, 'vault', 'windows', dpapi_used=True)

	def run(self, software_name=None):
		
		# retrieve passwords (IE, etc.) using the Windows Vault API (not all passwords can be decrypted using this technic, e.g. domain passwords)
		if float(get_os_version()) <= 6.1:
			print_debug('DEBUG', u'Vault not supported for this OS')
			return

		cbVaults 	= DWORD()
		vaults 		= LPGUID()
		hVault 		= HANDLE(INVALID_HANDLE_VALUE)
		cbItems 	= DWORD()
		items 		= c_char_p()
		pwdFound 	= []

		if vaultEnumerateVaults(0, byref(cbVaults), byref(vaults)) == 0:
			if cbVaults.value == 0:
				print_debug('INFO', u'No Vaults found') 
				return
			else:
				for i in range(cbVaults.value):
					if vaultOpenVault(byref(vaults[i]), 0, byref(hVault)) == 0:
						if hVault:
							if vaultEnumerateItems(hVault, 0x200, byref(cbItems), byref(items)) == 0:
								
								for j in range(cbItems.value):
									
									items8 = cast(items, POINTER(VAULT_ITEM_WIN8))
									pItem8 = PVAULT_ITEM_WIN8()
									try:
										values = {
											'URL' 		: str(items8[j].pResource.contents.data.string),
											'Login' 	: str(items8[j].pUsername.contents.data.string)
										}
										if items8[j].pName:		
											values['Name'] = items8[j].pName

										if vaultGetItem8(hVault, byref(items8[j].id), items8[j].pResource, items8[j].pUsername, items8[j].unknown0, None, 0, byref(pItem8)) == 0:
											password = pItem8.contents.pPassword.contents.data.string
											if password:
												values['Password'] = password

										pwdFound.append(values)

									except Exception, e:
										print_debug('DEBUG', u'{error}'.format(e))

									if pItem8:
										vaultFree(pItem8)

								if items:
									vaultFree(items)
						
							vaultCloseVault(byref(hVault))
				
				vaultFree(vaults)

		return pwdFound