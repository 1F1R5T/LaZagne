# -*- coding: utf-8 -*- 
import os
import sys
import traceback
from xml.etree.cElementTree import ElementTree
from subprocess import Popen, PIPE

from lazagne.config.constant import constant
from lazagne.config.dpapi_structure import Decrypt_DPAPI
from lazagne.config.module_info import ModuleInfo
from lazagne.config.write_output import print_debug


class Wifi(ModuleInfo):
    def __init__(self):
        ModuleInfo.__init__(self, 'Wifi', 'wifi', dpapi_used=True)

    def decrypt_using_lsa_secret(self, key):
        """
        Needs admin priv but will work with all systems
        """
        if not constant.dpapi:
            constant.dpapi = Decrypt_DPAPI(password=constant.user_password)
        decrypted_blob = constant.dpapi.decrypt_wifi_blob(key)
        if decrypted_blob:
            return decrypted_blob.decode(sys.getfilesystemencoding())

    def decrypt_using_netsh(self, ssid):
        """
        Does not need admin priv but would work only with english and french systems
        """
        language_keys = [
            'key content', 'contenu de la cl', 'содержимое ключа'
        ]
        print_debug('DEBUG', u'Try using netsh method')
        process = Popen(['netsh.exe', 'wlan', 'show', 'profile', '{SSID}'.format(SSID=ssid), 'key=clear'],
                        stdout=PIPE,
                        stderr=PIPE)
        stdout, stderr = process.communicate()
        for st in stdout.split('\n'):
            if any(i in st.lower() for i in language_keys):
                password = st.split(':')[1].strip()
                return password

    def run(self, software_name=None):

        if not constant.wifi_password:
            interfaces_dir = os.path.join(constant.profile['ALLUSERSPROFILE'],
                                          u'Microsoft\\Wlansvc\\Profiles\\Interfaces')

            # for windows Vista or higher
            if os.path.exists(interfaces_dir):

                pwd_found = []

                for wifi_dir in os.listdir(interfaces_dir):
                    if os.path.isdir(os.path.join(interfaces_dir, wifi_dir)):

                        repository = os.path.join(interfaces_dir, wifi_dir)
                        for file in os.listdir(repository):
                            values = {}
                            if os.path.isfile(os.path.join(repository, file)):
                                f = os.path.join(repository, file)
                                tree = ElementTree(file=f)
                                root = tree.getroot()
                                xmlns = root.tag.split("}")[0] + '}'

                                for elem in tree.iter():
                                    if elem.tag.endswith('SSID'):
                                        for w in elem:
                                            if w.tag == xmlns + 'name':
                                                values['SSID'] = w.text

                                    if elem.tag.endswith('authentication'):
                                        values['Authentication'] = elem.text

                                    if elem.tag.endswith('protected'):
                                        values['Protected'] = elem.text

                                    if elem.tag.endswith('keyMaterial'):
                                        key = elem.text
                                        try:
                                            password = self.decrypt_using_lsa_secret(key=key)
                                            if not password:
                                                password = self.decrypt_using_netsh(ssid=values['SSID'])

                                            if password:
                                                values['Password'] = password
                                            else:
                                                values['INFO'] = '[!] Password not found.'
                                        except Exception:
                                            print_debug("ERROR", traceback.format_exc())
                                            values['INFO'] = '[!] Password not found.'

                                if values and values['Authentication'] != 'open':
                                    pwd_found.append(values)

                constant.wifi_password = True
                return pwd_found
