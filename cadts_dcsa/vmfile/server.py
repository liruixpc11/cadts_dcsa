# coding=utf-8
import json
import struct
import threading
import uuid
import os
import sys
import time
import subprocess
import logging.config
from cadts_dcsa.block.server.async_server import FileReceiveProtocol
from cadts_dcsa.block.utils import encode_header
from twisted.internet.protocol import Factory, connectionDone

LOG = logging.getLogger(__name__)

STATE_LEN = 0
STATE_HEADER = 1
VMRUN_PATH = None

if os.name == 'nt':
    for drive in 'CDEFGH':
        guess_path_list = (r"C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe",
                           r"C:\Program Files\VMware\VMware Workstation\vmrun.exe",
                           r"H:\shiyan\VmWare\vmrun.exe")
        for _guess_path in guess_path_list:
            if os.path.exists(_guess_path):
                VMRUN_PATH = _guess_path
                break
        if VMRUN_PATH:
            break

    if not VMRUN_PATH:
        raise Exception("vmrun.exe not found!")
else:
    VMRUN_PATH = 'vmrun'


class VmFileServer(object):
    def __init__(self, http_host, http_base_dir):
        self.http_host = http_host
        self.http_base_dir = http_base_dir
        self.files_dir = 'vm_files'

    def on_download_request(self, vm_path, guest_path):
        file_name = str(uuid.uuid4())
        file_path = os.path.join(self.http_base_dir, self.files_dir, file_name)
        # TODO download file to file_path
        self.download_file(vm_path, guest_path, file_path, guest='SXY', password='1234')
        url = 'http://{}/{}/{}'.format(self.http_host, self.files_dir, file_name)
        # response url
        # register timeout
        timeout_seconds = max(os.path.getsize(file_path) / (1024 * 1024), 30)
        threading.Thread(target=self.begin_timeout, args=[timeout_seconds, url]).start()
        # self.begin_timeout(timeout_seconds)
        return url

    def begin_timeout(self, timeout_seconds, url):
        try:
            time.sleep(timeout_seconds)
            self.on_timeout(url)
        except Exception:
            pass


    def on_progress(self, url, progress):
        LOG.debug('url: %s; progress: %f.', url, progress)
        if progress == 100.:
            self.clear_file(url)

    def on_timeout(self, url):
        self.clear_file(url)

    def on_cancel(self, url):
        self.clear_file(url)

    def clear_file(self, url):
        file_name = self.extract_file_name(url)
        if os.path.exists(file_name):
            os.remove(file_name)

    def extract_file_name(self, url):
        file_name = self.http_base_dir +'/'+ url.split('/')[-2] + '/' + url.split('/')[-1]
        return file_name

    def download_file(self, vm_path, guest_path, file_path, guest, password):
        cmd = [VMRUN_PATH, '-T', 'ws', '-gu', guest, '-gp', password, 'copyFileFromGuestToHost', vm_path, guest_path, file_path]
        LOG.debug('EXEC: %s', ' '.join(cmd))
        subprocess.check_call(cmd)


class VmFileProtocol(FileReceiveProtocol):
    def __init__(self, server):
        FileReceiveProtocol.__init__(self)
        self.state = STATE_LEN
        self.buffer = ''
        self.header_len = 0
        self.server = server

    def connectionMade(self):
        self.state = STATE_LEN
        LOG.info('Connection from %s', self.transport.getPeer())

    def connectionLost(self, reason=connectionDone):
        LOG.info('Connection lost %s: %s', self.transport.getPeer(), reason)

    def dataReceived(self, data):
        if self.state == STATE_LEN:
            self.buffer = data
        else:
            self.buffer += data

        if self.state == STATE_LEN:
            if len(self.buffer) >= 4:
                self.header_len = struct.unpack('!I', self.buffer[0:4])[0]
                self.buffer = self.buffer[4:]
                self.state = STATE_HEADER

        if self.state == STATE_HEADER:
            try:
                if len(self.buffer) >= self.header_len:
                    header_string = self.buffer[0:self.header_len]
                    header_json = json.loads(header_string)
                    if 'vm_path' in header_json:
                        vm_path = header_json['vm_path']
                        guest_path = header_json['guest_path']
                        url = self.server.on_download_request(vm_path, guest_path)
                        # send url
                        self.transport.write(encode_header({'url': url}))
                        LOG.debug('Header: %s', header_json)
                    if 'cancel' in header_json:
                        self.server.on_cancel(header_json['url'])
                        LOG.debug('Header: %s', header_json)
                    if 'progress' in header_json:
                        self.server.on_progress(header_json['url'], header_json['progress'])
                    if 'receive' in header_json:
                        LOG.debug('Client: %s', header_json['receive'])
                    self.buffer = self.buffer[self.header_len:]
                    self.state = STATE_LEN
            except Exception as ex:
                self.sendData({'server error ':str(ex)})

    def sendData(self,data):
        self.transport.write(encode_header(data))

def main(http_host='127.0.0.1', http_base_dir='e:\\tmp'):
    if os.name != 'nt':
        from twisted.internet import epollreactor

        epollreactor.install()

    from twisted.internet import reactor

    server = VmFileServer(http_host=http_host, http_base_dir=http_base_dir)
    factory = Factory()
    factory.protocol = lambda: VmFileProtocol(server)
    reactor.listenTCP(4444, factory)
    reactor.run()


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    main(http_host='127.0.0.1:8000')