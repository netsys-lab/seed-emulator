#!/usr/bin/env python3
# encoding: utf-8

import unittest as ut
import time
from tests.scion import ScionTestCase
from typing import List
from docker.models.containers import Container

def to_oci(command: str) -> str:
    return f"/bin/bash -c \"/bin/bash -c '{command}'\" "


class SCIONPKITestCase(ScionTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.wait_until_all_containers_up(19)
        cls.containers: List[Container] = cls.containers

    def getNode(self, asn: int, name: str):
        for cnt in self.containers:
            if (cnt.labels.get('org.seedsecuritylabs.seedemu.meta.nodename').strip('"') == name and
            cnt.labels.get('org.seedsecuritylabs.seedemu.meta.asn').strip('"') == str(asn)):
                return cnt
        raise Exception('not found')

    def test_root_cert_installed(self):
        """
        check that all end hosts have the MiniCA root certificate
            #minica:     /usr/local/share/ca-certificates/SEEDEMU_Internal_Root_CA.crt
        in their trust store
        """
        for container in self.containers:



            if (container.labels.get('org.seedsecuritylabs.seedemu.meta.role') == "Host" and
                container.labels.get('org.seedsecuritylabs.seedemu.meta.nodename') == "host_0"):

                code, out = container.exec_run(to_oci('number=`ls /etc/ssl/certs | grep SEEDEMU_Internal_Root_CA | wc -l`; if [ "$number" -ge 1 ]; then exit 0; else  exit 1; fi'))
                self.assertEqual(code, 0, f'{out}')



    def do_tests(self, container, domain):

        nodename = container.name
        code, out = container.exec_run(f"ping -c1 -w 1 10.151.0.53")
        self.assertEqual(code, 0, f'cant ping global-dns from {nodename}: {out}')
        code, out = container.exec_run(f"dig +short A {domain} | grep -q . && exit 0 || exit 1")
        self.assertEqual(code, 0, f'name resolution failed on {nodename} for domain {domain}: {out}')
        if '1' in domain:
            code, out = container.exec_run(f"ping -c1 -w 1 10.150.0.9")
            self.assertEqual(code, 0, f'cant ping web1 from {nodename}: {out}')
        elif '2' in domain:
            code, out = container.exec_run(f"ping -c1 -w 1 10.151.0.7")
            self.assertEqual(code, 0, f'cant ping web2 from {nodename}: {out}')
        #code, out = container.exec_run(f"curl http://{domain}")
        #self.assertEqual(code, 0, f'requesting web page failed from {nodename} to {domain}: {out}')
        # apparently certbot configures nginx to not listen on HTTP:80 but only HTTPS:443
        code, out = container.exec_run(f"curl https://{domain}")
        self.assertEqual(code, 0, f'secure connection failed from {nodename} to {domain}: {out}')

    ''' exdns
        // "Usage: %s [options] [@server] [qtype...] [qclass...] [name ...]
            "args": ["-port=53", "@127.0.0.127", "ANY", "IN", "www.example.com."]
            "args": ["-port=853", "-sni", "ns1.", "-squic","@2-235,10.235.0.71", "ANY", "IN", "com."]
    '''

    def test_sdns_resolver(self):
        time.sleep(120)

        c102h = self.getNode(102, 'host_0') # the host with the sdns resolver installation

        self.assertTrue( self.scion_ping_test(c102h, dst='2-235,10.235.0.71', count = 1) , 'cant reach "." root nameserver')

        self.assertTrue( self.scion_ping_test(c102h, dst='2-234,10.234.0.71', count = 1) , 'cant reach "com." nameserver')
        self.assertTrue( self.scion_ping_test(c102h, dst='2-203,10.203.0.71', count = 1) , 'cant reach "net." nameserver')
        self.assertTrue( self.scion_ping_test(c102h, dst='2-242,10.242.0.71', count = 1) , 'cant reach "edu." nameserver')

        self.assertTrue( self.scion_ping_test(c102h, dst='1-150,10.150.0.71', count = 1) , 'cant reach "example.com." nameserver')
        self.assertTrue( self.scion_ping_test(c102h, dst='2-240,10.240.0.71', count = 1) , 'cant reach "example.net." nameserver')
        self.assertTrue( self.scion_ping_test(c102h, dst='2-242,10.242.0.71', count = 1) , 'cant reach "example.edu." nameserver')

        self.assertTrue( self.scion_ping_test(c102h, dst='2-241,10.241.0.71', count = 1) , 'cant reach "www.example.edu." web server')
        self.assertTrue( self.scion_ping_test(c102h, dst='1-173,10.173.0.71', count = 1) , 'cant reach "www.example.net." web server')
        self.assertTrue( self.scion_ping_test(c102h, dst='1-172,10.172.0.71', count = 1) , 'cant reach "www.example.com." web server')

        code, out = c102h.exec_run(f"dig +short ANY www.example.com | grep -q . && exit 0 || exit 1")

        code, out = c102h.exec_run(f"sdig @127.0.0.127 IN ANY www.example.com")

        code, out = c102h.exec_run(f"sdig -squic -sni ns1. @2-235,10.235.0.71 IN ANY com.")

        pass
        #self.assertEqual(code, 0, f'cant ping global-dns from {nodename}: {out}')

    def test_nameserver_certs(self):
        """
        test that for nameserver nodes which use a MiniCAServer
                   certificate is present under /etc/coredns/ca/{zone}-cert.pem
            and corresponding private key under /etc/coredns/ca/{zone}-key.pem
        """
        for container in self.containers:
            if container.labels.get('org.seedsecuritylabs.seedemu.meta.nodename') is None:
                continue
            if (classlabels:=container.labels.get('org.seedsecuritylabs.seedemu.meta.class'))==None:
                continue
            classes = [c.strip().strip(']').strip('[').strip('"') for c in classlabels.split(',')]
            if 'DomainNameService' in classes:
                # TODO test the SubjectName of the certificate !
                code, out = container.exec_run('sh -c "ls /etc/coredns/ca/ | grep -q \'cert\\.pem\$\'"')
                self.assertEqual(code, 0, f'certificate missing on nameserver {container.name}: {out}')
                code, out = container.exec_run('sh -c "ls /etc/coredns/ca/ | grep -q \'key\\.pem\$\'"')
                self.assertEqual(code, 0, f'private key missing on name server {container.name}: {out} ')
                continue

    def test_web_server_certs(self):
        """
        test that for web server nodes which use a MiniCAServer
                   certificate is present under /etc/ssl/certs/nginx.crt
            and corresponding private key under /etc/ssl/private/nginx.key
        """
        for container in self.containers:
            if container.labels.get('org.seedsecuritylabs.seedemu.meta.nodename') is None:
                continue
            if 'WebService' in container.labels.get('org.seedsecuritylabs.seedemu.meta.class'):
                # TODO test the SubjectName of the certificate !
                code, _ = container.exec_run('ls /etc/ssl/certs/nginx.crt')
                self.assertEqual(code, 0, 'certificate missing on web server')
                code, out = container.exec_run('ls /etc/ssl/private/nginx.key')
                self.assertEqual(code, 0, f'private key missing on web server {container.name}: {out} ')
                continue

    def test_web_integration(self):
        for container in self.containers:
            if 'web' in container.name:
                continue
            if container.labels.get('org.seedsecuritylabs.seedemu.meta.nodename') is None:
                continue
            if container.labels.get('org.seedsecuritylabs.seedemu.meta.role') == "Route Server":
                continue
            if container.labels.get('org.seedsecuritylabs.seedemu.meta.role') == "Router":
                continue
            if container.labels.get('org.seedsecuritylabs.seedemu.meta.role') == "BorderRouter":
                continue

            if container.labels.get('org.seedsecuritylabs.seedemu.meta.asn') == "151":
                self.do_tests(container, 'user1.internal')
                self.do_tests(container, 'user2.internal')
                continue

    @classmethod
    def get_test_suite(cls):
        test_suite = ut.TestSuite()
        test_suite.addTest(cls('test_root_cert_installed'))
        #test_suite.addTest(cls('test_web_server_certs'))
        test_suite.addTest(cls('test_nameserver_certs'))
        test_suite.addTest(cls('test_sdns_resolver'))
        #test_suite.addTest(cls('test_web_integration'))
        return test_suite

if __name__ == "__main__":
    test_suite = SCIONPKITestCase.get_test_suite()
    res = ut.TextTestRunner(verbosity=2).run(test_suite)

    SCIONPKITestCase.printLog("==========Test=========")
    num, errs, fails = res.testsRun, len(res.errors), len(res.failures)
    SCIONPKITestCase.printLog("score: %d of %d (%d errors, %d failures)" % (num - (errs+fails), num, errs, fails))

