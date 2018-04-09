# coding=utf-8
import json
import logging.config
import os
import sys
import socket
import struct
import urllib2

from cadts_dcsa.block.utils import encode_header, send_all, receive_all

LOG = logging.getLogger(__name__)


class VmFileClient(object):
    def __init__(self, vm_server):
        self.vm_server = vm_server
        self.s = None

    def begin_download(self, vm_path, guest_path):
        download_url = send_request(s=self.s, vm_path=vm_path, guest_path=guest_path)
        LOG.debug("file: '%s' url is: %s", guest_path, download_url)
        send_message(s=self.s, request={'receive': 'begin to receive'})
        return download_url

    def download(self, url, local_path, progress_listener=None):
        file_name = url.split('/')[-1]
        local_file = local_path + os.sep + file_name
        u = urllib2.urlopen(url)
        file_len = int(u.info().getheaders("Content-Length")[0])
        LOG.debug("begin download file '%s' , size: %d", local_file, file_len)
        recv_size = 0
        tmp_buf = 0
        BUF_SIZE = 4096
        progress = 0.
        try:
            with open(local_file, 'wb') as f:
                buf = u.read(BUF_SIZE)
                while buf:
                    f.write(buf)
                    recv_size += len(buf)
                    tmp_buf += len(buf)
                    progress = recv_size * 100.0 / file_len
                    # 每1MB报告一次进度
                    if tmp_buf >= 1024 * 1024:
                        # self.report_progress(url, progress)
                        progress_listener(self, url, progress)
                        tmp_buf = 0
                        LOG.debug("progress: %f", progress)
                    if progress == 100.:
                        # self.report_progress(url, progress)
                        progress_listener(self, url, progress)
                        LOG.debug("progress: %f", progress)
                    buf = u.read(BUF_SIZE)
        except Exception, ex:
            progress_listener(self, url, progress, str(ex))
            LOG.error("download file '%s' from %s failed: %s", local_file, url, ex)

    def cancel(self, url):
        request = {'cancel': True, 'url': url}
        send_message(self.s, request)

    def report_progress(self, url, progress):
        request = {'url': url, 'progress': progress}
        send_message(self.s, request)

    def __enter__(self):
        self.s = socket.socket()
        self.s.connect(self.vm_server)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.s:
            try:
                self.s.close()
            except:
                pass
            self.s = None


def send_request(s, vm_path, guest_path):  # request is a dict type
    url = ''
    request = {'vm_path': vm_path, 'guest_path': guest_path}
    header_string = encode_header(request)
    send_all(s, header_string)
    # receive response
    len_string = receive_all(s, 4)
    if len_string:
        header_length, = struct.unpack('!I', len_string)
        json_string = receive_all(s, header_length)
        response = json.loads(json_string)
        if 'server error ' in response:
            raise Exception("Server error: %s", response['server error '])

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
            c.cancel(url)
            pass

    with VmFileClient(vm_server) as client:
        # client.listen(client.s)
        url = client.begin_download(vm_path, guest_path)
        client.download(url, local_path, on_progress)


def demo():
    vm_server = '127.0.0.1', 4444
    vm_path = r"H:\shiyan\os\windows7x64\Windows 7 x64.vmx"
    guest_path = r"C:\Windows\System32\winevt\Logs\Security.evtx"
    local_path = r"E:\tmp\1"
    fetch_file(vm_server, vm_path, local_path, guest_path)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
    demo()
