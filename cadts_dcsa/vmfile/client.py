# coding=utf-8
import json
import struct
import urllib2
import os
import requests
import socket
import sys

import time

from cadts_dcsa.block.utils import encode_header, send_all, receive_all, file_size_string


class VmFileClient(object):
    def __init__(self, vm_server):
        self.vm_server = vm_server
        self.s = socket.socket()
        self.s.connect((host, port))

    def begin_download(self, vm_path, guest_path):
        download_url = send_request(s=self.s, vm_path=vm_path, guest_path=guest_path)
        return download_url

    def download(self, url, local_path, progress_listener=None):
        file_name = url.split('/')[-1]
        u = urllib2.urlopen(url)
        file_len = int(u.info().getheaders("Content-Length")[0])
        recv_size = 0
        BUF_SIZE = 4096
        with open(os.path.join(local_path, file_name), 'wb')as f:
            buf = u.read(BUF_SIZE)
            # s=socket.socket()
            while buf:
                f.write(buf)
                recv_size += len(buf)
                buf = u.read(BUF_SIZE)
                self.report_progress(url, '{:.2f}'.format(recv_size *100.0 / file_len))
                sys.stdout.write('\r{:.2f}'.format(recv_size *100.0 / file_len))
        # report progress
        progress_listener(self, url, 0.1)
        # on error
        progress_listener(self, url, 0.1, '404')

    def cancel(self, url):
        request = {'cancel': True, 'url': url}
        send_message(self.s,request)

    def report_progress(self, url, progress):
        request = {'url': url, 'progress': progress}
        send_message(self.s,request)


def send_request(s, vm_path, guest_path):  # request is a dict type
    request = {'vm_path': vm_path, 'guest_path': guest_path}
    header_string = encode_header(request)
    send_all(s, header_string)
    # receive response
    len_string = receive_all(s, 4)
    if len_string:
        header_length, = struct.unpack('!I', len_string)
        json_string = receive_all(s, header_length)
        response = json.loads(json_string)
        if 'url' in response:
            url = response['url']
            return url


def send_message(s, request):
    header_string = encode_header(request)
    send_all(s, header_string)

def fetch_file(vm_server, vm_path, local_path, guest_path):
    def on_progress(c, url, progress, error=None):
        c.report_progress(url, progress)
        timeout = False
        if timeout or error:
            # c.cancel(url)
            pass

    client = VmFileClient(vm_server)
    url = client.begin_download(vm_path, guest_path)
    client.download(url, local_path, on_progress)


if __name__ == '__main__':
    vm_server = '127.0.0.1'
    vm_path = r"H:\shiyan\os\windows7x64\Windows 7 x64.vmx"
    guest_path = r"C:\Windows\System32\winevt\Logs\Security.evtx"
    local_path = r"E:\1"
    host = '127.0.0.1'
    port = 4444
    fetch_file(vm_server, vm_path, local_path, guest_path)
