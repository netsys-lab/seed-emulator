#!/usr/bin/env python3
# encoding: utf-8

import unittest as ut
from tests.scion import ScionTestCase
from typing import List
from docker.models.containers import Container

def to_oci(command: str) -> str:
    return f"/bin/bash -c \"/bin/bash -c '{command}'\" "

# TODO create a test case for SCION-DoQ name resolution
class PKITestCase(ScionTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.wait_until_all_containers_up(19)
        cls.containers: List[Container] = cls.containers

    def test_root_cert_installed(self):
        for container in self.containers:
            if container.labels.get('org.seedsecuritylabs.seedemu.meta.nodename') is None:
                continue
            if 'web' in container.name:
                continue

            #minica:     /usr/local/share/ca-certificates/SEEDEMU_Internal_Root_CA.crt
            #smallstep:  /usr/local/share/ca-certificates/SEEDEMU_Internal_Root_CA_{self.serverID()}.crt

            # CA will install its own root cert
            if container.labels.get('org.seedsecuritylabs.seedemu.meta.nodename') == "ca1":

                # number=`ls /etc/ssl/certs | grep SEEDEMU_Internal_Root_CA | wc -l`; if [ "$number" -ge 2 ]; then exit 0; else  exit 1; fi
                code, out = container.exec_run(to_oci('number=`ls /etc/ssl/certs | grep SEEDEMU_Internal_Root_CA | wc -l`; if [ "$number" -ge 1 ]; then exit 0; else  exit 1; fi'))
                self.assertEqual(code, 0, f'{out}')

                continue
            if container.labels.get('org.seedsecuritylabs.seedemu.meta.nodename') == "ca2":
                code, out = container.exec_run(to_oci('number=`ls /etc/ssl/certs | grep SEEDEMU_Internal_Root_CA | wc -l`; if [ "$number" -ge 1 ]; then exit 0; else  exit 1; fi'))
                self.assertEqual(code, 0, f'{out}')
                continue
            if container.labels.get('org.seedsecuritylabs.seedemu.meta.asn') == "150":
                code, out = container.exec_run(to_oci('number=`ls /etc/ssl/certs | grep SEEDEMU_Internal_Root_CA | wc -l`; if [ "$number" -ge 2 ]; then exit 0; else  exit 1; fi'))
                self.assertEqual(code, 0, f'{out}')
                continue
            if container.labels.get('org.seedsecuritylabs.seedemu.meta.asn') == "151":
                code, out = container.exec_run(to_oci('number=`ls /etc/ssl/certs | grep SEEDEMU_Internal_Root_CA | wc -l`; if [ "$number" -ge 2 ]; then exit 0; else  exit 1; fi'))
                self.assertEqual(code, 0, f'{out}')
                continue

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

    def test_web_server_certs(self):
        """
        test that for web server nodes which use a MiniCAServer
                   certificate is present under /etc/ssl/certs/nginx.crt
            and corresponding private key under /etc/ssl/private/nginx.key
        """
        for container in self.containers:
            if container.labels.get('org.seedsecuritylabs.seedemu.meta.nodename') is None:
                continue
            if 'web2' in container.labels.get('org.seedsecuritylabs.seedemu.meta.nodename'):
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
            # CA will install its own root cert
            if container.labels.get('org.seedsecuritylabs.seedemu.meta.nodename') == "ca1":
                self.do_tests(container, 'user1.internal')
                self.do_tests(container, 'user2.internal')
                continue
            if container.labels.get('org.seedsecuritylabs.seedemu.meta.nodename') == "ca2":
                self.do_tests(container, 'user1.internal')
                self.do_tests(container, 'user2.internal')
                continue
            if container.labels.get('org.seedsecuritylabs.seedemu.meta.asn') == "150":
                self.do_tests(container, 'user1.internal')
                self.do_tests(container, 'user2.internal')
                continue
            if container.labels.get('org.seedsecuritylabs.seedemu.meta.asn') == "151":
                self.do_tests(container, 'user1.internal')
                self.do_tests(container, 'user2.internal')
                continue

    @classmethod
    def get_test_suite(cls):
        test_suite = ut.TestSuite()
        test_suite.addTest(cls('test_root_cert_installed'))
        test_suite.addTest(cls('test_web_server_certs'))
        test_suite.addTest(cls('test_web_integration'))
        return test_suite

if __name__ == "__main__":
    test_suite = PKITestCase.get_test_suite()
    res = ut.TextTestRunner(verbosity=2).run(test_suite)

    PKITestCase.printLog("==========Test=========")
    num, errs, fails = res.testsRun, len(res.errors), len(res.failures)
    PKITestCase.printLog("score: %d of %d (%d errors, %d failures)" % (num - (errs+fails), num, errs, fails))

