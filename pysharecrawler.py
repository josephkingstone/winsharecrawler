#!/usr/bin/python

from impacket.dcerpc import srvsvc

import sys
import string
import time
import logging
from impacket import smb, version, smb3, nt_errors
from impacket.dcerpc.v5 import samr, transport, srvs
from impacket.dcerpc.v5.dtypes import NULL
from impacket.smbconnection import *
import argparse
import ntpath
#import os


class SmbCrawler():    
    def __init__(self):
        self.host = ''
        self.smb = None
        self.maxdepth = 999
        self.password = None
        self.lmhash = None
        self.nthash = None
        self.username = ''
        self.domain = ''
        self.debug = True

    def open(self, host, port):
        self.host = host
        if port == 139:
            self.smb = SMBConnection('*SMBSERVER', host, sess_port=port)
        else:
            self.smb = SMBConnection(host, host, sess_port=port)

        dialect = self.smb.getDialect()
        if dialect == SMB_DIALECT:
            logging.info("SMBv1 dialect used")
        elif dialect == SMB2_DIALECT_002:
            logging.info("SMBv2.0 dialect used")
        elif dialect == SMB2_DIALECT_21:
            logging.info("SMBv2.1 dialect used")
        else:
            logging.info("SMBv3.0 dialect used")

    def login(self, domain, username):
        if self.smb is None:
            logging.error("No connection open")
            return

        from getpass import getpass
        password = getpass("Password:")

        try:
            self.smb.login(username, password, domain=domain)
        except Exception,e:
            print "Authentication failed : " + str(e)
            sys.exit(0)
        self.username = username
        self.domain = domain

        if self.smb.isGuestSession() > 0:
            logging.info("GUEST Session Granted")
        else:
            logging.info("USER Session Granted")

    def shares(self):
        shares = []
        rpctransport = transport.SMBTransport(self.smb.getRemoteHost(), self.smb.getRemoteHost(), filename = r'\srvsvc', smb_connection = self.smb)
        dce = rpctransport.get_dce_rpc()
        dce.connect()
        dce.bind(srvs.MSRPC_UUID_SRVS)
        res = srvs.hNetrShareEnum(dce,1)
        resp = res['InfoStruct']['ShareInfo']['Level1']['Buffer']
        for i in range(len(resp)):                        
            shares += [resp[i]['shi1_netname'][:-1]]
        return shares

    def ls(self, share, pwd):
        files = []
        f_pwd = ''
        f_pwd = ntpath.join(pwd, '*')
        f_pwd = string.replace(f_pwd,'/','\\')
        f_pwd = ntpath.normpath(f_pwd)
        for f in self.smb.listPath(share, f_pwd):
            tmp =  { 'directory': True if f.is_directory() else False,
                     'size' : f.get_filesize(),
                     'ctime': time.ctime(float(f.get_mtime_epoch())),
                     'shortname' : f.get_shortname(), 
                     'longname' : f.get_longname() }
            if tmp['longname'] not in ['.', '..']:
                files += [tmp]
        return files

    def use(self,share):
        tid = self.smb.connectTree(share)
        self.ls(share, '\\')
        return tid

    def spider(self, share, root, maxdepth):
        if maxdepth < 0:
            return []
        try:
            files = self.ls(share, root)
        except Exception,e:
            if self.debug:
                print "Error in ls("+share+","+root+","+str(maxdepth)+") : " + str(e)
            return []
        for f in files:
            new_root = ntpath.join(root, f['longname'])
            new_root = ntpath.normpath(new_root)
            if not f['directory']:
                print u"  [*] -F- ".encode('utf-8') + self.host.encode('utf-8') + u'\\'.encode('utf-8') + share.encode('utf-8') + new_root
            else:
                print u"  [*] -D- ".encode('utf-8') + self.host.encode('utf-8') + u'\\'.encode('utf-8') + share.encode('utf-8') + new_root
                self.spider(share, root + f['longname'] + '\\', maxdepth - 1)

    def crawl(self, maxdepth, thread = 1):
        self.maxdepth = maxdepth
        shares = self.shares()
        for share in shares:
            print '[+] Spidering ' + share
            try:
                tid = self.use(share)
            except Exception,e:
                if self.debug:
                    print "Error in use("+share+") : " + str(e)
            self.spider(share, '\\', maxdepth)

if __name__ == "__main__":
    try:
        host,username,maxdepth = sys.argv[1], sys.argv[2], int(sys.argv[3])
        crawler = SmbCrawler()
        crawler.open(host,445)
        domain = ''
        if '/' in username:
            domain,username = tuple(username.split('/'))
        crawler.login(domain, username)
        crawler.crawl(maxdepth = maxdepth)
    except Exception,e:
        if True:
            print "Error : " + str(e)


